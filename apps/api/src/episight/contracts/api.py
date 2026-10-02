"""Frontend-facing DTOs — API Contract v1 §2–§4.

These models are the canonical contract. OpenAPI and the TypeScript types in
packages/shared-types are generated from them; never edit the generated files by hand.
"""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from episight.contracts.enums import (
    AdmissionType,
    Availability,
    DiagnosisMatch,
    EncounterType,
    EpisodeRole,
    ErrorCode,
    EvidenceCategory,
    ExtractionMethod,
    InvestigationMode,
    NoteType,
    Outcome,
    PlannerSource,
    ProgressStatus,
    RequirementDirection,
    RequirementKey,
    RequirementState,
    ReviewStatus,
    RunStatus,
    SignalType,
    SourceType,
    Stance,
    StopReason,
    ToolName,
    ToolStatus,
)

CONTRACT_VERSION = "1"
SIGNAL_DISCLAIMER = "A risk signal starts an investigation. It is not a finding."
HUMAN_DECISION_NOTICE = (
    "EPISIGHT does not determine fraud, approve or reject claims, or make payment decisions. The reviewer decides."
)


class _Dto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


# --- errors / health -------------------------------------------------------------------------


class ApiErrorBody(_Dto):
    code: ErrorCode
    message: str
    details: dict[str, Any] | None = None
    request_id: str


class ApiError(_Dto):
    error: ApiErrorBody


class Health(_Dto):
    status: Literal["ok", "degraded"]
    db: Literal["ok", "down"]
    policy_index: Literal["ok", "empty", "down"]
    dataset_version: str | None
    corpus_version: str | None


# --- cases -----------------------------------------------------------------------------------


class ProviderRef(_Dto):
    provider_id: str
    name: str


class CaseSummary(_Dto):
    case_id: str
    signal_type: SignalType
    patient_id: str
    provider: ProviderRef
    index_date: date
    min_interval_days: int
    episode_count: int
    progress_status: ProgressStatus
    outcome: Outcome | None
    updated_at: datetime


class CaseList(_Dto):
    items: list[CaseSummary]
    total: int
    limit: int
    offset: int


class EpisodePair(_Dto):
    from_episode_id: str
    to_episode_id: str


class SignalParams(_Dto):
    threshold_days: int
    diagnosis_match: DiagnosisMatch


class PairMatch(_Dto):
    same_patient: bool
    same_provider: bool
    same_primary_diagnosis: bool
    encounter_type: EncounterType


class SignalPair(_Dto):
    from_episode_id: str
    to_episode_id: str
    interval_days: int
    matched: PairMatch


class RiskSignal(_Dto):
    rule_id: str
    rule_version: str
    description: str
    params: SignalParams
    pairs: list[SignalPair]
    disclaimer: Literal["A risk signal starts an investigation. It is not a finding."] = SIGNAL_DISCLAIMER


class RunSummary(_Dto):
    run_id: str
    mode: InvestigationMode
    run_status: RunStatus
    step: int
    max_steps: int
    started_at: datetime
    finished_at: datetime | None
    outcome: Outcome | None
    stop_reason: StopReason | None


class RunList(_Dto):
    items: list[RunSummary]
    total: int
    limit: int
    offset: int


class CaseDetail(CaseSummary):
    episode_group_ids: list[str]
    primary_pair: EpisodePair
    signal: RiskSignal
    stop_reason: StopReason | None
    latest_run: RunSummary | None
    brief_available: bool
    data_quality_issues: list[str]


# --- episode timeline ------------------------------------------------------------------------


class CodeRef(_Dto):
    code: str
    label: str | None


class ProcedureRef(_Dto):
    code: str
    label: str | None
    performed_at: datetime | None


class TimelineProvider(_Dto):
    provider_id: str
    name: str
    hospital_class: str | None


class ClaimRef(_Dto):
    claim_id: str
    inacbg_code: str | None
    claim_status: str | None


class DocumentRef(_Dto):
    note_id: str
    note_type: NoteType
    title: str | None
    availability: Availability


class TimelineEpisode(_Dto):
    episode_id: str
    role: EpisodeRole
    encounter_type: EncounterType
    admission_type: AdmissionType | None
    provider: TimelineProvider
    start_at: datetime | None
    end_at: datetime | None
    length_of_stay_days: int | None
    interval_from_previous_days: int | None
    primary_diagnosis: CodeRef
    secondary_diagnoses: list[CodeRef]
    procedures: list[ProcedureRef]
    claim: ClaimRef | None
    documents: list[DocumentRef]
    relation_reasons: list[str]
    evidence_ids: list[str]


class EpisodeTimeline(_Dto):
    case_id: str
    patient_id: str
    episodes: list[TimelineEpisode]


# --- investigation ---------------------------------------------------------------------------


class InvestigateRequest(_Dto):
    mode: InvestigationMode = InvestigationMode.FULL
    rerun: bool = False
    max_steps: int = Field(default=12, ge=1, le=30)


class InvestigateAccepted(_Dto):
    run_id: str
    run_status: RunStatus
    poll_url: str


class Evidence(_Dto):
    evidence_id: str
    case_id: str
    run_id: str
    episode_id: str | None
    source_type: SourceType
    source_id: str
    source_title: str
    source_excerpt: str
    field_path: str | None
    char_start: int | None
    char_end: int | None
    requirement_key: RequirementKey
    stance: Stance
    relevance_category: EvidenceCategory
    exception_type: str | None
    retrieved_by_tool: ToolName
    retrieval_reason: str
    extraction_method: ExtractionMethod
    retrieved_at: datetime
    investigation_step: int
    policy_version: str | None


