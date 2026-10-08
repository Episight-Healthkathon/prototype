"""Golden-case behavior through the real engine (architecture §7.7). Behavioral assertions, not exact trails."""

from dataclasses import replace

import pytest

from episight.agent.orchestrator import run_investigation
from episight.agent.planners.rule_planner import RulePlanner
from episight.contracts.enums import (
    EvidenceCategory,
    InvestigationMode,
    Outcome,
    RequirementKey,
    RequirementState,
    SourceType,
    StopReason,
)
from tests.unit.engine_helpers import ctx_for, run

K, S = RequirementKey, RequirementState
GOLDEN = {
    "PAT-000001": (Outcome.EVIDENCE_SUFFICIENT, StopReason.SUFFICIENT_EVIDENCE),  # A
    "PAT-000002": (Outcome.HUMAN_REVIEW_REQUIRED, StopReason.EVIDENCE_PATHS_EXHAUSTED),  # B
    "PAT-000003": (Outcome.EVIDENCE_SUFFICIENT, StopReason.SUFFICIENT_EVIDENCE),  # C
    "PAT-000004": (Outcome.EVIDENCE_UNAVAILABLE, StopReason.REQUIRED_EVIDENCE_UNAVAILABLE),  # D
    "PAT-000005": (Outcome.EVIDENCE_CONFLICTING, StopReason.CONFLICTING_EVIDENCE),  # E
}


def states(result):
    return {k: r.state for k, r in result.state.requirements.items()}


@pytest.mark.parametrize("patient_id,expected", GOLDEN.items(), ids=["A", "B", "C", "D", "E"])
def test_golden_outcome_and_stop_reason(patient_id, expected):
    result = run(patient_id)
    assert (result.state.outcome, result.state.stop_reason) == expected
    assert result.state.step <= result.state.max_steps
    assert result.validation.passed, result.validation.violations


def test_case_a_surfaces_emergency_context_from_notes_and_keeps_risk_evidence():
    result = run("PAT-000001")
    s = states(result)
    assert s[K.EMERGENCY_CONTEXT] == S.FOUND and s[K.CHRONIC_CONDITION_CONTEXT] == S.FOUND
    emergency = result.state.evidence_for(K.EMERGENCY_CONTEXT)
    assert emergency and all(e.source_type == SourceType.CLINICAL_NOTE for e in emergency)
    # Dual evidence: the risk side stays visible next to the explanation.
    cats = {e.relevance_category for e in result.state.evidence.values()}
    assert {EvidenceCategory.SUPPORTING_RISK, EvidenceCategory.EXPLAINING_CONTEXT} <= cats
    assert result.brief.supporting_risk_evidence and result.brief.explaining_context_evidence


def test_case_b_exhausts_every_context_path_before_stopping():
    result = run("PAT-000002")
    s = states(result)
    for key in (
        K.EMERGENCY_CONTEXT,
        K.CHRONIC_CONDITION_CONTEXT,
        K.SCHEDULED_PROCEDURE_CONTEXT,
        K.SUPPORTING_EXAM_FOLLOWUP_CONTEXT,
        K.CLINICAL_JUSTIFICATION,
    ):
        assert s[key] == S.NOT_FOUND
    assert s[K.RISK_INDICATORS_IN_NOTES] == S.FOUND
    assert "remains unresolved" in result.brief.case_summary[-1].text


def test_case_c_spawns_and_confirms_schedule_consistency():
    result = run("PAT-000003")
    req = result.state.requirements[K.SCHEDULE_CONSISTENCY]
    assert req.spawned_by == K.SCHEDULED_PROCEDURE_CONTEXT and req.state == S.FOUND
    assert states(result)[K.PROCEDURE_RELATIONSHIP] == S.FOUND  # 88.56 -> 36.06 is still visible as risk side


def test_case_d_keeps_missing_evidence_missing():
    result = run("PAT-000004")
    s = states(result)
    assert s[K.EMERGENCY_CONTEXT] == S.UNAVAILABLE and s[K.CLINICAL_JUSTIFICATION] == S.UNAVAILABLE
    assert all(e.requirement_key != K.EMERGENCY_CONTEXT for e in result.state.evidence.values())
    gap_keys = {g.key for g in result.brief.remaining_gaps}
    assert {K.EMERGENCY_CONTEXT, K.CLINICAL_JUSTIFICATION} <= gap_keys
    assert result.brief.outcome == Outcome.EVIDENCE_UNAVAILABLE


