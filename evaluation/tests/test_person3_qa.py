"""Person 3 acceptance through the real ingest/screen/investigate/brief pipeline."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("person3_qa", ROOT / "evaluation/run_person3_qa.py")
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)


@pytest.fixture(scope="module")
def acceptance(tmp_path_factory):
    # main only writes in evaluation/runs. The test builds/runs its challenge in pytest scratch.
    directory = tmp_path_factory.mktemp("person3")
    truth = qa.build_challenge(directory / "dataset")
    output, audits = qa.run_dataset(directory / "dataset", truth)
    return truth, output, audits


def test_challenge_complete_and_every_governance_check_passes(acceptance):
    truth, output, audits = acceptance
    assert len(truth) == len(output["cases"]) == len(audits) == 40
    assert len({tuple(c["anchor_episode_ids"]) for c in output["cases"]}) == 40
    assert all(all(a["checks"].values()) for a in audits)
    scores = qa.score_run(output, truth)["aggregate"]
    assert not scores["missing_runs"] and not scores["escalation"]["unsafe_closures"]
    # Real clinical expectations remain fixed. Four misses escalate safely and remain visible.
    assert set(scores["failing_cases"]) <= {"P11", "P17", "P23", "P28"}
    assert scores["outcome_accuracy"] >= 0.9


@pytest.mark.parametrize("id", ["P09", "P10", "P32", "P12", "P39", "P40"])
def test_negation_history_hypothetical_and_episode_scope_never_close_as_sufficient(acceptance, id):
    truth, output, _ = acceptance
    label = next(t for t in truth if t["gt_id"] == id)
    case = next(c for c in output["cases"] if c["anchor_episode_ids"] == label["anchor_episode_ids"])
    assert case["outcome"] == "HUMAN_REVIEW_REQUIRED"
    assert case["requirement_states"][next(iter(label["expected_requirement_states"]))] == "NOT_FOUND"


def test_label_amendment_only_corrects_surfaced_context_without_changing_decision():
    old, new = qa.load_jsonl(qa.TRUTH), qa.load_jsonl(qa.AMENDED_TRUTH)
    differences = [(a["gt_id"], k) for a, b in zip(old, new, strict=True) for k in a if a[k] != b[k]]
    assert differences == [("GT-B06", "expected_exceptions")]
    assert qa.label_audit(old)["contradictions"] == [
        {"gt_id": "GT-B06", "found_but_not_labelled": ["SCHEDULED_PROCEDURE_CONTEXT"]}
    ]
    assert not qa.label_audit(new)["contradictions"]


def test_challenge_source_tables_do_not_expose_expectations(acceptance):
    _, _, audits = acceptance
    assert all(a["checks"]["prompt_has_no_label_fields"] for a in audits)
    assert qa.forbidden_keys({"episodes": [{"expected_outcome": "x"}]}) == ["expected_outcome"]


def test_challenge_build_is_byte_reproducible(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    first, second = qa.build_challenge(a), qa.build_challenge(b)
    assert first == second
    assert {p.name: p.read_bytes() for p in a.iterdir()} == {p.name: p.read_bytes() for p in b.iterdir()}
    assert json.loads((a / "manifest.json").read_text(encoding="utf-8"))["synthetic"] is True
