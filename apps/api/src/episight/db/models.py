"""PostgreSQL schema — Data Contract v1 §5.

Source tables (patients … policy_sections) are written only by ingest and never updated afterwards.
Evaluation labels have no table here by design (architecture §10).
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# --- source data (ingest only) ---------------------------------------------------------------


class IngestManifest(Base):
    __tablename__ = "ingest_manifests"

    kind: Mapped[str] = mapped_column(String(16), primary_key=True)  # "dataset" | "policies"
    version: Mapped[str] = mapped_column(String(64))
    source_path: Mapped[str] = mapped_column(Text)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PatientRow(Base):
    __tablename__ = "patients"

    patient_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    birth_year: Mapped[int | None] = mapped_column(Integer)
    sex: Mapped[str | None] = mapped_column(String(1))
    chronic_conditions: Mapped[list[str]] = mapped_column(ARRAY(String(16)), default=list)
    dataset_version: Mapped[str] = mapped_column(String(64))


class ProviderRow(Base):
    __tablename__ = "providers"

    provider_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    provider_type: Mapped[str] = mapped_column(String(8))
    hospital_class: Mapped[str | None] = mapped_column(String(1))
    region: Mapped[str | None] = mapped_column(Text)
    dataset_version: Mapped[str] = mapped_column(String(64))


class EpisodeRow(Base):
    __tablename__ = "episodes"

    episode_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.patient_id"), index=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.provider_id"))
    encounter_type: Mapped[str] = mapped_column(String(16))
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    admission_type: Mapped[str | None] = mapped_column(String(16))
    primary_diagnosis: Mapped[str] = mapped_column(String(16))
    secondary_diagnoses: Mapped[list[str]] = mapped_column(ARRAY(String(16)), default=list)
    procedures: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    discharge_status: Mapped[str | None] = mapped_column(String(16))
    class_of_care: Mapped[str | None] = mapped_column(String(1))
    dataset_version: Mapped[str] = mapped_column(String(64))


class ClaimRow(Base):
    __tablename__ = "claims"

    claim_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.episode_id"), unique=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    inacbg_code: Mapped[str | None] = mapped_column(String(32))
    claimed_amount_idr: Mapped[int | None] = mapped_column(Integer)
    claim_status: Mapped[str | None] = mapped_column(String(16))
    dataset_version: Mapped[str] = mapped_column(String(64))


class ClinicalNoteRow(Base):
    __tablename__ = "clinical_notes"

    note_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.episode_id"), index=True)
    note_type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str | None] = mapped_column(Text)
    authored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    language: Mapped[str] = mapped_column(String(2))
    availability: Mapped[str] = mapped_column(String(16))
    text: Mapped[str | None] = mapped_column(Text)
    dataset_version: Mapped[str] = mapped_column(String(64))


class PolicySectionRow(Base):
    __tablename__ = "policy_sections"

    policy_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_title: Mapped[str] = mapped_column(Text)
    section: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    source_ref: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    version: Mapped[str] = mapped_column(String(64))
    effective_date: Mapped[date | None] = mapped_column(Date)
    topics: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list)
    corpus_version: Mapped[str] = mapped_column(String(64))


# --- backend-created objects ------------------------------------------------------------------


class CaseRow(Base):
    __tablename__ = "cases"

    case_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    signal_type: Mapped[str] = mapped_column(String(16), index=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.patient_id"))
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.provider_id"))
    episode_group_ids: Mapped[list[str]] = mapped_column(ARRAY(String(32)))
    primary_pair: Mapped[dict[str, str]] = mapped_column(JSONB)
    signal_details: Mapped[dict[str, Any]] = mapped_column(JSONB)
    min_interval_days: Mapped[int] = mapped_column(Integer)
    index_date: Mapped[date] = mapped_column(Date, index=True)
    progress_status: Mapped[str] = mapped_column(String(32), index=True)
    outcome: Mapped[str | None] = mapped_column(String(32))
    stop_reason: Mapped[str | None] = mapped_column(String(32))
    latest_run_id: Mapped[str | None] = mapped_column(String(40))
    data_quality_issues: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class InvestigationRunRow(Base):
    __tablename__ = "investigation_runs"

    run_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id"), index=True)
    mode: Mapped[str] = mapped_column(String(32))
    run_status: Mapped[str] = mapped_column(String(16))
    step: Mapped[int] = mapped_column(Integer, default=0)
    max_steps: Mapped[int] = mapped_column(Integer)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    dataset_version: Mapped[str | None] = mapped_column(String(64))
    corpus_version: Mapped[str | None] = mapped_column(String(64))
    code_version: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str | None] = mapped_column(String(32))
    stop_reason: Mapped[str | None] = mapped_column(String(32))
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class InvestigationStateRow(Base):
    __tablename__ = "investigation_states"
    __table_args__ = (UniqueConstraint("run_id", "step"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("investigation_runs.run_id"), index=True)
    step: Mapped[int] = mapped_column(Integer)
    state: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InvestigationActionRow(Base):
    """Append-only audit log of every investigation step."""

    __tablename__ = "investigation_actions"
    __table_args__ = (UniqueConstraint("run_id", "step"),)

    action_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("investigation_runs.run_id"), index=True)
    step: Mapped[int] = mapped_column(Integer)
    tool_name: Mapped[str] = mapped_column(String(48))
    tool_input: Mapped[dict[str, Any]] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(Text)
    requirement_key: Mapped[str | None] = mapped_column(String(48))
    tool_status: Mapped[str] = mapped_column(String(16))
    evidence_ids: Mapped[list[str]] = mapped_column(ARRAY(String(48)), default=list)
    requirement_updates: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    planner_source: Mapped[str] = mapped_column(String(16))
    planner_model: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    planner_request_hash: Mapped[str | None] = mapped_column(String(64))
    planner_note: Mapped[str | None] = mapped_column(Text)
    priority_ranking: Mapped[list[str]] = mapped_column(ARRAY(String(48)), default=list)
    skipped_requirements: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    validation_errors: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    planner_latency_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int] = mapped_column(Integer)


class EvidenceRow(Base):
    """Evidence ledger. Immutable once written; re-surfacing appends to surfaced_in_steps."""

    __tablename__ = "evidence"

    evidence_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id"), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("investigation_runs.run_id"), index=True)
    episode_id: Mapped[str | None] = mapped_column(String(32))
    source_type: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[str] = mapped_column(String(64))
    source_title: Mapped[str] = mapped_column(Text)
    field_path: Mapped[str | None] = mapped_column(Text)
    source_excerpt: Mapped[str] = mapped_column(Text)
    char_start: Mapped[int | None] = mapped_column(Integer)
    char_end: Mapped[int | None] = mapped_column(Integer)
    requirement_key: Mapped[str] = mapped_column(String(48))
    stance: Mapped[str] = mapped_column(String(16))
    relevance_category: Mapped[str] = mapped_column(String(32))
    exception_type: Mapped[str | None] = mapped_column(String(48))
    retrieved_by_tool: Mapped[str] = mapped_column(String(48))
    retrieval_reason: Mapped[str] = mapped_column(Text)
    extraction_method: Mapped[str] = mapped_column(String(32))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    investigation_step: Mapped[int] = mapped_column(Integer)
    surfaced_in_steps: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    policy_version: Mapped[str | None] = mapped_column(String(64))
    policy_effective_date: Mapped[date | None] = mapped_column(Date)


class BriefRow(Base):
    __tablename__ = "briefs"

    brief_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("investigation_runs.run_id"), unique=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id"), index=True)
    generator_version: Mapped[str] = mapped_column(String(32))
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    validation: Mapped[dict[str, Any]] = mapped_column(JSONB)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewActionRow(Base):
    __tablename__ = "review_actions"

    review_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id"), index=True)
    brief_id: Mapped[str | None] = mapped_column(ForeignKey("briefs.brief_id"))
    action: Mapped[str] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(Text)
    reviewer_label: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlannerRecordingRow(Base):
    """Record/replay store for AI planner calls (D-21)."""

    __tablename__ = "planner_recordings"

    request_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    model: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(32))
    request: Mapped[dict[str, Any]] = mapped_column(JSONB)
    response: Mapped[dict[str, Any]] = mapped_column(JSONB)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
