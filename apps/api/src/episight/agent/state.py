"""Mutable investigation state (architecture §7) and its conversion to the API `CaseState`."""

import json
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel

from episight.agent.catalog import SPECS, RequirementSpec, initial_requirements, priority_order
from episight.agent.context import CaseContext
from episight.contracts.api import (
    CaseState,
    Coverage,
    Evidence,
    InvestigationAction,
    KnownFact,
    NextAction,
    Requirement,
    ToolCallRef,
    UnresolvedQuestion,
)
from episight.contracts.enums import (
    EvidenceCategory,
    InvestigationMode,
    Outcome,
    ProgressStatus,
    RequirementKey,
    RequirementState,
    StopReason,
    ToolName,
    ToolStatus,
)


@dataclass
class RequirementTracker:
    spec: RequirementSpec
    state: RequirementState = RequirementState.OPEN
    explanation: str = "Not assessed yet."
    evidence_ids: list[str] = field(default_factory=list)
    attempted_tools: list[ToolName] = field(default_factory=list)
    searched: set[str] = field(default_factory=set)
    error_count: int = 0
    spawned_by: RequirementKey | None = None

    @property
    def key(self) -> RequirementKey:
        return self.spec.key

    @property
    def material(self) -> bool:
        return self.spec.material


def call_signature(tool: ToolName, tool_input: BaseModel) -> str:
    return f"{tool.value}:{json.dumps(tool_input.model_dump(mode='json'), sort_keys=True)}"


@dataclass
class InvestigationState:
    case_id: str
    run_id: str
    mode: InvestigationMode
    max_steps: int
    signal_type: object
    requirements: dict[RequirementKey, RequirementTracker]
    started_at: datetime
    step: int = 0
    evidence: dict[str, Evidence] = field(default_factory=dict)
    surfaced_in_steps: dict[str, list[int]] = field(default_factory=dict)
    calls: dict[str, list[ToolStatus]] = field(default_factory=dict)
    trail: list[InvestigationAction] = field(default_factory=list)
    related_known: bool = False
    progress_status: ProgressStatus = ProgressStatus.INVESTIGATING
    outcome: Outcome | None = None
    stop_reason: StopReason | None = None
    priority_ranking: list[RequirementKey] = field(default_factory=list)
    next_action: NextAction | None = None
    updated_at: datetime | None = None

    @classmethod
    def new(cls, ctx: CaseContext, run_id: str, mode: InvestigationMode, max_steps: int, now: datetime):
        reqs = {s.key: RequirementTracker(spec=s) for s in initial_requirements(ctx.signal_type)}
        order = {k: i for i, k in enumerate(priority_order(ctx.signal_type))}
        reqs = dict(sorted(reqs.items(), key=lambda kv: order.get(kv[0], 99)))
        return cls(
            case_id=ctx.case_id,
            run_id=run_id,
            mode=mode,
            max_steps=max_steps,
            signal_type=ctx.signal_type,
            requirements=reqs,
            started_at=now,
            updated_at=now,
        )

    # --- queries ------------------------------------------------------------------------------

    def open_material(self) -> list[RequirementTracker]:
        return [r for r in self.requirements.values() if r.material and r.state == RequirementState.OPEN]

    def evidence_for(self, key: RequirementKey) -> list[Evidence]:
        return [e for e in self.evidence.values() if e.requirement_key == key]

    def coverage(self, req: RequirementTracker, ctx: CaseContext) -> tuple[list[str], list[str]]:
        """(available, unavailable) sources in scope for a note-reading requirement."""
        episode_ids = ctx.scope_episode_ids(req.spec.scope, self.related_known)
        return ctx.coverage_sources(episode_ids)

    def spawn(self, key: RequirementKey, parent: RequirementKey) -> RequirementTracker | None:
        if key in self.requirements:
            return None
        tracker = RequirementTracker(spec=SPECS[key], spawned_by=parent)
        items = list(self.requirements.items())
        at = next(i for i, (k, _) in enumerate(items) if k == parent) + 1
        items.insert(at, (key, tracker))
        self.requirements = dict(items)
        return tracker

    # --- API view -----------------------------------------------------------------------------

    def to_case_state(self, ctx: CaseContext) -> CaseState:
        requirements = []
        for req in self.requirements.values():
            if req.spec.scope.value != "NONE":
                available, unavailable = self.coverage(req, ctx)
                coverage = Coverage(
                    in_scope_sources=len(available) + len(unavailable),
                    searched_sources=len(req.searched & set(available)),
                    unavailable_sources=len(unavailable),
                )
            else:
                done = req.state != RequirementState.OPEN
                coverage = Coverage(in_scope_sources=1, searched_sources=int(done), unavailable_sources=0)
            requirements.append(
                Requirement(
                    key=req.key,
                    label=req.spec.label,
                    direction=req.spec.direction,
                    material=req.material,
                    state=req.state,
                    state_explanation=req.explanation,
                    coverage=coverage,
                    evidence_ids=list(req.evidence_ids),
                    attempted_tools=list(req.attempted_tools),
                    spawned_by=req.spawned_by,
                )
            )
        by_category: dict[EvidenceCategory, list[str]] = {c: [] for c in EvidenceCategory}
        for ev in self.evidence.values():
            by_category[ev.relevance_category].append(ev.evidence_id)
        facts = [
            KnownFact(fact_id=f"F-{r.key.value}", text=r.explanation, evidence_ids=list(r.evidence_ids))
            for r in self.requirements.values()
            if r.state == RequirementState.FOUND and r.evidence_ids
        ]
        return CaseState(
            case_id=self.case_id,
            run_id=self.run_id,
            signal_type=self.signal_type,
            related_episode_ids=ctx.reconstruction.related_scope_ids if self.related_known else list(ctx.group_ids),
            known_facts=facts,
            supporting_risk_evidence=by_category[EvidenceCategory.SUPPORTING_RISK],
            explaining_context_evidence=by_category[EvidenceCategory.EXPLAINING_CONTEXT],
            neutral_evidence=by_category[EvidenceCategory.NEUTRAL],
            requirements=requirements,
            missing_evidence=[
                r.key
                for r in self.requirements.values()
                if r.state in (RequirementState.UNAVAILABLE, RequirementState.FAILED)
            ],
            unresolved_questions=[
                UnresolvedQuestion(key=r.key, question=r.spec.label, state=r.state)
                for r in self.requirements.values()
                if r.state in (RequirementState.OPEN, RequirementState.CONFLICTING, RequirementState.UNAVAILABLE)
            ],
            tools_called=[
                ToolCallRef(step=a.step, tool_name=a.tool_name, tool_status=a.tool_status) for a in self.trail
            ],
            next_action=self.next_action,
            investigation_step=self.step,
            max_steps=self.max_steps,
            progress_status=self.progress_status,
            outcome=self.outcome,
            stop_reason=self.stop_reason,
            priority_ranking=list(self.priority_ranking),
            updated_at=self.updated_at or self.started_at,
        )
