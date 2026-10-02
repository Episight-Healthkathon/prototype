"""Planner-proposal validator (architecture §7.4, checks V1–V9). Pure code; knows nothing about LLMs."""

import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from episight.agent.envelope.allowed import AllowedAction, is_repeat
from episight.agent.state import InvestigationState
from episight.contracts.enums import NoteType, RequirementKey, RequirementState

NO_FURTHER_USEFUL_ACTION = "NO_FURTHER_USEFUL_ACTION"


class ProposalScope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    episode_ids: list[str] | None = None
    note_types: list[NoteType] | None = None
    query: str | None = Field(default=None, max_length=200)


class ProposalSkip(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requirement_key: RequirementKey
    reason: str = Field(max_length=300)


class PlannerProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_id: str
    scope: ProposalScope | None = None
    priority_ranking: list[RequirementKey] = Field(default_factory=list)
    skip: list[ProposalSkip] = Field(default_factory=list)
    planner_note: str | None = Field(default=None, max_length=400)


@dataclass
class ValidatedDecision:
    action: AllowedAction | None  # None = accepted NO_FURTHER_USEFUL_ACTION
    tool_input: BaseModel | None
    skips: list[tuple[RequirementKey, str]]
    priority_ranking: list[RequirementKey]
    note: str | None


@dataclass
class ValidationOutcome:
    decision: ValidatedDecision | None
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.decision is not None


def validate(raw: Any, allowed: list[AllowedAction], st: InvestigationState) -> ValidationOutcome:
    # V1 — schema
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        proposal = PlannerProposal.model_validate(data)
    except (ValueError, ValidationError) as exc:
        return ValidationOutcome(None, [f"V1: response does not match the proposal schema ({str(exc)[:200]})"])

    errors: list[str] = []
    # V7 — budget
    if st.step >= st.max_steps:
        errors.append("V7: step budget exhausted")

    # V8 — skips: open, non-material requirements only
    skips: list[tuple[RequirementKey, str]] = []
    for skip in proposal.skip:
        req = st.requirements.get(skip.requirement_key)
        if req is None or req.state != RequirementState.OPEN:
            errors.append(f"V8: cannot skip {skip.requirement_key.value}: not an open requirement")
        elif req.material:
            errors.append(f"V8: cannot skip material requirement {skip.requirement_key.value}")
        else:
            skips.append((skip.requirement_key, skip.reason))

    ranking = [
        k
        for k in proposal.priority_ranking
        if k in st.requirements and st.requirements[k].state == RequirementState.OPEN
    ]

    # V9 — "no further useful action" only when nothing material is open
    if proposal.action_id == NO_FURTHER_USEFUL_ACTION:
        open_material = [r.key.value for r in st.open_material()]
        if open_material:
            errors.append(f"V9: material requirements still open: {', '.join(open_material)}")
        if errors:
            return ValidationOutcome(None, errors)
        leftover = [
            (r.key, proposal.planner_note or "planner judged no further action useful")
            for r in st.requirements.values()
            if r.state == RequirementState.OPEN and not r.material
        ]
        return ValidationOutcome(
            ValidatedDecision(
                None, None, skips + [s for s in leftover if s not in skips], ranking, proposal.planner_note
            )
        )

    # V2 — action is in this step's allowed set
    action = next((a for a in allowed if a.action_id == proposal.action_id), None)
    if action is None:
        errors.append(f"V2: action {proposal.action_id} is not in the allowed set")
        return ValidationOutcome(None, errors)

    # V3 — requirement still open; V4 — tool permitted for it
    req = st.requirements.get(action.requirement_key)
    if req is None or req.state != RequirementState.OPEN:
        errors.append(f"V3: requirement {action.requirement_key.value} is not open")
    elif action.tool_name not in req.spec.tools:
        errors.append(f"V4: tool {action.tool_name.value} cannot address {action.requirement_key.value}")
    if any(k == action.requirement_key for k, _ in skips):
        errors.append("V8: cannot skip the requirement the action addresses")

    # V5 — scope within bounds, then the tool's own input schema
    update: dict[str, Any] = {}
    scope = proposal.scope
    if scope is not None:
        if scope.episode_ids is not None:
            if not scope.episode_ids or not set(scope.episode_ids) <= set(action.bounds.episode_ids):
                errors.append("V5: episode_ids outside the action's scope bounds")
            elif set(scope.episode_ids) != set(action.bounds.episode_ids):
                if not action.narrowing_allowed:
                    errors.append("V5: narrowing the scope is not allowed with the remaining step budget")
                update["episode_ids"] = [e for e in action.bounds.episode_ids if e in set(scope.episode_ids)]
        if scope.note_types is not None:
            if not action.bounds.note_types_allowed:
                errors.append("V5: note_types not applicable to this tool")
            elif not action.narrowing_allowed:
                errors.append("V5: narrowing the scope is not allowed with the remaining step budget")
            else:
                update["note_types"] = list(scope.note_types)
        if scope.query is not None:
            if not action.bounds.query_allowed:
                errors.append("V5: query not applicable to this tool")
            else:
                update["query"] = scope.query
    tool_input = None
    try:
        merged = {**action.default_input.model_dump(mode="json"), **{k: v for k, v in update.items()}}
        tool_input = type(action.default_input).model_validate(merged)
    except ValidationError as exc:
        errors.append(f"V5: tool input invalid ({str(exc)[:200]})")

    # V6 — no repeat of an identical earlier call
    if tool_input is not None and is_repeat(st, action.tool_name, tool_input):
        errors.append("V6: duplicate of an earlier identical call")

    if errors:
        return ValidationOutcome(None, errors)
    return ValidationOutcome(ValidatedDecision(action, tool_input, skips, ranking, proposal.planner_note))
