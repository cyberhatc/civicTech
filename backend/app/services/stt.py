"""Speech-to-text via Groq's Whisper endpoint (with a graceful "unavailable" state)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import settings
from app.core.logging_conf import get_logger

log = get_logger(__name__)

_TIMEOUT = 60.0

# Whisper language hints we accept from the client.
_LANG_MAP = {
    "hi": "hi",
    "hin": "hi",
    "hindi": "hi",
    "bho": "hi",
    "bhojpuri": "hi",
    "awd": "hi",
    "awadhi": "hi",
    "hif": "hi",
    "hinglish": "hi",
}


@dataclass
class Transcription:
    """Result of a speech-to-text attempt."""

    text: str = ""
    language: str = "hi"
    confidence: float = 0.0
    provider: str = "unavailable"
    duration: float = 0.0
    segments: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return bool(self.text.strip())

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "lang": self.language,
            "confidence": round(self.confidence, 3),
            "provider": self.provider,
            "duration": self.duration,
            "segments": self.segments,
            "error": self.error,
        }


class WhisperSTT:
    """Whisper large-v3 through Groq's OpenAI-compatible audio API."""

    def __init__(self) -> None:
        self.api_key = settings.groq_api_key
        self.base_url = settings.groq_base_url.rstrip("/")
        self.model = settings.groq_stt_model
        self.available = bool(self.api_key)
        self.last_error: str | None = None

    def transcribe(
        self,
        audio: bytes,
        *,
        filename: str = "recording.webm",
        mime_type: str = "audio/webm",
        language_hint: str | None = None,
        prompt: str | None = None,
    ) -> Transcription:
        """Transcribe an audio payload. Never raises - returns an error result."""
        if not audio:
            return Transcription(error="empty audio payload", provider="unavailable")
        if not self.available:
            return Transcription(
                provider="unavailable",
                error="No ASR key configured - the frontend text mode was used instead.",
            )

        hint = _LANG_MAP.get((language_hint or "").lower())
        files = {"file": (filename, audio, mime_type)}
        data: dict[str, Any] = {"model": self.model, "response_format": "verbose_json"}
        if hint:
            data["language"] = hint
        if prompt:
            data["prompt"] = prompt

        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                response = client.post(
                    f"{self.base_url}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files=files,
                    data=data,
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            self.last_error = str(exc)
            log.warning("STT failed: %s", exc)
            return Transcription(provider="groq-whisper", error=str(exc))

        text = (payload.get("text") or "").strip()
        segments = payload.get("segments") or []
        duration = float(payload.get("duration") or 0.0)
        confidence = 0.0
        if segments:
            # Average the per-segment log-probability when Whisper provides it.
            probs = [float(s.get("avg_logprob", 0.0)) for s in segments if "avg_logprob" in s]
            if probs:
                import math

                confidence = sum(math.exp(p) for p in probs) / len(probs)

        return Transcription(
            text=text,
            language=payload.get("language") or (hint or "hi"),
            confidence=confidence,
            provider="groq-whisper",
            duration=duration,
            segments=[
                {"start": s.get("start"), "end": s.get("end"), "text": (s.get("text") or "").strip()}
                for s in segments
            ],
        )

    def health(self) -> dict[str, Any]:
        return {
            "provider": "groq-whisper",
            "model": self.model,
            "available": self.available,
            "lastError": self.last_error,
        }


_stt: WhisperSTT | None = None


def get_stt() -> WhisperSTT:
    global _stt
    if _stt is None:
        _stt = WhisperSTT()
    return _stt


def reset_stt() -> None:
    global _stt
    _stt = None
