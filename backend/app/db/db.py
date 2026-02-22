from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import get_settings

settings = get_settings()


def _postgres_connect_args() -> dict:
    if not settings.database_url.startswith("postgresql"):
        return {}

    options = (
        f"-c statement_timeout={settings.db_statement_timeout_ms} "
        f"-c lock_timeout={settings.db_lock_timeout_ms} "
        f"-c idle_in_transaction_session_timeout={settings.db_idle_tx_timeout_ms}"
    )
    return {
        "connect_timeout": settings.db_connect_timeout_seconds,
        "options": options,
    }

# Create the SQLAlchemy engine and session factory
engine = create_engine(
    settings.database_url,
    future=True,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout_seconds,
    pool_recycle=settings.db_pool_recycle_seconds,
    connect_args=_postgres_connect_args(),
)

# Create a configured "Session" class
SessionLocal = sessionmaker(bind=engine, future=True)

def get_db():
    """Dependency that provides a database session."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
