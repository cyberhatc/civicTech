"""Text-to-speech: edge-tts (free, high-quality Hindi) with a Bhashini fallback.

If neither provider is reachable the service returns `None` and the frontend falls
back to the browser's Web Speech API - the demo always speaks.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.logging_conf import get_logger

log = get_logger(__name__)

try:  # optional dependency
    import edge_tts  # type: ignore

    EDGE_TTS_AVAILABLE = True
except Exception:  # pragma: no cover - depends on the environment
    edge_tts = None  # type: ignore
    EDGE_TTS_AVAILABLE = False

# Preferred voices, most specific first. Bhojpuri / Awadhi voices are used when the
# installed edge-tts catalogue exposes them.
_VOICE_PREFERENCE: dict[str, list[str]] = {
    "bho": ["bho-IN-ShaanviNeural", "bho-IN-HemantNeural", "hi-IN-SwaraNeural"],
    "awd": ["hi-IN-MadhurNeural", "awd-IN-???", "hi-IN-SwaraNeural"],
    "hin": ["hi-IN-SwaraNeural", "hi-IN-AaravNeural", "hi-IN-AnanyaNeural", "hi-IN-MadhurNeural"],
    "en": ["en-IN-NeerjaNeural", "en-US-AriaNeural"],
}

_DEFAULT_VOICE = "hi-IN-SwaraNeural"

_voice_cache: list[str] | None = None


@dataclass
class Speech:
    """Generated audio plus its metadata."""

    audio: bytes | None
    filename: str | None
    voice: str
    provider: str
    error: str | None = None

    @property
    def ok(self) -> bool:
        return bool(self.audio)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hasAudio": bool(self.audio),
            "filename": self.filename,
            "voice": self.voice,
            "provider": self.provider,
            "error": self.error,
        }


def available_voices() -> list[str]:
    """List the edge-tts voices installed (cached)."""
    global _voice_cache
    if _voice_cache is not None:
        return _voice_cache
    if not EDGE_TTS_AVAILABLE:
        _voice_cache = []
        return _voice_cache
    try:
        voices = asyncio.run(edge_tts.list_voices())
        _voice_cache = sorted({v["ShortName"] for v in voices if v.get("ShortName")})
    except Exception as exc:  # pragma: no cover - network dependent
        log.warning("Could not list edge-tts voices: %s", exc)
        _voice_cache = []
    return _voice_cache


def select_voice(lang: str = "hin", female: bool = True) -> str:
    """Pick the best available voice for a language code."""
    voices = available_voices()
    key = (lang or "hin").lower()
    if key not in _VOICE_PREFERENCE:
        key = "hin"
    for candidate in _VOICE_PREFERENCE[key]:
        if not voices or candidate in voices:
            if candidate.endswith("???"):
                continue
            return candidate
    if female and settings.tts_voice_hi:
        return settings.tts_voice_hi
    return _DEFAULT_VOICE


class TTSService:
    """Synthesises speech and caches the resulting mp3 on disk."""

    def __init__(self) -> None:
        self.audio_dir = settings.audio_dir
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.provider = settings.tts_provider.lower()
        self.last_error: str | None = None

    # -- providers -----------------------------------------------------------
    def _synthesize_edge_sync(self, text: str, voice: str) -> bytes | None:
        """edge-tts renders to a temp file; this is the blocking worker."""
        if not EDGE_TTS_AVAILABLE:
            return None
        import tempfile

        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            communicate = edge_tts.Communicate(text, voice, rate=settings.tts_rate, pitch=settings.tts_pitch)
            asyncio.run(communicate.save(str(tmp_path)))
            data = tmp_path.read_bytes()
            tmp_path.unlink(missing_ok=True)
            return data or None
        except Exception as exc:
            self.last_error = f"edge-tts: {exc}"
            log.warning("edge-tts synthesis failed: %s", exc)
            return None

    def _synthesize_bhashini(self, text: str, lang: str) -> bytes | None:
        if not settings.bhashini_api_key:
            return None
        try:
            import httpx

            payload = {
                "text": text,
                "lang": {"hi": "hi", "bho": "hi", "awd": "hi"}.get(lang, "hi"),
                "category": "tts",
                "model": "vits",
                "speaker": "female",
                "format": "mp3",
            }
            with httpx.Client(timeout=45.0) as client:
                response = client.post(
                    f"{settings.bhashini_base_url}/synthesize",
                    headers={"api-key": settings.bhashini_api_key, "Content-Type": "application/json"},
                    json=payload,
                )
                response.raise_for_status()
                return response.content
        except Exception as exc:
            self.last_error = f"bhashini: {exc}"
            log.warning("Bhashini synthesis failed: %s", exc)
            return None

    # -- public API ----------------------------------------------------------
    def synthesize(self, text: str, lang: str = "hin") -> Speech:
        """Produce speech audio for `text`. Returns `hasAudio=False` on failure."""
        cleaned = (text or "").strip()
        if not cleaned:
            return Speech(audio=None, filename=None, voice=_DEFAULT_VOICE, provider="none", error="empty text")

        voice = select_voice(lang)
        digest = hashlib.sha1(f"{voice}|{cleaned}".encode("utf-8")).hexdigest()[:16]
        filename = f"tts_{digest}.mp3"
        target = self.audio_dir / filename

        if target.exists() and target.stat().st_size > 0:
            return Speech(
                audio=target.read_bytes(),
                filename=filename,
                voice=voice,
                provider=self._last_provider(target) or "cache",
            )

        provider_order: list[str]
        if self.provider == "edge":
            provider_order = ["edge"]
        elif self.provider == "bhashini":
            provider_order = ["bhashini"]
        elif self.provider == "none":
            provider_order = []
        else:
            provider_order = ["edge", "bhashini"]

        for provider in provider_order:
            data = (
                self._synthesize_edge_sync(cleaned, voice)
                if provider == "edge"
                else self._synthesize_bhashini(cleaned, lang)
            )
            if data:
                target.write_bytes(data)
                return Speech(audio=data, filename=filename, voice=voice, provider=provider)

        return Speech(
            audio=None,
            filename=None,
            voice=voice,
            provider="none",
            error=self.last_error or "No TTS provider available - the browser will read the reply aloud.",
        )

    @staticmethod
    def _last_provider(_target: Path) -> str | None:
        return None

    async def synthesize_async(self, text: str, lang: str = "hin") -> Speech:
        """Async wrapper - edge-tts is blocking, so it runs in a worker thread."""
        import anyio.to_thread

        return await anyio.to_thread.run_sync(self.synthesize, text, lang)

    def health(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "edgeTtsAvailable": EDGE_TTS_AVAILABLE,
            "bhashiniAvailable": bool(settings.bhashini_api_key),
            "voices": len(available_voices()),
            "defaultVoice": _DEFAULT_VOICE,
            "lastError": self.last_error,
        }


_tts: TTSService | None = None


def get_tts() -> TTSService:
    global _tts
    if _tts is None:
        _tts = TTSService()
    return _tts


def reset_tts() -> None:
    global _tts
    _tts = None


logging.getLogger("edge_tts").setLevel(logging.WARNING)
