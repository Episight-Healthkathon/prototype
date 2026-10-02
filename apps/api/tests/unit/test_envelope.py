"""Safety envelope: allowed actions, validator V1–V9, stopping S1–S8, failure handling, termination."""

import random
from datetime import UTC, datetime

import pytest

from episight.agent.envelope.allowed import compute_allowed
from episight.agent.envelope.stopping import evaluate
from episight.agent.envelope.validator import NO_FURTHER_USEFUL_ACTION, validate
from episight.agent.planners.base import Decision
from episight.agent.state import InvestigationState
from episight.agent.tools import TOOLS, ToolOutcome
from episight.contracts.enums import (
    InvestigationMode,
    Outcome,
    PlannerSource,
    RequirementKey,
    RequirementState,
    StopReason,
    ToolName,
    ToolStatus,
)
from episight.evidence.ledger import EvidenceCandidate, ProvenanceError, check_provenance
from tests.unit.engine_helpers import ctx_for, run

K, S = RequirementKey, RequirementState
NOW = datetime(2026, 10, 2, tzinfo=UTC)


def fresh(patient_id="PAT-000001", mode=InvestigationMode.FULL, max_steps=12):
    ctx = ctx_for(patient_id)
    return ctx, InvestigationState.new(ctx, "RUN-X", mode, max_steps, NOW)


# --- allowed actions --------------------------------------------------------------------------------


def test_note_requirements_wait_for_prerequisites():
    ctx, st = fresh()
    keys = {a.requirement_key for a in compute_allowed(st, ctx)}
    assert K.EMERGENCY_CONTEXT not in keys and K.CLINICAL_DOCUMENT_AVAILABILITY not in keys
    assert K.EPISODE_RELATEDNESS in keys and K.APPLICABLE_POLICY in keys


def test_rules_only_mode_offers_structural_tools_only():
    ctx, st = fresh(mode=InvestigationMode.RULES_ONLY)
    assert {a.tool_name for a in compute_allowed(st, ctx)} <= {
        ToolName.GET_EPISODE_HISTORY,
        ToolName.COMPARE_DIAGNOSIS,
        ToolName.COMPARE_PROCEDURES,
        ToolName.GET_PROVIDER_CONTEXT,
    }


# --- validator: every adversarial proposal is rejected -------------------------------------------------


def _st_ready_for_notes():
    ctx, st = fresh()
    for key in (K.EPISODE_RELATEDNESS, K.CLINICAL_DOCUMENT_AVAILABILITY):
        st.requirements[key].state = S.FOUND
    st.related_known = True
    return ctx, st


def _action(allowed, key):
    return next(a for a in allowed if a.requirement_key == key)


def test_valid_proposal_with_narrowed_scope_is_accepted():
    ctx, st = _st_ready_for_notes()
    allowed = compute_allowed(st, ctx)
    a = _action(allowed, K.EMERGENCY_CONTEXT)
    out = validate(
        {"action_id": a.action_id, "scope": {"note_types": ["TRIAGE"]}, "planner_note": "triage first"}, allowed, st
    )
    assert out.ok and out.decision.tool_input.note_types == ["TRIAGE"]


@pytest.mark.parametrize(
    "proposal_factory,code",
    [
        (lambda a, al: "not json", "V1"),
        (lambda a, al: {"action": "A1"}, "V1"),
        (lambda a, al: {"action_id": "A999"}, "V2"),
        (lambda a, al: {"action_id": a.action_id, "scope": {"episode_ids": ["EPI-999999"]}}, "V5"),
        (lambda a, al: {"action_id": a.action_id, "scope": {"query": "x"}}, "V5"),
        (
            lambda a, al: {"action_id": a.action_id, "skip": [{"requirement_key": "EMERGENCY_CONTEXT", "reason": "x"}]},
            "V8",
        ),
        (
            lambda a, al: {
                "action_id": a.action_id,
                "skip": [{"requirement_key": "CHRONIC_CONDITION_CONTEXT", "reason": "x"}],
            },
            "V8",
        ),
        (lambda a, al: {"action_id": NO_FURTHER_USEFUL_ACTION}, "V9"),
    ],
    ids=[
        "not-json",
        "wrong-schema",
        "unknown-action",
        "out-of-scope-episode",
        "query-on-note-tool",
        "skip-own-requirement",
        "skip-material",
        "premature-stop",
    ],
)
def test_adversarial_proposals_are_rejected(proposal_factory, code):
    ctx, st = _st_ready_for_notes()
    allowed = compute_allowed(st, ctx)
    out = validate(proposal_factory(_action(allowed, K.EMERGENCY_CONTEXT), allowed), allowed, st)
    assert not out.ok and any(e.startswith(code) for e in out.errors), out.errors


def test_duplicate_call_is_rejected():
    ctx, st = _st_ready_for_notes()
    allowed = compute_allowed(st, ctx)
    a = _action(allowed, K.APPLICABLE_POLICY)
    from episight.agent.state import call_signature

    st.calls[call_signature(a.tool_name, a.default_input)] = [ToolStatus.OK]
    out = validate({"action_id": a.action_id}, allowed, st)
    assert not out.ok and any(e.startswith("V6") for e in out.errors)


def test_narrowing_is_refused_when_the_step_budget_is_tight():
    ctx, st = _st_ready_for_notes()
    st.step = st.max_steps - 2  # fewer steps left than open material requirements
    allowed = compute_allowed(st, ctx)
    a = _action(allowed, K.EMERGENCY_CONTEXT)
    out = validate({"action_id": a.action_id, "scope": {"note_types": ["TRIAGE"]}}, allowed, st)
    assert not out.ok and any("budget" in e for e in out.errors)


