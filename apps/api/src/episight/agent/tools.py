"""The eight investigation tools (context doc §10). Typed input, structured output, explicit failure.

Tools read only the CaseContext (and, for plan checks, evidence already in the ledger). They never invent
records: a tool that finds nothing returns EMPTY, a tool whose sources cannot be read returns UNAVAILABLE.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from episight.agent.catalog import CONTEXT_TYPE_TO_KEY
from episight.agent.context import CaseContext
from episight.agent.state import InvestigationState
from episight.contracts.api import ActionError
from episight.contracts.enums import (
    Availability,
    EncounterType,
    ExtractionMethod,
    NoteType,
    RequirementKey,
    RequirementState,
    SignalType,
    SourceType,
    Stance,
    ToolName,
    ToolStatus,
)
from episight.episodes.codes import diagnosis_label, procedure_label
from episight.episodes.reconstruction import icd10_category, is_chronic_class
from episight.evidence.ledger import EvidenceCandidate
from episight.retrieval.bm25 import BM25
from episight.retrieval.context import ContextType, match_context
from episight.retrieval.text import sentences, tokenize

K = RequirementKey
S = RequirementState


# --- inputs ------------------------------------------------------------------------------------


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EpisodeHistoryInput(_Input):
    window_days: int = Field(default=90, ge=1, le=365)


class CompareDiagnosisInput(_Input):
    episode_ids: list[str] = Field(min_length=2)


class CompareProceduresInput(_Input):
    episode_ids: list[str] = Field(min_length=2)
    check_plan: bool = False


class ProviderContextInput(_Input):
    provider_id: str
    episode_ids: list[str] = Field(min_length=1)


class RetrieveClinicalInput(_Input):
    episode_ids: list[str] = Field(min_length=1)
    note_types: list[NoteType] | None = None
    query: str | None = Field(default=None, max_length=200)


class FindExceptionInput(_Input):
    context_type: ContextType
    episode_ids: list[str] = Field(min_length=1)
    note_types: list[NoteType] | None = None


class FindSupportingInput(_Input):
    signal_type: SignalType
    episode_ids: list[str] = Field(min_length=1)
    note_types: list[NoteType] | None = None


class RetrievePolicyInput(_Input):
    signal_type: SignalType
    topics: list[str] = Field(default_factory=list)
    query: str = Field(max_length=200)


# --- output ------------------------------------------------------------------------------------


@dataclass
class ToolOutcome:
    status: ToolStatus
    candidates: list[EvidenceCandidate] = field(default_factory=list)
    # Direct resolutions (structural tools): requirement -> (state, explanation).
    resolutions: dict[RequirementKey, tuple[RequirementState, str]] = field(default_factory=dict)
    # Note ids read per requirement (coverage-based resolution in the reducer).
    searched: dict[RequirementKey, set[str]] = field(default_factory=dict)
    findings: dict[str, Any] = field(default_factory=dict)
    error: ActionError | None = None


# Routine diagnostics do not make two episodes "related by procedure".
ROUTINE_PROCEDURES = frozenset({"89.52", "87.44", "89.54", "90.59", "88.72"})
# Diagnostic -> therapeutic pairs that link episodes clinically.
RELATED_PROCEDURES = frozenset({("88.56", "36.06"), ("88.56", "36.07"), ("88.55", "36.06"), ("88.55", "36.07")})
ICD9CM_CODE = re.compile(r"(?<![\d.])(\d{2}\.\d{1,2})(?![\d.])")


def _ep_label(ctx: CaseContext, eid: str) -> str:
    ep = ctx.episodes[eid]
    kind = "inpatient" if ep.encounter_type == EncounterType.INPATIENT else "outpatient"
    return f"{eid} ({kind}, {ep.start_at.date().isoformat()})"


def _note_title(ctx: CaseContext, note_id: str) -> str:
    note = ctx.notes[note_id]
    return f"{note.title or note.note_type.value.replace('_', ' ').title()} - {note.episode_id}"


# --- tools -------------------------------------------------------------------------------------


def get_episode_history(ctx: CaseContext, st: InvestigationState, inp: EpisodeHistoryInput) -> ToolOutcome:
    rec = ctx.reconstruction
    unit = "discharge" if ctx.index_episode.encounter_type == EncounterType.INPATIENT else "the previous visit"
    candidates = [
        EvidenceCandidate(
            requirement_key=K.EPISODE_RELATEDNESS,
            source_type=SourceType.SCREENING_RULE,
            source_id=ctx.rule_id,
            source_title=f"Screening rule {ctx.rule_id} v{ctx.rule_version}",
            source_excerpt=(
                f"{p.to_episode_id} started {p.interval_days} day(s) after {unit} of {p.from_episode_id}; "
                "same patient, same FKRTL, same primary diagnosis"
            ),
            stance=Stance.AFFIRMS,
            extraction_method=ExtractionMethod.STRUCTURED_FIELD,
            episode_id=p.to_episode_id,
            field_path=f"pairs[{p.from_episode_id}->{p.to_episode_id}]",
        )
        for p in ctx.pairs
    ]
    for eid in rec.related_ids:
        ep = ctx.episodes[eid]
        candidates.append(
            EvidenceCandidate(
                requirement_key=K.EPISODE_RELATEDNESS,
                source_type=SourceType.EPISODE_RECORD,
                source_id=eid,
                source_title=f"Episode record {eid}",
                source_excerpt=f"Related episode {_ep_label(ctx, eid)}: {ep.primary_diagnosis}",
                stance=Stance.INFORMS,
                extraction_method=ExtractionMethod.STRUCTURED_FIELD,
                episode_id=eid,
                field_path="episodes.primary_diagnosis",
            )
        )
    intervals = ", ".join(f"{p.interval_days} d" for p in ctx.pairs)
    explanation = (
        f"{len(rec.anchor_ids)} anchor episodes chained ({intervals}); "
        f"{len(rec.related_ids)} related and {len(rec.context_ids)} context episode(s) within "
        f"{inp.window_days} days."
    )
    return ToolOutcome(
        status=ToolStatus.OK,
        candidates=candidates,
        resolutions={K.EPISODE_RELATEDNESS: (S.FOUND, explanation)},
        findings={"anchor_ids": rec.anchor_ids, "related_ids": rec.related_ids, "context_ids": rec.context_ids},
    )


def compare_diagnosis(ctx: CaseContext, st: InvestigationState, inp: CompareDiagnosisInput) -> ToolOutcome:
    eps = [ctx.episodes[i] for i in inp.episode_ids]
    codes = [e.primary_diagnosis for e in eps]
    if len(set(codes)) == 1:
        match, state, stance = "EXACT", S.FOUND, Stance.AFFIRMS
    elif len({icd10_category(c) for c in codes}) == 1:
        match, state, stance = "CATEGORY", S.FOUND, Stance.AFFIRMS
    else:
        match, state, stance = "DIFFERENT", S.NOT_FOUND, Stance.NEGATES
    candidates = []
    for prev, cur in zip(eps, eps[1:], strict=False):
        candidates.append(
            EvidenceCandidate(
                requirement_key=K.DIAGNOSIS_CONSISTENCY,
                source_type=SourceType.EPISODE_RECORD,
                source_id=cur.episode_id,
                source_title=f"Episode record {cur.episode_id}",
                source_excerpt=(
                    f"{prev.primary_diagnosis} ({prev.episode_id}) vs {cur.primary_diagnosis} ({cur.episode_id})"
                ),
                stance=stance,
                extraction_method=ExtractionMethod.STRUCTURED_FIELD,
                episode_id=cur.episode_id,
                field_path="episodes.primary_diagnosis",
            )
        )
    chronic = is_chronic_class(codes[0])
    if chronic:
        candidates.append(
            EvidenceCandidate(
                requirement_key=K.DIAGNOSIS_CONSISTENCY,
                source_type=SourceType.EPISODE_RECORD,
                source_id=eps[0].episode_id,
                source_title=f"Episode record {eps[0].episode_id}",
                source_excerpt=f"{codes[0]} ({diagnosis_label(codes[0]) or 'diagnosis'}) is a chronic-class diagnosis",
                stance=Stance.INFORMS,
                extraction_method=ExtractionMethod.STRUCTURED_FIELD,
                episode_id=eps[0].episode_id,
                field_path="episodes.primary_diagnosis",
            )
        )
    label = {
        "EXACT": "Same primary diagnosis",
        "CATEGORY": "Same ICD-10 category",
        "DIFFERENT": "Different primary diagnoses",
    }[match]
    explanation = f"{label} ({', '.join(dict.fromkeys(codes))})" + ("; chronic-class code." if chronic else ".")
    return ToolOutcome(
        status=ToolStatus.OK,
        candidates=candidates,
        resolutions={K.DIAGNOSIS_CONSISTENCY: (state, explanation)},
        findings={"match": match, "codes": codes, "chronic_class": chronic},
    )


def _plan_sources(ctx: CaseContext, st: InvestigationState) -> list[tuple[str, Any]]:
    """Plan sentences (affirming scheduled-procedure evidence in earlier episodes) that name a procedure code."""
    later = set(ctx.later_ids)
    out = []
    for ev in st.evidence_for(K.SCHEDULED_PROCEDURE_CONTEXT):
        if ev.stance == Stance.AFFIRMS and ev.episode_id not in later and ICD9CM_CODE.search(ev.source_excerpt):
            out.append((ev, ICD9CM_CODE.findall(ev.source_excerpt)))
    return out


def compare_procedures(ctx: CaseContext, st: InvestigationState, inp: CompareProceduresInput) -> ToolOutcome:
    eps = [ctx.episodes[i] for i in inp.episode_ids]
    if inp.check_plan:
        plans = _plan_sources(ctx, st)
        if not plans:
            return ToolOutcome(
                status=ToolStatus.EMPTY,
                resolutions={
                    K.SCHEDULE_CONSISTENCY: (
                        S.NOT_FOUND,
                        "The documented plan names no procedure code; plan-to-procedure match cannot be verified.",
                    )
                },
            )
        planned = {code for _, codes in plans for code in codes}
        performed = {p.code: e.episode_id for e in eps[1:] for p in e.procedures}
        candidates = [
            EvidenceCandidate(
                requirement_key=K.SCHEDULE_CONSISTENCY,
                source_type=SourceType.CLINICAL_NOTE,
                source_id=ev.source_id,
                source_title=ev.source_title,
                source_excerpt=ev.source_excerpt,
                stance=Stance.AFFIRMS,
                extraction_method=ExtractionMethod.RULE_MATCH,
                episode_id=ev.episode_id,
                char_start=ev.char_start,
                char_end=ev.char_end,
                exception_type="SCHEDULED_PROCEDURE",
            )
            for ev, _ in plans
        ]
        matched = sorted(planned & performed.keys())
        if matched:
            for code in matched:
                candidates.append(
                    EvidenceCandidate(
                        requirement_key=K.SCHEDULE_CONSISTENCY,
                        source_type=SourceType.EPISODE_RECORD,
                        source_id=performed[code],
                        source_title=f"Episode record {performed[code]}",
                        source_excerpt=(
                            f"Planned {code} ({procedure_label(code) or 'procedure'}) performed in {performed[code]}"
                        ),
                        stance=Stance.AFFIRMS,
                        extraction_method=ExtractionMethod.STRUCTURED_FIELD,
                        episode_id=performed[code],
                        field_path="episodes.procedures",
                    )
                )
            return ToolOutcome(
                status=ToolStatus.OK,
                candidates=candidates,
                resolutions={
                    K.SCHEDULE_CONSISTENCY: (
                        S.FOUND,
                        f"Planned procedure {', '.join(matched)} was performed in the later episode.",
                    )
                },
                findings={"planned": sorted(planned), "performed": sorted(performed)},
            )
        if not performed:
            return ToolOutcome(
                status=ToolStatus.EMPTY,
                candidates=candidates,
                resolutions={
                    K.SCHEDULE_CONSISTENCY: (
                        S.NOT_FOUND,
                        f"Plan names {', '.join(sorted(planned))}, but no procedure is recorded in later episodes.",
                    )
                },
            )
        for code, eid in sorted(performed.items()):
            candidates.append(
                EvidenceCandidate(
                    requirement_key=K.SCHEDULE_CONSISTENCY,
                    source_type=SourceType.EPISODE_RECORD,
                    source_id=eid,
                    source_title=f"Episode record {eid}",
                    source_excerpt=f"Performed {code} in {eid}; plan named {', '.join(sorted(planned))}",
                    stance=Stance.NEGATES,
                    extraction_method=ExtractionMethod.STRUCTURED_FIELD,
                    episode_id=eid,
                    field_path="episodes.procedures",
                )
            )
        return ToolOutcome(
            status=ToolStatus.OK,
            candidates=candidates,
            resolutions={
                K.SCHEDULE_CONSISTENCY: (S.CONFLICTING, "The performed procedure differs from the documented plan.")
            },
            findings={"planned": sorted(planned), "performed": sorted(performed)},
        )

    by_episode = {e.episode_id: [p.code for p in e.procedures if p.code not in ROUTINE_PROCEDURES] for e in eps}
    candidates, links = [], []
    for prev, cur in zip(eps, eps[1:], strict=False):
        for a in by_episode[prev.episode_id]:
            for b in by_episode[cur.episode_id]:
                if a == b or (a, b) in RELATED_PROCEDURES:
                    kind = "repeated" if a == b else "related"
                    links.append((a, b, kind))
                    candidates.append(
                        EvidenceCandidate(
                            requirement_key=K.PROCEDURE_RELATIONSHIP,
                            source_type=SourceType.EPISODE_RECORD,
                            source_id=cur.episode_id,
                            source_title=f"Episode record {cur.episode_id}",
                            source_excerpt=(
                                f"{a} ({prev.episode_id}) -> {b} ({cur.episode_id}): {kind} procedure "
                                f"({procedure_label(b) or b})"
                            ),
                            stance=Stance.AFFIRMS,
                            extraction_method=ExtractionMethod.STRUCTURED_FIELD,
                            episode_id=cur.episode_id,
                            field_path="episodes.procedures",
                        )
                    )
    if links:
        return ToolOutcome(
            status=ToolStatus.OK,
            candidates=candidates,
            resolutions={
                K.PROCEDURE_RELATIONSHIP: (S.FOUND, "; ".join(f"{a} -> {b} ({kind})" for a, b, kind in links) + ".")
            },
            findings={"links": links},
        )
    any_procs = any(e.procedures for e in eps)
    explanation = (
        "No repeated or related therapeutic procedure (routine diagnostics excluded)."
        if any_procs
        else "No procedures recorded in the anchor episodes."
    )
    return ToolOutcome(status=ToolStatus.EMPTY, resolutions={K.PROCEDURE_RELATIONSHIP: (S.NOT_FOUND, explanation)})


def get_provider_context(ctx: CaseContext, st: InvestigationState, inp: ProviderContextInput) -> ToolOutcome:
    provider = ctx.providers[inp.provider_id]
    eps = [ctx.episodes[i] for i in inp.episode_ids]
    classes = [e.class_of_care for e in eps]
    referred = [e.episode_id for e in eps if e.discharge_status and e.discharge_status.value == "REFERRED"]
    candidates = [
        EvidenceCandidate(
            requirement_key=K.PROVIDER_CONTEXT,
            source_type=SourceType.PROVIDER_RECORD,
            source_id=provider.provider_id,
            source_title=f"Provider record {provider.provider_id}",
            source_excerpt=f"{provider.name} ({provider.provider_type.value}, class {provider.hospital_class or '-'})",
            stance=Stance.INFORMS,
            extraction_method=ExtractionMethod.STRUCTURED_FIELD,
            field_path="providers.hospital_class",
        )
    ]
    notes = []
    if len(set(classes)) > 1:
        notes.append("class of care changed (" + " -> ".join(c or "-" for c in classes) + ")")
    if referred:
        notes.append("referred out from " + ", ".join(referred))
    explanation = f"{provider.name}, class {provider.hospital_class or '-'}; " + (
        "; ".join(notes) or "no class change or referral."
    )
    return ToolOutcome(
        status=ToolStatus.OK, candidates=candidates, resolutions={K.PROVIDER_CONTEXT: (S.FOUND, explanation)}
    )


def retrieve_clinical_evidence(ctx: CaseContext, st: InvestigationState, inp: RetrieveClinicalInput) -> ToolOutcome:
    notes = ctx.notes_for(inp.episode_ids, inp.note_types)
    expected_missing = ctx.expected_missing_documents(inp.episode_ids)
    available = [n for n in notes if n.availability == Availability.AVAILABLE]
    unavailable = [n for n in notes if n.availability != Availability.AVAILABLE]
    inventory = [
        {
            "note_id": n.note_id,
            "episode_id": n.episode_id,
            "note_type": n.note_type.value,
            "availability": n.availability.value,
        }
        for n in notes
    ]
    findings: dict[str, Any] = {"inventory": inventory, "expected_missing": expected_missing}
    if inp.query and available:
        sents = [(n, s) for n in available for s in sentences(n.text)]
        hits = BM25([tokenize(s.text) for _, s in sents]).search(tokenize(inp.query), top_k=5)
        findings["passages"] = [
            {"note_id": sents[h.index][0].note_id, "excerpt": sents[h.index][1].text, "score": round(h.score, 3)}
            for h in hits
        ]
    total = len(notes) + len(expected_missing)
    if total == 0:
        return ToolOutcome(
            status=ToolStatus.UNAVAILABLE,
            findings=findings,
            resolutions={
                K.CLINICAL_DOCUMENT_AVAILABILITY: (
                    S.UNAVAILABLE,
                    "No clinical documents are registered for these episodes.",
                )
            },
        )
    missing = [f"{n.note_id} ({n.note_type.value}, {n.availability.value})" for n in unavailable]
    missing += [m.removeprefix("EXPECTED:").replace(":", " ") + " (expected, not registered)" for m in expected_missing]
    if missing:
        explanation = f"{len(missing)} of {total} documents cannot be read: " + "; ".join(missing) + "."
        return ToolOutcome(
            status=ToolStatus.OK,
            findings=findings,
            resolutions={K.CLINICAL_DOCUMENT_AVAILABILITY: (S.UNAVAILABLE, explanation)},
        )
    return ToolOutcome(
        status=ToolStatus.OK,
        findings=findings,
        resolutions={K.CLINICAL_DOCUMENT_AVAILABILITY: (S.FOUND, f"{total} documents registered, all available.")},
    )


def _search_notes(
    ctx: CaseContext,
    key: RequirementKey,
    context: ContextType,
    episode_ids: list[str],
    note_types: list[NoteType] | None,
) -> ToolOutcome:
    notes = ctx.notes_for(episode_ids, note_types)
    available = [n for n in notes if n.availability == Availability.AVAILABLE]
    candidates = []
    for note in available:
        for m in match_context(note.text, context):
            candidates.append(
                EvidenceCandidate(
                    requirement_key=key,
                    source_type=SourceType.CLINICAL_NOTE,
                    source_id=note.note_id,
                    source_title=_note_title(ctx, note.note_id),
                    source_excerpt=m.excerpt,
                    stance=m.stance,
                    extraction_method=ExtractionMethod.RULE_MATCH,
                    episode_id=note.episode_id,
                    char_start=m.char_start,
                    char_end=m.char_end,
                    exception_type=context.value if key != K.RISK_INDICATORS_IN_NOTES else None,
                )
            )
    status = ToolStatus.OK if candidates else (ToolStatus.EMPTY if available else ToolStatus.UNAVAILABLE)
    return ToolOutcome(
        status=status,
        candidates=candidates,
        searched={key: {n.note_id for n in available}},
        findings={
            "read": [n.note_id for n in available],
            "unreadable": [n.note_id for n in notes if n not in available],
        },
    )


def find_exception_evidence(ctx: CaseContext, st: InvestigationState, inp: FindExceptionInput) -> ToolOutcome:
    return _search_notes(ctx, CONTEXT_TYPE_TO_KEY[inp.context_type], inp.context_type, inp.episode_ids, inp.note_types)


def find_supporting_evidence(ctx: CaseContext, st: InvestigationState, inp: FindSupportingInput) -> ToolOutcome:
    outcome = _search_notes(
        ctx, K.RISK_INDICATORS_IN_NOTES, ContextType.RISK_INDICATOR, inp.episode_ids, inp.note_types
    )
    for eid in inp.episode_ids[:-1]:
        ep = ctx.episodes[eid]
        if ep.discharge_status and ep.discharge_status.value == "AGAINST_ADVICE":
            outcome.candidates.append(
                EvidenceCandidate(
                    requirement_key=K.RISK_INDICATORS_IN_NOTES,
                    source_type=SourceType.EPISODE_RECORD,
                    source_id=eid,
                    source_title=f"Episode record {eid}",
                    source_excerpt=f"{eid} discharge status: AGAINST_ADVICE",
                    stance=Stance.AFFIRMS,
                    extraction_method=ExtractionMethod.STRUCTURED_FIELD,
                    episode_id=eid,
                    field_path="episodes.discharge_status",
                )
            )
            outcome.status = ToolStatus.OK
    return outcome


def retrieve_policy(ctx: CaseContext, st: InvestigationState, inp: RetrievePolicyInput) -> ToolOutcome:
    if len(ctx.policy) == 0:
        return ToolOutcome(
            status=ToolStatus.UNAVAILABLE,
            resolutions={K.APPLICABLE_POLICY: (S.UNAVAILABLE, "Policy corpus not loaded.")},
        )
    hits = ctx.policy.search(inp.query, inp.topics)
    candidates = []
    for hit in hits:
        first = sentences(hit.section.text)[0]
        candidates.append(
            EvidenceCandidate(
                requirement_key=K.APPLICABLE_POLICY,
                source_type=SourceType.POLICY_SECTION,
                source_id=hit.section.policy_id,
                source_title=f"{hit.section.document_title}: {hit.section.section}",
                source_excerpt=first.text,
                stance=Stance.INFORMS,
                extraction_method=ExtractionMethod.BM25_RETRIEVAL,
                char_start=first.start,
                char_end=first.end,
                policy_version=hit.section.version,
            )
        )
    if not candidates:
        return ToolOutcome(
            status=ToolStatus.EMPTY,
            resolutions={K.APPLICABLE_POLICY: (S.NOT_FOUND, "No applicable rule found in the policy corpus.")},
        )
    titles = "; ".join(h.section.section for h in hits)
    return ToolOutcome(
        status=ToolStatus.OK,
        candidates=candidates,
        resolutions={K.APPLICABLE_POLICY: (S.FOUND, f"{len(hits)} policy section(s): {titles}.")},
        findings={"policy_ids": [h.section.policy_id for h in hits], "scores": [h.score for h in hits]},
    )


@dataclass(frozen=True)
class ToolDef:
    name: ToolName
    label: str
    input_model: type[_Input]
    fn: Callable[[CaseContext, InvestigationState, Any], ToolOutcome]


TOOLS: dict[ToolName, ToolDef] = {
    t.name: t
    for t in [
        ToolDef(
            ToolName.GET_EPISODE_HISTORY, "Reconstructing episode history", EpisodeHistoryInput, get_episode_history
        ),
        ToolDef(ToolName.COMPARE_DIAGNOSIS, "Comparing diagnoses", CompareDiagnosisInput, compare_diagnosis),
        ToolDef(ToolName.COMPARE_PROCEDURES, "Comparing procedures", CompareProceduresInput, compare_procedures),
        ToolDef(ToolName.GET_PROVIDER_CONTEXT, "Checking provider context", ProviderContextInput, get_provider_context),
        ToolDef(
            ToolName.RETRIEVE_CLINICAL_EVIDENCE,
            "Inventorying clinical documents",
            RetrieveClinicalInput,
            retrieve_clinical_evidence,
        ),
        ToolDef(ToolName.RETRIEVE_POLICY, "Checking policy context", RetrievePolicyInput, retrieve_policy),
        ToolDef(
            ToolName.FIND_SUPPORTING_EVIDENCE,
            "Searching notes for risk indicators",
            FindSupportingInput,
            find_supporting_evidence,
        ),
        ToolDef(
            ToolName.FIND_EXCEPTION_EVIDENCE,
            "Searching notes for explaining context",
            FindExceptionInput,
            find_exception_evidence,
        ),
    ]
}
