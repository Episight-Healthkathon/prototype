"""Seed the database from a validated dataset and run screening. Idempotent: replaces previous data."""

from dataclasses import dataclass

from sqlalchemy import delete
from sqlalchemy.orm import Session

from episight.contracts.enums import ProgressStatus
from episight.db import convert
from episight.db.models import (
    BriefRow,
    CaseRow,
    ClaimRow,
    ClinicalNoteRow,
    EpisodeRow,
    EvidenceRow,
    IngestManifest,
    InvestigationActionRow,
    InvestigationRunRow,
    InvestigationStateRow,
    PatientRow,
    PlannerRecordingRow,
    PolicySectionRow,
    ProviderRow,
    ReviewActionRow,
)
from episight.ingest.loader import Dataset, PolicyCorpus
from episight.screening.rules import ScreenedCase, screen

# Children first, so foreign keys never block the wipe.
_CASE_TABLES = (
    EvidenceRow,
    ReviewActionRow,
    BriefRow,
    InvestigationActionRow,
    InvestigationStateRow,
    InvestigationRunRow,
    CaseRow,
)
_SOURCE_TABLES = (ClinicalNoteRow, ClaimRow, EpisodeRow, PatientRow, ProviderRow)


@dataclass
class SeedSummary:
    dataset_version: str
    corpus_version: str | None
    counts: dict[str, int]
    cases: int
    data_quality_issues: list[str]


def case_row(case: ScreenedCase) -> CaseRow:
    return CaseRow(
        case_id=case.case_id,
        signal_type=case.signal_type.value,
        patient_id=case.patient_id,
        provider_id=case.provider_id,
        episode_group_ids=case.episode_group_ids,
        primary_pair={
            "from_episode_id": case.primary_pair.from_episode_id,
            "to_episode_id": case.primary_pair.to_episode_id,
        },
        signal_details=case.signal_details(),
        min_interval_days=case.min_interval_days,
        index_date=case.index_date,
        progress_status=ProgressStatus.FLAGGED.value,
        outcome=None,
        stop_reason=None,
        latest_run_id=None,
        data_quality_issues=case.data_quality_issues,
    )


def seed(
    session: Session, dataset: Dataset, policies: PolicyCorpus | None, source_path: str, policy_path: str | None
) -> SeedSummary:
    version = dataset.manifest.dataset_version
    for table in _CASE_TABLES + _SOURCE_TABLES:
        session.execute(delete(table))
    session.execute(delete(PlannerRecordingRow))
    session.flush()

    session.add_all(convert.provider_row(p, version) for p in dataset.providers)
    session.add_all(convert.patient_row(p, version) for p in dataset.patients)
    session.flush()
    session.add_all(convert.episode_row(e, version) for e in dataset.episodes)
    session.flush()
    session.add_all(convert.claim_row(c, version) for c in dataset.claims)
    session.add_all(convert.note_row(n, version) for n in dataset.notes)
    session.merge(
        IngestManifest(
            kind="dataset", version=version, source_path=source_path, manifest=dataset.manifest.model_dump(mode="json")
        )
    )

    corpus_version = None
    if policies is not None:
        corpus_version = policies.manifest.corpus_version
        session.execute(delete(PolicySectionRow))
        session.add_all(convert.policy_row(s, corpus_version) for s in policies.sections)
        session.merge(
            IngestManifest(
                kind="policies",
                version=corpus_version,
                source_path=policy_path or "",
                manifest=policies.manifest.model_dump(mode="json"),
            )
        )

    result = screen(dataset.episodes)
    session.flush()
    session.add_all(case_row(c) for c in result.cases)
    session.commit()
    return SeedSummary(
        dataset_version=version,
        corpus_version=corpus_version,
        counts={
            "patients": len(dataset.patients),
            "providers": len(dataset.providers),
            "episodes": len(dataset.episodes),
            "claims": len(dataset.claims),
            "clinical_notes": len(dataset.notes),
            "policy_sections": len(policies.sections) if policies else 0,
        },
        cases=len(result.cases),
        data_quality_issues=result.data_quality_issues,
    )
