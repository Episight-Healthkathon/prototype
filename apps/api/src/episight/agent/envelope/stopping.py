"""Stopping policy S1–S8 (architecture §7.6). Ordered; the first matching rule wins."""

from episight.agent.catalog import SPAWNS
from episight.agent.state import InvestigationState
from episight.contracts.enums import InvestigationMode, Outcome, RequirementState, StopReason

S = RequirementState


def evaluate(
    st: InvestigationState, allowed_count: int, elapsed_s: float, timeout_s: float
) -> tuple[Outcome, StopReason] | None:
    material = [r for r in st.requirements.values() if r.material]
    # The non-adaptive baseline runs every available action before judging the evidence.
    adaptive = st.mode != InvestigationMode.RULES_RETRIEVAL
    if not adaptive and allowed_count and st.step < st.max_steps and elapsed_s <= timeout_s:
        return None

    if any(r.state == S.CONFLICTING for r in material):  # S1
        return Outcome.EVIDENCE_CONFLICTING, StopReason.CONFLICTING_EVIDENCE
    if elapsed_s > timeout_s:  # S2
        return Outcome.HUMAN_REVIEW_REQUIRED, StopReason.TIMEOUT
    if any(r.state == S.FAILED for r in material):  # S3
        return Outcome.HUMAN_REVIEW_REQUIRED, StopReason.TOOL_FAILURE

    open_material = [r for r in material if r.state == S.OPEN]
    if not open_material:
        context = [r for r in material if r.spec.is_explaining_context]
        if any(r.state == S.UNAVAILABLE for r in context):  # S4
            return Outcome.EVIDENCE_UNAVAILABLE, StopReason.REQUIRED_EVIDENCE_UNAVAILABLE

        def checks_found(parent) -> bool:
            children = [st.requirements[c] for c in SPAWNS.get(parent.key, ()) if c in st.requirements]
            return all(c.state == S.FOUND for c in children)

        if any(r.state == S.FOUND and checks_found(r) for r in context):  # S5
            return Outcome.EVIDENCE_SUFFICIENT, StopReason.SUFFICIENT_EVIDENCE
        return Outcome.HUMAN_REVIEW_REQUIRED, StopReason.EVIDENCE_PATHS_EXHAUSTED  # S6

    if st.step >= st.max_steps:  # S7
        return Outcome.HUMAN_REVIEW_REQUIRED, StopReason.MAX_STEPS_REACHED
    if allowed_count == 0:  # S8
        return Outcome.EVIDENCE_UNAVAILABLE, StopReason.NO_ACTIONABLE_GAP
    return None
