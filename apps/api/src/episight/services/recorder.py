"""Persists every investigation state change, so the UI can poll progress step by step (architecture §8)."""

from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.orm import Session

from episight.agent.context import CaseContext
from episight.agent.planners.base import Decision
from episight.agent.state import InvestigationState
from episight.brief.validator import BriefValidation
from episight.contracts.api import Evidence, InvestigationAction, InvestigationBrief
from episight.contracts.enums import ProgressStatus, RunStatus
from episight.db.models import (
    BriefRow,
    CaseRow,
    EvidenceRow,
    InvestigationActionRow,
    InvestigationRunRow,
    InvestigationStateRow,
)


class DbRecorder:
    def __init__(self, session: Session, run_id: str):
        self.session = session
        self.run_id = run_id
        self._persisted_surfaced: dict[str, int] = {}

    def _snapshot(self, st: InvestigationState, ctx: CaseContext) -> None:
        self.session.execute(
            delete(InvestigationStateRow).where(
                InvestigationStateRow.run_id == self.run_id, InvestigationStateRow.step == st.step
            )
        )
        self.session.add(
            InvestigationStateRow(
                run_id=self.run_id, step=st.step, state=st.to_case_state(ctx).model_dump(mode="json", by_alias=True)
            )
        )
        run = self.session.get(InvestigationRunRow, self.run_id)
        run.step = st.step

    def on_state(self, st: InvestigationState, ctx: CaseContext) -> None:
        self._snapshot(st, ctx)
        self.session.commit()

    def on_step(
        self,
        st: InvestigationState,
        ctx: CaseContext,
        action: InvestigationAction,
        new_evidence: list[Evidence],
        decision: Decision,
    ) -> None:
        for ev in new_evidence:
            section = ctx.policy.get(ev.source_id) if ev.policy_version else None
            self.session.add(
                EvidenceRow(
                    **ev.model_dump(
                        exclude={
                            "requirement_key",
                            "stance",
                            "relevance_category",
                            "source_type",
                            "retrieved_by_tool",
                            "extraction_method",
                        }
                    ),
                    source_type=ev.source_type.value,
                    requirement_key=ev.requirement_key.value,
                    stance=ev.stance.value,
                    relevance_category=ev.relevance_category.value,
                    retrieved_by_tool=ev.retrieved_by_tool.value,
                    extraction_method=ev.extraction_method.value,
                    surfaced_in_steps=list(st.surfaced_in_steps[ev.evidence_id]),
                    policy_effective_date=section.effective_date if section else None,
                )
            )
            self._persisted_surfaced[ev.evidence_id] = len(st.surfaced_in_steps[ev.evidence_id])
        for evidence_id, steps in st.surfaced_in_steps.items():
            if self._persisted_surfaced.get(evidence_id, len(steps)) != len(steps):
                self.session.flush()
                self.session.get(EvidenceRow, evidence_id).surfaced_in_steps = list(steps)
                self._persisted_surfaced[evidence_id] = len(steps)

        self.session.add(
            InvestigationActionRow(
                action_id=f"{self.run_id}-S{action.step:02d}",
                run_id=self.run_id,
                step=action.step,
                tool_name=action.tool_name.value,
                tool_input=action.input_summary,
                reason=action.reason,
                requirement_key=action.requirement_key.value if action.requirement_key else None,
                tool_status=action.tool_status.value,
                evidence_ids=action.evidence_ids,
                requirement_updates=[u.model_dump(mode="json", by_alias=True) for u in action.requirement_updates],
                planner_source=action.planner.source.value,
                planner_model=decision.model,
                prompt_version=decision.prompt_version,
                planner_request_hash=decision.request_hash,
                planner_note=action.planner.note,
                priority_ranking=[k.value for k in action.planner.priority_ranking],
                skipped_requirements=[s.model_dump(mode="json") for s in action.planner.skipped_requirements],
                validation_errors=list(action.planner.validation_errors),
                planner_latency_ms=decision.latency_ms,
                error=action.error.model_dump() if action.error else None,
                started_at=action.started_at,
                duration_ms=action.duration_ms,
            )
        )
        self._snapshot(st, ctx)
        self.session.commit()

    def on_finish(
        self, st: InvestigationState, ctx: CaseContext, brief: InvestigationBrief, validation: BriefValidation
    ) -> None:
        self._snapshot(st, ctx)
        self.session.add(
            BriefRow(
                brief_id=brief.brief_id,
                run_id=self.run_id,
                case_id=st.case_id,
                generator_version=brief.generator_version,
                content=brief.model_dump(mode="json", by_alias=True),
                validation={"passed": validation.passed, "violations": validation.violations},
            )
        )
        run = self.session.get(InvestigationRunRow, self.run_id)
        run.run_status = RunStatus.COMPLETED.value
        run.outcome = brief.outcome.value
        run.stop_reason = brief.stop_reason.value
        run.finished_at = datetime.now(UTC)
        case = self.session.get(CaseRow, st.case_id)
        if case.latest_run_id == self.run_id:
            case.progress_status = ProgressStatus.BRIEF_READY.value
            case.outcome = brief.outcome.value
            case.stop_reason = brief.stop_reason.value
        self.session.commit()
