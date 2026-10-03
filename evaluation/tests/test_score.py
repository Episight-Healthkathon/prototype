"""Scoring harness tests on a hand-built runner output + ground truth (no backend needed)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import score


def ev(st, sid, key, cat="EXPLAINING_CONTEXT", mandatory=True):
    return {"source_type": st, "source_id": sid, "requirement_key": key, "category": cat, "mandatory": mandatory}


def out_ev(st, sid, key):
    return {"evidence_id": f"EV-{sid}-{key}", "source_type": st, "source_id": sid, "requirement_key": key,
            "stance": "AFFIRMS", "relevance_category": "EXPLAINING_CONTEXT"}


GT = [
    {"gt_id": "GT-A", "golden_case": "A", "scenario_class": "LEGIT_READMISSION_EMERGENCY",
     "expected_signal_type": "READMISSION", "anchor_episode_ids": ["E1", "E2"],
     "expected_related_episode_ids": ["E0", "E1", "E2"],
     "expected_evidence": [ev("CLINICAL_NOTE", "N2", "EMERGENCY_CONTEXT"),
                           ev("CLINICAL_NOTE", "N0", "CHRONIC_CONDITION_CONTEXT"),
                           ev("CLINICAL_NOTE", "N3", "EMERGENCY_CONTEXT", mandatory=False),
                           ev("POLICY_SECTION", "P-RA", "APPLICABLE_POLICY", "NEUTRAL", False),
                           ev("POLICY_SECTION", "P-FR", "APPLICABLE_POLICY", "IRRELEVANT", False)],
     "expected_exceptions": ["EMERGENCY_CONTEXT", "CHRONIC_CONDITION_CONTEXT"],
     "expected_requirement_states": {"EMERGENCY_CONTEXT": "FOUND", "CHRONIC_CONDITION_CONTEXT": "FOUND"},
     "expected_outcome": "EVIDENCE_SUFFICIENT", "expected_stop_reason": "SUFFICIENT_EVIDENCE"},
    {"gt_id": "GT-B", "golden_case": "B", "scenario_class": "POTENTIAL_FRAGMENTATION",
     "expected_signal_type": "FRAGMENTATION", "anchor_episode_ids": ["F1", "F2"],
     "expected_related_episode_ids": ["F1", "F2"], "expected_evidence": [], "expected_exceptions": [],
     "expected_requirement_states": {}, "expected_outcome": "HUMAN_REVIEW_REQUIRED",
     "expected_stop_reason": "EVIDENCE_PATHS_EXHAUSTED"},
    {"gt_id": "GT-N1", "golden_case": None, "scenario_class": "NOT_FLAGGABLE", "expected_signal_type": None,
     "anchor_episode_ids": ["X1", "X2"], "expected_related_episode_ids": ["X1", "X2"], "expected_evidence": [],
     "expected_exceptions": [], "expected_requirement_states": {}, "expected_outcome": None,
     "expected_stop_reason": None},
    {"gt_id": "GT-N2", "golden_case": None, "scenario_class": "NOT_FLAGGABLE", "expected_signal_type": None,
     "anchor_episode_ids": ["Y1", "Y2"], "expected_related_episode_ids": ["Y1", "Y2"], "expected_evidence": [],
     "expected_exceptions": [], "expected_requirement_states": {}, "expected_outcome": None,
     "expected_stop_reason": None},
]


def case(anchors, recon, evidence, states, outcome, stop, run_index=0, **kw):
    return {"case_id": "CASE-" + anchors[0], "run_index": run_index, "signal_type": "READMISSION",
            "anchor_episode_ids": anchors, "reconstructed_episode_ids": recon, "evidence": evidence,
            "requirement_states": states, "outcome": outcome, "stop_reason": stop, "tool_call_count": 9,
            "step_count": kw.get("steps", 9), "tool_failures": 0, "elapsed_ms": kw.get("ms", 10),
            "planner": {"llm_steps": 0, "llm_retry_steps": 0, "fallback_steps": 0, "rule_steps": 9,
                        "validation_rejections": 0},
            "brief_traceability": {"material_statements": 4, "with_evidence": kw.get("traced", 4)},
            "brief_validation": {"passed": True, "violations": []}}


def run_output():
    a = case(["E1", "E2"], ["E1", "E2"],  # misses related E0
             [out_ev("SCREENING_RULE", "R", "EPISODE_RELATEDNESS"),
              out_ev("CLINICAL_NOTE", "N2", "EMERGENCY_CONTEXT"),
              out_ev("CLINICAL_NOTE", "N2", "EMERGENCY_CONTEXT"),  # duplicate triple counts once
              out_ev("CLINICAL_NOTE", "N9", "CLINICAL_JUSTIFICATION"),  # unlabelled -> not relevant
              out_ev("POLICY_SECTION", "P-RA", "APPLICABLE_POLICY"),
              out_ev("POLICY_SECTION", "P-FR", "APPLICABLE_POLICY")],
             {"EMERGENCY_CONTEXT": "FOUND", "CHRONIC_CONDITION_CONTEXT": "NOT_FOUND"},
             "EVIDENCE_SUFFICIENT", "SUFFICIENT_EVIDENCE", traced=3)
    b = case(["F1", "F2"], ["F1", "F2"], [], {"EMERGENCY_CONTEXT": "FOUND"}, "EVIDENCE_SUFFICIENT",
             "SUFFICIENT_EVIDENCE")
    return {"header": {"mode": "FULL_RULE_PLANNER", "dataset_version": "vT", "corpus_version": "pc-T",
                       "code_version": "abc", "config_hash": "h"},
            "cases": [a, b],
            "screening": {"flagged_anchor_sets": [["E1", "E2"], ["F1", "F2"], ["X1", "X2"], ["Z1", "Z2"]]}}


@pytest.fixture
def scored():
    return score.score_run(run_output(), GT)


def test_screening_recall_and_false_positives(scored):
    s = scored["aggregate"]["screening"]
    assert s["recall"] == 1.0
    assert s["must_not_flag_violations"] == ["GT-N1"]
    assert s["false_positive_sets"] == 2  # X1/X2 (labelled negative) + Z1/Z2 (unknown)


def test_episode_recall(scored):
    a = scored["cases"]["GT-A"][0]
    assert a["episode_recall"] == pytest.approx(2 / 3)
    assert a["episode_precision"] == 1.0


def test_evidence_precision_dedupes_and_ignores_structured_sources(scored):
    a = scored["cases"]["GT-A"][0]
    # retrieved (notes + policy, deduped): N2/EMERG, N9/JUST, P-RA, P-FR -> relevant: N2, P-RA
    assert a["evidence_retrieved"] == 4
    assert a["evidence_precision"] == pytest.approx(0.5)
    assert a["note_evidence_precision"] == pytest.approx(0.5)
    assert a["policy_precision"] == pytest.approx(0.5)


def test_evidence_coverage_counts_mandatory_only(scored):
    a = scored["cases"]["GT-A"][0]
    assert a["evidence_coverage"] == pytest.approx(0.5)  # N2 found, N0 chronic missed
    assert a["missed_mandatory"] == ["CLINICAL_NOTE:N0:CHRONIC_CONDITION_CONTEXT"]
    assert scored["cases"]["GT-B"][0]["evidence_coverage"] is None


def test_exception_identification(scored):
    a = scored["cases"]["GT-A"][0]
    assert a["exception_exact"] is False
    assert a["exceptions_found"] == ["EMERGENCY_CONTEXT"]
    b = scored["cases"]["GT-B"][0]
    assert b["exception_exact"] is False  # surfaced an exception that should not exist
    agg = scored["aggregate"]["exceptions"]
    assert agg["tp"] == 1 and agg["fn"] == 1 and agg["fp"] == 1


def test_escalation_and_unsafe_closure(scored):
    a, b = scored["cases"]["GT-A"][0], scored["cases"]["GT-B"][0]
    assert a["outcome_correct"] and a["stop_reason_correct"]
    assert not b["outcome_correct"]
    assert b["unsafe_closure"] is True  # should have escalated, closed as sufficient
    agg = scored["aggregate"]
    assert agg["escalation"]["unsafe_closures"] == ["GT-B"]
    assert agg["outcome_accuracy"] == pytest.approx(0.5)


def test_requirement_state_accuracy_and_golden(scored):
    a = scored["cases"]["GT-A"][0]
    assert a["state_accuracy"] == pytest.approx(0.5)
    assert a["golden_pass"] is False  # chronic state wrong
    assert scored["aggregate"]["golden"] == {"A": False, "B": False}


def test_traceability(scored):
    assert scored["cases"]["GT-A"][0]["traceability"] == pytest.approx(0.75)


def test_missing_case_is_reported_not_crashed():
    out = run_output()
    out["cases"] = out["cases"][:1]
    out["screening"]["flagged_anchor_sets"] = [["E1", "E2"]]
    s = score.score_run(out, GT)
    assert s["aggregate"]["screening"]["missed"] == ["GT-B"]
    assert s["cases"]["GT-B"] == []
    assert s["aggregate"]["golden"]["B"] is False


def test_repeats_are_scored_per_run_and_variance_reported():
    out = run_output()
    rep = json.loads(json.dumps(out["cases"][1]))
    rep["run_index"] = 1
    rep["outcome"], rep["stop_reason"] = "HUMAN_REVIEW_REQUIRED", "EVIDENCE_PATHS_EXHAUSTED"
    out["cases"].append(rep)
    s = score.score_run(out, GT)
    assert len(s["cases"]["GT-B"]) == 2
    assert s["aggregate"]["variance"]["unstable_cases"] == ["GT-B"]
    assert s["aggregate"]["golden"]["B"] is False  # golden must pass on every repeat


def test_compare_flags_regressions():
    base = score.score_run(run_output(), GT)
    better = run_output()
    better["cases"][1]["outcome"], better["cases"][1]["stop_reason"] = (
        "HUMAN_REVIEW_REQUIRED", "EVIDENCE_PATHS_EXHAUSTED")
    new = score.score_run(better, GT)
    diff = score.compare(base, new)
    assert diff["fixed"] == ["GT-B"] and diff["newly_failing"] == []
    back = score.compare(new, base)
    assert back["newly_failing"] == ["GT-B"]
    assert back["metric_delta"]["outcome_accuracy"] == pytest.approx(-0.5)


def test_cli_writes_report(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "FULL_RULE_PLANNER.json").write_text(json.dumps(run_output()), encoding="utf-8")
    gt = tmp_path / "cases.jsonl"
    gt.write_text("".join(json.dumps(r) + "\n" for r in GT), encoding="utf-8")
    code = score.main(["--run", str(run), "--ground-truth", str(gt)])
    assert code == 0
    assert (run / "scores.json").exists()
    assert (run / "per_case_FULL_RULE_PLANNER.csv").exists()
    report = (run / "report.md").read_text(encoding="utf-8")
    assert "GT-B" in report and "FULL_RULE_PLANNER" in report
    assert score.main(["--run", str(run), "--ground-truth", str(gt), "--fail-on-golden"]) == 1
