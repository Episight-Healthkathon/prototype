import os
from pathlib import Path

import pytest

API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = API_DIR.parents[1]
FIXTURES = API_DIR / "tests" / "fixtures"
DATASET_DIR = FIXTURES / "dataset" / "v0-interim"
POLICY_DIR = FIXTURES / "policies" / "pc-0-interim"
SHARED_TYPES = REPO_ROOT / "packages" / "shared-types"

TEST_DATABASE_URL = os.environ.get(
    "EPISIGHT_TEST_DATABASE_URL", "postgresql+psycopg://episight:episight@localhost:5433/episight_test"
)


@pytest.fixture(scope="session")
def dataset():
    from episight.ingest.loader import load_dataset

    return load_dataset(DATASET_DIR)


@pytest.fixture(scope="session")
def migrated_db():
    """Migrated test database. Skips DB tests when PostgreSQL is not running."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import OperationalError

    from alembic import command

    try:
        with create_engine(TEST_DATABASE_URL).connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError:
        pytest.skip("test database unavailable; run `docker compose up -d` from the repo root")

    from episight.cli import _alembic_config

    cfg = _alembic_config(TEST_DATABASE_URL)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    return TEST_DATABASE_URL


@pytest.fixture(scope="module")
def seeded_db(migrated_db, dataset):
    """Freshly seeded data for each test module, so modules that start investigations stay independent."""
    from episight.db.session import make_session
    from episight.ingest.loader import load_policies
    from episight.ingest.seed import seed

    with make_session(migrated_db) as session:
        seed(session, dataset, load_policies(POLICY_DIR), str(DATASET_DIR), str(POLICY_DIR))
    return migrated_db


@pytest.fixture(scope="module")
def client(seeded_db):
    from fastapi.testclient import TestClient

    from episight.api.routers.cases import get_run_executor
    from episight.db.session import get_session, make_session
    from episight.main import create_app
    from episight.services.investigations import execute_run

    app = create_app()

    def _session():
        session = make_session(seeded_db)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_run_executor] = lambda: lambda run_id: execute_run(run_id, seeded_db)
    with TestClient(app) as c:
        yield c
