"""AI planner (M6, D-07): the LLM proposes, the envelope validates, the rule planner catches every failure.

Per step: build a request from the state -> ask the model for a schema-constrained decision -> validate it
(V1–V9) -> on rejection ask once more with the validator's errors -> otherwise fall back to the rule planner.
Model errors, refusals and timeouts also fall back; a replay miss in replay mode raises (D-21).
"""

import json
import logging

from episight.agent.context import CaseContext
from episight.agent.envelope.allowed import AllowedAction
from episight.agent.envelope.validator import ValidationOutcome, validate
from episight.agent.planners.base import Decision, Planner
from episight.agent.planners.rule_planner import RulePlanner
from episight.agent.state import InvestigationState
from episight.contracts.enums import PlannerSource
from episight.llm.clients import AnthropicClient, LlmClient, LlmError, OpenAIClient
from episight.llm.config import LlmSettings, Provider, get_llm_settings
from episight.llm.prompt import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_payload,
    decision_schema,
    request_hash,
    retry_message,
)
from episight.llm.recording import NullStore, RecordingStore, ReplayMiss

log = logging.getLogger(__name__)


class _ReplayOnlyClient:
    """Stands in for a vendor client in replay mode: every answer must come from recordings."""

    def __init__(self, provider: str, model: str):
        self.provider = provider
        self.model = model

    def complete_json(self, system, user, schema):
        raise ReplayMiss("no recording for this planner request (EPISIGHT_LLM_REPLAY=replay)")


class LlmPlanner:
    def __init__(self, client: LlmClient, store: RecordingStore | None = None, replay: bool = False):
        self.client = client
        self.store = store or NullStore()
        self.replay = replay
        self.fallback = RulePlanner(source=PlannerSource.RULE_FALLBACK)

    def _ask(self, user: str, schema: dict) -> tuple[str, str, str, int]:
        """Returns (text, model, request hash, latency ms), from a recording when one exists."""
        h = request_hash(self.client.provider, self.client.model, SYSTEM_PROMPT, user, schema)
        recorded = self.store.get(h)
        if recorded is not None:
            return recorded["text"], recorded["model"], h, 0
        if self.replay:
            raise ReplayMiss(f"no recording for planner request {h[:12]} (EPISIGHT_LLM_REPLAY=replay)")
        reply = self.client.complete_json(SYSTEM_PROMPT, user, schema)
        self.store.put(
            h,
            model=reply.model,
            prompt_version=PROMPT_VERSION,
            request={"provider": self.client.provider, "user": user, "schema": schema},
            response={"text": reply.text, "model": reply.model},
        )
        return reply.text, reply.model, h, reply.latency_ms

    def _decision(
        self, outcome: ValidationOutcome, source: PlannerSource, model: str, h: str, latency: int, errors: list[str]
    ) -> Decision:
        d = outcome.decision
        return Decision(
            action=d.action,
            tool_input=d.tool_input,
            source=source,
            skips=d.skips,
            priority_ranking=d.priority_ranking,
            note=d.note,
            validation_errors=errors,
            model=model,
            prompt_version=PROMPT_VERSION,
            request_hash=h,
            latency_ms=latency,
        )

    def decide(self, st: InvestigationState, ctx: CaseContext, allowed: list[AllowedAction]) -> Decision:
        user = json.dumps(build_user_payload(st, ctx, allowed), ensure_ascii=False)
        schema = decision_schema(st, ctx, allowed)
        try:
            text, model, h, latency = self._ask(user, schema)
            first = validate(text, allowed, st, ctx)
            if first.ok:
                return self._decision(first, PlannerSource.LLM, model, h, latency, [])
            text2, model2, h2, latency2 = self._ask(retry_message(user, first.errors), schema)
            second = validate(text2, allowed, st, ctx)
            if second.ok:
                return self._decision(second, PlannerSource.LLM_RETRY, model2, h2, latency + latency2, first.errors)
            errors = first.errors + second.errors
        except LlmError as exc:
            log.warning(
                "AI planner unavailable for this step; using rule fallback",
                extra={"fields": {"run_id": st.run_id, "step": st.step + 1, "error": str(exc)}},
            )
            errors = [f"LLM: {exc}"]
        decision = self.fallback.decide(st, ctx, allowed, validation_errors=errors)
        decision.model = self.client.model
        decision.prompt_version = PROMPT_VERSION
        return decision


def build_client(settings: LlmSettings) -> LlmClient | None:
    provider = settings.resolved_provider()
    model = settings.resolved_model(provider)
    if provider == Provider.NONE:
        return None
    if settings.replay == "replay":
        return _ReplayOnlyClient(provider.value, model)
    if provider == Provider.ANTHROPIC:
        return AnthropicClient(
            model, effort=settings.effort, timeout_s=settings.timeout_s, api_key=settings.anthropic_api_key
        )
    return OpenAIClient(model, timeout_s=settings.timeout_s, api_key=settings.openai_api_key)


def llm_planner_or_none(store: RecordingStore | None = None, settings: LlmSettings | None = None) -> Planner | None:
    """The configured AI planner, or None when no LLM is configured (FULL mode then uses the rule fallback)."""
    settings = settings or get_llm_settings()
    client = build_client(settings)
    if client is None:
        return None
    return LlmPlanner(client, store=store, replay=settings.replay == "replay")
