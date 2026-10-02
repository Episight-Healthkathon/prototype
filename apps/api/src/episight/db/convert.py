"""Conversions between ORM rows and contract data models."""

from episight.contracts.data import Claim, ClinicalNote, Episode, Patient, PolicySection, Provider
from episight.db.models import (
    ClaimRow,
    ClinicalNoteRow,
    EpisodeRow,
    PatientRow,
    PolicySectionRow,
    ProviderRow,
)


def patient_row(p: Patient, version: str) -> PatientRow:
    return PatientRow(**p.model_dump(), dataset_version=version)


def provider_row(p: Provider, version: str) -> ProviderRow:
    return ProviderRow(**p.model_dump(mode="json"), dataset_version=version)


def episode_row(e: Episode, version: str) -> EpisodeRow:
    data = e.model_dump()
    data["procedures"] = [p.model_dump(mode="json") for p in e.procedures]
    for key in ("encounter_type", "admission_type", "discharge_status"):
        data[key] = data[key].value if data[key] is not None else None
    return EpisodeRow(**data, dataset_version=version)


def claim_row(c: Claim, version: str) -> ClaimRow:
    data = c.model_dump()
    data["claim_status"] = c.claim_status.value if c.claim_status else None
    return ClaimRow(**data, dataset_version=version)


def note_row(n: ClinicalNote, version: str) -> ClinicalNoteRow:
    data = n.model_dump()
    data["note_type"] = n.note_type.value
    data["availability"] = n.availability.value
    return ClinicalNoteRow(**data, dataset_version=version)


def policy_row(s: PolicySection, version: str) -> PolicySectionRow:
    return PolicySectionRow(**s.model_dump(), corpus_version=version)


def to_provider(r: ProviderRow) -> Provider:
    return Provider(
        provider_id=r.provider_id,
        name=r.name,
        provider_type=r.provider_type,
        hospital_class=r.hospital_class,
        region=r.region,
    )


def to_episode(r: EpisodeRow) -> Episode:
    return Episode(
        episode_id=r.episode_id,
        patient_id=r.patient_id,
        provider_id=r.provider_id,
        encounter_type=r.encounter_type,
        start_at=r.start_at,
        end_at=r.end_at,
        admission_type=r.admission_type,
        primary_diagnosis=r.primary_diagnosis,
        secondary_diagnoses=list(r.secondary_diagnoses or []),
        procedures=r.procedures or [],
        discharge_status=r.discharge_status,
        class_of_care=r.class_of_care,
    )


def to_claim(r: ClaimRow) -> Claim:
    return Claim(
        claim_id=r.claim_id,
        episode_id=r.episode_id,
        submitted_at=r.submitted_at,
        inacbg_code=r.inacbg_code,
        claimed_amount_idr=r.claimed_amount_idr,
        claim_status=r.claim_status,
    )


def to_note(r: ClinicalNoteRow) -> ClinicalNote:
    return ClinicalNote(
        note_id=r.note_id,
        episode_id=r.episode_id,
        note_type=r.note_type,
        title=r.title,
        authored_at=r.authored_at,
        language=r.language,
        availability=r.availability,
        text=r.text,
    )
