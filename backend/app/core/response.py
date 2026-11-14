"""Uniform API response envelope and error handling."""

from __future__ import annotations

import time
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """Raised anywhere in the app to produce a structured error response."""

    def __init__(self, status_code: int, code: str, message: str, detail: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.detail = detail


def envelope(
    data: Any,
    *,
    mode: str = "live",
    latency_ms: float | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {"mode": mode}
    if latency_ms is not None:
        meta["latencyMs"] = round(latency_ms, 1)
    if extra:
        meta.update(extra)
    return {"ok": True, "data": data, "meta": meta}


def error_envelope(code: str, message: str, detail: Any = None, mode: str = "live") -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message, "detail": detail}, "meta": {"mode": mode}}


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    from app.config import settings

    return JSONResponse(
        status_code=exc.status_code,
        content=error_envelope(exc.code, exc.message, exc.detail, mode="live" if settings.llm_available else "mock"),
    )


class Timer:
    """Tiny helper for measuring per-stage latency."""

    def __init__(self) -> None:
        self.marks: dict[str, float] = {}
        self._start = time.perf_counter()

    def mark(self, name: str) -> None:
        self.marks[name] = round((time.perf_counter() - self._start) * 1000, 1)

    @property
    def total_ms(self) -> float:
        return round((time.perf_counter() - self._start) * 1000, 1)
