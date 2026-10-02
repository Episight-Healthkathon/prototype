"""AI planner: proposals go through the envelope, failures fall back, recordings replay. No network calls."""

import json
from types import SimpleNamespace

import pytest

from episight.agent.envelope.validator import NO_FURTHER_USEFUL_ACTION
from episight.contracts.enums import (
    InvestigationMode,
    Outcome,
    PlannerSource,
    RequirementKey,
    RequirementState,
    StopReason,
)
from episight.llm.clients import AnthropicClient, LlmError, LlmRefusal, LlmReply, OpenAIClient
from episight.llm.config import LlmSettings, Provider
from episight.llm.planner import LlmPlanner, llm_planner_or_none
from episight.llm.prompt import PROMPT_VERSION, build_user_payload, decision_schema
from episight.llm.recording import JsonDirStore, MemoryStore, ReplayMiss
from tests.unit.engine_helpers import run

K = RequirementKey


def _payload(user: str) -> dict:
    return json.loads(user.split("\n\nYour previous proposal")[0])


class ScriptedClient:
    """Fake vendor client: a policy function maps the request payload to a proposal dict (or raises)."""

    provider = "fake"
    model = "fake-model-1"

    def __init__(self, policy):
        self.policy = policy
        self.calls: list[dict] = []

    def complete_json(self, system, user, schema):
        payload = _payload(user)
        self.calls.append({"payload": payload, "retry": "previous proposal was rejected" in user, "schema": schema})
        result = self.policy(payload, self.calls[-1]["retry"])
        return LlmReply(
            text=json.dumps(result) if not isinstance(result, str) else result, model=self.model, latency_ms=7
        )


def adaptive_policy(payload, retry):
    """A sensible planner: emergency evidence first, read the triage note of the repeat episode before the rest."""
    actions = {a["requirement_key"]: a for a in payload["allowed_actions"]}
    order = [
        "EPISODE_RELATEDNESS",
        "CLINICAL_DOCUMENT_AVAILABILITY",
        "EMERGENCY_CONTEXT",
        "SCHEDULED_PROCEDURE_CONTEXT",
        "SCHEDULE_CONSISTENCY",
        "SUPPORTING_EXAM_FOLLOWUP_CONTEXT",
        "CLINICAL_JUSTIFICATION",
        "CHRONIC_CONDITION_CONTEXT",
        "DIAGNOSIS_CONSISTENCY",
        "PROCEDURE_RELATIONSHIP",
        "RISK_INDICATORS_IN_NOTES",
        "APPLICABLE_POLICY",
        "PROVIDER_CONTEXT",
    ]
    key = next(k for k in order if k in actions)
    action = actions[key]
    scope = None
    emergency_tried = any(t["requirement"] == "EMERGENCY_CONTEXT" for t in payload["trail"])
    anchors = [e for e in payload["case"]["episodes"] if e["role"] == "ANCHOR"]
    repeat_has_triage = any(
        d["note_type"] == "TRIAGE" and d["availability"] == "AVAILABLE" for e in anchors[1:] for d in e["documents"]
    )
    if key == "EMERGENCY_CONTEXT" and action["narrowing_allowed"] and not emergency_tried and repeat_has_triage:
        scope = {"episode_ids": None, "note_types": ["TRIAGE"], "query": None}
    skip = []
    if "PROVIDER_CONTEXT" in actions:
        skip = [{"requirement_key": "PROVIDER_CONTEXT", "reason": "same provider throughout"}]
    return {
        "action_id": action["action_id"],
        "scope": scope,
        "priority_ranking": [key],
        "skip": skip,
        "planner_note": f"Resolve {key.lower().replace('_', ' ')} next.",
    }


GOLDEN = {
    "PAT-000001": (Outcome.EVIDENCE_SUFFICIENT, StopReason.SUFFICIENT_EVIDENCE),
    "PAT-000002": (Outcome.HUMAN_REVIEW_REQUIRED, StopReason.EVIDENCE_PATHS_EXHAUSTED),
    "PAT-000003": (Outcome.EVIDENCE_SUFFICIENT, StopReason.SUFFICIENT_EVIDENCE),
    "PAT-000004": (Outcome.EVIDENCE_UNAVAILABLE, StopReason.REQUIRED_EVIDENCE_UNAVAILABLE),
    "PAT-000005": (Outcome.EVIDENCE_CONFLICTING, StopReason.CONFLICTING_EVIDENCE),
}


@pytest.mark.parametrize("patient_id,expected", GOLDEN.items(), ids=list("ABCDE"))
def test_ai_planner_reaches_the_same_golden_outcomes(patient_id, expected):
    result = run(patient_id, mode=InvestigationMode.FULL, planner=LlmPlanner(ScriptedClient(adaptive_policy)))
    assert (result.state.outcome, result.state.stop_reason) == expected
    assert {a.planner.source for a in result.state.trail} == {PlannerSource.LLM}
    assert result.validation.passed


