"""Investigation run lifecycle: start (with guards), background execution, recovery, and read-back.

Prototype constraint (D-20): runs execute in the API process. A restart interrupts them; on startup they are
marked FAILED / INTERRUPTED rather than silently disappearing.
"""

import logging
import secrets
import subprocess
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from episight.agent.catalog import CATALOG_VERSION
from episight.agent.orchestrator import run_investigation
from episight.agent.planners.base import Planner
from episight.agent.planners.rule_planner import RulePlanner
from episight.agent.state import InvestigationState
from episight.api import views
from episight.api.errors import ApiException, not_found
from episight.contracts.api import (
    ActionError,
    CaseState,
    InvestigateRequest,
    InvestigationAction,
    InvestigationView,
    PlannerInfo,
    RequirementUpdate,
    SkippedRequirement,
)
from episight.contracts.enums import (
    ErrorCode,
    InvestigationMode,
    PlannerSource,
    ProgressStatus,
    RunStatus,
    StopReason,
)
from episight.db.models import (
    CaseRow,
    IngestManifest,
    InvestigationActionRow,
    InvestigationRunRow,
    InvestigationStateRow,
)
from episight.db.session import make_session
from episight.services.context_loader import load_case_context
from episight.services.recorder import DbRecorder

log = logging.getLogger(__name__)
ACTIVE = (RunStatus.QUEUED.value, RunStatus.RUNNING.value)


@lru_cache
def code_version() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=2)
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def planner_for(mode: InvestigationMode) -> Planner:
    """FULL uses the AI planner when configured; until then every step is decided by the rule fallback."""
    if mode == InvestigationMode.FULL:
        from episight.llm.planner import llm_planner_or_none

        return llm_planner_or_none() or RulePlanner(source=PlannerSource.RULE_FALLBACK)
    return RulePlanner()


def new_run_id() -> str:
    return f"RUN-{datetime.now(UTC):%Y%m%d%H%M%S}-{secrets.token_hex(3).upper()}"


def start_run(session: Session, case: CaseRow, request: InvestigateRequest) -> InvestigationRunRow:
    active = session.scalar(
        select(InvestigationRunRow).where(
            InvestigationRunRow.case_id == case.case_id, InvestigationRunRow.run_status.in_(ACTIVE)
        )
    )
    if active is not None:
        raise ApiException(
            409,
            ErrorCode.INVESTIGATION_IN_PROGRESS,
            f"Investigation {active.run_id} is already running for case {case.case_id}",
            {"run_id": active.run_id},
        )
    if case.latest_run_id and not request.rerun:
        raise ApiException(
            409,
            ErrorCode.INVESTIGATION_ALREADY_COMPLETED,
            f"Case {case.case_id} already has an investigation; pass rerun=true to start a new one",
            {"run_id": case.latest_run_id},
        )
    manifests = {m.kind: m.version for m in session.scalars(select(IngestManifest))}
    run = InvestigationRunRow(
        run_id=new_run_id(),
        case_id=case.case_id,
        mode=request.mode.value,
        run_status=RunStatus.QUEUED.value,
        step=0,
        max_steps=request.max_steps,
        config={"catalog_version": CATALOG_VERSION, "max_steps": request.max_steps, "mode": request.mode.value},
        dataset_version=manifests.get("dataset"),
        corpus_version=manifests.get("policies"),
        code_version=code_version(),
        started_at=datetime.now(UTC),
    )
    session.add(run)
    case.latest_run_id = run.run_id
    case.progress_status = ProgressStatus.INVESTIGATING.value
    session.commit()
    return run


def execute_run(run_id: str, database_url: str | None = None) -> None:
    """Runs one investigation to completion. Meant for a background task; never raises."""
    session = make_session(database_url)
    try:
        run = session.get(InvestigationRunRow, run_id)
        case = session.get(CaseRow, run.case_id)
        run.run_status = RunStatus.RUNNING.value
        session.commit()
        ctx = load_case_context(session, case)
        mode = InvestigationMode(run.mode)
        run_investigation(
            ctx,
            run_id=run_id,
            planner=planner_for(mode),
            mode=mode,
            max_steps=run.max_steps,
            recorder=DbRecorder(session, run_id),
        )
    except Exception as exc:  # noqa: BLE001 — a failed run must be visible as failed, never as a conclusion
        log.exception("investigation run failed", extra={"fields": {"run_id": run_id}})
        session.rollback()
        _mark_failed(session, run_id, {"code": "RUN_FAILED", "message": str(exc)[:500]}, None)
    finally:
        session.close()


