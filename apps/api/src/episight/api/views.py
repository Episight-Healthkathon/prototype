"""Row -> DTO mapping. Pure functions; used by the routers and by the fixture generator."""

from collections.abc import Mapping

from episight.contracts.api import (
    CaseDetail,
    CaseSummary,
    EpisodePair,
    Evidence,
    PairMatch,
    ProviderRef,
    RiskSignal,
    RunSummary,
    SignalPair,
    SignalParams,
)
from episight.db.models import CaseRow, EvidenceRow, InvestigationRunRow, ProviderRow
from episight.screening.rules import RULES_BY_SIGNAL


def case_summary(case: CaseRow, provider: ProviderRow) -> CaseSummary:
    return CaseSummary(
        case_id=case.case_id,
        signal_type=case.signal_type,
        patient_id=case.patient_id,
        provider=ProviderRef(provider_id=provider.provider_id, name=provider.name),
        index_date=case.index_date,
        min_interval_days=case.min_interval_days,
        episode_count=len(case.episode_group_ids),
        progress_status=case.progress_status,
        outcome=case.outcome,
        updated_at=case.updated_at,
    )


def risk_signal(case: CaseRow) -> RiskSignal:
    details = case.signal_details
    rule = RULES_BY_SIGNAL[case.signal_type]
    return RiskSignal(
        rule_id=details["rule_id"],
        rule_version=details["rule_version"],
        description=rule.description,
        params=SignalParams(**details["params"]),
        pairs=[
            SignalPair(
                from_episode_id=p["from_episode_id"],
                to_episode_id=p["to_episode_id"],
                interval_days=p["interval_days"],
                matched=PairMatch(**p["matched"]),
            )
            for p in details["pairs"]
        ],
    )


def run_summary(run: InvestigationRunRow) -> RunSummary:
    return RunSummary(
        run_id=run.run_id,
        mode=run.mode,
        run_status=run.run_status,
        step=run.step,
        max_steps=run.max_steps,
        started_at=run.started_at,
        finished_at=run.finished_at,
        outcome=run.outcome,
        stop_reason=run.stop_reason,
    )


def case_detail(
    case: CaseRow, provider: ProviderRow, latest_run: InvestigationRunRow | None, brief_available: bool
) -> CaseDetail:
    return CaseDetail(
        **case_summary(case, provider).model_dump(),
        episode_group_ids=list(case.episode_group_ids),
        primary_pair=EpisodePair(**case.primary_pair),
        signal=risk_signal(case),
        stop_reason=case.stop_reason,
        latest_run=run_summary(latest_run) if latest_run else None,
        brief_available=brief_available,
        data_quality_issues=list(case.data_quality_issues or []),
    )


def evidence(row: EvidenceRow) -> Evidence:
    return Evidence(
        evidence_id=row.evidence_id,
        case_id=row.case_id,
        run_id=row.run_id,
        episode_id=row.episode_id,
        source_type=row.source_type,
        source_id=row.source_id,
        source_title=row.source_title,
        source_excerpt=row.source_excerpt,
        field_path=row.field_path,
        char_start=row.char_start,
        char_end=row.char_end,
        requirement_key=row.requirement_key,
        stance=row.stance,
        relevance_category=row.relevance_category,
        exception_type=row.exception_type,
        retrieved_by_tool=row.retrieved_by_tool,
        retrieval_reason=row.retrieval_reason,
        extraction_method=row.extraction_method,
        retrieved_at=row.retrieved_at,
        investigation_step=row.investigation_step,
        policy_version=row.policy_version,
    )


def evidence_ids_by_episode(rows: list[EvidenceRow]) -> Mapping[str, list[str]]:
    out: dict[str, list[str]] = {}
    for r in rows:
        if r.episode_id:
            out.setdefault(r.episode_id, []).append(r.evidence_id)
    return out
