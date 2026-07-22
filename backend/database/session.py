"""
Database engine and session management.

SQLite is used as the storage engine (free, zero-ops, file-based — fits
the "100% free stack" requirement). This module exposes:

    - `engine`            the SQLAlchemy Engine
    - `SessionLocal`       a session factory
    - `get_db()`           a FastAPI-style dependency that yields a session
                            and guarantees it is closed afterwards
    - `init_db()`          creates all tables (idempotent)
"""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config.settings import get_settings
from backend.database.models import Base
from backend.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

# `check_same_thread=False` is required because FastAPI/Streamlit may access
# the connection from different threads; safety is preserved because each
# request/session gets its own Session object via get_db()/db_session().
engine = create_engine(
    f"sqlite:///{settings.DATABASE_PATH}",
    connect_args={"check_same_thread": False},
    echo=False,
)


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    """SQLite has foreign keys off by default — turn them on for referential integrity."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create all tables that don't already exist. Safe to call on every startup."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized at %s", settings.DATABASE_PATH)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """
    Context manager for use outside FastAPI request handlers (agents,
    scripts, Streamlit pages). Commits on success, rolls back on error.

    Example:
        with db_session() as db:
            repo = TicketRepository(db)
            repo.create_ticket(...)
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
