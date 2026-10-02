"""Full investigation flow through the real API and database: start -> poll -> evidence -> brief."""

from datetime import UTC, datetime

import pytest

from episight.contracts.api import (
    CaseDetail,
    EpisodeTimeline,
    EvidenceDetail,
    EvidenceList,
    InvestigateAccepted,
    InvestigationBrief,
    InvestigationView,
)

pytestmark = pytest.mark.db

EXPECTED = {
    "PAT-000001": ("EVIDENCE_SUFFICIENT", "SUFFICIENT_EVIDENCE"),
    "PAT-000002": ("HUMAN_REVIEW_REQUIRED", "EVIDENCE_PATHS_EXHAUSTED"),
    "PAT-000003": ("EVIDENCE_SUFFICIENT", "SUFFICIENT_EVIDENCE"),
    "PAT-000004": ("EVIDENCE_UNAVAILABLE", "REQUIRED_EVIDENCE_UNAVAILABLE"),
    "PAT-000005": ("EVIDENCE_CONFLICTING", "CONFLICTING_EVIDENCE"),
}


def case_id(client, patient_id):
    return client.get("/api/v1/cases", params={"q": patient_id}).json()["items"][0]["case_id"]


@pytest.fixture(scope="module")
def runs(client):
    """Start every golden investigation once (TestClient runs the background task before returning)."""
    out = {}
    for patient_id in EXPECTED:
        cid = case_id(client, patient_id)
        r = client.post(f"/api/v1/cases/{cid}/investigate", json={"mode": "FULL"})
        assert r.status_code == 202, r.text
        out[patient_id] = (cid, InvestigateAccepted.model_validate(r.json()))
    return out


@pytest.mark.parametrize("patient_id", EXPECTED)
def test_golden_case_through_the_api(client, runs, patient_id):
    cid, accepted = runs[patient_id]
    view = InvestigationView.model_validate(client.get(accepted.poll_url).json())
    assert view.run.run_status.value == "COMPLETED"
    assert (view.state.outcome.value, view.state.stop_reason.value) == EXPECTED[patient_id]
    assert view.state.progress_status.value == "BRIEF_READY" and view.state.next_action is None
    assert [a.step for a in view.trail] == list(range(1, view.state.investigation_step + 1))
    # Without an LLM configured, FULL mode decides every step with the deterministic fallback.
    assert {a.planner.source.value for a in view.trail} == {"RULE_FALLBACK"}

    brief = InvestigationBrief.model_validate(client.get(f"/api/v1/cases/{cid}/brief").json())
    assert (brief.outcome.value, brief.stop_reason.value) == EXPECTED[patient_id]
    assert brief.traceability.material_statements == brief.traceability.with_evidence

    detail = CaseDetail.model_validate(client.get(f"/api/v1/cases/{cid}").json())
    assert detail.progress_status.value == "BRIEF_READY" and detail.brief_available
    assert detail.outcome.value == EXPECTED[patient_id][0]
    assert detail.latest_run.run_id == accepted.run_id


def test_evidence_list_and_detail_carry_provenance(client, runs):
    cid, _ = runs["PAT-000001"]
    evidence = EvidenceList.model_validate(client.get(f"/api/v1/cases/{cid}/evidence").json())
    assert evidence.total > 0
    notes = [e for e in evidence.items if e.source_type.value == "CLINICAL_NOTE"]
    detail = EvidenceDetail.model_validate(client.get(f"/api/v1/evidence/{notes[0].evidence_id}").json())
    src = detail.source
    assert src.text[src.highlight.char_start : src.highlight.char_end] == detail.source_excerpt
    explaining = client.get(f"/api/v1/cases/{cid}/evidence", params={"category": "EXPLAINING_CONTEXT"}).json()
    assert explaining["total"] and all(e["relevance_category"] == "EXPLAINING_CONTEXT" for e in explaining["items"])


def test_every_brief_evidence_id_resolves(client, runs):
    for cid, _ in runs.values():
        brief = client.get(f"/api/v1/cases/{cid}/brief").json()
        for evidence_id in brief["provenance"]["evidence_ids"]:
            assert client.get(f"/api/v1/evidence/{evidence_id}").status_code == 200


