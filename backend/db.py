# -*- coding: utf-8 -*-
"""Database engine and session management.

SQLite for now (`backend.config.database_url`), via SQLAlchemy. `init_db()`
is additive and idempotent — safe to call on every startup. `create_all()`
only creates tables that don't exist yet; it never alters an existing one,
so a new *column* on an already-existing table (like `users.google_sub`,
added after accounts already existed) needs the small explicit migration
below instead. Still no destructive migration tooling (Alembic) — the one
column added so far doesn't warrant it, and this keeps the same "no data
existed yet" simplicity for everything that predates it.
"""

from __future__ import annotations

from typing import Iterator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config import database_url

_URL = database_url()
_connect_args = {"check_same_thread": False} if _URL.startswith("sqlite") else {}

engine = create_engine(_URL, connect_args=_connect_args)


@event.listens_for(Engine, "connect")
def _enable_sqlite_fk(dbapi_connection, _connection_record) -> None:
    """SQLite ignores foreign keys (and therefore ON DELETE CASCADE) unless
    this pragma is set per-connection."""
    if _URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def _migrate_added_columns() -> None:
    """Additive, idempotent column patches for tables that may already
    exist from before the column was introduced. Checks first, so it's a
    no-op on a fresh database (create_all() above already made the final
    shape) and safe to run on every startup. Never touches existing rows."""
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("users")}
    if "google_sub" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN google_sub VARCHAR(64)"))
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_sub ON users (google_sub)"
            ))


def init_db() -> None:
    from backend import models  # noqa: F401 - register models on Base

    Base.metadata.create_all(bind=engine)
    _migrate_added_columns()


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