class EvidenceList(_Dto):
    items: list[Evidence]
    total: int
    limit: int
    offset: int


class TextHighlight(_Dto):
    char_start: int
    char_end: int


class EvidenceSource(_Dto):
    source_type: SourceType
    source_id: str
    title: str
    # CLINICAL_NOTE
    text: str | None = None
    highlight: TextHighlight | None = None
    availability: Availability | None = None
    # POLICY_SECTION
    document_title: str | None = None
    section: str | None = None
    version: str | None = None
    effective_date: date | None = None
    source_ref: str | None = None
    source_url: str | None = None
    # structured records
    field_path: str | None = None
    value: Any | None = None


class EvidenceDetail(Evidence):
    source: EvidenceSource


class Coverage(_Dto):
    in_scope_sources: int
    searched_sources: int
    unavailable_sources: int


class Requirement(_Dto):
    key: RequirementKey
    label: str
    direction: RequirementDirection
    material: bool
    state: RequirementState
    state_explanation: str
    coverage: Coverage
    evidence_ids: list[str]
    attempted_tools: list[ToolName]
    spawned_by: RequirementKey | None


class NextAction(_Dto):
    tool_name: ToolName
    tool_label: str
    requirement_key: RequirementKey
    reason: str


class RequirementUpdate(_Dto):
    key: RequirementKey
    from_state: RequirementState = Field(alias="from")
    to_state: RequirementState = Field(alias="to")


class SkippedRequirement(_Dto):
    key: RequirementKey
    reason: str


class PlannerInfo(_Dto):
    source: PlannerSource
    note: str | None
    priority_ranking: list[RequirementKey]
    skipped_requirements: list[SkippedRequirement]
    validation_errors: list[str]


class ActionError(_Dto):
    code: str
    message: str


class InvestigationAction(_Dto):
    step: int
    tool_name: ToolName
    tool_label: str
    requirement_key: RequirementKey | None
    reason: str
    input_summary: dict[str, Any]
    tool_status: ToolStatus
    evidence_ids: list[str]
    requirement_updates: list[RequirementUpdate]
    planner: PlannerInfo
    error: ActionError | None
    started_at: datetime
    duration_ms: int


class KnownFact(_Dto):
    fact_id: str
    text: str
    evidence_ids: list[str]


class UnresolvedQuestion(_Dto):
    key: RequirementKey
    question: str
    state: RequirementState


class ToolCallRef(_Dto):
    step: int
    tool_name: ToolName
    tool_status: ToolStatus


class CaseState(_Dto):
    case_id: str
    run_id: str
    signal_type: SignalType
    related_episode_ids: list[str]
    known_facts: list[KnownFact]
    supporting_risk_evidence: list[str]
    explaining_context_evidence: list[str]
    neutral_evidence: list[str]
    requirements: list[Requirement]
    missing_evidence: list[RequirementKey]
    unresolved_questions: list[UnresolvedQuestion]
    tools_called: list[ToolCallRef]
    next_action: NextAction | None
    investigation_step: int
    max_steps: int
    progress_status: ProgressStatus
    outcome: Outcome | None
    stop_reason: StopReason | None
    priority_ranking: list[RequirementKey]
    updated_at: datetime


class InvestigationView(_Dto):
    run: RunSummary
    state: CaseState
    trail: list[InvestigationAction]


# --- brief -----------------------------------------------------------------------------------


class BriefStatement(_Dto):
    statement_id: str
    text: str
    evidence_ids: list[str]
    requirement_keys: list[RequirementKey]
    material: bool


class BriefTimelineItem(_Dto):
    episode_id: str
    label: str
    start_at: datetime | None
    end_at: datetime | None
    interval_from_previous_days: int | None


class PolicyReference(_Dto):
    evidence_id: str
    policy_id: str
    document_title: str
    section: str
    version: str
    excerpt: str


class RemainingGap(_Dto):
    key: RequirementKey
    question: str
    state: RequirementState
    explanation: str


class Conflict(_Dto):
    key: RequirementKey
    affirming_evidence_ids: list[str]
    negating_evidence_ids: list[str]


class Traceability(_Dto):
    material_statements: int
    with_evidence: int


class Provenance(_Dto):
    evidence_ids: list[str]


class InvestigationBrief(_Dto):
    brief_id: str
    case_id: str
    run_id: str
    generated_at: datetime
    generator_version: str
    progress_status: ProgressStatus
    outcome: Outcome
    stop_reason: StopReason
    case_summary: list[BriefStatement]
    risk_signal: RiskSignal
    episode_timeline: list[BriefTimelineItem]
    supporting_risk_evidence: list[BriefStatement]
    explaining_context_evidence: list[BriefStatement]
    policy_references: list[PolicyReference]
    remaining_gaps: list[RemainingGap]
    conflicts: list[Conflict]
    uncertainty: list[BriefStatement]
    suggested_next_review: list[BriefStatement]
    review_status: ReviewStatus
    human_decision_notice: Literal[
        "EPISIGHT does not determine fraud, approve or reject claims, or make payment decisions. The reviewer decides."
    ] = HUMAN_DECISION_NOTICE
    traceability: Traceability
    provenance: Provenance