def test_ai_planner_adapts_the_sequence_and_targets_the_triage_note():
    rule = run("PAT-000001")
    ai = run("PAT-000001", mode=InvestigationMode.FULL, planner=LlmPlanner(ScriptedClient(adaptive_policy)))
    assert [a.requirement_key for a in ai.state.trail] != [a.requirement_key for a in rule.state.trail]
    first_emergency = next(a for a in ai.state.trail if a.requirement_key == K.EMERGENCY_CONTEXT)
    assert first_emergency.input_summary["note_types"] == ["TRIAGE"]
    # Coverage rule: the targeted read found evidence but the question stays open until every note is read.
    assert first_emergency.requirement_updates == [] or all(
        u.to_state != RequirementState.FOUND
        for u in first_emergency.requirement_updates
        if u.key == K.EMERGENCY_CONTEXT
    )
    assert ai.state.requirements[K.EMERGENCY_CONTEXT].state == RequirementState.FOUND
    assert first_emergency.planner.note and first_emergency.planner.source == PlannerSource.LLM


def test_rejected_proposal_is_retried_once_with_the_validator_errors():
    def policy(payload, retry):
        if not retry:
            return {"action_id": "A999", "scope": None, "priority_ranking": [], "skip": [], "planner_note": "x"}
        return adaptive_policy(payload, retry)

    client = ScriptedClient(policy)
    result = run("PAT-000001", mode=InvestigationMode.FULL, planner=LlmPlanner(client))
    first = result.state.trail[0]
    assert first.planner.source == PlannerSource.LLM_RETRY
    assert any(e.startswith("V2") for e in first.planner.validation_errors)
    assert client.calls[1]["retry"]


def test_two_rejections_fall_back_to_the_rule_planner():
    def policy(payload, retry):
        return {
            "action_id": NO_FURTHER_USEFUL_ACTION,
            "scope": None,
            "priority_ranking": [],
            "skip": [],
            "planner_note": "stop now",
        }

    result = run("PAT-000001", mode=InvestigationMode.FULL, planner=LlmPlanner(ScriptedClient(policy)))
    assert {a.planner.source for a in result.state.trail} == {PlannerSource.RULE_FALLBACK}
    assert any(e.startswith("V9") for e in result.state.trail[0].planner.validation_errors)
    assert result.state.outcome == Outcome.EVIDENCE_SUFFICIENT  # the investigation itself is unaffected


@pytest.mark.parametrize("error", [LlmError("API unreachable"), LlmRefusal("declined")])
def test_model_errors_and_refusals_fall_back_per_step(error):
    def policy(payload, retry):
        raise error

    result = run("PAT-000005", mode=InvestigationMode.FULL, planner=LlmPlanner(ScriptedClient(policy)))
    assert {a.planner.source for a in result.state.trail} == {PlannerSource.RULE_FALLBACK}
    assert result.state.outcome == Outcome.EVIDENCE_CONFLICTING
    assert result.state.trail[0].planner.validation_errors[0].startswith("LLM:")


def test_garbage_output_is_rejected_by_v1_and_falls_back():
    result = run("PAT-000003", mode=InvestigationMode.FULL, planner=LlmPlanner(ScriptedClient(lambda p, r: "not json")))
    assert result.state.trail[0].planner.source == PlannerSource.RULE_FALLBACK
    assert any(e.startswith("V1") for e in result.state.trail[0].planner.validation_errors)


def test_record_then_replay_reproduces_the_run_without_calling_the_model(tmp_path):
    store = JsonDirStore(tmp_path / "recordings")
    live = run("PAT-000003", mode=InvestigationMode.FULL, planner=LlmPlanner(ScriptedClient(adaptive_policy), store))

    def must_not_be_called(payload, retry):
        raise AssertionError("replay must not call the model")

    replayed = run(
        "PAT-000003",
        mode=InvestigationMode.FULL,
        planner=LlmPlanner(ScriptedClient(must_not_be_called), store, replay=True),
    )
    strip = lambda r: [a.model_dump(exclude={"duration_ms", "started_at"}) for a in r.state.trail]  # noqa: E731
    assert strip(live) == strip(replayed)
    assert list((tmp_path / "recordings").glob("*.json"))


def test_replay_miss_fails_loudly():
    with pytest.raises(ReplayMiss):
        run(
            "PAT-000001",
            mode=InvestigationMode.FULL,
            planner=LlmPlanner(ScriptedClient(adaptive_policy), MemoryStore(), replay=True),
        )


# --- prompt & schema -----------------------------------------------------------------------------------


