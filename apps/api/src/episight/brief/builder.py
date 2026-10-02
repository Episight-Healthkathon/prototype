"""Reviewer brief from persisted structured state (API Contract §4.6). Deterministic templates, no LLM.

Every material statement cites evidence IDs. Absence is reported as absence ("not found in available sources",
"could not be assessed"), never as a finding, and nothing here expresses a fraud, approval or payment decision.
"""

from datetime import datetime

from episight.agent.context import CaseContext
from episight.agent.state import InvestigationState
from episight.contracts.api import (
    BriefStatement,
    BriefTimelineItem,
    Conflict,
    InvestigationBrief,
    PairMatch,
    PolicyReference,
    Provenance,
    RemainingGap,
    RiskSignal,
    SignalPair,
    SignalParams,
    Traceability,
)
from episight.contracts.enums import (
    EncounterType,
    EvidenceCategory,
    Outcome,
    ProgressStatus,
    RequirementKey,
    RequirementState,
    ReviewStatus,
    SourceType,
    Stance,
    StopReason,
)
from episight.episodes.codes import diagnosis_label

GENERATOR_VERSION = "brief-template-1"
K = RequirementKey
S = RequirementState

TOPIC = {
    K.EPISODE_RELATEDNESS: "Episode chain",
    K.DIAGNOSIS_CONSISTENCY: "Diagnosis",
    K.PROCEDURE_RELATIONSHIP: "Procedures",
    K.PROVIDER_CONTEXT: "Provider context",
    K.CLINICAL_DOCUMENT_AVAILABILITY: "Clinical documents",
    K.EMERGENCY_CONTEXT: "emergency context",
    K.CHRONIC_CONDITION_CONTEXT: "chronic condition",
    K.SCHEDULED_PROCEDURE_CONTEXT: "scheduled or staged procedure",
    K.SUPPORTING_EXAM_FOLLOWUP_CONTEXT: "supporting-examination follow-up",
    K.CLINICAL_JUSTIFICATION: "clinical justification",
    K.RISK_INDICATORS_IN_NOTES: "Risk indicators in notes",
    K.APPLICABLE_POLICY: "Policy",
    K.SCHEDULE_CONSISTENCY: "plan versus performed procedure",
}
MAX_QUOTES = 3


def _quote(excerpt: str, limit: int = 160) -> str:
    text = excerpt if len(excerpt) <= limit else excerpt[: limit - 1].rstrip() + "…"
    return f"“{text}”"


class _Ids:
    def __init__(self) -> None:
        self.n = 0

    def next(self, prefix: str) -> str:
        self.n += 1
        return f"{prefix}{self.n}"


def _risk_signal(ctx: CaseContext) -> RiskSignal:
    kind = ctx.index_episode.encounter_type
    return RiskSignal(
        rule_id=ctx.rule_id,
        rule_version=ctx.rule_version,
        description=ctx.rule_description,
        params=SignalParams(threshold_days=ctx.threshold_days, diagnosis_match=ctx.diagnosis_match),
        pairs=[
            SignalPair(
                from_episode_id=p.from_episode_id,
                to_episode_id=p.to_episode_id,
                interval_days=p.interval_days,
                matched=PairMatch(
                    same_patient=True, same_provider=True, same_primary_diagnosis=True, encounter_type=kind
                ),
            )
            for p in ctx.pairs
        ],
    )


def _timeline(st: InvestigationState, ctx: CaseContext) -> list[BriefTimelineItem]:
    ids = ctx.reconstruction.related_scope_ids if st.related_known else ctx.group_ids
    items, previous = [], None
    for eid in ids:
        ep = ctx.episodes[eid]
        kind = "inpatient stay" if ep.encounter_type == EncounterType.INPATIENT else "outpatient visit"
        dx = diagnosis_label(ep.primary_diagnosis) or ep.primary_diagnosis
        if eid == ctx.group_ids[0]:
            role = "Index"
        elif eid in ctx.group_ids:
            role = "Repeat"
        else:
            role = "Related"
        interval = None
        if previous is not None:
            interval = (ep.start_at.date() - (previous.end_at or previous.start_at).date()).days
        items.append(
            BriefTimelineItem(
                episode_id=eid,
                label=f"{role} {kind}: {dx}",
                start_at=ep.start_at,
                end_at=ep.end_at,
                interval_from_previous_days=interval,
            )
        )
        previous = ep
    return items


