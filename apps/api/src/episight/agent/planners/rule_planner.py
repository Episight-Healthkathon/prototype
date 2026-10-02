"""Deterministic rule planner: the fallback for the AI planner and the planner for rule-based modes."""

from episight.agent.context import CaseContext
from episight.agent.envelope.allowed import AllowedAction
from episight.agent.planners.base import Decision
from episight.agent.state import InvestigationState
from episight.contracts.enums import InvestigationMode, PlannerSource, RequirementKey, RequirementState


def provider_context_skip_reason(ctx: CaseContext) -> str | None:
    """Provider context is not material when all anchors share provider, class of care, and nobody was referred."""
    eps = [ctx.episodes[i] for i in ctx.group_ids]
    if len({e.provider_id for e in eps}) != 1 or len({e.class_of_care for e in eps}) != 1:
        return None
    if any(e.discharge_status and e.discharge_status.value == "REFERRED" for e in eps):
        return None
    return "same provider and class of care across episodes, no referral"


class RulePlanner:
    def __init__(self, source: PlannerSource = PlannerSource.RULE):
        self.source = source

    def decide(
        self,
        st: InvestigationState,
        ctx: CaseContext,
        allowed: list[AllowedAction],
        validation_errors: list[str] | None = None,
    ) -> Decision:
        skips: list[tuple[RequirementKey, str]] = []
        provider = st.requirements.get(RequirementKey.PROVIDER_CONTEXT)
        adaptive = st.mode in (InvestigationMode.FULL, InvestigationMode.FULL_RULE_PLANNER)
        if adaptive and provider is not None and provider.state == RequirementState.OPEN:
            reason = provider_context_skip_reason(ctx)
            if reason:
                skips.append((RequirementKey.PROVIDER_CONTEXT, reason))
        skipped = {k for k, _ in skips}
        candidates = [a for a in allowed if a.requirement_key not in skipped]
        ranking = list(dict.fromkeys(a.requirement_key for a in candidates))
        action = candidates[0] if candidates else None
        return Decision(
            action=action,
            tool_input=action.default_input if action else None,
            source=self.source,
            skips=skips,
            priority_ranking=ranking[:5],
            validation_errors=validation_errors or [],
        )