def test_schema_is_strict_compatible():
    from episight.agent.envelope.allowed import compute_allowed
    from tests.unit.test_envelope import fresh

    ctx, st = fresh()
    allowed = compute_allowed(st, ctx)
    schema = decision_schema(st, ctx, allowed)

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(schema)
    assert schema["properties"]["action_id"]["enum"][-1] == NO_FURTHER_USEFUL_ACTION
    assert len(schema["properties"]["action_id"]["enum"]) == len(allowed) + 1


def test_payload_is_built_from_state_only_and_is_run_independent():
    from episight.agent.envelope.allowed import compute_allowed
    from tests.unit.test_envelope import fresh

    ctx, st = fresh()
    payload = json.dumps(build_user_payload(st, ctx, compute_allowed(st, ctx)))
    assert "RUN-" not in payload
    assert "ground_truth" not in payload.lower() and "ground-truth" not in payload.lower()
    assert PROMPT_VERSION == "planner-2"


# --- configuration & adapters ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "env,expected",
    [
        ({}, Provider.NONE),
        ({"ANTHROPIC_API_KEY": "a"}, Provider.ANTHROPIC),
        ({"OPENAI_API_KEY": "o"}, Provider.OPENAI),
        ({"ANTHROPIC_API_KEY": "a", "OPENAI_API_KEY": "o"}, Provider.ANTHROPIC),
        ({"ANTHROPIC_API_KEY": "a", "OPENAI_API_KEY": "o", "EPISIGHT_LLM_PROVIDER": "openai"}, Provider.OPENAI),
        ({"ANTHROPIC_API_KEY": "a", "EPISIGHT_LLM_PROVIDER": "none"}, Provider.NONE),
        ({"EPISIGHT_LLM_PROVIDER": "openai"}, Provider.NONE),  # explicit provider without its key
    ],
)
def test_provider_resolution(env, expected, monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "EPISIGHT_LLM_PROVIDER"):
        monkeypatch.delenv(var, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert LlmSettings(_env_file=None).resolved_provider() == expected


def test_no_key_means_no_ai_planner(monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("EPISIGHT_LLM_PROVIDER", "auto")
    assert llm_planner_or_none(settings=LlmSettings(_env_file=None)) is None


def _anthropic_response(text, stop_reason="end_turn"):
    return SimpleNamespace(
        stop_reason=stop_reason, model="claude-opus-5-5", content=[SimpleNamespace(type="text", text=text)]
    )


class _Capture:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def test_anthropic_adapter_uses_structured_output_effort_and_refusal_fallback():
    capture = _Capture(_anthropic_response('{"ok": true}'))
    sdk = SimpleNamespace(beta=SimpleNamespace(messages=capture))
    reply = AnthropicClient("claude-opus-5-5", effort="low", sdk_client=sdk).complete_json(
        "sys", "usr", {"type": "object"}
    )
    assert reply.text == '{"ok": true}'
    kw = capture.kwargs
    assert kw["model"] == "claude-opus-5-5" and kw["fallbacks"] == "default"
    assert kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert kw["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": {"type": "object"}}}
    assert kw["system"] == "sys" and kw["messages"] == [{"role": "user", "content": "usr"}]


@pytest.mark.parametrize("stop_reason,error", [("refusal", LlmRefusal), ("max_tokens", LlmError)])
def test_anthropic_adapter_reports_refusal_and_truncation(stop_reason, error):
    sdk = SimpleNamespace(beta=SimpleNamespace(messages=_Capture(_anthropic_response("{}", stop_reason))))
    with pytest.raises(error):
        AnthropicClient("claude-opus-5-5", sdk_client=sdk).complete_json("s", "u", {})


def test_openai_adapter_uses_strict_json_schema():
    message = SimpleNamespace(content='{"ok": true}', refusal=None)
    response = SimpleNamespace(model="gpt-4o", choices=[SimpleNamespace(message=message, finish_reason="stop")])
    capture = _Capture(response)
    sdk = SimpleNamespace(chat=SimpleNamespace(completions=capture))
    reply = OpenAIClient("gpt-4o", sdk_client=sdk).complete_json("sys", "usr", {"type": "object"})
    assert reply.text == '{"ok": true}'
    rf = capture.kwargs["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["strict"] is True
    assert capture.kwargs["messages"][0] == {"role": "system", "content": "sys"}


def test_openai_adapter_reports_refusal():
    message = SimpleNamespace(content=None, refusal="I can't help with that")
    response = SimpleNamespace(model="gpt-4o", choices=[SimpleNamespace(message=message, finish_reason="stop")])
    sdk = SimpleNamespace(chat=SimpleNamespace(completions=_Capture(response)))
    with pytest.raises(LlmRefusal):
        OpenAIClient("gpt-4o", sdk_client=sdk).complete_json("s", "u", {})