def test_timeline_links_evidence_to_episodes(client, runs):
    cid, _ = runs["PAT-000001"]
    tl = EpisodeTimeline.model_validate(client.get(f"/api/v1/cases/{cid}/episodes").json())
    readmission = next(e for e in tl.episodes if e.episode_id == "EPI-000102")
    assert readmission.evidence_ids


def test_queue_reflects_progress_and_outcomes(client, runs):
    done = client.get("/api/v1/cases", params={"progress_status": "BRIEF_READY"}).json()
    assert done["total"] == len(EXPECTED)
    conflicting = client.get("/api/v1/cases", params={"outcome": "EVIDENCE_CONFLICTING"}).json()
    assert [c["patient_id"] for c in conflicting["items"]] == ["PAT-000005"]


def test_second_start_without_rerun_is_rejected_and_rerun_creates_a_new_run(client, runs):
    cid, first = runs["PAT-000003"]
    again = client.post(f"/api/v1/cases/{cid}/investigate")
    assert again.status_code == 409 and again.json()["error"]["code"] == "INVESTIGATION_ALREADY_COMPLETED"
    rerun = client.post(f"/api/v1/cases/{cid}/investigate", json={"rerun": True})
    assert rerun.status_code == 202
    new_id = rerun.json()["run_id"]
    assert new_id != first.run_id
    history = client.get(f"/api/v1/cases/{cid}/runs").json()
    assert [r["run_id"] for r in history["items"]][:2] == [new_id, first.run_id]
    # The old run stays readable.
    assert client.get(first.poll_url).json()["run"]["run_id"] == first.run_id


def test_start_while_running_is_rejected(client, seeded_db):
    from episight.db.models import CaseRow, InvestigationRunRow
    from episight.db.session import make_session

    cid = case_id(client, "PAT-000008")
    with make_session(seeded_db) as s:
        s.add(
            InvestigationRunRow(
                run_id="RUN-FAKE-ACTIVE",
                case_id=cid,
                mode="FULL",
                run_status="RUNNING",
                step=2,
                max_steps=12,
                config={},
                started_at=datetime.now(UTC),
            )
        )
        s.get(CaseRow, cid).latest_run_id = "RUN-FAKE-ACTIVE"
        s.commit()
    r = client.post(f"/api/v1/cases/{cid}/investigate", json={"rerun": True})
    assert r.status_code == 409 and r.json()["error"]["code"] == "INVESTIGATION_IN_PROGRESS"


def test_interrupted_runs_are_marked_failed_on_startup(client, seeded_db):
    from episight.db.models import CaseRow, InvestigationRunRow
    from episight.db.session import make_session
    from episight.services.investigations import recover_interrupted_runs

    cid = case_id(client, "PAT-000008")
    with make_session(seeded_db) as s:
        assert "RUN-FAKE-ACTIVE" in recover_interrupted_runs(s)
        run = s.get(InvestigationRunRow, "RUN-FAKE-ACTIVE")
        assert (run.run_status, run.stop_reason) == ("FAILED", "INTERRUPTED")
        assert s.get(CaseRow, cid).progress_status == "INVESTIGATION_FAILED"
    assert client.get(f"/api/v1/cases/{cid}/brief").status_code == 409


def test_unknown_run_id_is_404(client, runs):
    cid, _ = runs["PAT-000001"]
    r = client.get(f"/api/v1/cases/{cid}/investigation", params={"run_id": "RUN-NOPE"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "RUN_NOT_FOUND"


def test_rules_only_mode_through_the_api(client):
    cid = case_id(client, "PAT-000008")
    r = client.post(f"/api/v1/cases/{cid}/investigate", json={"mode": "RULES_ONLY", "rerun": True})
    assert r.status_code == 202
    view = client.get(r.json()["poll_url"]).json()
    assert (view["state"]["outcome"], view["state"]["stop_reason"]) == ("EVIDENCE_UNAVAILABLE", "NO_ACTIONABLE_GAP")
