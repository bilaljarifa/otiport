# -*- coding: utf-8 -*-
"""Ensures `backend` (and other top-level Optiport packages) import cleanly
regardless of the directory pytest is invoked from.

Also points the backend at an isolated, disposable SQLite file for the whole
test session — set via environment variables *before* `backend.db` (or
anything importing it) is ever imported, so the engine `backend.db` builds at
import time already targets the test database. This never touches the real
dev database (`optiport.db`) and never depends on a real `AUTH_SECRET_KEY`.
"""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TEST_DB_PATH = Path(tempfile.gettempdir()) / f"optiport_test_{os.getpid()}.db"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB_PATH}")
os.environ.setdefault("AUTH_SECRET_KEY", "test-secret-key-do-not-use-in-production")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import api as api_module  # noqa: E402
from backend import crud  # noqa: E402
from backend.db import Base, SessionLocal, engine  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_db():
    """Fresh schema before every test — full isolation between tests without
    paying for a new engine/connection each time."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def client() -> TestClient:
    with TestClient(api_module.app) as c:
        yield c


@pytest.fixture()
def register_user(client: TestClient):
    """Factory fixture: `register_user(username="bob")` registers through the
    real API and returns the `TokenResponse` body (`access_token` + `user`)."""

    def _register(*, username: str = "alice", email: str | None = None,
                  password: str = "password123", full_name: str = "Alice Anderson") -> dict:
        response = client.post("/auth/register", json={
            "username": username,
            "email": email or f"{username}@example.com",
            "password": password,
            "full_name": full_name,
        })
        assert response.status_code == 201, response.text
        return response.json()

    return _register


@pytest.fixture()
def make_admin():
    """Factory fixture creating an admin directly at the DB layer, bypassing
    the API — there is deliberately no public "register as admin" endpoint."""

    def _make_admin(*, username: str = "admin", password: str = "adminpass123",
                     full_name: str = "Site Admin") -> int:
        db = SessionLocal()
        try:
            user = crud.create_user(
                db, username=username, email=f"{username}@example.com",
                password=password, full_name=full_name, role="admin",
            )
            return user.id
        finally:
            db.close()

    return _make_admin
