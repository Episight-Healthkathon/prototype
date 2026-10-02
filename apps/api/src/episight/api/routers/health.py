from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from episight.contracts.api import Health
from episight.db.models import IngestManifest, PolicySectionRow
from episight.db.session import get_session

router = APIRouter(tags=["health"])


@router.get("/health", response_model=Health, responses={503: {"model": Health}})
def health(session: Annotated[Session, Depends(get_session)]):
    try:
        session.execute(text("SELECT 1"))
        versions = {m.kind: m.version for m in session.scalars(select(IngestManifest))}
        policy_count = session.scalar(select(func.count()).select_from(PolicySectionRow)) or 0
    except SQLAlchemyError:
        body = Health(status="degraded", db="down", policy_index="down", dataset_version=None, corpus_version=None)
        return JSONResponse(status_code=503, content=body.model_dump(mode="json"))
    return Health(
        status="ok",
        db="ok",
        policy_index="ok" if policy_count else "empty",
        dataset_version=versions.get("dataset"),
        corpus_version=versions.get("policies"),
    )
