from collections import defaultdict
from collections.abc import Callable
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from episight.api import views
from episight.api.errors import ApiException, not_found
from episight.contracts.api import (
    ApiError,
    CaseDetail,
    CaseList,
    EpisodeTimeline,
    EvidenceList,
    InvestigateAccepted,
    InvestigateRequest,
    InvestigationBrief,
    InvestigationView,
    RunList,
)
from episight.contracts.enums import ErrorCode, EvidenceCategory, Outcome, ProgressStatus, RequirementKey, SignalType
from episight.db import convert
from episight.db.models import (
    BriefRow,
    CaseRow,
    ClaimRow,
    ClinicalNoteRow,
    EpisodeRow,
    EvidenceRow,
    InvestigationRunRow,
    ProviderRow,
)
from episight.db.session import get_session
from episight.episodes.timeline import build_timeline
from episight.screening.rules import RULES_BY_SIGNAL
from episight.services import investigations

router = APIRouter(prefix="/cases", tags=["cases"])
SessionDep = Annotated[Session, Depends(get_session)]
_ERR = {"model": ApiError}

_SORTS = {
    "index_date": CaseRow.index_date.asc(),
    "-index_date": CaseRow.index_date.desc(),
    "min_interval_days": CaseRow.min_interval_days.asc(),
    "case_id": CaseRow.case_id.asc(),
}


def _get_case(session: Session, case_id: str) -> CaseRow:
    case = session.get(CaseRow, case_id)
    if case is None:
        raise not_found(ErrorCode.CASE_NOT_FOUND, f"Case {case_id} not found", case_id=case_id)
    return case


def _latest_run(session: Session, case: CaseRow) -> InvestigationRunRow | None:
    return session.get(InvestigationRunRow, case.latest_run_id) if case.latest_run_id else None


@router.get("", response_model=CaseList, responses={422: _ERR, 503: _ERR})
def list_cases(
    session: SessionDep,
    signal_type: SignalType | None = None,
    progress_status: Annotated[list[ProgressStatus] | None, Query()] = None,
    outcome: Annotated[list[Outcome] | None, Query()] = None,
    q: str | None = None,
    sort: Literal["index_date", "-index_date", "min_interval_days", "case_id"] = "-index_date",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CaseList:
    stmt: Select = select(CaseRow, ProviderRow).join(ProviderRow, ProviderRow.provider_id == CaseRow.provider_id)
    if signal_type:
        stmt = stmt.where(CaseRow.signal_type == signal_type.value)
    if progress_status:
        stmt = stmt.where(CaseRow.progress_status.in_([s.value for s in progress_status]))
    if outcome:
        stmt = stmt.where(CaseRow.outcome.in_([o.value for o in outcome]))
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(CaseRow.case_id.ilike(pattern), CaseRow.patient_id.ilike(pattern)))
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.execute(stmt.order_by(_SORTS[sort], CaseRow.case_id).limit(limit).offset(offset)).all()
    return CaseList(items=[views.case_summary(c, p) for c, p in rows], total=total, limit=limit, offset=offset)


@router.get("/{case_id}", response_model=CaseDetail, responses={404: _ERR, 503: _ERR})
def get_case(case_id: str, session: SessionDep) -> CaseDetail:
    case = _get_case(session, case_id)
    provider = session.get(ProviderRow, case.provider_id)
    latest = _latest_run(session, case)
    brief_available = (
        latest is not None
        and session.scalar(select(func.count()).select_from(BriefRow).where(BriefRow.run_id == latest.run_id)) > 0
    )
    return views.case_detail(case, provider, latest, brief_available)


