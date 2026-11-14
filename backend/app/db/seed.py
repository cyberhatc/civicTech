"""Idempotent database seeding from the JSON fixtures in `app/data`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.logging_conf import get_logger
from app.db.database import Database, get_db

log = get_logger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load(name: str) -> dict[str, Any]:
    with (DATA_DIR / name).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def seed(db: Database | None = None, *, force: bool = False) -> dict[str, int]:
    """Populate citizens, applications and grievances. Safe to run repeatedly."""
    db = db or get_db()
    counts = {"citizens": 0, "applications": 0, "applicationEvents": 0, "grievances": 0, "notes": 0}

    citizens = _load("citizens.json").get("citizens", [])
    for citizen in citizens:
        existing = db.query_one("SELECT id FROM citizens WHERE id = ?", (citizen["id"],))
        if existing and not force:
            continue
        if existing:
            db.execute("DELETE FROM citizens WHERE id = ?", (citizen["id"],))

        db.insert(
            "citizens",
            {
                "id": citizen["id"],
                "name": citizen["name"],
                "name_hi": citizen.get("name_hi"),
                "gender": citizen.get("gender"),
                "age": citizen.get("age"),
                "aadhaar_last4": citizen["aadhaar_last4"],
                "mobile": citizen["mobile"],
                "district": citizen["district"],
                "block": citizen.get("block"),
                "village": citizen.get("village"),
                "land_bigha": citizen.get("land_bigha", 0),
                "occupation": citizen.get("occupation"),
                "social_category": citizen.get("social_category"),
                "family_members": citizen.get("family_members", 1),
                "income_monthly": citizen.get("income_monthly", 0),
                "language": citizen.get("language", "hi"),
            },
        )
        counts["citizens"] += 1

        for app in citizen.get("applications", []):
            db.insert(
                "applications",
                {
                    "id": app["id"],
                    "citizen_id": citizen["id"],
                    "scheme_id": app["scheme_id"],
                    "status": app["status"],
                    "status_hi": app.get("status_hi"),
                    "amount": app.get("amount", 0),
                    "reference": app.get("reference"),
                    "last_updated": app.get("last_updated"),
                    "created_at": app.get("created_at"),
                },
            )
            counts["applications"] += 1
            for event in app.get("events", []):
                db.insert(
                    "application_events",
                    {
                        "application_id": app["id"],
                        "seq": event.get("seq", 0),
                        "date": event.get("date"),
                        "label": event.get("label"),
                        "label_hi": event.get("label_hi"),
                        "status": event.get("status"),
                    },
                )
                counts["applicationEvents"] += 1

    payload = _load("citizens.json")
    for ticket in payload.get("grievances", []):
        existing = db.query_one("SELECT id FROM grievances WHERE id = ?", (ticket["id"],))
        if existing and not force:
            continue
        if existing:
            db.execute("DELETE FROM grievances WHERE id = ?", (ticket["id"],))
        db.insert(
            "grievances",
            {
                "id": ticket["id"],
                "citizen_name": ticket.get("citizen_name"),
                "contact": ticket.get("contact"),
                "category": ticket["category"],
                "category_hi": ticket.get("category_hi"),
                "issue": ticket.get("issue"),
                "district": ticket.get("district"),
                "block": ticket.get("block"),
                "village": ticket.get("village"),
                "duration_days": ticket.get("duration_days", 0),
                "urgency": ticket.get("urgency", "medium"),
                "sentiment": ticket.get("sentiment", "neutral"),
                "status": ticket.get("status", "NEW"),
                "priority": ticket.get("priority", "P2"),
                "assigned_to": ticket.get("assigned_to"),
                "summary": ticket.get("summary"),
                "summary_en": ticket.get("summary_en"),
                "transcript": ticket.get("transcript"),
                "language": ticket.get("language", "hi"),
                "channel": ticket.get("channel", "voice"),
                "created_at": ticket.get("created_at"),
                "updated_at": ticket.get("created_at"),
            },
        )
        counts["grievances"] += 1
        for note in ticket.get("notes", []):
            db.insert(
                "grievance_notes",
                {
                    "grievance_id": ticket["id"],
                    "note": note["note"],
                    "author": note.get("author", "DM Office"),
                    "created_at": note.get("created_at"),
                },
            )
            counts["notes"] += 1

    log.info("Seed complete: %s", counts)

    # Report the totals that are actually in the database, not just what was
    # inserted during this run (seeding is idempotent).
    totals = {
        "citizens": _count(db, "citizens"),
        "applications": _count(db, "applications"),
        "grievances": _count(db, "grievances"),
    }
    return totals


def _count(db: Database, table: str) -> int:
    row = db.query_one(f"SELECT COUNT(*) AS c FROM {table}")
    return int(row["c"]) if row else 0


def is_seeded(db: Database | None = None) -> bool:
    db = db or get_db()
    row = db.query_one("SELECT COUNT(*) AS c FROM citizens")
    return bool(row and row["c"] > 0)
