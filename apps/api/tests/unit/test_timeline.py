from collections import defaultdict

from episight.episodes.timeline import build_timeline
from episight.screening.rules import screen


def _timeline(dataset, patient_id):
    case = next(c for c in screen(dataset.episodes).cases if c.patient_id == patient_id)
    notes = defaultdict(list)
    for n in dataset.notes:
        notes[n.episode_id].append(n)
    return build_timeline(
        case_id=case.case_id,
        patient_id=case.patient_id,
        episode_group_ids=case.episode_group_ids,
        threshold_days=case.rule.threshold_days,
        patient_episodes=[e for e in dataset.episodes if e.patient_id == patient_id],
        providers={p.provider_id: p for p in dataset.providers},
        claims_by_episode={c.episode_id: c for c in dataset.claims},
        notes_by_episode=notes,
    )


def test_readmission_timeline_orders_episodes_and_marks_roles(dataset):
    tl = _timeline(dataset, "PAT-000001")
    assert [(e.episode_id, e.role.value) for e in tl.episodes] == [
        ("EPI-000103", "RELATED"),
        ("EPI-000101", "ANCHOR"),
        ("EPI-000102", "ANCHOR"),
    ]
    readmission = tl.episodes[2]
    assert readmission.interval_from_previous_days == 5
    assert readmission.length_of_stay_days == 4
    assert "WITHIN_30_DAYS" in readmission.relation_reasons
    assert [d.note_type.value for d in readmission.documents] == ["TRIAGE", "DISCHARGE_SUMMARY"]
    assert readmission.primary_diagnosis.label == "Congestive heart failure"


def test_unavailable_documents_are_listed_with_their_availability(dataset):
    tl = _timeline(dataset, "PAT-000004")
    docs = {d.note_id: d.availability.value for e in tl.episodes for d in e.documents}
    assert docs == {"NOTE-000401": "AVAILABLE", "NOTE-000402": "UNAVAILABLE", "NOTE-000403": "RESTRICTED"}


def test_fragmentation_chain_timeline_has_three_anchors(dataset):
    tl = _timeline(dataset, "PAT-000002")
    assert [e.interval_from_previous_days for e in tl.episodes] == [None, 4, 3]
    assert all(e.role.value == "ANCHOR" for e in tl.episodes)
