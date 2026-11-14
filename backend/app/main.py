"""JanVaani UP - FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.logging_conf import configure_logging, get_logger
from app.core.response import ApiError, api_error_handler, error_envelope
from app.db.database import get_db
from app.db.seed import seed

log = get_logger(__name__)

DESCRIPTION = """
**JanVaani UP (जनवाणी यूपी)** - a voice-first, dialect-aware citizen assistant for
Uttar Pradesh government schemes.

* Speak in **Hindi, Bhojpuri or Awadhi**
* Ask which **scheme you qualify for**
* Track **ration card / PM-KISAN / pension** status
* Lodge a **grievance** by voice and get an IGRS-style tracking number

Every AI call degrades gracefully: with no API key the assistant still answers,
just with a deterministic offline engine instead of a live model.
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.log_level)
    settings.ensure_dirs()
    db = get_db()
    try:
        counts = seed(db)
        log.info(
            "Seed verified: %s citizens, %s applications, %s grievances in the database",
            counts["citizens"],
            counts["applications"],
            counts["grievances"],
        )
    except Exception as exc:  # pragma: no cover - the app must still boot
        log.error("Seeding failed: %s", exc)
    log.info("JanVaani UP ready - mode=%s", "live" if settings.groq_api_key else "mock")
    yield
    log.info("JanVaani UP shutting down")


def create_app() -> FastAPI:
    configure_logging(settings.log_level)

    app = FastAPI(
        title="JanVaani UP API",
        description=DESCRIPTION,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]

    from app.routers import admin, applications, chat, grievances, health, schemes, voice, whatsapp

    api_prefix = "/api"
    app.include_router(health.router, prefix=api_prefix)
    app.include_router(voice.router, prefix=api_prefix)
    app.include_router(chat.router, prefix=api_prefix)
    app.include_router(schemes.router, prefix=api_prefix)
    app.include_router(grievances.router, prefix=api_prefix)
    app.include_router(applications.router, prefix=api_prefix)
    app.include_router(admin.router, prefix=api_prefix)
    app.include_router(whatsapp.router, prefix=api_prefix)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, Any]:
        return {
            "service": "JanVaani UP",
            "tagline": "आपकी आवाज़, आपकी योजना",
            "docs": "/docs",
            "health": "/api/health",
            "mode": "live" if settings.groq_api_key else "mock",
        }

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:  # pragma: no cover
        log.exception("Unhandled error on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content=error_envelope("internal_error", "कुछ गड़बड़ हो गई। कृपया दोबारा कोशिश करें।", str(exc)),
        )

    return app


app = create_app()
