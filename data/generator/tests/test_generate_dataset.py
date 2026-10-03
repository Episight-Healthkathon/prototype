"""Generator guarantees: determinism, golden stability, contract hygiene, ground-truth consistency."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import generate_dataset as gen

FORBIDDEN = {"scenario", "label", "case_class", "ground_truth", "is_fraud", "is_legitimate"}


def _read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    root = tmp_path_factory.mktemp("data")
    return gen.write_all(root, "vtest", gen.DEFAULT_SEED, 12)


def test_same_seed_is_byte_identical(tmp_path):
    a = gen.write_all(tmp_path / "a", "v", 123, 12)
    b = gen.write_all(tmp_path / "b", "v", 123, 12)
    for key in a:
        for f in sorted(a[key].iterdir()):
            assert f.read_bytes() == (b[key] / f.name).read_bytes(), f"{key}/{f.name} differs"


def test_golden_cases_do_not_depend_on_seed():
    b1, b2 = gen.build(1, 5), gen.build(999, 40)
    golden = lambda b: [t.row() for t in b.truth if t.golden_case]
    assert golden(b1) == golden(b2)
    ids = {e for t in b1.truth if t.golden_case for e in t.expected_related_episode_ids}
    eps = lambda b: [e for e in b.episodes if e["episode_id"] in ids]
    assert eps(b1) == eps(b2)


def test_seed_changes_benchmark_cases():
    b1, b2 = gen.build(1, 0), gen.build(2, 0)
    assert b1.episodes != b2.episodes


def test_five_golden_cases_and_twenty_plus_benchmark_rows(out):
    gt = _read(out["ground_truth"] / "cases.jsonl")
    assert sorted(t["golden_case"] for t in gt if t["golden_case"]) == ["A", "B", "C", "D", "E"]
    assert len(gt) >= 20
    assert any(t["expected_signal_type"] is None for t in gt)
    assert len({t["gt_id"] for t in gt}) == len(gt)


def test_no_label_fields_in_agent_readable_data(out):
    for f in out["dataset"].glob("*.jsonl"):
        for row in _read(f):
            bad = {k for k in row if k in FORBIDDEN or k.startswith("expected_")}
            assert not bad, f"{f.name}: {bad}"
            for value in row.values():
                if isinstance(value, str):
                    assert "ground_truth" not in value and "GT-" not in value


def test_ground_truth_is_outside_the_dataset_dir(out):
    assert "ground-truth" not in str(out["dataset"])
    assert not any("ground" in p.name for p in out["dataset"].iterdir())


def test_referential_integrity(out):
    d = out["dataset"]
    patients = {r["patient_id"] for r in _read(d / "patients.jsonl")}
    providers = {r["provider_id"] for r in _read(d / "providers.jsonl")}
    episodes = _read(d / "episodes.jsonl")
    eids = [e["episode_id"] for e in episodes]
    assert len(eids) == len(set(eids))
    for e in episodes:
        assert e["patient_id"] in patients and e["provider_id"] in providers
    claims = _read(d / "claims.jsonl")
    assert sorted(c["episode_id"] for c in claims) == sorted(eids)
    notes = _read(d / "clinical_notes.jsonl")
    for n in notes:
        assert n["episode_id"] in set(eids)
        assert (n["text"] is None) == (n["availability"] != "AVAILABLE")


def test_ground_truth_references_resolve(out):
    d = out["dataset"]
    eids = {e["episode_id"] for e in _read(d / "episodes.jsonl")}
    nids = {n["note_id"] for n in _read(d / "clinical_notes.jsonl")}
    pids = {p["policy_id"] for p in _read(out["policies"] / "policy_sections.jsonl")}
    resolvers = {"CLINICAL_NOTE": nids, "EPISODE_RECORD": eids, "POLICY_SECTION": pids}
    for t in _read(out["ground_truth"] / "cases.jsonl"):
        assert set(t["anchor_episode_ids"]) <= eids, t["gt_id"]
        assert set(t["anchor_episode_ids"]) <= set(t["expected_related_episode_ids"]), t["gt_id"]
        for item in t["expected_evidence"]:
            assert item["source_id"] in resolvers[item["source_type"]], (t["gt_id"], item)


def test_inpatient_episodes_register_a_discharge_summary_unless_by_design(out):
    d = out["dataset"]
    with_ds = {n["episode_id"] for n in _read(d / "clinical_notes.jsonl") if n["note_type"] == "DISCHARGE_SUMMARY"}
    missing = [e["episode_id"] for e in _read(d / "episodes.jsonl")
               if e["encounter_type"] == "INPATIENT" and e["episode_id"] not in with_ds]
    # GT-B08: the repeat episode's summary is missing on purpose; GT-N05: the duplicate row is a data error.
    by_design = {a for t in _read(out["ground_truth"] / "cases.jsonl") if t["gt_id"] in ("GT-B08", "GT-N05")
                 for a in t["anchor_episode_ids"][1:]}
    assert set(missing) == by_design


def test_manifest_hashes_match_files(out):
    import hashlib

    manifest = json.loads((out["dataset"] / "manifest.json").read_text(encoding="utf-8"))
    for name, digest in manifest["files"].items():
        assert digest == "sha256:" + hashlib.sha256((out["dataset"] / name).read_bytes()).hexdigest()


def test_policy_sections_carry_topics_and_source(out):
    rows = _read(out["policies"] / "policy_sections.jsonl")
    topics = {t for r in rows for t in r["topics"]}
    assert {"READMISSION", "FRAGMENTATION", "EXCEPTION_EMERGENCY", "EXCEPTION_CHRONIC", "EXCEPTION_SCHEDULED",
            "EXCEPTION_SUPPORTING_EXAM"} <= topics
    assert all(r["source_ref"] and r["version"] and "INTERIM" not in r["policy_id"] for r in rows)
