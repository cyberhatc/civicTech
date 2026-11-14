"""WhatsApp Cloud API stub.

The webhook is intentionally dumb: WhatsApp delivers a text message, we run the very
same orchestrator the PWA uses, and we reply with text. Wiring a real number only
requires setting `WHATSAPP_PHONE_NUMBER_ID` and `WHATSAPP_ACCESS_TOKEN`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request, Response

from app.config import settings
from app.core.logging_conf import get_logger
from app.core.response import envelope
from app.db.database import get_db
from app.services import orchestrator

log = get_logger(__name__)
router = APIRouter(tags=["whatsapp"])


@router.get("/whatsapp/verify")
def verify(
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
) -> Response:
    """Meta webhook verification handshake."""
    if hub_verify_token and hub_verify_token == settings.whatsapp_verify_token:
        return Response(content=hub_challenge or "", media_type="text/plain")
    return Response(content="verification failed", status_code=403, media_type="text/plain")


@router.post("/whatsapp/webhook")
async def webhook(request: Request) -> dict[str, Any]:
    """Accept an inbound WhatsApp message and answer it."""
    payload = await request.json()
    entry = (payload.get("entry") or [{}])[0]
    change = (entry.get("changes") or [{}])[0]
    value = change.get("value") or {}
    messages = value.get("messages") or []

    replies: list[dict[str, Any]] = []
    for message in messages:
        text = ((message.get("text") or {}).get("body") or "").strip()
        if not text:
            continue
        from_number = message.get("from", "")
        session_id = f"wa_{from_number}" if from_number else None
        result = orchestrator.handle_turn(
            text, session_id=session_id, language_hint="hi", channel="whatsapp", db=get_db()
        )
        replies.append({"to": from_number, "text": result["reply"]["text"], "sessionId": result["sessionId"]})
        log.info("WhatsApp turn handled for session %s", result["sessionId"])

    return envelope({"processed": len(replies), "replies": replies, "mode": "stub"})
