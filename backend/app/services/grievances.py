"""Grievance (Jansunwai / IGRS) ticket lifecycle."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.core.guardrails import mask_all
from app.core.logging_conf import get_logger
from app.db.database import Database, row_to_dict, utcnow
from app.services.llm import LLMUnavailable, get_llm
from app.services.nlu import CATEGORY_HI, CATEGORY_ICON

log = get_logger(__name__)

STATUSES = ["NEW", "IN_PROGRESS", "RESOLVED", "REJECTED", "ESCALATED"]
PRIORITIES = ["P1", "P2", "P3"]

_ISSUE_LABELS = {
    "electricity": "बिजली आपूर्ति",
    "roads": "सड़क / गड्ढा",
    "water": "पेयजल आपूर्ति",
    "sanitation": "कचरा प्रबंधन",
    "health": "स्वास्थ्य सेवा",
    "education": "शिक्षा",
    "agriculture": "कृषि",
    "housing": "आवास",
    "policing": "पुलिस",
    "others": "अन्य",
}

_SUMMARY_SYSTEM = (
    "You draft a formal government grievance summary in Hindi for a UP district "
    "officer. Use ONLY the facts given: category, issue, place, duration, urgency. "
    "Do not invent a remedy, a deadline or a compensation. Write 2-3 sentences in "
    "formal Hindi (Devanagari). Also return a one-sentence English version under "
    "the key 'en'. Reply with a single JSON object."
)


def next_ticket_id(db: Database) -> str:
    """Allocate the next `JVUP-YYYY-NNNN` identifier."""
    year = datetime.now(timezone.utc).year
    prefix = f"JVUP-{year}-"
    rows = db.query("SELECT id FROM grievances WHERE id LIKE ?", (f"{prefix}%",))
    highest = 0
    for row in rows:
        try:
            highest = max(highest, int(row["id"].split("-")[-1]))
        except (ValueError, IndexError):
            continue
    return f"{prefix}{highest + 1:04d}"


def _priority_for(urgency: str, duration_days: int) -> str:
    if urgency == "high" or duration_days >= 14:
        return "P1"
    if urgency == "medium" or duration_days >= 5:
        return "P2"
    return "P3"


def _offline_summary(category: str, issue: str, place: str, duration: int, urgency: str) -> tuple[str, str]:
    """Deterministic bilingual summary built from the extracted entities."""
    label = _ISSUE_LABELS.get(category, "सामान्य समस्या")
    hindi_parts = []
    if place:
        hindi_parts.append(f"{place} में")
    hindi_parts.append(f"{label} संबंधी शिकायत दर्ज कराई गई है।")
    if issue:
        hindi_parts.append(f"समस्या का विवरण: {issue}।")
    if duration:
        hindi_parts.append(f"समस्या लगभग {duration} दिनों से चल रही है।")
    if urgency == "high":
        hindi_parts.append("मामला उच्च प्राथमिकता का है, कृपया शीघ्र कार्रवाई करें।")
    else:
        hindi_parts.append("कृपया संबंधित विभाग से शीघ्र जाँच करवाएँ।")

    english_parts = [f"A grievance has been registered under {label}"]
    if place:
        english_parts[0] += f" in {place}"
    english_parts[0] += "."
    if issue:
        english_parts.append(f"Issue: {issue}.")
    if duration:
        english_parts.append(f"The issue has persisted for about {duration} days.")
    if urgency == "high":
        english_parts.append("Flagged as high priority for prompt action.")

    return " ".join(hindi_parts), " ".join(english_parts)


def _llm_summary(category: str, issue: str, place: str, duration: int, urgency: str) -> tuple[str, str] | None:
    llm = get_llm()
    if not llm.available:
        return None
    facts = {
        "category": CATEGORY_HI.get(category, category),
        "issue": issue,
        "place": place,
        "durationDays": duration,
        "urgency": urgency,
    }
    messages = [
        {"role": "system", "content": _SUMMARY_SYSTEM},
        {"role": "user", "content": f"FACTS:\n{facts}"},
    ]
    try:
        payload = llm.chat_json(messages, temperature=0.1, max_tokens=500)
    except LLMUnavailable:
        return None
    if not isinstance(payload, dict):
        return None
    hindi = str(payload.get("hi") or payload.get("summary") or "").strip()
    english = str(payload.get("en") or payload.get("summary_en") or "").strip()
    if not hindi:
        return None
    return hindi, english


def create_ticket(
    db: Database,
    entities: dict[str, Any],
    *,
    transcript: str = "",
    language: str = "hi",
    channel: str = "voice",
) -> dict[str, Any]:
    """Create a grievance ticket from extracted entities."""
    category = entities.get("category") or "others"
    if category not in CATEGORY_HI:
        category = "others"

    issue = str(entities.get("issue") or "").strip()
    if not issue:
        # No LLM extraction available - fall back to the citizen's own words.
        snippet = re.split(r"[.?!,]", (transcript or "").strip())[0].strip()
        issue = snippet[:180] if snippet else _ISSUE_LABELS.get(category, "सामान्य समस्या")
    # Never persist raw identifiers that the citizen may have spoken.
    issue = mask_all(issue)
    transcript = mask_all(transcript)

    district = entities.get("district")
    block = entities.get("block")
    village = entities.get("village")
    place_parts = [p for p in [village, block, district] if p]
    place = ", ".join(place_parts)

    duration = int(entities.get("durationDays") or 0)
    urgency = entities.get("urgency") or ("medium" if duration >= 5 else "low")
    if urgency not in ("low", "medium", "high"):
        urgency = "medium"
    sentiment = entities.get("sentiment") or "neutral"

    summary = _llm_summary(category, issue, place, duration, urgency)
    if summary is None:
        summary = _offline_summary(category, issue, place, duration, urgency)
    summary_hi, summary_en = summary

    ticket_id = next_ticket_id(db)
    now = utcnow()

    db.insert(
        "grievances",
        {
            "id": ticket_id,
            "citizen_name": entities.get("citizenName") or "नागरिक (गुमनाम)",
            "contact": mask_all(str(entities.get("contact") or "")),
            "category": category,
            "category_hi": CATEGORY_HI.get(category, "अन्य"),
            "issue": issue,
            "district": district,
            "block": block,
            "village": village,
            "duration_days": duration,
            "urgency": urgency,
            "sentiment": sentiment,
            "status": "NEW",
            "priority": _priority_for(urgency, duration),
            "assigned_to": None,
            "summary": summary_hi,
            "summary_en": summary_en,
            "transcript": transcript,
            "language": language,
            "channel": channel,
            "created_at": now,
            "updated_at": now,
        },
    )
    log.info("Grievance %s created | category=%s urgency=%s", ticket_id, category, urgency)
    return get_ticket(db, ticket_id)  # type: ignore[return-value]


def list_tickets(
    db: Database,
    *,
    status: str | None = None,
    category: str | None = None,
    district: str | None = None,
    urgency: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if category:
        clauses.append("category = ?")
        params.append(category)
    if district:
        clauses.append("LOWER(district) = LOWER(?)")
        params.append(district)
    if urgency:
        clauses.append("urgency = ?")
        params.append(urgency)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    rows = db.query(
        f"SELECT * FROM grievances {where} ORDER BY datetime(created_at) DESC LIMIT ?",
        tuple(params),
    )
    return [dict(row_to_dict(r) or {}) for r in rows]


def get_ticket(db: Database, ticket_id: str) -> dict[str, Any] | None:
    row = db.query_one("SELECT * FROM grievances WHERE id = ?", (ticket_id,))
    if row is None:
        return None
    ticket = dict(row_to_dict(row) or {})
    notes = db.query(
        "SELECT note, author, created_at FROM grievance_notes WHERE grievance_id = ? ORDER BY id ASC",
        (ticket_id,),
    )
    ticket["notes"] = [dict(row_to_dict(n) or {}) for n in notes]
    ticket["icon"] = CATEGORY_ICON.get(ticket.get("category", "others"), "📌")
    ticket["categoryLabel"] = CATEGORY_HI.get(ticket.get("category", "others"), "अन्य")
    return ticket


def update_ticket(db: Database, ticket_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Update the mutable fields of a ticket."""
    allowed = {"status", "priority", "assigned_to", "district", "block", "village", "category"}
    clean = {k: v for k, v in updates.items() if k in allowed and v not in (None, "")}
    if "status" in clean and clean["status"] not in STATUSES:
        raise ValueError(f"invalid status: {clean['status']}")
    if "priority" in clean and clean["priority"] not in PRIORITIES:
        raise ValueError(f"invalid priority: {clean['priority']}")

    clean["updated_at"] = utcnow()
    db.update("grievances", clean, "id = ?", (ticket_id,))
    return get_ticket(db, ticket_id)


def add_note(db: Database, ticket_id: str, note: str, author: str = "DM Office") -> dict[str, Any] | None:
    if get_ticket(db, ticket_id) is None:
        return None
    db.insert(
        "grievance_notes",
        {"grievance_id": ticket_id, "note": note, "author": author, "created_at": utcnow()},
    )
    return get_ticket(db, ticket_id)


def issue_label(category: str) -> str:
    return _ISSUE_LABELS.get(category, "सामान्य समस्या")


_ISSUE_RE = re.compile(r"^[A-Za-z0-9 .\-]{3,60}$")


def sanitize_issue(text: str) -> str:
    """Keep the issue short and free of control characters."""
    cleaned = re.sub(r"[\r\n\t]", " ", (text or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:300]