def _mark_failed(session: Session, run_id: str, error: dict, stop_reason: StopReason | None) -> None:
    run = session.get(InvestigationRunRow, run_id)
    if run is None:
        return
    run.run_status = RunStatus.FAILED.value
    run.error = error
    run.stop_reason = stop_reason.value if stop_reason else None
    run.finished_at = datetime.now(UTC)
    case = session.get(CaseRow, run.case_id)
    if case is not None and case.latest_run_id == run_id:
        case.progress_status = ProgressStatus.INVESTIGATION_FAILED.value
    session.commit()


def recover_interrupted_runs(session: Session) -> list[str]:
    stale = session.scalars(select(InvestigationRunRow).where(InvestigationRunRow.run_status.in_(ACTIVE))).all()
    ids = [r.run_id for r in stale]
    for run_id in ids:
        _mark_failed(
            session,
            run_id,
            {"code": "INTERRUPTED", "message": "API process restarted during the run"},
            StopReason.INTERRUPTED,
        )
    return ids


def _action_dto(row: InvestigationActionRow) -> InvestigationAction:
    from episight.agent.tools import TOOLS

    return InvestigationAction(
        step=row.step,
        tool_name=row.tool_name,
        tool_label=TOOLS[row.tool_name].label,
        requirement_key=row.requirement_key,
        reason=row.reason,
        input_summary=row.tool_input,
        tool_status=row.tool_status,
        evidence_ids=list(row.evidence_ids or []),
        requirement_updates=[RequirementUpdate.model_validate(u) for u in row.requirement_updates or []],
        planner=PlannerInfo(
            source=row.planner_source,
            note=row.planner_note,
            priority_ranking=list(row.priority_ranking or []),
            skipped_requirements=[SkippedRequirement.model_validate(s) for s in row.skipped_requirements or []],
            validation_errors=list(row.validation_errors or []),
        ),
        error=ActionError.model_validate(row.error) if row.error else None,
        started_at=row.started_at,
        duration_ms=row.duration_ms,
    )


def get_view(session: Session, case: CaseRow, run_id: str | None) -> InvestigationView:
    target = run_id or case.latest_run_id
    run = session.get(InvestigationRunRow, target) if target else None
    if run is None or run.case_id != case.case_id:
        raise not_found(
            ErrorCode.RUN_NOT_FOUND,
            f"No investigation run {'with id ' + run_id if run_id else 'yet'} for case {case.case_id}",
            case_id=case.case_id,
        )
    snapshot = session.scalar(
        select(InvestigationStateRow)
        .where(InvestigationStateRow.run_id == run.run_id)
        .order_by(InvestigationStateRow.step.desc(), InvestigationStateRow.id.desc())
        .limit(1)
    )
    if snapshot is None:
        # Queued but not started: show the initial state (all questions open, step 0) instead of an error.
        ctx = load_case_context(session, case)
        initial = InvestigationState.new(ctx, run.run_id, InvestigationMode(run.mode), run.max_steps, run.started_at)
        state = initial.to_case_state(ctx)
    else:
        state = CaseState.model_validate(snapshot.state)
    if run.run_status == RunStatus.FAILED.value:
        state = state.model_copy(
            update={
                "progress_status": ProgressStatus.INVESTIGATION_FAILED,
                "next_action": None,
                "stop_reason": run.stop_reason,
            }
        )
    actions = session.scalars(
        select(InvestigationActionRow)
        .where(InvestigationActionRow.run_id == run.run_id)
        .order_by(InvestigationActionRow.step)
    ).all()
    return InvestigationView(run=views.run_summary(run), state=state, trail=[_action_dto(a) for a in actions])


def list_runs(session: Session, case: CaseRow) -> list[InvestigationRunRow]:
    return list(
        session.scalars(
            select(InvestigationRunRow)
            .where(InvestigationRunRow.case_id == case.case_id)
            .order_by(InvestigationRunRow.started_at.desc())
        )
    )
