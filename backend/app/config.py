"""Application configuration.

Every AI credential is optional. When a key is missing the corresponding service
transparently degrades to a deterministic offline twin so the live demo never dies.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent


class Settings(BaseSettings):
    """Runtime settings loaded from environment / `.env`."""

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Groq (chat LLM + Whisper ASR) --------------------------------------
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    groq_stt_model: str = "whisper-large-v3"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    # --- Bhashini (optional native-dialect ASR/TTS) -------------------------
    bhashini_api_key: str = ""
    bhashini_base_url: str = "https://api.bhashini.ai/v1"

    # --- Text to speech ------------------------------------------------------
    tts_provider: str = "auto"  # auto | edge | bhashini | none
    tts_voice_hi: str = "hi-IN-SwaraNeural"
    tts_voice_m: str = "hi-IN-MadhurNeural"
    tts_rate: str = "+0%"
    tts_pitch: str = "+0Hz"

    # --- Vector backend ------------------------------------------------------
    vector_backend: str = "local"  # local | chroma

    # --- Storage -------------------------------------------------------------
    db_path: str = str(PROJECT_ROOT / ".runtime" / "janvaani.db")
    audio_out_dir: str = str(PROJECT_ROOT / ".runtime" / "audio")

    # --- Server --------------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    log_level: str = "INFO"

    # --- WhatsApp stub -------------------------------------------------------
    whatsapp_verify_token: str = "janvaani_up_verify_token"
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""

    # --- Derived -------------------------------------------------------------
    llm_available: bool = Field(default=False, exclude=True)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def db_file(self) -> Path:
        p = Path(self.db_path)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p

    @property
    def audio_dir(self) -> Path:
        p = Path(self.audio_out_dir)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p

    def ensure_dirs(self) -> None:
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    # A key that is present but only whitespace counts as absent.
    settings.groq_api_key = settings.groq_api_key.strip()
    settings.bhashini_api_key = settings.bhashini_api_key.strip()
    settings.llm_available = bool(settings.groq_api_key)
    return settings


def reload_settings() -> Settings:
    """Clear the cache and re-read the environment (used by tests)."""
    get_settings.cache_clear()
    return get_settings()


# Keep a module-level instance for convenience.
settings = get_settings()

# Silence noisy third-party loggers in the console.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
