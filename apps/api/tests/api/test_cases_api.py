"""Read endpoints against a real, seeded PostgreSQL test database (API Contract v1)."""

import pytest

from episight.contracts.api import ApiError, CaseDetail, CaseList, EpisodeTimeline, EvidenceList, Health

pytestmark = pytest.mark.db

GOLDEN_A = "PAT-000001"


def _case_id(client, patient_id):
    items = client.get("/api/v1/cases", params={"q": patient_id}).json()["items"]
    assert len(items) == 1
    return items[0]["case_id"]


def test_health_reports_db_and_versions(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = Health.model_validate(r.json())
    assert (body.db, body.policy_index, body.dataset_version, body.corpus_version) == (
        "ok",
        "ok",
        "v0-interim",
        "pc-0-interim",
    )


def test_every_response_carries_request_id_and_contract_version(client):
    r = client.get("/api/v1/cases", headers={"X-Request-ID": "req-123"})
    assert r.headers["X-Request-ID"] == "req-123"
    assert r.headers["X-Contract-Version"] == "1"


def test_case_queue_lists_all_flagged_cases(client):
    body = CaseList.model_validate(client.get("/api/v1/cases").json())
    assert body.total == 6
    assert all(c.progress_status.value == "FLAGGED" and c.outcome is None for c in body.items)
    dates = [c.index_date for c in body.items]
    assert dates == sorted(dates, reverse=True)


def test_case_queue_filters_sort_and_paginates(client):
    frag = client.get("/api/v1/cases", params={"signal_type": "FRAGMENTATION"}).json()
    assert {c["signal_type"] for c in frag["items"]} == {"FRAGMENTATION"} and frag["total"] == 2
    by_interval = client.get("/api/v1/cases", params={"sort": "min_interval_days"}).json()["items"]
    assert [c["min_interval_days"] for c in by_interval] == sorted(c["min_interval_days"] for c in by_interval)
    page = client.get("/api/v1/cases", params={"limit": 2, "offset": 2}).json()
    assert (len(page["items"]), page["total"], page["limit"], page["offset"]) == (2, 6, 2, 2)
    none = client.get("/api/v1/cases", params={"progress_status": "BRIEF_READY"}).json()
    assert none["total"] == 0


def test_case_detail_has_episode_group_and_signal(client):
    case_id = _case_id(client, GOLDEN_A)
    detail = CaseDetail.model_validate(client.get(f"/api/v1/cases/{case_id}").json())
    assert detail.episode_group_ids == ["EPI-000101", "EPI-000102"]
    assert detail.primary_pair.to_episode_id == "EPI-000102"
    assert detail.signal.pairs[0].interval_days == 5
    assert detail.signal.disclaimer.startswith("A risk signal starts an investigation")
    assert (detail.latest_run, detail.brief_available, detail.stop_reason) == (None, False, None)


def test_episode_timeline(client):
    case_id = _case_id(client, GOLDEN_A)
    tl = EpisodeTimeline.model_validate(client.get(f"/api/v1/cases/{case_id}/episodes").json())
    assert [e.episode_id for e in tl.episodes] == ["EPI-000103", "EPI-000101", "EPI-000102"]
    assert tl.episodes[2].interval_from_previous_days == 5


def test_chain_case_detail_lists_all_pairs(client):
    case_id = _case_id(client, "PAT-000002")
    detail = client.get(f"/api/v1/cases/{case_id}").json()
    assert detail["episode_count"] == 3 and len(detail["signal"]["pairs"]) == 2
    assert detail["min_interval_days"] == 3


def test_unknown_case_returns_contract_error(client):
    r = client.get("/api/v1/cases/CASE-RA-00000000")
    assert r.status_code == 404
    err = ApiError.model_validate(r.json())
    assert err.error.code.value == "CASE_NOT_FOUND" and err.error.request_id == r.headers["X-Request-ID"]


def test_invalid_query_returns_validation_envelope(client):
    r = client.get("/api/v1/cases", params={"limit": 0})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_not_yet_available_endpoints_answer_honestly(client):
    case_id = _case_id(client, GOLDEN_A)
    assert client.post(f"/api/v1/cases/{case_id}/investigate").json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert client.get(f"/api/v1/cases/{case_id}/investigation").json()["error"]["code"] == "RUN_NOT_FOUND"
    assert client.get(f"/api/v1/cases/{case_id}/brief").status_code == 409
    assert EvidenceList.model_validate(client.get(f"/api/v1/cases/{case_id}/evidence").json()).total == 0
    assert client.get("/api/v1/evidence/EV-nope").json()["error"]["code"] == "EVIDENCE_NOT_FOUND"
