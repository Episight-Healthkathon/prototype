"""Investigation loop (architecture §7.2): allowed actions -> planner -> validated tool call -> reducer -> stop?

The orchestrator is persistence-agnostic: a Recorder receives every state change. It never imports the web or
database layers, and the planner can only act through actions the envelope allows.
"""

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from episight.agent.context import CaseContext
from episight.agent.envelope.allowed import compute_allowed
from episight.agent.envelope.stopping import evaluate
from episight.agent.planners.base import Decision, Planner
from episight.agent.reducer import apply_outcome, apply_skip
from episight.agent.state import InvestigationState, call_signature
from episight.agent.tools import TOOLS, ToolOutcome
from episight.brief.builder import build_brief
from episight.brief.validator import BriefValidation, validate_brief
from episight.contracts.api import (
    ActionError,
    Evidence,
    InvestigationAction,
    InvestigationBrief,
    NextAction,
    PlannerInfo,
    SkippedRequirement,
)
from episight.contracts.enums import InvestigationMode, ProgressStatus, RequirementState, ToolStatus
from episight.evidence.ledger import ProvenanceError

DEFAULT_MAX_STEPS = 12
TOOL_TIMEOUT_S = 10.0
RUN_TIMEOUT_S = {InvestigationMode.FULL: 180.0}
DEFAULT_RUN_TIMEOUT_S = 60.0


class Recorder(Protocol):
    def on_state(self, st: InvestigationState, ctx: CaseContext) -> None: ...

    def on_step(
        self,
        st: InvestigationState,
        ctx: CaseContext,
        action: InvestigationAction,
        new_evidence: list[Evidence],
        decision: Decision,
    ) -> None: ...

    def on_finish(
        self, st: InvestigationState, ctx: CaseContext, brief: InvestigationBrief, validation: BriefValidation
    ) -> None: ...


class NullRecorder:
    def on_state(self, st, ctx) -> None: ...

    def on_step(self, st, ctx, action, new_evidence, decision) -> None: ...

    def on_finish(self, st, ctx, brief, validation) -> None: ...


@dataclass
class InvestigationResult:
    state: InvestigationState
    brief: InvestigationBrief
    validation: BriefValidation
    elapsed_ms: int


def _reason(st: InvestigationState, decision: Decision) -> str:
    req = st.requirements[decision.action.requirement_key]
    return f"{req.spec.label} (requirement {req.key.value} is open)"


def _run_tool(
    executor: ThreadPoolExecutor, decision: Decision, ctx: CaseContext, st: InvestigationState, timeout_s: float
) -> ToolOutcome:
    tool = TOOLS[decision.action.tool_name]
    future = executor.submit(tool.fn, ctx, st, decision.tool_input)
    try:
        return future.result(timeout=timeout_s)
    except FutureTimeout:
        return ToolOutcome(
            status=ToolStatus.TIMEOUT, error=ActionError(code="TIMEOUT", message=f"{tool.name} timed out")
        )
    except ProvenanceError as exc:
        return ToolOutcome(status=ToolStatus.ERROR, error=ActionError(code="PROVENANCE", message=str(exc)))
    except Exception as exc:  # noqa: BLE001 — a tool failure is represented, never hidden or replaced
        return ToolOutcome(status=ToolStatus.ERROR, error=ActionError(code="TOOL_ERROR", message=str(exc)[:300]))


def run_investigation(
    ctx: CaseContext,
    *,
    run_id: str,
    planner: Planner,
    mode: InvestigationMode = InvestigationMode.FULL,
    max_steps: int = DEFAULT_MAX_STEPS,
    recorder: Recorder | None = None,
    tool_timeout_s: float = TOOL_TIMEOUT_S,
    run_timeout_s: float | None = None,
    clock: Callable[[], float] = time.monotonic,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> InvestigationResult:
    recorder = recorder or NullRecorder()
    run_timeout_s = run_timeout_s or RUN_TIMEOUT_S.get(mode, DEFAULT_RUN_TIMEOUT_S)
    started = clock()
    st = InvestigationState.new(ctx, run_id, mode, max_steps, now())
    recorder.on_state(st, ctx)

    with ThreadPoolExecutor(max_workers=1) as executor:
        while True:
            allowed = compute_allowed(st, ctx)
            verdict = evaluate(st, len(allowed), clock() - started, run_timeout_s)
            if verdict is not None:
                st.outcome, st.stop_reason = verdict
                break

            decision = planner.decide(st, ctx, allowed)
            skip_updates = [u for k, r in decision.skips if (u := apply_skip(st, k, r)) is not None]
            st.priority_ranking = decision.priority_ranking
            if decision.action is None:
                if not skip_updates:
                    # Nothing left that the planner considers useful: with no action taken, the stopping
                    # rules always resolve (S4-S6 if nothing material is open, otherwise S7/S8).
                    st.outcome, st.stop_reason = evaluate(st, 0, clock() - started, run_timeout_s)
                    break
                continue

            tool = TOOLS[decision.action.tool_name]
            reason = _reason(st, decision)
            st.next_action = NextAction(
                tool_name=tool.name,
                tool_label=tool.label,
                requirement_key=decision.action.requirement_key,
                reason=reason,
            )
            st.updated_at = now()
            recorder.on_state(st, ctx)

            st.step += 1
            step_started_at = now()
            t0 = clock()
            outcome = _run_tool(executor, decision, ctx, st, tool_timeout_s)
            duration_ms = int((clock() - t0) * 1000)
            updates, new_evidence = apply_outcome(
                st,
                ctx,
                requirement=decision.action.requirement_key,
                tool=tool.name,
                signature=call_signature(tool.name, decision.tool_input),
                outcome=outcome,
                reason=reason,
                step=st.step,
                now=step_started_at,
            )

            action = InvestigationAction(
                step=st.step,
                tool_name=tool.name,
                tool_label=tool.label,
                requirement_key=decision.action.requirement_key,
                reason=reason,
                input_summary=decision.tool_input.model_dump(mode="json"),
                tool_status=outcome.status,
                evidence_ids=[e.evidence_id for e in new_evidence],
                requirement_updates=[*skip_updates, *updates],
                planner=PlannerInfo(
                    source=decision.source,
                    note=decision.note,
                    priority_ranking=decision.priority_ranking,
                    skipped_requirements=[SkippedRequirement(key=k, reason=r) for k, r in decision.skips],
                    validation_errors=decision.validation_errors,
                ),
                error=outcome.error,
                started_at=step_started_at,
                duration_ms=duration_ms,
            )
            st.trail.append(action)
            st.next_action = None
            st.updated_at = now()
            recorder.on_step(st, ctx, action, new_evidence, decision)

    st.next_action = None
    for req in st.requirements.values():
        if req.state == RequirementState.OPEN and not req.material:
            apply_skip(st, req.key, "not assessed before the investigation stopped")
    st.progress_status = ProgressStatus.BRIEF_READY
    st.updated_at = now()
    brief, validation = validate_brief(build_brief(st, ctx, now()), st)
    recorder.on_finish(st, ctx, brief, validation)
    return InvestigationResult(st, brief, validation, int((clock() - started) * 1000))
