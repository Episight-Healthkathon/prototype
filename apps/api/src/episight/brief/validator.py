"""Brief guardrails (API Contract §4.6), enforced before a brief is persisted or shown."""

from dataclasses import dataclass, field

from episight.agent.state import InvestigationState
from episight.contracts.api import BriefStatement, InvestigationBrief
from episight.contracts.enums import Outcome, RequirementState

# Decision language the brief must never contain (English + Indonesian).
BANNED_PHRASES = (
    "fraud",
    "fraudulent",
    "terbukti curang",
    "kecurangan terbukti",
    "reject claim",
    "claim rejected",
    "tolak klaim",
    "klaim ditolak",
    "approve payment",
    "payment approved",
    "approve claim",
    "setujui pembayaran",
    "pembayaran disetujui",
    "setujui klaim",
    "violation confirmed",
    "pelanggaran terbukti",
)


@dataclass
class BriefValidation:
    passed: bool
    violations: list[str] = field(default_factory=list)


def _statements(brief: InvestigationBrief) -> list[BriefStatement]:
    return (
        brief.case_summary
        + brief.supporting_risk_evidence
        + brief.explaining_context_evidence
        + brief.uncertainty
        + brief.suggested_next_review
    )


def check(brief: InvestigationBrief, st: InvestigationState) -> list[str]:
    violations = []
    for s in _statements(brief):
        if s.material and not s.evidence_ids:
            violations.append(f"{s.statement_id}: material statement without evidence")
        unknown = [e for e in s.evidence_ids if e not in st.evidence]
        if unknown:
            violations.append(f"{s.statement_id}: cites unknown evidence {unknown}")
        lower = s.text.lower()
        for phrase in BANNED_PHRASES:
            if phrase in lower:
                violations.append(f"{s.statement_id}: contains banned decision language '{phrase}'")
    covered = {g.key for g in brief.remaining_gaps} | {k for s in brief.uncertainty for k in s.requirement_keys}
    for req in st.requirements.values():
        if req.state in (RequirementState.UNAVAILABLE, RequirementState.NOT_FOUND) and req.key not in covered:
            violations.append(f"{req.key.value}: {req.state.value} requirement missing from gaps/uncertainty")
    if brief.outcome == Outcome.EVIDENCE_CONFLICTING:
        if not brief.conflicts or any(
            not c.affirming_evidence_ids or not c.negating_evidence_ids for c in brief.conflicts
        ):
            violations.append("conflicting outcome without both sides of the conflict")
    return violations


def validate_brief(brief: InvestigationBrief, st: InvestigationState) -> tuple[InvestigationBrief, BriefValidation]:
    """A failed brief is never shown as a successful conclusion: it is re-labelled for human review."""
    violations = check(brief, st)
    if not violations:
        return brief, BriefValidation(True)
    st.outcome = Outcome.HUMAN_REVIEW_REQUIRED
    notice = BriefStatement(
        statement_id="V1",
        text="This brief failed automated validation; review the investigation trail and the evidence directly.",
        evidence_ids=[],
        requirement_keys=[],
        material=False,
    )
    fallback = brief.model_copy(
        update={"outcome": Outcome.HUMAN_REVIEW_REQUIRED, "uncertainty": [notice, *brief.uncertainty]}
    )
    return fallback, BriefValidation(False, violations)
