"""Builds a CaseContext from the database: the case's permission scope, nothing more."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from episight.agent.context import CaseContext, SignalPairData
from episight.contracts.data import PolicySection
from episight.db import convert
from episight.db.models import (
    CaseRow,
    ClaimRow,
    ClinicalNoteRow,
    EpisodeRow,
    IngestManifest,
    PolicySectionRow,
    ProviderRow,
)
from episight.retrieval.policy import PolicyIndex
from episight.screening.rules import RULES_BY_SIGNAL


def _policy_index(session: Session) -> PolicyIndex:
    rows = session.scalars(select(PolicySectionRow).order_by(PolicySectionRow.policy_id)).all()
    manifest = session.get(IngestManifest, "policies")
    sections = [
        PolicySection(
            policy_id=r.policy_id,
            document_title=r.document_title,
            section=r.section,
            text=r.text,
            source_ref=r.source_ref,
            source_url=r.source_url,
            version=r.version,
            effective_date=r.effective_date,
            topics=list(r.topics or []),
        )
        for r in rows
    ]
    return PolicyIndex(sections, manifest.version if manifest else None)


def load_case_context(session: Session, case: CaseRow) -> CaseContext:
    rule = RULES_BY_SIGNAL[case.signal_type]
    episodes = {
        e.episode_id: convert.to_episode(e)
        for e in session.scalars(select(EpisodeRow).where(EpisodeRow.patient_id == case.patient_id))
    }
    ids = list(episodes)
    providers = {p.provider_id: convert.to_provider(p) for p in session.scalars(select(ProviderRow))}
    claims = {
        c.episode_id: convert.to_claim(c) for c in session.scalars(select(ClaimRow).where(ClaimRow.episode_id.in_(ids)))
    }
    notes = {
        n.note_id: convert.to_note(n)
        for n in session.scalars(select(ClinicalNoteRow).where(ClinicalNoteRow.episode_id.in_(ids)))
    }
    manifest = session.get(IngestManifest, "dataset")
    details = case.signal_details
    return CaseContext(
        case_id=case.case_id,
        signal_type=case.signal_type,
        patient_id=case.patient_id,
        provider_id=case.provider_id,
        group_ids=list(case.episode_group_ids),
        pairs=[SignalPairData(p["from_episode_id"], p["to_episode_id"], p["interval_days"]) for p in details["pairs"]],
        rule_id=details["rule_id"],
        rule_version=details["rule_version"],
        rule_description=rule.description,
        threshold_days=details["params"]["threshold_days"],
        diagnosis_match=details["params"]["diagnosis_match"],
        episodes=episodes,
        providers=providers,
        claims=claims,
        notes=notes,
        policy=_policy_index(session),
        dataset_version=manifest.version if manifest else None,
    )
