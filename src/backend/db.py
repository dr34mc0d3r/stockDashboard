"""SQLAlchemy engine, session factory, and declarative base for MariaDB."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import DATABASE_URL

# pool_pre_ping avoids stale-connection errors against the remote MariaDB box,
# which may drop idle connections. echo can be flipped on for SQL debugging.
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)

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
