from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from episight.config import get_settings


@lru_cache
def get_engine(url: str | None = None) -> Engine:
    return create_engine(url or get_settings().database_url, pool_pre_ping=True)


def make_session(url: str | None = None) -> Session:
    return sessionmaker(bind=get_engine(url), expire_on_commit=False)()


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    session = make_session()
    try:
        yield session
    finally:
        session.close()
