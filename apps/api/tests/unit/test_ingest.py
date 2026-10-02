import json
import shutil

import pytest

from episight.ingest.loader import IngestError, load_dataset, load_policies
from tests.conftest import DATASET_DIR, POLICY_DIR


@pytest.fixture
def dataset_copy(tmp_path):
    target = tmp_path / "ds"
    shutil.copytree(DATASET_DIR, target)
    return target


def _append(path, row):
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def test_interim_dataset_and_policies_load(dataset):
    assert dataset.manifest.dataset_version == "v0-interim"
    assert len(dataset.episodes) == 24
    assert len(load_policies(POLICY_DIR).sections) == 2


def test_forbidden_label_field_is_rejected(dataset_copy):
    _append(dataset_copy / "patients.jsonl", {"patient_id": "PAT-X", "scenario": "LEGIT_READMISSION"})
    with pytest.raises(IngestError, match="forbidden label-like field"):
        load_dataset(dataset_copy)


def test_expected_prefixed_field_is_rejected(dataset_copy):
    _append(dataset_copy / "patients.jsonl", {"patient_id": "PAT-X", "expected_outcome": "X"})
    with pytest.raises(IngestError, match="forbidden"):
        load_dataset(dataset_copy)


def test_unknown_field_is_rejected(dataset_copy):
    _append(
        dataset_copy / "providers.jsonl",
        {"provider_id": "PRV-X", "name": "x", "provider_type": "FKRTL", "colour": "red"},
    )
    with pytest.raises(IngestError, match="colour"):
        load_dataset(dataset_copy)


def test_note_text_must_be_null_when_unavailable(dataset_copy):
    _append(
        dataset_copy / "clinical_notes.jsonl",
        {
            "note_id": "NOTE-X",
            "episode_id": "EPI-000101",
            "note_type": "TRIAGE",
            "authored_at": "2026-03-03T10:00:00+07:00",
            "language": "id",
            "availability": "UNAVAILABLE",
            "text": "should not be here",
        },
    )
    with pytest.raises(IngestError, match="text must be null"):
        load_dataset(dataset_copy)


def test_unknown_foreign_key_is_rejected(dataset_copy):
    _append(
        dataset_copy / "claims.jsonl",
        {"claim_id": "CLM-X", "episode_id": "EPI-NOPE", "submitted_at": "2026-03-03T10:00:00+07:00"},
    )
    with pytest.raises(IngestError, match="unknown episode_id EPI-NOPE"):
        load_dataset(dataset_copy)


def test_conflicting_duplicate_id_is_rejected(dataset_copy):
    _append(dataset_copy / "providers.jsonl", {"provider_id": "PRV-0001", "name": "Other", "provider_type": "FKRTL"})
    with pytest.raises(IngestError, match="duplicate provider_id PRV-0001"):
        load_dataset(dataset_copy)


def test_ground_truth_location_is_refused(tmp_path):
    target = tmp_path / "data" / "ground-truth" / "v1"
    shutil.copytree(DATASET_DIR, target)
    with pytest.raises(IngestError, match="ground-truth"):
        load_dataset(target)


def test_all_problems_are_reported_together(dataset_copy):
    _append(dataset_copy / "patients.jsonl", {"patient_id": "PAT-X", "label": "x"})
    _append(
        dataset_copy / "claims.jsonl",
        {"claim_id": "CLM-X", "episode_id": "EPI-NOPE", "submitted_at": "2026-03-03T10:00:00+07:00"},
    )
    with pytest.raises(IngestError) as info:
        load_dataset(dataset_copy)
    assert len(info.value.problems) == 2
