"""Groq-backed chat LLM with a deterministic offline twin.

When `GROQ_API_KEY` is absent (or the API is unreachable) every caller transparently
falls back to a rule-based path implemented next to the feature itself, so the demo
always produces a complete, sensible answer - never a stack trace.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx

from app.config import settings
from app.core.logging_conf import get_logger

log = get_logger(__name__)

_JSON_BLOCK = re.compile(r"```(?:json)?\s*(.+?)```", re.S)
_TIMEOUT = 30.0


class LLMUnavailable(RuntimeError):
    """Raised when a live LLM call is required but impossible."""


def extract_json(text: str) -> dict[str, Any] | list[Any] | None:
    """Pull the first JSON object/array out of an LLM response."""
    if not text:
        return None
    text = text.strip()

    fenced = _JSON_BLOCK.search(text)
    if fenced:
        text = fenced.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fall back to the outermost balanced object.
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start == -1:
            continue
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
    return None


class GroqLLM:
    """Thin, robust wrapper over the Groq OpenAI-compatible chat endpoint."""

    def __init__(self) -> None:
        self.api_key = settings.groq_api_key
        self.base_url = settings.groq_base_url.rstrip("/")
        self.model = settings.groq_model
        self.available = bool(self.api_key)
        self.last_error: str | None = None

    # -- plumbing ------------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.post(url, headers=self._headers(), json=payload)
            response.raise_for_status()
            return response.json()

    # -- public API ----------------------------------------------------------
    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.25,
        max_tokens: int = 900,
        response_format: dict[str, Any] | None = None,
        stop: list[str] | None = None,
    ) -> str:
        """Send a chat completion and return the assistant text.

        Raises `LLMUnavailable` when Groq cannot serve the request.
        """
        if not self.available:
            raise LLMUnavailable("GROQ_API_KEY is not configured")

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format
        if stop:
            payload["stop"] = stop

        try:
            data = self._post(payload)
        except Exception as exc:  # network / auth / rate limit
            self.last_error = str(exc)
            log.warning("LLM call failed, falling back to offline path: %s", exc)
            raise LLMUnavailable(str(exc)) from exc

        try:
            return (data["choices"][0]["message"]["content"] or "").strip()
        except (KeyError, IndexError) as exc:
            self.last_error = "malformed response"
            raise LLMUnavailable("malformed LLM response") from exc

    def chat_json(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 700,
    ) -> dict[str, Any] | list[Any] | None:
        """Chat completion that must return JSON.

        A JSON response-format is requested first; if the model ignores it we retry
        once with a stricter instruction before giving up.
        """
        try:
            text = self.chat(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            parsed = extract_json(text)
            if parsed is not None:
                return parsed
        except LLMUnavailable:
            raise

        strict = list(messages) + [
            {
                "role": "user",
                "content": "Respond with a single valid JSON object only. No prose, no markdown fences.",
            }
        ]
        try:
            text = self.chat(strict, temperature=temperature, max_tokens=max_tokens)
        except LLMUnavailable:
            raise
        return extract_json(text)

    def health(self) -> dict[str, Any]:
        return {
            "provider": "groq",
            "model": self.model,
            "available": self.available,
            "lastError": self.last_error,
        }


_llm: GroqLLM | None = None


def get_llm() -> GroqLLM:
    global _llm
    if _llm is None:
        _llm = GroqLLM()
    return _llm


def reset_llm() -> None:
    """Force re-read of the configuration (used by tests)."""
    global _llm
    _llm = None


def mode() -> str:
    return "live" if get_llm().available else "mock"


def wait_for_llm(max_wait: float = 0.0) -> None:  # pragma: no cover - helper
    """Placeholder for future warm-up logic."""
    if max_wait > 0:
        time.sleep(0)