def test_case_e_keeps_both_sides_of_the_conflict_visible():
    result = run("PAT-000005")
    conflict = next(c for c in result.brief.conflicts if c.key == K.EMERGENCY_CONTEXT)
    assert conflict.affirming_evidence_ids and conflict.negating_evidence_ids
    sources = {
        result.state.evidence[e].source_id for e in conflict.affirming_evidence_ids + conflict.negating_evidence_ids
    }
    assert sources == {"NOTE-000502", "NOTE-000503"}


@pytest.mark.parametrize("text,expected", [
    ("Pasien ditangani segera di ruang resusitasi dengan dua jalur infus.", S.FOUND),
    ("Pasien distabilisasi dalam ruangan resusitasi setelah penilaian awal.", S.FOUND),
    ("The patient was treated immediately in the resuscitation room.", S.FOUND),
    ("Pasien diantar ambulans untuk kontrol rutin.", S.NOT_FOUND),
    ("Jika memburuk, pasien akan ditangani di ruang resusitasi.", S.NOT_FOUND),
])
def test_resuscitation_context_through_engine_preserves_scope_and_provenance(text, expected):
    original = ctx_for("PAT-000001")
    repeat_ids = set(original.later_ids)
    notes = {nid: n.model_copy(update={"text": text if n.note_type.value == "TRIAGE" else "Kondisi stabil."})
             if n.episode_id in repeat_ids else n for nid, n in original.notes.items()}
    ctx = replace(original, notes=notes)
    result = run_investigation(ctx, run_id="RUN-RESUSCITATION", planner=RulePlanner())
    assert states(result)[K.EMERGENCY_CONTEXT] == expected
    evidence = result.state.evidence_for(K.EMERGENCY_CONTEXT)
    if expected == S.FOUND:
        assert evidence and all(e.source_type == SourceType.CLINICAL_NOTE for e in evidence)
        assert all(e.source_id in notes
                   and notes[e.source_id].text[e.char_start:e.char_end] == e.source_excerpt for e in evidence)
    else:
        assert not evidence
    assert result.validation.passed


def test_state_transitions_differ_across_cases():
    # The rule planner uses a fixed order, so A and D can share a tool sequence; what must differ is what the
    # evidence did to the state. Sequence differences are the AI planner's job (tested with it).
    trails = {
        p: tuple(
            (a.tool_name, a.requirement_key, tuple(u.to_state for u in a.requirement_updates))
            for a in run(p).state.trail
        )
        for p in GOLDEN
    }
    assert len(set(trails.values())) == len(trails)


def test_runs_are_deterministic():
    a, b = run("PAT-000003"), run("PAT-000003")
    assert a.brief.model_dump() == b.brief.model_dump()

    # Timings are wall-clock; everything else must be identical.
    def trail(r):
        return [x.model_dump(exclude={"duration_ms"}) for x in r.state.trail]

    assert trail(a) == trail(b)


def test_every_material_brief_statement_is_traceable():
    for patient_id in GOLDEN:
        t = run(patient_id).brief.traceability
        assert t.material_statements == t.with_evidence


# --- ablation modes (architecture §11) ----------------------------------------------------------------


def test_rules_only_cannot_assess_context():
    result = run("PAT-000001", mode=InvestigationMode.RULES_ONLY)
    assert (result.state.outcome, result.state.stop_reason) == (
        Outcome.EVIDENCE_UNAVAILABLE,
        StopReason.NO_ACTIONABLE_GAP,
    )
    assert all(
        a.tool_name.value in {"get_episode_history", "compare_diagnosis", "compare_procedures", "get_provider_context"}
        for a in result.state.trail
    )


def test_rules_retrieval_runs_everything_and_never_spawns():
    result = run("PAT-000005", mode=InvestigationMode.RULES_RETRIEVAL)
    assert K.SCHEDULE_CONSISTENCY not in result.state.requirements
    assert result.state.outcome == Outcome.EVIDENCE_CONFLICTING
    assert result.state.step > run("PAT-000005").state.step  # no early stop on conflict
