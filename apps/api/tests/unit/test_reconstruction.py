from datetime import datetime, timedelta

from episight.contracts.data import Episode
from episight.contracts.enums import EpisodeRole
from episight.episodes.reconstruction import is_chronic_class, reconstruct

BASE = datetime.fromisoformat("2026-03-01T10:00:00+07:00")


def ep(eid, day, *, dx="I50.0", provider="H1", kind="INPATIENT", los=3):
    start = BASE + timedelta(days=day)
    end = start + timedelta(days=los) if kind == "INPATIENT" else None
    return Episode(
        episode_id=eid,
        patient_id="P1",
        provider_id=provider,
        encounter_type=kind,
        start_at=start,
        end_at=end,
        primary_diagnosis=dx,
    )


def test_two_related_episodes_are_anchors():
    rec = reconstruct(["E1", "E2"], [ep("E1", 0), ep("E2", 10)], 30)
    assert rec.anchor_ids == ["E1", "E2"] and rec.related_ids == [] and rec.context_ids == []


def test_three_anchor_chain_and_out_of_order_input():
    rec = reconstruct(["E3", "E1", "E2"], [ep("E3", 20), ep("E1", 0), ep("E2", 10)], 30)
    assert rec.anchor_ids == ["E1", "E2", "E3"]
    assert rec.reasons["E1"] == ["INDEX_EPISODE"]
    assert "WITHIN_30_DAYS" in rec.reasons["E3"]


def test_same_diagnosis_at_other_provider_is_related_not_anchor():
    rec = reconstruct(["E1", "E2"], [ep("E1", 0), ep("E2", 10), ep("X", 15, provider="H2")], 30)
    assert rec.roles["X"] == EpisodeRole.RELATED
    assert "SAME_PROVIDER" not in rec.reasons["X"]


def test_same_icd10_category_is_related():
    rec = reconstruct(["E1", "E2"], [ep("E1", 0), ep("E2", 10), ep("X", -20, dx="I50.9", kind="OUTPATIENT")], 30)
    assert rec.roles["X"] == EpisodeRole.RELATED and "SAME_DIAGNOSIS_CATEGORY" in rec.reasons["X"]


def test_similar_but_unrelated_episode_is_context_only():
    rec = reconstruct(["E1", "E2"], [ep("E1", 0), ep("E2", 10), ep("X", 12, dx="J18.9")], 30)
    assert rec.roles["X"] == EpisodeRole.CONTEXT
    assert "X" not in rec.related_scope_ids


def test_episodes_outside_the_window_are_ignored():
    rec = reconstruct(["E1", "E2"], [ep("E1", 0), ep("E2", 10), ep("OLD", -200)], 30)
    assert "OLD" not in rec.roles


def test_chronic_class_codes():
    assert is_chronic_class("I50.0") and is_chronic_class("E11.9")
    assert not is_chronic_class("J18.9")
