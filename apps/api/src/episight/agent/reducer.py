"""Deterministic state reducer: applies one tool outcome to the investigation state.

Resolution rules (architecture §7.1):
- Structural tools resolve their requirement directly.
- Note-reading requirements resolve only when every *available* in-scope document has been read:
  AFFIRMS + NEGATES -> CONFLICTING, AFFIRMS -> FOUND, otherwise UNAVAILABLE if any in-scope source could not
  be read, else NOT_FOUND. Missing evidence never becomes a negative finding.
- A FOUND parent opens its follow-up checks (dependency graph), except in the non-adaptive baseline mode.
"""

from datetime import datetime

from episight.agent.catalog import SPAWNS
from episight.agent.context import CaseContext
from episight.agent.state import InvestigationState, RequirementTracker
from episight.agent.tools import ToolOutcome
from episight.contracts.api import Evidence, RequirementUpdate
from episight.contracts.enums import (
    InvestigationMode,
    RequirementKey,
    RequirementState,
    Stance,
    ToolName,
    ToolStatus,
)
from episight.evidence.ledger import to_evidence

S = RequirementState
MAX_TOOL_ERRORS = 2  # one retry after ERROR/TIMEOUT, then FAILED


def _set(req: RequirementTracker, state: RequirementState, explanation: str, updates: list[RequirementUpdate]):
    if req.state != state:
        updates.append(RequirementUpdate(key=req.key, from_state=req.state, to_state=state))
    req.state = state
    req.explanation = explanation


def resolve_by_coverage(
    st: InvestigationState, ctx: CaseContext, req: RequirementTracker, updates: list[RequirementUpdate]
) -> None:
    available, unavailable = st.coverage(req, ctx)
    searched = req.searched & set(available)
    if len(searched) < len(available):
        req.explanation = f"Read {len(searched)} of {len(available)} available document(s) so far."
        return
    stances = {e.stance for e in st.evidence_for(req.key)}
    found_part = f"read all {len(available)} available document(s)"
    missing_part = f"; {len(unavailable)} in-scope document(s) could not be read" if unavailable else ""
    if Stance.AFFIRMS in stances and Stance.NEGATES in stances:
        _set(req, S.CONFLICTING, f"Sources disagree ({found_part}{missing_part}).", updates)
    elif Stance.AFFIRMS in stances:
        _set(req, S.FOUND, f"Documented ({found_part}{missing_part}).", updates)
    elif unavailable:
        if available:
            text = f"Not found in the {len(available)} readable document(s); {len(unavailable)} could not be read."
        else:
            text = f"Cannot be assessed: none of the {len(unavailable)} in-scope document(s) can be read."
        _set(req, S.UNAVAILABLE, text, updates)
    elif not available:
        _set(req, S.UNAVAILABLE, "Cannot be assessed: no documents are registered in scope.", updates)
    else:
        negated = " (documented as absent)" if Stance.NEGATES in stances else ""
        _set(req, S.NOT_FOUND, f"Not found in available sources{negated}; {found_part}.", updates)


def apply_outcome(
    st: InvestigationState,
    ctx: CaseContext,
    *,
    requirement: RequirementKey,
    tool: ToolName,
    signature: str,
    outcome: ToolOutcome,
    reason: str,
    step: int,
    now: datetime,
) -> tuple[list[RequirementUpdate], list[Evidence]]:
    updates: list[RequirementUpdate] = []
    st.calls.setdefault(signature, []).append(outcome.status)
    target = st.requirements[requirement]
    target.attempted_tools.append(tool)

    if outcome.status in (ToolStatus.ERROR, ToolStatus.TIMEOUT):
        target.error_count += 1
        if target.error_count >= MAX_TOOL_ERRORS:
            message = outcome.error.message if outcome.error else outcome.status.value
            _set(target, S.FAILED, f"Tool failed after retry: {message}", updates)
        else:
            target.explanation = f"Tool {outcome.status.value.lower()}; one retry allowed."
        return updates, []

    new_evidence: list[Evidence] = []
    for cand in outcome.candidates:
        ev = to_evidence(ctx, st.run_id, cand, tool=tool, reason=reason, step=step, retrieved_at=now)
        if ev.evidence_id in st.evidence:
            st.surfaced_in_steps[ev.evidence_id].append(step)
            continue
        st.evidence[ev.evidence_id] = ev
        st.surfaced_in_steps[ev.evidence_id] = [step]
        new_evidence.append(ev)
        tracker = st.requirements.get(ev.requirement_key)
        if tracker is not None and ev.evidence_id not in tracker.evidence_ids:
            tracker.evidence_ids.append(ev.evidence_id)

    for key, (state, explanation) in outcome.resolutions.items():
        if key in st.requirements:
            _set(st.requirements[key], state, explanation, updates)
    if requirement == RequirementKey.EPISODE_RELATEDNESS and target.state != S.OPEN:
        st.related_known = True

    for key, note_ids in outcome.searched.items():
        if key in st.requirements:
            st.requirements[key].searched |= note_ids
            resolve_by_coverage(st, ctx, st.requirements[key], updates)

    if st.mode != InvestigationMode.RULES_RETRIEVAL:
        for parent, children in SPAWNS.items():
            if parent in st.requirements and st.requirements[parent].state == S.FOUND:
                for child in children:
                    if st.spawn(child, parent) is not None:
                        updates.append(RequirementUpdate(key=child, from_state=S.OPEN, to_state=S.OPEN))
    return updates, new_evidence


def apply_skip(st: InvestigationState, key: RequirementKey, reason: str) -> RequirementUpdate | None:
    req = st.requirements.get(key)
    if req is None or req.state != S.OPEN or req.material:
        return None
    update = RequirementUpdate(key=key, from_state=req.state, to_state=S.SKIPPED)
    req.state = S.SKIPPED
    req.explanation = f"Skipped as not material: {reason}"
    return update
