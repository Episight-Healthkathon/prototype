"""Batch runner (M8): Data Contract §6 output, all modes, reproducibility, record/replay. No network."""

import csv
import json

import pytest
from typer.testing import CliRunner

from episight.batch import ALL_MODES, PlannerInfo, run_batch
from episight.cli import app
from episight.contracts.enums import InvestigationMode
from episight.llm.planner import LlmPlanner
from episight.llm.recording import JsonDirStore
from tests.conftest import DATASET_DIR, POLICY_DIR
from tests.unit.test_llm_planner import ScriptedClient, adaptive_policy

RULE_MODES = [m for m in ALL_MODES if m != InvestigationMode.FULL]
CASE_KEYS = {
    "case_id",
    "run_index",
    "signal_type",
    "anchor_episode_ids",
    "reconstructed_episode_ids",
    "evidence",
    "requirement_states",
    "outcome",
    "stop_reason",
    "tool_call_count",
    "step_count",
    "tool_failures",
    "elapsed_ms",
    "planner",
    "brief",
    "brief_traceability",
    "brief_validation",
}


@pytest.fixture(scope="module")
def rule_batch(tmp_path_factory):
    out = tmp_path_factory.mktemp("batch")
    run_batch(DATASET_DIR, POLICY_DIR, out, RULE_MODES)
    return out


def load(out, mode):
    return json.loads((out / f"{mode.value}.json").read_text(encoding="utf-8"))


def test_output_files_per_mode_and_summary(rule_batch):
    for mode in RULE_MODES:
        assert (rule_batch / f"{mode.value}.json").exists() and (rule_batch / f"{mode.value}.csv").exists()
    summary = (rule_batch / "summary.md").read_text(encoding="utf-8")
    assert all(m.value in summary for m in RULE_MODES)


def test_runner_output_matches_data_contract_section_6(rule_batch):
    doc = load(rule_batch, InvestigationMode.FULL_RULE_PLANNER)
    header = doc["header"]
    assert header["runner_version"] == "1" and header["mode"] == "FULL_RULE_PLANNER"
    assert header["dataset_version"] == "v0-interim" and header["corpus_version"] == "pc-0-interim"
    assert header["config_hash"] and header["config"]["max_steps"] == 12
    assert len(doc["cases"]) == 6
    for case in doc["cases"]:
        assert set(case) == CASE_KEYS
        assert case["anchor_episode_ids"] == sorted(case["anchor_episode_ids"])
        assert set(case["anchor_episode_ids"]) <= set(case["reconstructed_episode_ids"])
        assert all(
            {"source_type", "source_id", "requirement_key", "stance", "relevance_category"} <= set(e)
            for e in case["evidence"]
        )
        assert case["brief_validation"]["passed"]
    assert sorted(map(tuple, doc["screening"]["flagged_anchor_sets"])) == sorted(
        tuple(c["anchor_episode_ids"]) for c in doc["cases"]
    )


def test_golden_outcomes_in_the_batch(rule_batch):
    by_patient_episode = {
        c["anchor_episode_ids"][0]: c for c in load(rule_batch, InvestigationMode.FULL_RULE_PLANNER)["cases"]
    }
    assert by_patient_episode["EPI-000101"]["outcome"] == "EVIDENCE_SUFFICIENT"
    assert by_patient_episode["EPI-000201"]["stop_reason"] == "EVIDENCE_PATHS_EXHAUSTED"
    assert by_patient_episode["EPI-000401"]["outcome"] == "EVIDENCE_UNAVAILABLE"
    assert by_patient_episode["EPI-000501"]["outcome"] == "EVIDENCE_CONFLICTING"


def test_ablation_modes_behave_differently(rule_batch):
    rules_only = load(rule_batch, InvestigationMode.RULES_ONLY)["cases"]
    assert {c["stop_reason"] for c in rules_only} == {"NO_ACTIONABLE_GAP"}
    assert all(not any(e["source_type"] == "CLINICAL_NOTE" for e in c["evidence"]) for c in rules_only)
    retrieval = {c["case_id"]: c["step_count"] for c in load(rule_batch, InvestigationMode.RULES_RETRIEVAL)["cases"]}
    full_rule = {c["case_id"]: c["step_count"] for c in load(rule_batch, InvestigationMode.FULL_RULE_PLANNER)["cases"]}
    assert any(retrieval[k] > full_rule[k] for k in full_rule)  # adaptive stopping saves steps somewhere


