"""Shared pytest fixtures - every test runs against a throwaway database."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Point the app at a temporary database *before* anything imports it.
_TMP = Path(os.environ.get("JANVAANI_TEST_DIR", BACKEND.parent / ".runtime" / "test"))
_TMP.mkdir(parents=True, exist_ok=True)
os.environ["DB_PATH"] = str(_TMP / "test.db")
os.environ["AUDIO_OUT_DIR"] = str(_TMP / "audio")
os.environ.setdefault("GROQ_API_KEY", "")
os.environ.setdefault("LOG_LEVEL", "WARNING")

from app.config import reload_settings  # noqa: E402
from app.db.database import get_db, reset_db  # noqa: E402
from app.db.seed import seed  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _settings():
    reload_settings()


@pytest.fixture()
def db():
    """A freshly seeded database for each test."""
    target = _TMP / "test.db"
    if target.exists():
        target.unlink()
    handle = reset_db(target)
    seed(handle)
    yield handle
    handle.close()


@pytest.fixture()
def client(db):
    """A FastAPI TestClient wired to the test database."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture()
def chat(db):
    """Helper that posts a text turn and returns the parsed payload."""

    def _chat(text: str, session: str | None = None) -> dict:
        from app.services import orchestrator

        payload = {"text": text}
        if session:
            payload["sessionId"] = session
        return orchestrator.handle_turn(text, session_id=session, db=db)

    return _chat


@pytest.fixture(autouse=True)
def _reset_db_singleton():
    """Make sure the global handle points at the test database after each test."""
    yield
    get_db()