@router.get("/{case_id}/episodes", response_model=EpisodeTimeline, responses={404: _ERR, 503: _ERR})
def get_episodes(case_id: str, session: SessionDep) -> EpisodeTimeline:
    case = _get_case(session, case_id)
    episodes = session.scalars(select(EpisodeRow).where(EpisodeRow.patient_id == case.patient_id)).all()
    episode_ids = [e.episode_id for e in episodes]
    providers = {
        p.provider_id: convert.to_provider(p)
        for p in session.scalars(
            select(ProviderRow).where(ProviderRow.provider_id.in_({e.provider_id for e in episodes}))
        )
    }
    claims = {
        c.episode_id: convert.to_claim(c)
        for c in session.scalars(select(ClaimRow).where(ClaimRow.episode_id.in_(episode_ids)))
    }
    notes: dict[str, list] = defaultdict(list)
    for n in session.scalars(select(ClinicalNoteRow).where(ClinicalNoteRow.episode_id.in_(episode_ids))):
        notes[n.episode_id].append(convert.to_note(n))
    evidence_rows = []
    if case.latest_run_id:
        evidence_rows = list(session.scalars(select(EvidenceRow).where(EvidenceRow.run_id == case.latest_run_id)))
    return build_timeline(
        case_id=case.case_id,
        patient_id=case.patient_id,
        episode_group_ids=case.episode_group_ids,
        threshold_days=RULES_BY_SIGNAL[case.signal_type].threshold_days,
        patient_episodes=[convert.to_episode(e) for e in episodes],
        providers=providers,
        claims_by_episode=claims,
        notes_by_episode=notes,
        evidence_ids_by_episode=views.evidence_ids_by_episode(evidence_rows),
    )


RunExecutor = Callable[[str], None]


def get_run_executor() -> RunExecutor:
    """Dependency so tests can point background runs at their own database."""
    return investigations.execute_run


@router.post(
    "/{case_id}/investigate",
    response_model=InvestigateAccepted,
    status_code=202,
    responses={404: _ERR, 409: _ERR, 503: _ERR},
)
def start_investigation(
    case_id: str,
    session: SessionDep,
    background: BackgroundTasks,
    executor: Annotated[RunExecutor, Depends(get_run_executor)],
    body: InvestigateRequest | None = None,
) -> InvestigateAccepted:
    case = _get_case(session, case_id)
    run = investigations.start_run(session, case, body or InvestigateRequest())
    background.add_task(executor, run.run_id)
    return InvestigateAccepted(
        run_id=run.run_id,
        run_status=run.run_status,
        poll_url=f"/api/v1/cases/{case.case_id}/investigation?run_id={run.run_id}",
    )


@router.get("/{case_id}/investigation", response_model=InvestigationView, responses={404: _ERR, 503: _ERR})
def get_investigation(case_id: str, session: SessionDep, run_id: str | None = None) -> InvestigationView:
    return investigations.get_view(session, _get_case(session, case_id), run_id)


@router.get("/{case_id}/runs", response_model=RunList, responses={404: _ERR, 503: _ERR})
def list_runs(case_id: str, session: SessionDep) -> RunList:
    runs = investigations.list_runs(session, _get_case(session, case_id))
    return RunList(items=[views.run_summary(r) for r in runs], total=len(runs), limit=len(runs), offset=0)


@router.get("/{case_id}/evidence", response_model=EvidenceList, responses={404: _ERR, 503: _ERR})
def list_evidence(
    case_id: str,
    session: SessionDep,
    category: EvidenceCategory | None = None,
    requirement_key: RequirementKey | None = None,
    run_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EvidenceList:
    case = _get_case(session, case_id)
    target_run = run_id or case.latest_run_id
    stmt = select(EvidenceRow).where(EvidenceRow.case_id == case.case_id, EvidenceRow.run_id == target_run)
    if category:
        stmt = stmt.where(EvidenceRow.relevance_category == category.value)
    if requirement_key:
        stmt = stmt.where(EvidenceRow.requirement_key == requirement_key.value)
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.scalars(
        stmt.order_by(EvidenceRow.investigation_step, EvidenceRow.evidence_id).limit(limit).offset(offset)
    )
    return EvidenceList(items=[views.evidence(r) for r in rows], total=total, limit=limit, offset=offset)


@router.get("/{case_id}/brief", response_model=InvestigationBrief, responses={404: _ERR, 409: _ERR, 503: _ERR})
def get_brief(case_id: str, session: SessionDep, run_id: str | None = None) -> InvestigationBrief:
    case = _get_case(session, case_id)
    target_run = run_id or case.latest_run_id
    brief = session.scalar(select(BriefRow).where(BriefRow.run_id == target_run)) if target_run else None
    if brief is None:
        raise ApiException(409, ErrorCode.BRIEF_NOT_READY, f"No brief available for case {case.case_id}")
    return InvestigationBrief.model_validate(brief.content)
