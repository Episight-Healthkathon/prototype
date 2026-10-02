"""Evidence ledger: turns tool candidates into provenance-checked, deterministic evidence objects.

Nothing becomes evidence unless it points at a stored source in the case's permission scope, and every
note/policy excerpt must be the literal substring at its recorded offsets (architecture §3, §9).
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime

from episight.agent.catalog import SPECS
from episight.agent.context import CaseContext
from episight.contracts.api import Evidence
from episight.contracts.enums import (
    EvidenceCategory,
    ExtractionMethod,
    RequirementDirection,
    RequirementKey,
    SourceType,
    Stance,
    ToolName,
)


class ProvenanceError(ValueError):
    pass


@dataclass(frozen=True)
class EvidenceCandidate:
    requirement_key: RequirementKey
    source_type: SourceType
    source_id: str
    source_title: str
    source_excerpt: str
    stance: Stance
    extraction_method: ExtractionMethod
    episode_id: str | None = None
    field_path: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    exception_type: str | None = None
    policy_version: str | None = None


def category_for(key: RequirementKey, stance: Stance) -> EvidenceCategory:
    direction = SPECS[key].direction
    if stance == Stance.INFORMS or direction in (RequirementDirection.POLICY, RequirementDirection.BACKGROUND):
        return EvidenceCategory.NEUTRAL
    if direction == RequirementDirection.RISK:
        return EvidenceCategory.SUPPORTING_RISK if stance == Stance.AFFIRMS else EvidenceCategory.EXPLAINING_CONTEXT
    return EvidenceCategory.EXPLAINING_CONTEXT if stance == Stance.AFFIRMS else EvidenceCategory.SUPPORTING_RISK


def evidence_id(case_id: str, run_id: str, c: EvidenceCandidate) -> str:
    # D-22: run and requirement are part of the identity, so reruns and multi-requirement spans never collide.
    parts = [
        case_id,
        run_id,
        c.requirement_key.value,
        c.source_type.value,
        c.source_id,
        str(c.char_start),
        str(c.char_end),
        c.field_path or "",
    ]
    return "EV-" + hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def check_provenance(ctx: CaseContext, c: EvidenceCandidate) -> None:
    def literal(text: str | None) -> None:
        if text is None or c.char_start is None or c.char_end is None:
            raise ProvenanceError(f"{c.source_id}: text excerpt without offsets or source text")
        if text[c.char_start : c.char_end] != c.source_excerpt:
            raise ProvenanceError(f"{c.source_id}: excerpt does not match source text at offsets")

    if c.source_type == SourceType.CLINICAL_NOTE:
        note = ctx.notes.get(c.source_id)
        if note is None:
            raise ProvenanceError(f"unknown note {c.source_id}")
        literal(note.text)
    elif c.source_type == SourceType.POLICY_SECTION:
        section = ctx.policy.get(c.source_id)
        if section is None:
            raise ProvenanceError(f"unknown policy section {c.source_id}")
        literal(section.text)
    elif c.source_type == SourceType.EPISODE_RECORD:
        if c.source_id not in ctx.episodes:
            raise ProvenanceError(f"unknown episode {c.source_id}")
    elif c.source_type == SourceType.CLAIM_RECORD:
        if c.source_id not in ctx.claims:
            raise ProvenanceError(f"unknown claim {c.source_id}")
    elif c.source_type == SourceType.PROVIDER_RECORD:
        if c.source_id not in ctx.providers:
            raise ProvenanceError(f"unknown provider {c.source_id}")
    elif c.source_type == SourceType.SCREENING_RULE:
        if c.source_id != ctx.rule_id:
            raise ProvenanceError(f"unknown screening rule {c.source_id}")


def to_evidence(
    ctx: CaseContext,
    run_id: str,
    c: EvidenceCandidate,
    *,
    tool: ToolName,
    reason: str,
    step: int,
    retrieved_at: datetime,
) -> Evidence:
    check_provenance(ctx, c)
    return Evidence(
        evidence_id=evidence_id(ctx.case_id, run_id, c),
        case_id=ctx.case_id,
        run_id=run_id,
        episode_id=c.episode_id,
        source_type=c.source_type,
        source_id=c.source_id,
        source_title=c.source_title,
        source_excerpt=c.source_excerpt,
        field_path=c.field_path,
        char_start=c.char_start,
        char_end=c.char_end,
        requirement_key=c.requirement_key,
        stance=c.stance,
        relevance_category=category_for(c.requirement_key, c.stance),
        exception_type=c.exception_type,
        retrieved_by_tool=tool,
        retrieval_reason=reason,
        extraction_method=c.extraction_method,
        retrieved_at=retrieved_at,
        investigation_step=step,
        policy_version=c.policy_version,
    )
