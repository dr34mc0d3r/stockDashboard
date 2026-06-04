"""SQLAlchemy engine, session factory, and declarative base for MariaDB."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import DATABASE_URL

# pool_pre_ping avoids stale-connection errors against the remote MariaDB box,
# which may drop idle connections. echo can be flipped on for SQL debugging.
#
# connect_timeout bounds the TCP connect to the remote DB. Without it, if the
# box is down/slow the startup `create_all` blocks in a C-level socket connect
# that holds the GIL — so Ctrl+C can't be handled until the OS connect timeout
# (~75s). A short timeout keeps startup fast and the process interruptible.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True,
    connect_args={"connect_timeout": 5},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a session and always closes it."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# The one annotation every router handler uses for its DB session. Writing
# `session: SessionDep` keeps handler signatures short and gives tests a single
# dependency (get_session) to override.
SessionDep = Annotated[Session, Depends(get_session)]
