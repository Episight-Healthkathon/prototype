"""Database outage: health reports 503 with its own shape, every other endpoint the 503 error envelope."""

import pytest
from fastapi.testclient import TestClient

from episight.db.session import get_session, make_session
from episight.main import create_app

DEAD_DB = "postgresql+psycopg://episight:episight@127.0.0.1:1/episight?connect_timeout=1"


@pytest.fixture(scope="module")
def dead_client():
    app = create_app()

    def _session():
        session = make_session(DEAD_DB)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = _session
    with TestClient(app) as c:  # startup recovery must tolerate the outage too
        yield c


def test_health_reports_degraded(dead_client):
    r = dead_client.get("/api/v1/health")
    assert r.status_code == 503
    assert r.json() == {
        "status": "degraded",
        "db": "down",
        "policy_index": "down",
        "dataset_version": None,
        "corpus_version": None,
    }


@pytest.mark.parametrize("path", ["/api/v1/cases", "/api/v1/cases/CASE-RA-x", "/api/v1/evidence/EV-x"])
def test_read_endpoints_return_the_503_envelope(dead_client, path):
    r = dead_client.get(path)
    assert r.status_code == 503
    body = r.json()["error"]
    assert body["code"] == "SERVICE_UNAVAILABLE" and body["request_id"] == r.headers["X-Request-ID"]


def test_starting_an_investigation_during_an_outage_is_a_clean_503(dead_client):
    r = dead_client.post("/api/v1/cases/CASE-RA-x/investigate")
    assert r.status_code == 503 and r.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
