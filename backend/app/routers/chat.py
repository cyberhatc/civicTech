"""Text-first conversation endpoint (low-bandwidth fallback and demo script)."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.response import envelope
from app.db.database import get_db
from app.services import orchestrator
from app.services.tts import get_tts

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    text: str = Field(default="", max_length=2000)
    sessionId: str | None = Field(default=None)  # noqa: N815 - matches the wire format
    lang: str | None = Field(default=None)
    channel: str = Field(default="text")
    speak: bool = Field(default=True)


@router.post("/chat/text")
async def chat_text(payload: ChatRequest) -> dict[str, Any]:
    started = time.perf_counter()
    db = get_db()

    result = orchestrator.handle_turn(
        payload.text,
        session_id=payload.sessionId,
        language_hint=payload.lang,
        channel=payload.channel,
        db=db,
    )

    if payload.speak:
        speech = await get_tts().synthesize_async(
            result["reply"]["text"], lang=result["intent"].get("language", "hi")
        )
        if speech.ok:
            result["reply"]["speech"] = speech.voice
            result["reply"]["audioUrl"] = f"/api/voice/audio/{speech.filename}"
        else:
            result["reply"]["audioUrl"] = None
    else:
        result["reply"]["audioUrl"] = None

    return envelope(result, mode="live" if get_tts().health()["edgeTtsAvailable"] else "mock",
                    latency_ms=(time.perf_counter() - started) * 1000)
