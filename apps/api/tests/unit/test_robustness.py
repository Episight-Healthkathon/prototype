"""M9 failure behaviour: hung tools, run timeout, malformed notes, repeated evidence, governance surface."""

import copy
import json
import time

import pytest

from episight.agent.tools import TOOLS, ToolDef
from episight.contracts.enums import Outcome, RequirementKey, RequirementState, StopReason, ToolName, ToolStatus
from tests.conftest import SHARED_TYPES
from tests.unit.engine_helpers import ctx_for, run

K, S = RequirementKey, RequirementState


def test_hung_tool_times_out_without_blocking_later_tools(monkeypatch):
    original = TOOLS[ToolName.RETRIEVE_POLICY]

    def hang(ctx, st, inp):
        time.sleep(1.5)
        return original.fn(ctx, st, inp)

    monkeypatch.setitem(
        TOOLS, ToolName.RETRIEVE_POLICY, ToolDef(original.name, original.label, original.input_model, hang)
    )
    started = time.perf_counter()
    result = run("PAT-000001", tool_timeout_s=0.2)
    assert time.perf_counter() - started < 1.5 * 2  # the hung calls were abandoned, not awaited
    statuses = [a.tool_status for a in result.state.trail if a.tool_name == ToolName.RETRIEVE_POLICY]
    assert statuses == [ToolStatus.TIMEOUT, ToolStatus.TIMEOUT]
    others = [a for a in result.state.trail if a.tool_name != ToolName.RETRIEVE_POLICY]
    assert all(a.tool_status != ToolStatus.TIMEOUT for a in others)  # nothing else was blocked
    assert (result.state.outcome, result.state.stop_reason) == (Outcome.HUMAN_REVIEW_REQUIRED, StopReason.TOOL_FAILURE)
    assert result.validation.passed


def test_run_timeout_stops_with_human_review_and_a_valid_brief():
    ticks = iter(range(0, 10_000, 100))  # every clock read advances 100 s
    result = run("PAT-000003", clock=lambda: next(ticks), run_timeout_s=60)
    assert (result.state.outcome, result.state.stop_reason) == (Outcome.HUMAN_REVIEW_REQUIRED, StopReason.TIMEOUT)
    assert result.validation.passed
    assert "stopped early" in result.brief.case_summary[-1].text


@pytest.mark.parametrize(
    "text",
    ["", "   ", "IGD" * 5000, "tidak ada catatan. . . ???", "Kategori triase: merah\n\n\n(gawat darurat)", "💉 \x00 ✓"],
    ids=["empty", "whitespace", "very-long", "punctuation", "line-breaks", "odd-chars"],
)
def test_malformed_note_text_never_crashes_and_excerpts_stay_literal(text):
    ctx = copy.deepcopy(ctx_for("PAT-000001"))
    note = ctx.notes["NOTE-000102"]
    ctx.notes["NOTE-000102"] = note.model_copy(update={"text": text})
    ctx.notes_by_episode["EPI-000102"] = [ctx.notes[n.note_id] for n in ctx.notes_by_episode["EPI-000102"]]
    from episight.agent.orchestrator import run_investigation
    from episight.agent.planners.rule_planner import RulePlanner
    from episight.contracts.enums import InvestigationMode

    result = run_investigation(
        ctx, run_id="RUN-MALFORMED", planner=RulePlanner(), mode=InvestigationMode.FULL_RULE_PLANNER
    )
    assert result.state.outcome is not None and result.validation.passed
    for ev in result.state.evidence.values():
        if ev.source_id == "NOTE-000102":
            assert text[ev.char_start : ev.char_end] == ev.source_excerpt


def test_repeated_evidence_is_deduplicated_and_tracked():
    from datetime import UTC, datetime

    from episight.agent.reducer import apply_outcome
    from episight.agent.state import InvestigationState
    from episight.agent.tools import FindExceptionInput, find_exception_evidence
    from episight.contracts.enums import InvestigationMode
    from episight.retrieval.context import ContextType

    ctx = ctx_for("PAT-000001")
    st = InvestigationState.new(ctx, "RUN-DEDUPE", InvestigationMode.FULL, 12, datetime.now(UTC))
    st.related_known = True
    inp = FindExceptionInput(context_type=ContextType.EMERGENCY, episode_ids=["EPI-000102"], note_types=["TRIAGE"])
    for step in (1, 2):
        outcome = find_exception_evidence(ctx, st, inp)
        apply_outcome(
            st,
            ctx,
            requirement=K.EMERGENCY_CONTEXT,
            tool=ToolName.FIND_EXCEPTION_EVIDENCE,
            signature=f"sig-{step}",
            outcome=outcome,
            reason="r",
            step=step,
            now=datetime.now(UTC),
        )
    ids = st.requirements[K.EMERGENCY_CONTEXT].evidence_ids
    assert len(ids) == len(set(ids)) > 0
    assert all(st.surfaced_in_steps[e] == [1, 2] for e in ids)


def test_api_surface_exposes_no_decision_authority():
    spec = json.loads((SHARED_TYPES / "openapi.json").read_text(encoding="utf-8"))
    banned = ("fraud", "approve", "reject", "payment", "verdict", "adjudicat")
    for path, ops in spec["paths"].items():
        assert not any(b in path.lower() for b in banned), path
        for op in ops.values():
            text = json.dumps({k: op.get(k) for k in ("operationId", "summary", "description")}).lower()
            assert not any(b in text for b in banned), (path, text)