def _evidence_statements(
    st: InvestigationState, category: EvidenceCategory, ids: _Ids, prefix: str
) -> list[BriefStatement]:
    out = []
    for req in st.requirements.values():
        evs = [st.evidence[e] for e in req.evidence_ids if st.evidence[e].relevance_category == category]
        if not evs:
            continue
        topic = TOPIC[req.key]
        context_negation = req.spec.direction.value == "CONTEXT" and evs[0].stance == Stance.NEGATES
        head = f"Against {topic}" if context_negation else topic[0].upper() + topic[1:]
        quotes = "; ".join(f"{_quote(e.source_excerpt)} ({e.source_id})" for e in evs[:MAX_QUOTES])
        more = f" (+{len(evs) - MAX_QUOTES} more)" if len(evs) > MAX_QUOTES else ""
        out.append(
            BriefStatement(
                statement_id=ids.next(prefix),
                text=f"{head}: {quotes}{more}",
                evidence_ids=[e.evidence_id for e in evs],
                requirement_keys=[req.key],
                material=True,
            )
        )
    return out


def _labels(reqs) -> str:
    return ", ".join(TOPIC[r.key] for r in reqs)


def build_brief(st: InvestigationState, ctx: CaseContext, now: datetime) -> InvestigationBrief:
    ids = _Ids()
    reqs = list(st.requirements.values())
    context = [r for r in reqs if r.spec.is_explaining_context]
    found_context = [r for r in context if r.state == S.FOUND]
    conflicting = [r for r in reqs if r.state == S.CONFLICTING]
    unavailable = [r for r in reqs if r.state == S.UNAVAILABLE]
    affirming = lambda r: [e for e in r.evidence_ids if st.evidence[e].stance == Stance.AFFIRMS]  # noqa: E731
    negating = lambda r: [e for e in r.evidence_ids if st.evidence[e].stance == Stance.NEGATES]  # noqa: E731
    supporting_risk = [
        e.evidence_id for e in st.evidence.values() if e.relevance_category == EvidenceCategory.SUPPORTING_RISK
    ]

    provider = ctx.providers[ctx.provider_id].name
    intervals = ", ".join(f"{p.interval_days} d" for p in ctx.pairs)
    chain_ids = [
        e
        for e in st.requirements[K.EPISODE_RELATEDNESS].evidence_ids
        if st.evidence[e].source_type == SourceType.SCREENING_RULE
    ]
    summary = [
        BriefStatement(
            statement_id=ids.next("S"),
            text=f"{ctx.rule_description}: {len(ctx.group_ids)} episodes ({intervals}) at {provider}.",
            evidence_ids=chain_ids,
            requirement_keys=[K.EPISODE_RELATEDNESS],
            material=bool(chain_ids),
        )
    ]

    outcome, stop = st.outcome, st.stop_reason
    if outcome == Outcome.EVIDENCE_SUFFICIENT:
        ev = [e for r in found_context for e in affirming(r)[:1]]
        summary.append(
            BriefStatement(
                statement_id=ids.next("S"),
                text=f"Explaining context documented: {_labels(found_context)}.",
                evidence_ids=ev,
                requirement_keys=[r.key for r in found_context],
                material=True,
            )
        )
    elif outcome == Outcome.EVIDENCE_CONFLICTING:
        ev = [e for r in conflicting for e in affirming(r) + negating(r)]
        summary.append(
            BriefStatement(
                statement_id=ids.next("S"),
                text=f"Sources disagree on: {_labels(conflicting)}.",
                evidence_ids=ev,
                requirement_keys=[r.key for r in conflicting],
                material=True,
            )
        )
    elif outcome == Outcome.EVIDENCE_UNAVAILABLE:
        missing = [r for r in context if r.state in (S.UNAVAILABLE, S.OPEN)] or unavailable
        summary.append(
            BriefStatement(
                statement_id=ids.next("S"),
                text=f"Key context could not be assessed: {_labels(missing)}.",
                evidence_ids=[],
                requirement_keys=[r.key for r in missing],
                material=False,
            )
        )
    elif stop == StopReason.EVIDENCE_PATHS_EXHAUSTED:
        summary.append(
            BriefStatement(
                statement_id=ids.next("S"),
                text="No explaining context was found in the available sources; the risk signal remains unresolved.",
                evidence_ids=supporting_risk,
                requirement_keys=[r.key for r in context],
                material=bool(supporting_risk),
            )
        )
    else:
        summary.append(
            BriefStatement(
                statement_id=ids.next("S"),
                text=(
                    f"Investigation stopped early ({stop.value if stop else 'unknown'}); "
                    "open questions need human review."
                ),
                evidence_ids=[],
                requirement_keys=[r.key for r in reqs if r.state == S.OPEN],
                material=False,
            )
        )

    policy_refs = []
    for ev in st.evidence.values():
        if ev.source_type == SourceType.POLICY_SECTION:
            section = ctx.policy.get(ev.source_id)
            policy_refs.append(
                PolicyReference(
                    evidence_id=ev.evidence_id,
                    policy_id=ev.source_id,
                    document_title=section.document_title,
                    section=section.section,
                    version=section.version,
                    excerpt=ev.source_excerpt,
                )
            )

    gaps = [
        RemainingGap(key=r.key, question=r.spec.label, state=r.state, explanation=r.explanation)
        for r in reqs
        if r.state in (S.NOT_FOUND, S.UNAVAILABLE, S.FAILED, S.OPEN)
    ]
    conflicts = [
        Conflict(key=r.key, affirming_evidence_ids=affirming(r), negating_evidence_ids=negating(r)) for r in conflicting
    ]

    uncertainty = []
    for r in unavailable:
        uncertainty.append(
            BriefStatement(
                statement_id=ids.next("U"),
                text=f"{r.spec.label} {r.explanation}",
                evidence_ids=[],
                requirement_keys=[r.key],
                material=False,
            )
        )
    for r in conflicting:
        uncertainty.append(
            BriefStatement(
                statement_id=ids.next("U"),
                text=f"Conflicting sources on {TOPIC[r.key]}; neither side is assumed correct.",
                evidence_ids=affirming(r) + negating(r),
                requirement_keys=[r.key],
                material=True,
            )
        )
    for r in reqs:
        if r.state == S.SKIPPED:
            uncertainty.append(
                BriefStatement(
                    statement_id=ids.next("U"),
                    text=f"{TOPIC[r.key]} not assessed: {r.explanation.removeprefix('Skipped as not material: ')}.",
                    evidence_ids=[],
                    requirement_keys=[r.key],
                    material=False,
                )
            )

    if outcome == Outcome.EVIDENCE_SUFFICIENT:
        ev = [e for r in found_context for e in affirming(r)]
        next_review = [
            BriefStatement(
                statement_id=ids.next("N"),
                text=f"Verify the documented {_labels(found_context)} against the source records.",
                evidence_ids=ev,
                requirement_keys=[r.key for r in found_context],
                material=True,
            )
        ]
    elif outcome == Outcome.EVIDENCE_CONFLICTING:
        ev = [e for r in conflicting for e in affirming(r) + negating(r)]
        next_review = [
            BriefStatement(
                statement_id=ids.next("N"),
                text=f"Resolve the disagreement on {_labels(conflicting)} with the provider's "
                "source records before any judgement.",
                evidence_ids=ev,
                requirement_keys=[r.key for r in conflicting],
                material=True,
            )
        ]
    elif outcome == Outcome.EVIDENCE_UNAVAILABLE:
        next_review = [
            BriefStatement(
                statement_id=ids.next("N"),
                text="Request the unavailable documents from the provider before deciding.",
                evidence_ids=[],
                requirement_keys=[r.key for r in unavailable],
                material=False,
            )
        ]
    elif stop == StopReason.EVIDENCE_PATHS_EXHAUSTED:
        next_review = [
            BriefStatement(
                statement_id=ids.next("N"),
                text="Request a clinical justification for the repeated care from the provider.",
                evidence_ids=[],
                requirement_keys=[r.key for r in context],
                material=False,
            )
        ]
    else:
        next_review = [
            BriefStatement(
                statement_id=ids.next("N"),
                text="Complete the open questions manually using the investigation trail.",
                evidence_ids=[],
                requirement_keys=[r.key for r in reqs if r.state == S.OPEN],
                material=False,
            )
        ]

    statements = (
        summary
        + _evidence_statements(st, EvidenceCategory.SUPPORTING_RISK, ids, "R")
        + _evidence_statements(st, EvidenceCategory.EXPLAINING_CONTEXT, ids, "C")
        + uncertainty
        + next_review
    )
    risk = [s for s in statements if s.statement_id.startswith("R")]
    explain = [s for s in statements if s.statement_id.startswith("C")]
    material = [s for s in statements if s.material]
    referenced = {e for s in statements for e in s.evidence_ids} | {p.evidence_id for p in policy_refs}
    referenced |= {e for c in conflicts for e in c.affirming_evidence_ids + c.negating_evidence_ids}

    return InvestigationBrief(
        brief_id="BRF-" + st.run_id.removeprefix("RUN-"),
        case_id=st.case_id,
        run_id=st.run_id,
        generated_at=now,
        generator_version=GENERATOR_VERSION,
        progress_status=ProgressStatus.BRIEF_READY,
        outcome=outcome or Outcome.HUMAN_REVIEW_REQUIRED,
        stop_reason=stop or StopReason.INTERRUPTED,
        case_summary=summary,
        risk_signal=_risk_signal(ctx),
        episode_timeline=_timeline(st, ctx),
        supporting_risk_evidence=risk,
        explaining_context_evidence=explain,
        policy_references=policy_refs,
        remaining_gaps=gaps,
        conflicts=conflicts,
        uncertainty=uncertainty,
        suggested_next_review=next_review,
        review_status=ReviewStatus.PENDING_HUMAN_REVIEW,
        traceability=Traceability(
            material_statements=len(material), with_evidence=sum(1 for s in material if s.evidence_ids)
        ),
        provenance=Provenance(evidence_ids=sorted(referenced)),
    )
