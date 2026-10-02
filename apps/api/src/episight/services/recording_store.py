"""Planner recordings in PostgreSQL (D-21): every live AI planner call is kept for audit and replay."""

from typing import Any

from sqlalchemy.orm import Session

from episight.db.models import PlannerRecordingRow


class DbRecordingStore:
    def __init__(self, session: Session):
        self.session = session

    def get(self, request_hash: str) -> dict[str, Any] | None:
        row = self.session.get(PlannerRecordingRow, request_hash)
        return row.response if row else None

    def put(
        self, request_hash: str, *, model: str, prompt_version: str, request: dict[str, Any], response: dict[str, Any]
    ) -> None:
        self.session.merge(
            PlannerRecordingRow(
                request_hash=request_hash,
                model=model,
                prompt_version=prompt_version,
                request=request,
                response=response,
            )
        )
        self.session.commit()
