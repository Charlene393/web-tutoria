from __future__ import annotations

from threading import Lock

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from fastapi import HTTPException, status

from ..core.config import settings
from .models import Base


def _build_engine():
    connect_args: dict[str, object] = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(
        settings.database_url,
        future=True,
        connect_args=connect_args,
    )


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

_schema_lock = Lock()
_schema_initialized = False


def initialize_database() -> None:
    global _schema_initialized

    if _schema_initialized:
        return

    with _schema_lock:
        if _schema_initialized:
            return
        try:
            Base.metadata.create_all(bind=engine)
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Database connection failed. Check that PostgreSQL is running "
                    "and that DATABASE_URL points to a reachable database."
                ),
            ) from exc
        _schema_initialized = True


def get_db() -> Session:
    initialize_database()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