# --- stopping ---------------------------------------------------------------------------------------


def test_stopping_rules_in_order():
    ctx, st = fresh()
    assert evaluate(st, 5, 0, 60) is None
    st.requirements[K.EMERGENCY_CONTEXT].state = S.CONFLICTING
    st.requirements[K.APPLICABLE_POLICY].state = S.FAILED
    assert evaluate(st, 5, 0, 60) == (Outcome.EVIDENCE_CONFLICTING, StopReason.CONFLICTING_EVIDENCE)  # S1 first
    st.requirements[K.EMERGENCY_CONTEXT].state = S.OPEN
    assert evaluate(st, 5, 99, 60) == (Outcome.HUMAN_REVIEW_REQUIRED, StopReason.TIMEOUT)  # S2
    assert evaluate(st, 5, 0, 60) == (Outcome.HUMAN_REVIEW_REQUIRED, StopReason.TOOL_FAILURE)  # S3
    st.requirements[K.APPLICABLE_POLICY].state = S.OPEN
    st.step = st.max_steps
    assert evaluate(st, 5, 0, 60) == (Outcome.HUMAN_REVIEW_REQUIRED, StopReason.MAX_STEPS_REACHED)  # S7
    st.step = 0
    assert evaluate(st, 0, 0, 60) == (Outcome.EVIDENCE_UNAVAILABLE, StopReason.NO_ACTIONABLE_GAP)  # S8


def test_max_steps_stops_with_human_review():
    result = run("PAT-000001", max_steps=3)
    assert (result.state.outcome, result.state.stop_reason) == (
        Outcome.HUMAN_REVIEW_REQUIRED,
        StopReason.MAX_STEPS_REACHED,
    )
    assert result.state.step == 3 and result.validation.passed


# --- failures are explicit, never replaced --------------------------------------------------------------


def test_tool_error_is_retried_once_then_failed(monkeypatch):
    def broken(ctx, st, inp):
        raise RuntimeError("policy store offline")

    monkeypatch.setitem(
        TOOLS,
        ToolName.RETRIEVE_POLICY,
        TOOLS[ToolName.RETRIEVE_POLICY].__class__(
            ToolName.RETRIEVE_POLICY, "Checking policy context", TOOLS[ToolName.RETRIEVE_POLICY].input_model, broken
        ),
    )
    result = run("PAT-000001")
    policy_steps = [a for a in result.state.trail if a.tool_name == ToolName.RETRIEVE_POLICY]
    assert [a.tool_status for a in policy_steps] == [ToolStatus.ERROR, ToolStatus.ERROR]
    assert result.state.requirements[K.APPLICABLE_POLICY].state == S.FAILED
    assert (result.state.outcome, result.state.stop_reason) == (Outcome.HUMAN_REVIEW_REQUIRED, StopReason.TOOL_FAILURE)


def test_fabricated_excerpt_is_rejected_by_provenance_check():
    ctx = ctx_for("PAT-000001")
    fake = EvidenceCandidate(
        requirement_key=K.EMERGENCY_CONTEXT,
        source_type=__import__("episight").contracts.enums.SourceType.CLINICAL_NOTE,
        source_id="NOTE-000102",
        source_title="x",
        source_excerpt="Pasien datang via ambulans.",
        stance=__import__("episight").contracts.enums.Stance.AFFIRMS,
        extraction_method=__import__("episight").contracts.enums.ExtractionMethod.RULE_MATCH,
        char_start=0,
        char_end=26,
    )
    with pytest.raises(ProvenanceError):
        check_provenance(ctx, fake)


def test_empty_policy_corpus_is_unavailable_not_invented():
    ctx, st = fresh()
    from episight.agent.tools import RetrievePolicyInput, retrieve_policy
    from episight.retrieval.policy import PolicyIndex

    original = ctx.policy
    try:
        ctx.policy = PolicyIndex([])
        out = retrieve_policy(ctx, st, RetrievePolicyInput(signal_type="READMISSION", query="readmisi"))
    finally:
        ctx.policy = original
    assert out.status == ToolStatus.UNAVAILABLE and not out.candidates


# --- termination under arbitrary (but allowed) planner choices ---------------------------------------


class RandomPlanner:
    def __init__(self, seed):
        self.rng = random.Random(seed)

    def decide(self, st, ctx, allowed):
        action = self.rng.choice(allowed)
        return Decision(action=action, tool_input=action.default_input, source=PlannerSource.LLM)


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("patient_id", ["PAT-000001", "PAT-000002", "PAT-000003", "PAT-000004", "PAT-000005"])
def test_any_allowed_choice_order_terminates_with_a_valid_brief(seed, patient_id):
    result = run(patient_id, planner=RandomPlanner(seed))
    assert result.state.step <= result.state.max_steps
    assert result.state.outcome is not None and result.validation.passed


def test_unused_tool_outcome_type_is_constructible():
    assert ToolOutcome(status=ToolStatus.EMPTY).candidates == []


def test_narrowed_scope_without_readable_documents_is_rejected():
    ctx, st = fresh("PAT-000003")  # repeat episode has procedure + discharge notes, no triage note
    for key in (K.EPISODE_RELATEDNESS, K.CLINICAL_DOCUMENT_AVAILABILITY):
        st.requirements[key].state = S.FOUND
    st.related_known = True
    allowed = compute_allowed(st, ctx)
    a = _action(allowed, K.EMERGENCY_CONTEXT)
    out = validate({"action_id": a.action_id, "scope": {"note_types": ["TRIAGE"]}}, allowed, st, ctx)
    assert not out.ok and any("no unread readable document" in e for e in out.errors)
