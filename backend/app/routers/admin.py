"""District Magistrate / officer analytics endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.core.response import envelope
from app.db.database import get_db
from app.services import analytics

router = APIRouter(tags=["admin"])


@router.get("/admin/stats")
def stats() -> dict[str, Any]:
    db = get_db()
    return envelope({"stats": analytics.stats(db), "feed": analytics.live_feed(db, limit=25)})


@router.get("/admin/feed")
def feed(limit: int = Query(default=25, ge=1, le=100)) -> dict[str, Any]:
    return envelope({"feed": analytics.live_feed(get_db(), limit=limit)})
