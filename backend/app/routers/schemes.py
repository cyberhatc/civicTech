"""Scheme discovery, detail and grounded Q&A."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.response import envelope
from app.services import rag, schemes

router = APIRouter(tags=["schemes"])


class SearchRequest(BaseModel):
    query: str = Field(default="", max_length=1000)
    lang: str | None = Field(default=None)
    topK: int = Field(default=3, ge=1, le=10)  # noqa: N815 - matches the wire format


@router.get("/schemes")
def list_schemes() -> dict[str, Any]:
    return envelope(
        {
            "schemes": rag.all_schemes_summary(),
            "cards": schemes.list_cards(),
        }
    )


@router.get("/schemes/{scheme_id}")
def scheme_detail(scheme_id: str) -> dict[str, Any]:
    scheme = rag.get_scheme(scheme_id)
    if not scheme:
        raise HTTPException(status_code=404, detail="scheme not found")
    return envelope({"scheme": scheme, "card": schemes.scheme_card(scheme_id)})


@router.post("/schemes/search")
def search_schemes(payload: SearchRequest) -> dict[str, Any]:
    started = time.perf_counter()
    if not payload.query.strip():
        return envelope({"answer": "", "citations": [], "schemes": []})
    result = schemes.answer_question(payload.query, top_k=payload.topK)
    return envelope(result, latency_ms=(time.perf_counter() - started) * 1000)
