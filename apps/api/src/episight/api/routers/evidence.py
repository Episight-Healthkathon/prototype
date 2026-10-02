from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from episight.api import views
from episight.api.errors import not_found
from episight.contracts.api import ApiError, EvidenceDetail, EvidenceSource, TextHighlight
from episight.contracts.enums import ErrorCode, SourceType
from episight.db.models import ClaimRow, ClinicalNoteRow, EpisodeRow, EvidenceRow, PolicySectionRow, ProviderRow
from episight.db.session import get_session

router = APIRouter(prefix="/evidence", tags=["evidence"])
SessionDep = Annotated[Session, Depends(get_session)]

_RECORD_TABLES = {
    SourceType.EPISODE_RECORD: EpisodeRow,
    SourceType.CLAIM_RECORD: ClaimRow,
    SourceType.PROVIDER_RECORD: ProviderRow,
}


def _source(session: Session, row: EvidenceRow) -> EvidenceSource:
    source_type = SourceType(row.source_type)
    base = {"source_type": source_type, "source_id": row.source_id, "title": row.source_title}
    if source_type == SourceType.CLINICAL_NOTE:
        note = session.get(ClinicalNoteRow, row.source_id)
        highlight = (
            TextHighlight(char_start=row.char_start, char_end=row.char_end)
            if row.char_start is not None and row.char_end is not None
            else None
        )
        return EvidenceSource(
            **base,
            text=note.text if note else None,
            highlight=highlight,
            availability=note.availability if note else None,
        )
    if source_type == SourceType.POLICY_SECTION:
        policy = session.get(PolicySectionRow, row.source_id)
        if policy is None:
            return EvidenceSource(**base)
        return EvidenceSource(
            **base,
            text=policy.text,
            highlight=(
                TextHighlight(char_start=row.char_start, char_end=row.char_end)
                if row.char_start is not None and row.char_end is not None
                else None
            ),
            document_title=policy.document_title,
            section=policy.section,
            version=policy.version,
            effective_date=policy.effective_date,
            source_ref=policy.source_ref,
            source_url=policy.source_url,
        )
    table = _RECORD_TABLES.get(source_type)
    value = None
    if table is not None and row.field_path:
        record = session.get(table, row.source_id)
        attr = row.field_path.rsplit(".", 1)[-1]
        value = getattr(record, attr, None) if record else None
    return EvidenceSource(**base, field_path=row.field_path, value=value)


@router.get(
    "/{evidence_id}", response_model=EvidenceDetail, responses={404: {"model": ApiError}, 503: {"model": ApiError}}
)
def get_evidence(evidence_id: str, session: SessionDep) -> EvidenceDetail:
    row = session.get(EvidenceRow, evidence_id)
    if row is None:
        raise not_found(ErrorCode.EVIDENCE_NOT_FOUND, f"Evidence {evidence_id} not found", evidence_id=evidence_id)
    return EvidenceDetail(**views.evidence(row).model_dump(), source=_source(session, row))
