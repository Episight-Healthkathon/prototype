"""Source entities delivered by Person 3 — Data Contract v1 §2–§3.

These models validate the JSONL dataset at ingest. `extra="forbid"` rejects unknown fields,
which includes the forbidden label-like fields (§1) that must never reach agent-accessible data.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from episight.contracts.enums import (
    AdmissionType,
    Availability,
    ClaimStatus,
    DischargeStatus,
    EncounterType,
    NoteType,
    ProviderType,
)

# Data Contract v1 §1: these must never appear in agent-accessible data.
FORBIDDEN_FIELDS = frozenset({"scenario", "label", "case_class", "ground_truth", "is_fraud", "is_legitimate"})
FORBIDDEN_FIELD_PREFIXES = ("expected_",)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Patient(_Strict):
    patient_id: str
    birth_year: int | None = None
    sex: Literal["M", "F"] | None = None
    chronic_conditions: list[str] = Field(default_factory=list)


class Provider(_Strict):
    provider_id: str
    name: str
    provider_type: ProviderType
    hospital_class: Literal["A", "B", "C", "D"] | None = None
    region: str | None = None


class Procedure(_Strict):
    code: str
    performed_at: datetime | None = None


class Episode(_Strict):
    episode_id: str
    patient_id: str
    provider_id: str
    encounter_type: EncounterType
    start_at: datetime | None
    end_at: datetime | None = None
    admission_type: AdmissionType | None = None
    primary_diagnosis: str
    secondary_diagnoses: list[str] = Field(default_factory=list)
    procedures: list[Procedure] = Field(default_factory=list)
    discharge_status: DischargeStatus | None = None
    class_of_care: Literal["1", "2", "3"] | None = None


class Claim(_Strict):
    claim_id: str
    episode_id: str
    submitted_at: datetime
    inacbg_code: str | None = None
    claimed_amount_idr: int | None = None
    claim_status: ClaimStatus | None = None


class ClinicalNote(_Strict):
    note_id: str
    episode_id: str
    note_type: NoteType
    title: str | None = None
    authored_at: datetime
    language: Literal["id", "en"]
    availability: Availability
    text: str | None

    @model_validator(mode="after")
    def _text_matches_availability(self) -> "ClinicalNote":
        # D-12: text must be null exactly when the document is not available.
        if (self.availability == Availability.AVAILABLE) != (self.text is not None):
            raise ValueError("text must be null iff availability is not AVAILABLE")
        return self


class PolicySection(_Strict):
    policy_id: str
    document_title: str
    section: str
    text: str
    source_ref: str
    source_url: str | None = None
    version: str
    effective_date: date | None = None
    topics: list[str] = Field(default_factory=list)


class DatasetManifest(BaseModel):
    model_config = ConfigDict(extra="allow")

    dataset_version: str
    generator_version: str | None = None
    seed: int | None = None
    generated_at: datetime | None = None
    contract_version: str
    counts: dict[str, int] = Field(default_factory=dict)


class PolicyManifest(BaseModel):
    model_config = ConfigDict(extra="allow")

    corpus_version: str
    contract_version: str