def test_batch_is_reproducible_apart_from_timings(rule_batch, tmp_path):
    run_batch(DATASET_DIR, POLICY_DIR, tmp_path, [InvestigationMode.FULL_RULE_PLANNER])

    def stable(doc):
        return [{k: v for k, v in c.items() if k not in ("elapsed_ms", "brief")} for c in doc["cases"]]

    assert stable(load(tmp_path, InvestigationMode.FULL_RULE_PLANNER)) == stable(
        load(rule_batch, InvestigationMode.FULL_RULE_PLANNER)
    )


def test_csv_has_one_row_per_case(rule_batch):
    with (rule_batch / "FULL_RULE_PLANNER.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 6 and all(r["traceability"].split("/")[0] == r["traceability"].split("/")[1] for r in rows)


def test_full_mode_records_then_replays_with_repeats(tmp_path):
    def factory_for(replay):
        def factory(mode, repeat):
            store = JsonDirStore(tmp_path / "rec" / f"rep-{repeat}")
            client = ScriptedClient(adaptive_policy if not replay else (lambda p, r: pytest.fail("model called")))
            return LlmPlanner(client, store, replay=replay)

        return factory

    info = PlannerInfo("fake", "fake-model-1", "planner-2")
    run_batch(
        DATASET_DIR,
        POLICY_DIR,
        tmp_path / "live",
        [InvestigationMode.FULL],
        repeats=2,
        planner_factory=factory_for(False),
        planner_info=info,
    )
    run_batch(
        DATASET_DIR,
        POLICY_DIR,
        tmp_path / "replay",
        [InvestigationMode.FULL],
        repeats=2,
        planner_factory=factory_for(True),
        planner_info=info,
    )
    live, replay = load(tmp_path / "live", InvestigationMode.FULL), load(tmp_path / "replay", InvestigationMode.FULL)
    assert len(live["cases"]) == 12 and {c["run_index"] for c in live["cases"]} == {0, 1}
    assert all(c["planner"]["llm_steps"] > 0 and c["planner"]["fallback_steps"] == 0 for c in live["cases"])
    strip = lambda d: [(c["case_id"], c["run_index"], c["outcome"], c["step_count"]) for c in d["cases"]]  # noqa: E731
    assert strip(live) == strip(replay)
    assert live["header"]["config"]["planner"] == {
        "provider": "fake",
        "model": "fake-model-1",
        "prompt_version": "planner-2",
    }


def test_full_mode_without_an_llm_uses_the_rule_fallback(tmp_path):
    run_batch(DATASET_DIR, POLICY_DIR, tmp_path, [InvestigationMode.FULL], case_ids=None)
    doc = load(tmp_path, InvestigationMode.FULL)
    assert doc["header"]["config"]["planner"]["provider"] == "none"
    assert all(c["planner"]["fallback_steps"] == c["step_count"] for c in doc["cases"])


def test_case_filter_and_unknown_case(tmp_path):
    first = load_first_case_id()
    run_batch(DATASET_DIR, POLICY_DIR, tmp_path, [InvestigationMode.RULES_ONLY], case_ids=[first])
    assert [c["case_id"] for c in load(tmp_path, InvestigationMode.RULES_ONLY)["cases"]] == [first]
    with pytest.raises(ValueError, match="unknown case"):
        run_batch(DATASET_DIR, POLICY_DIR, tmp_path, [InvestigationMode.RULES_ONLY], case_ids=["CASE-RA-nope"])


def load_first_case_id():
    from episight.agent.loading import contexts_from_dataset
    from episight.ingest.loader import load_dataset

    return contexts_from_dataset(load_dataset(DATASET_DIR), None)[0].case_id


def test_cli_batch_command(tmp_path):
    result = CliRunner().invoke(
        app, ["batch", "--out", str(tmp_path), "--mode", "RULES_ONLY", "--mode", "FULL_RULE_PLANNER"]
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "RULES_ONLY.json").exists() and (tmp_path / "FULL_RULE_PLANNER.json").exists()


def test_batch_source_never_mentions_labels():
    from pathlib import Path

    import episight.batch as batch

    text = Path(batch.__file__).read_text(encoding="utf-8").lower()
    assert "ground_truth" not in text and "ground-truth" not in text and "expected_" not in text
