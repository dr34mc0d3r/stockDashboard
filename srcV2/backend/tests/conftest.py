"""Shared test fixtures: the FastAPI app wired to an in-memory SQLite DB.

The real app talks to MariaDB; tests swap that for SQLite by overriding the
`get_session` dependency — the one seam every router goes through. StaticPool +
check_same_thread=False make the single in-memory database visible across
threads (TestClient drives the app from a worker thread).

Isolation strategy: drop and recreate all tables per test. Slower than
transaction tricks, but completely obvious — every test starts truly empty.

Note: `TestClient(app)` is deliberately used without a `with` block so the
app's lifespan (which migrates the *real* database) never runs in tests.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db import Base, get_session
from main import app

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _override_get_session():
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


app.dependency_overrides[get_session] = _override_get_session


@pytest.fixture()
def session():
    """A SQLAlchemy session against freshly recreated, empty tables."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    s = TestingSession()
    yield s
    s.close()


@pytest.fixture()
def client(session):
    """A TestClient sharing the same in-memory DB as `session`."""
    return TestClient(app)
