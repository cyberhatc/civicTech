"""Voice turn endpoint: audio (and/or text) in, spoken reply out."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, File, Form, UploadFile

from app.core.logging_conf import get_logger
from app.core.response import envelope
from app.db.database import get_db
from app.services import orchestrator
from app.services.stt import get_stt
from app.services.tts import get_tts

log = get_logger(__name__)
router = APIRouter(tags=["voice"])

MAX_AUDIO_BYTES = 12 * 1024 * 1024  # 12 MB


@router.post("/voice/turn")
async def voice_turn(
    audio: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    sessionId: str | None = Form(default=None),  # noqa: N815 - matches the wire format
    lang: str | None = Form(default=None),
    channel: str = Form(default="voice"),
) -> dict[str, Any]:
    """Process one voice turn.

    Either `audio` or `text` must be supplied. The reply comes back with a spoken
    audio URL when a TTS provider is reachable, plus a text body that the browser
    can read aloud itself.
    """
    started = time.perf_counter()
    db = get_db()

    transcript_text = (text or "").strip()
    asr_info: dict[str, Any] = {"text": "", "lang": lang or "hi", "confidence": 0.0, "provider": "none"}

    if audio is not None and audio.filename:
        payload = await audio.read()
        if len(payload) > MAX_AUDIO_BYTES:
            return envelope(
                {"error": "audio_too_large", "limitBytes": MAX_AUDIO_BYTES},
                mode="live" if get_stt().available else "mock",
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        transcription = get_stt().transcribe(
            payload,
            filename=audio.filename,
            mime_type=audio.content_type or "audio/webm",
            language_hint=lang,
            prompt="हिंदी, भोजपुरी और अवधी बोली में उत्तर प्रदेश के किसान और नागरिक।",
        )
        asr_info = transcription.to_dict()
        if transcription.ok:
            transcript_text = transcription.text
        elif not transcript_text:
            return envelope(
                {
                    "sessionId": sessionId,
                    "transcript": asr_info,
                    "intent": {"name": "unknown", "confidence": 0, "language": asr_info.get("lang", "hi"), "entities": {}},
                    "reply": {
                        "text": "मैं आपकी आवाज़ सही से सुन नहीं पाया। कृपया फिर से बोलिए, या नीचे लिखकर भेजिए।",
                        "lang": asr_info.get("lang", "hi"),
                        "speech": "hi-IN-SwaraNeural",
                    },
                    "cards": [],
                    "citations": [],
                    "tickets": [],
                    "quickReplies": [],
                },
                mode="live" if get_stt().available else "mock",
                latency_ms=(time.perf_counter() - started) * 1000,
            )

    if not transcript_text:
        return envelope(
            {
                "sessionId": sessionId,
                "transcript": asr_info,
                "intent": {"name": "unknown", "confidence": 0, "language": "hi", "entities": {}},
                "reply": {"text": "कृपया बोलिए या लिखिए।", "lang": "hi", "speech": "hi-IN-SwaraNeural"},
                "cards": [],
                "citations": [],
                "tickets": [],
                "quickReplies": [],
            },
            mode="live" if get_stt().available else "mock",
            latency_ms=(time.perf_counter() - started) * 1000,
        )

    result = orchestrator.handle_turn(
        transcript_text,
        session_id=sessionId,
        language_hint=lang,
        channel=channel,
        db=db,
    )

    # Speech synthesis (never fatal).
    reply_text = result["reply"]["text"]
    speech = await get_tts().synthesize_async(reply_text, lang=result["intent"].get("language", "hi"))
    if speech.ok:
        result["reply"]["speech"] = speech.voice
        result["reply"]["audioUrl"] = f"/api/voice/audio/{speech.filename}"
    else:
        result["reply"]["audioUrl"] = None
        result["reply"]["speechError"] = speech.error

    result["transcript"] = {**result["transcript"], **asr_info, "text": transcript_text}
    result["mode"] = "live" if get_stt().available or get_tts().health()["edgeTtsAvailable"] else "mock"

    total_ms = (time.perf_counter() - started) * 1000
    return envelope(result, mode=result["mode"], latency_ms=total_ms)


@router.get("/voice/audio/{filename}")
def voice_audio(filename: str) -> Any:
    """Serve a generated mp3."""
    from fastapi.responses import FileResponse

    from app.config import settings

    safe = "".join(ch for ch in filename if ch.isalnum() or ch in "._-")
    path = settings.audio_dir / safe
    if not path.exists() or path.suffix != ".mp3":
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="audio not found")
    return FileResponse(path, media_type="audio/mpeg", filename=safe)


@router.get("/voice/session/{session_id}")
def voice_session(session_id: str) -> dict[str, Any]:
    """Full transcript of a session (used by the admin 'recent calls' panel)."""
    return envelope(orchestrator.history(get_db(), session_id))
