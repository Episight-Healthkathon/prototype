"""Allowed-action generator (architecture §7.3): the only actions any planner may choose from."""

from dataclasses import dataclass

from pydantic import BaseModel

from episight.agent.catalog import Scope, priority_order
from episight.agent.context import CaseContext
from episight.agent.reducer import MAX_TOOL_ERRORS
from episight.agent.state import InvestigationState, RequirementTracker, call_signature
from episight.agent.tools import (
    CompareDiagnosisInput,
    CompareProceduresInput,
    EpisodeHistoryInput,
    FindExceptionInput,
    FindSupportingInput,
    ProviderContextInput,
    RetrieveClinicalInput,
    RetrievePolicyInput,
)
from episight.contracts.enums import (
    InvestigationMode,
    NoteType,
    RequirementKey,
    RequirementState,
    SignalType,
    ToolName,
    ToolStatus,
)

STRUCTURAL_TOOLS = frozenset(
    {
        ToolName.GET_EPISODE_HISTORY,
        ToolName.COMPARE_DIAGNOSIS,
        ToolName.COMPARE_PROCEDURES,
        ToolName.GET_PROVIDER_CONTEXT,
    }
)
_POLICY_QUERY = {
    SignalType.READMISSION: "readmisi rawat inap berulang FKRTL diagnosis utama sama 30 hari pengecualian",
    SignalType.FRAGMENTATION: "fragmentasi rawat jalan berulang FKRTL diagnosis sama 7 hari pengecualian",
}
_EXCEPTION_TOPICS = {
    RequirementKey.EMERGENCY_CONTEXT: "EXCEPTION_EMERGENCY",
    RequirementKey.CHRONIC_CONDITION_CONTEXT: "EXCEPTION_CHRONIC",
    RequirementKey.SCHEDULED_PROCEDURE_CONTEXT: "EXCEPTION_SCHEDULED",
    RequirementKey.SUPPORTING_EXAM_FOLLOWUP_CONTEXT: "EXCEPTION_SUPPORTING_EXAM",
}


@dataclass(frozen=True)
class ScopeBounds:
    episode_ids: tuple[str, ...] = ()
    note_types_allowed: bool = False
    query_allowed: bool = False


@dataclass(frozen=True)
class AllowedAction:
    action_id: str
    requirement_key: RequirementKey
    tool_name: ToolName
    default_input: BaseModel
    bounds: ScopeBounds
    narrowing_allowed: bool


def permitted_tools(mode: InvestigationMode) -> frozenset[ToolName]:
    if mode == InvestigationMode.RULES_ONLY:
        return STRUCTURAL_TOOLS
    return frozenset(ToolName)


def _unsearched_scope(st: InvestigationState, ctx: CaseContext, req: RequirementTracker) -> list[str]:
    """Episodes in scope that still hold unread available notes; the whole scope if none are readable."""
    scope = ctx.scope_episode_ids(req.spec.scope, st.related_known)
    available, _ = st.coverage(req, ctx)
    pending = {ctx.notes[n].episode_id for n in available if n not in req.searched}
    return [e for e in scope if e in pending] or scope


def _default_input(st: InvestigationState, ctx: CaseContext, req: RequirementTracker, tool: ToolName) -> BaseModel:
    key = req.key
    if tool == ToolName.GET_EPISODE_HISTORY:
        return EpisodeHistoryInput()
    if tool == ToolName.COMPARE_DIAGNOSIS:
        return CompareDiagnosisInput(episode_ids=list(ctx.group_ids))
    if tool == ToolName.COMPARE_PROCEDURES:
        return CompareProceduresInput(
            episode_ids=list(ctx.group_ids), check_plan=key == RequirementKey.SCHEDULE_CONSISTENCY
        )
    if tool == ToolName.GET_PROVIDER_CONTEXT:
        return ProviderContextInput(provider_id=ctx.provider_id, episode_ids=list(ctx.group_ids))
    if tool == ToolName.RETRIEVE_CLINICAL_EVIDENCE:
        return RetrieveClinicalInput(episode_ids=ctx.scope_episode_ids(Scope.RELATED, st.related_known))
    if tool == ToolName.FIND_EXCEPTION_EVIDENCE:
        return FindExceptionInput(context_type=req.spec.context_type, episode_ids=_unsearched_scope(st, ctx, req))
    if tool == ToolName.FIND_SUPPORTING_EVIDENCE:
        return FindSupportingInput(signal_type=ctx.signal_type, episode_ids=_unsearched_scope(st, ctx, req))
    if tool == ToolName.RETRIEVE_POLICY:
        topics = [ctx.signal_type.value] + sorted(
            topic
            for k, topic in _EXCEPTION_TOPICS.items()
            if k in st.requirements and st.requirements[k].state == RequirementState.FOUND
        )
        return RetrievePolicyInput(signal_type=ctx.signal_type, topics=topics, query=_POLICY_QUERY[ctx.signal_type])
    raise ValueError(f"no default input for {tool}")


def _repeat_blocked(st: InvestigationState, signature: str) -> bool:
    history = st.calls.get(signature)
    if not history:
        return False
    errors = sum(s in (ToolStatus.ERROR, ToolStatus.TIMEOUT) for s in history)
    return history[-1] not in (ToolStatus.ERROR, ToolStatus.TIMEOUT) or errors >= MAX_TOOL_ERRORS


def is_repeat(st: InvestigationState, tool: ToolName, tool_input: BaseModel) -> bool:
    return _repeat_blocked(st, call_signature(tool, tool_input))


def compute_allowed(st: InvestigationState, ctx: CaseContext) -> list[AllowedAction]:
    permitted = permitted_tools(st.mode)
    order = {k: i for i, k in enumerate(priority_order(ctx.signal_type))}
    remaining = st.max_steps - st.step
    open_material = len(st.open_material())
    narrowing_allowed = remaining > open_material
    # Budget guard: when the remaining steps are only enough for the open material questions, optional
    # (non-material) questions are no longer offered, whatever the planner prefers.
    budget_tight = remaining <= open_material
    actions: list[AllowedAction] = []
    for req in sorted(st.requirements.values(), key=lambda r: order.get(r.key, 99)):
        if req.state != RequirementState.OPEN:
            continue
        if budget_tight and not req.material:
            continue
        if any(
            p in st.requirements and st.requirements[p].state == RequirementState.OPEN for p in req.spec.prerequisites
        ):
            continue
        for tool in req.spec.tools:
            if tool not in permitted:
                continue
            default = _default_input(st, ctx, req, tool)
            if is_repeat(st, tool, default):
                continue
            note_tool = req.spec.scope != Scope.NONE
            bounds = ScopeBounds(
                episode_ids=tuple(getattr(default, "episode_ids", ()) or ()),
                note_types_allowed=note_tool,
                query_allowed=tool in (ToolName.RETRIEVE_CLINICAL_EVIDENCE, ToolName.RETRIEVE_POLICY),
            )
            actions.append(
                AllowedAction(f"A{len(actions) + 1}", req.key, tool, default, bounds, narrowing_allowed and note_tool)
            )
    return actions


ALL_NOTE_TYPES = frozenset(NoteType)
