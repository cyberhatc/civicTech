"""Grievance (Jansunwai / IGRS) ticket endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.response import envelope
from app.db.database import get_db
from app.services import analytics, grievances

router = APIRouter(tags=["grievances"])


class TicketUpdate(BaseModel):
    status: str | None = Field(default=None)
    priority: str | None = Field(default=None)
    assignedTo: str | None = Field(default=None)  # noqa: N815 - matches the wire format
    district: str | None = Field(default=None)
    block: str | None = Field(default=None)
    village: str | None = Field(default=None)
    category: str | None = Field(default=None)
    note: str | None = Field(default=None)
    author: str = Field(default="DM Office")


@router.get("/tickets")
def list_tickets(
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    district: str | None = Query(default=None),
    urgency: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    db = get_db()
    tickets = grievances.list_tickets(
        db, status=status, category=category, district=district, urgency=urgency, limit=limit
    )
    counts: dict[str, int] = {}
    for ticket in tickets:
        counts[ticket.get("status", "NEW")] = counts.get(ticket.get("status", "NEW"), 0) + 1
    return envelope({"tickets": tickets, "counts": counts, "total": len(tickets)})


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str) -> dict[str, Any]:
    ticket = grievances.get_ticket(get_db(), ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    return envelope({"ticket": ticket})


@router.patch("/tickets/{ticket_id}")
def update_ticket(ticket_id: str, payload: TicketUpdate) -> dict[str, Any]:
    db = get_db()
    if grievances.get_ticket(db, ticket_id) is None:
        raise HTTPException(status_code=404, detail="ticket not found")

    updates = {
        "status": payload.status,
        "priority": payload.priority,
        "assigned_to": payload.assignedTo,
        "district": payload.district,
        "block": payload.block,
        "village": payload.village,
        "category": payload.category,
    }
    try:
        ticket = grievances.update_ticket(db, ticket_id, {k: v for k, v in updates.items() if v})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if payload.note:
        ticket = grievances.add_note(db, ticket_id, payload.note, payload.author)

    return envelope({"ticket": ticket, "stats": analytics.stats(db)})
