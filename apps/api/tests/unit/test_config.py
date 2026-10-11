"""Settings: database URLs from managed hosts work without hand-editing the driver."""

import pytest

from episight.config import Settings


@pytest.mark.parametrize(
    "given",
    [
        "postgres://u:p@db.example.com/episight?sslmode=require",
        "postgresql://u:p@db.example.com/episight?sslmode=require",
        "postgresql+psycopg://u:p@db.example.com/episight?sslmode=require",
    ],
)
def test_database_url_uses_psycopg_driver(given):
    settings = Settings(database_url=given, _env_file=None)
    assert settings.database_url == "postgresql+psycopg://u:p@db.example.com/episight?sslmode=require"
