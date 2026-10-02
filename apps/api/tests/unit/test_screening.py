from datetime import datetime, timedelta

from episight.contracts.data import Episode
from episight.contracts.enums import SignalType
from episight.screening.rules import make_case_id, screen

BASE = datetime.fromisoformat("2026-03-01T10:00:00+07:00")


def ep(eid, *, day, los=None, patient="P1", provider="H1", dx="I50.0", kind="INPATIENT", start=True):
    start_at = BASE + timedelta(days=day) if start else None
    end_at = start_at + timedelta(days=los) if (los is not None and start_at) else None
    return Episode(
        episode_id=eid,
        patient_id=patient,
        provider_id=provider,
        encounter_type=kind,
        start_at=start_at,
        end_at=end_at,
        primary_diagnosis=dx,
    )


def flagged(episodes):
    return [(c.signal_type, c.episode_group_ids, [p.interval_days for p in c.pairs]) for c in screen(episodes).cases]


# --- readmission (D-02: admission(ep2) - discharge(ep1) <= 30, inclusive) ---------------------------


def test_readmission_inside_threshold():
    assert flagged([ep("E1", day=0, los=4), ep("E2", day=10, los=2)]) == [(SignalType.READMISSION, ["E1", "E2"], [6])]


def test_readmission_exactly_at_threshold_is_flagged():
    assert flagged([ep("E1", day=0, los=4), ep("E2", day=34, los=2)])[0][2] == [30]


def test_readmission_outside_threshold_not_flagged():
    assert flagged([ep("E1", day=0, los=4), ep("E2", day=35, los=2)]) == []


def test_same_patient_different_provider_not_flagged():
    assert flagged([ep("E1", day=0, los=4), ep("E2", day=10, los=2, provider="H2")]) == []


def test_same_provider_different_diagnosis_not_flagged():
    assert flagged([ep("E1", day=0, los=4), ep("E2", day=10, los=2, dx="J18.9")]) == []


def test_inpatient_outpatient_mismatch_not_flagged():
    assert flagged([ep("E1", day=0, los=4), ep("E2", day=6, kind="OUTPATIENT")]) == []


def test_missing_discharge_time_is_reported_not_flagged():
    result = screen([ep("E1", day=0, los=None), ep("E2", day=10, los=2)])
    assert result.cases == []
    assert "MISSING_TIMESTAMP:E1" in result.data_quality_issues


def test_missing_start_time_is_reported_and_skipped():
    result = screen([ep("E1", day=0, los=4), ep("E2", day=0, start=False)])
    assert result.cases == []
    assert "MISSING_TIMESTAMP:E2" in result.data_quality_issues


def test_duplicate_row_is_dropped_and_reported():
    e1 = ep("E1", day=0, los=4)
    dup = e1.model_copy(update={"episode_id": "E9"})
    result = screen([e1, dup, ep("E2", day=10, los=2)])
    assert [c.episode_group_ids for c in result.cases] == [["E1", "E2"]]
    assert result.cases[0].data_quality_issues == ["DUPLICATE_EPISODE_ROW:E9"]


# --- fragmentation (visit(ep2) - visit(ep1) <= 7, inclusive) ---------------------------------------


def test_fragmentation_boundary_inclusive_and_outside():
    assert flagged([ep("V1", day=0, kind="OUTPATIENT"), ep("V2", day=7, kind="OUTPATIENT")])[0][2] == [7]
    assert flagged([ep("V1", day=0, kind="OUTPATIENT"), ep("V2", day=8, kind="OUTPATIENT")]) == []


# --- episode groups (D-03) ------------------------------------------------------------------------


def test_chain_of_three_is_one_case_with_shortest_primary_pair():
    cases = screen([ep(f"V{i}", day=d, kind="OUTPATIENT") for i, d in enumerate([0, 4, 7], start=1)]).cases
    assert len(cases) == 1
    case = cases[0]
    assert case.episode_group_ids == ["V1", "V2", "V3"]
    assert [(p.from_episode_id, p.to_episode_id, p.interval_days) for p in case.pairs] == [
        ("V1", "V2", 4),
        ("V2", "V3", 3),
    ]
    assert (case.primary_pair.from_episode_id, case.min_interval_days) == ("V2", 3)


def test_gap_splits_chain_into_separate_cases():
    days = [0, 3, 20, 24]
    cases = screen([ep(f"V{i}", day=d, kind="OUTPATIENT") for i, d in enumerate(days, start=1)]).cases
    assert [c.episode_group_ids for c in cases] == [["V1", "V2"], ["V3", "V4"]]


def test_case_id_is_deterministic_and_order_independent():
    assert make_case_id(SignalType.READMISSION, ["B", "A"]) == make_case_id(SignalType.READMISSION, ["A", "B"])
    assert make_case_id(SignalType.READMISSION, ["A", "B"]).startswith("CASE-RA-")
    eps = [ep("E1", day=0, los=4), ep("E2", day=10, los=2)]
    assert screen(eps).cases[0].case_id == screen(list(reversed(eps))).cases[0].case_id


def test_interim_dataset_flags_exactly_the_documented_groups(dataset):
    groups = {(c.signal_type.value, tuple(c.episode_group_ids)) for c in screen(dataset.episodes).cases}
    assert groups == {
        ("READMISSION", ("EPI-000101", "EPI-000102")),
        ("FRAGMENTATION", ("EPI-000201", "EPI-000202", "EPI-000203")),
        ("READMISSION", ("EPI-000301", "EPI-000302")),
        ("READMISSION", ("EPI-000401", "EPI-000402")),
        ("READMISSION", ("EPI-000501", "EPI-000502")),
        ("FRAGMENTATION", ("EPI-000801", "EPI-000802")),
    }


def test_signal_details_contain_no_verdict_language(dataset):
    for case in screen(dataset.episodes).cases:
        text = str(case.signal_details()).lower() + case.rule.description.lower()
        for word in ("fraud", "legitimate", "reject", "approve", "violation"):
            assert word not in text
