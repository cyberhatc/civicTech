"""Health / capability endpoint - the frontend uses it to show LIVE vs MOCK."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.config import settings
from app.core.response import envelope
from app.db.database import get_db
from app.db.seed import is_seeded
from app.services import rag
from app.services.llm import get_llm
from app.services.stt import get_stt
from app.services.tts import get_tts

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, Any]:
    llm = get_llm()
    stt = get_stt()
    tts = get_tts()
    db = get_db()
    return envelope(
        {
            "status": "ok",
            "service": "janvaani-up",
            "version": "1.0.0",
            "mode": "live" if llm.available else "mock",
            "llm": llm.health(),
            "asr": stt.health(),
            "tts": tts.health(),
            "vector": {
                "backend": settings.vector_backend,
                "chunks": len(rag.get_retriever().chunks),
                "schemes": len(rag.load_schemes()),
            },
            "database": {
                "engine": "sqlite",
                "path": str(settings.db_file),
                "seeded": is_seeded(db),
            },
            "languages": ["hi", "bho", "awd", "hinglish"],
        },
        mode="live" if llm.available else "mock",
    )
