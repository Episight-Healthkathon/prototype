"""Contract compliance: committed artifacts match the Pydantic models (no silent drift)."""

import json

import pytest

from episight.contracts import api as dto
from episight.contracts import enums
from episight.devtools.contract_export import export
from tests.conftest import DATASET_DIR, SHARED_TYPES

FIXTURE_MODELS = {
    "cases.list.json": dto.CaseList,
    ".detail.json": dto.CaseDetail,
    ".episodes.json": dto.EpisodeTimeline,
    ".investigation.running.json": dto.InvestigationView,
    ".investigation.completed.json": dto.InvestigationView,
    ".evidence.json": dto.EvidenceList,
    ".brief.json": dto.InvestigationBrief,
}


def _model_for(name: str):
    if name.startswith("EV-"):
        return dto.EvidenceDetail
    for suffix, model in FIXTURE_MODELS.items():
        if name.endswith(suffix):
            return model
    return None


def test_export_is_deterministic_and_matches_committed_artifacts(tmp_path):
    export(tmp_path, DATASET_DIR)
    generated = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*.json"))
    committed = sorted(p.relative_to(SHARED_TYPES) for p in (SHARED_TYPES / "fixtures").rglob("*.json"))
    assert [p for p in generated if p.parts[0] == "fixtures"] == committed
    for rel in generated:
        assert (tmp_path / rel).read_text(encoding="utf-8") == (SHARED_TYPES / rel).read_text(encoding="utf-8"), (
            f"{rel} is stale: run `uv run episight export-contract` and `pnpm generate`"
        )
    assert (tmp_path / "src" / "index.ts").read_text() == (SHARED_TYPES / "src" / "index.ts").read_text()


@pytest.mark.parametrize("path", sorted((SHARED_TYPES / "fixtures").rglob("*.json")), ids=lambda p: p.name)
def test_every_fixture_validates_against_its_contract_model(path):
    if path.name == "index.json":
        return
    model = _model_for(path.name)
    assert model is not None, f"no contract model mapped for fixture {path.name}"
    model.model_validate(json.loads(path.read_text(encoding="utf-8")))


def test_openapi_covers_every_contract_endpoint():
    spec = json.loads((SHARED_TYPES / "openapi.json").read_text(encoding="utf-8"))
    expected = {
        ("get", "/api/v1/health"),
        ("get", "/api/v1/cases"),
        ("get", "/api/v1/cases/{case_id}"),
        ("get", "/api/v1/cases/{case_id}/episodes"),
        ("post", "/api/v1/cases/{case_id}/investigate"),
        ("get", "/api/v1/cases/{case_id}/investigation"),
        ("get", "/api/v1/cases/{case_id}/evidence"),
        ("get", "/api/v1/evidence/{evidence_id}"),
        ("get", "/api/v1/cases/{case_id}/brief"),
    }
    actual = {(m, p) for p, ops in spec["paths"].items() for m in ops}
    assert expected <= actual


def test_requirement_update_uses_contract_field_names():
    update = dto.RequirementUpdate(key="EMERGENCY_CONTEXT", from_state="OPEN", to_state="FOUND")
    assert update.model_dump(by_alias=True, mode="json") == {"key": "EMERGENCY_CONTEXT", "from": "OPEN", "to": "FOUND"}


def test_status_enums_match_decision_d04():
    assert [s.value for s in enums.ProgressStatus] == [
        "FLAGGED",
        "INVESTIGATING",
        "BRIEF_READY",
        "INVESTIGATION_FAILED",
    ]
    assert [o.value for o in enums.Outcome] == [
        "EVIDENCE_SUFFICIENT",
        "EVIDENCE_CONFLICTING",
        "EVIDENCE_UNAVAILABLE",
        "HUMAN_REVIEW_REQUIRED",
    ]


def test_no_decision_authority_in_any_enum():
    # ToolStatus.REJECTED (a planner proposal rejected by the validator) is not a claim decision.
    banned = ("FRAUD", "APPROV", "PAYMENT", "DENY", "DENIED", "CLAIM_REJECT", "REJECT_CLAIM", "VERDICT")
    for enum_cls in vars(enums).values():
        if isinstance(enum_cls, type) and issubclass(enum_cls, enums.StrEnum) and enum_cls is not enums.StrEnum:
            for member in enum_cls:
                assert not any(b in member.value.upper() for b in banned), f"{enum_cls.__name__}.{member.value}"
