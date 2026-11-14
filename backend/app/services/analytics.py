"""Aggregations behind the District Magistrate analytics dashboard."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.db.database import Database, row_to_dict

_SCHEME_FOCUS = {
    "electricity": "बिजली",
    "roads": "सड़क",
    "water": "पानी",
    "sanitation": "स्वच्छता",
    "health": "स्वास्थ्य",
    "education": "शिक्षा",
    "agriculture": "कृषि",
    "housing": "आवास",
    "policing": "पुलिस",
    "others": "अन्य",
}


def _counter(sql: str, db: Database, params: tuple = ()) -> list[dict[str, Any]]:
    rows = db.query(sql, params)
    return [dict(row_to_dict(r) or {}) for r in rows]


def stats(db: Database) -> dict[str, Any]:
    """Everything the dashboard needs in one payload."""
    total_row = db.query_one("SELECT COUNT(*) AS c FROM grievances")
    total = total_row["c"] if total_row else 0

    status_counts = _counter("SELECT status, COUNT(*) AS count FROM grievances GROUP BY status", db)
    category_counts = _counter(
        "SELECT category, COUNT(*) AS count FROM grievances GROUP BY category ORDER BY count DESC", db
    )
    district_counts = _counter(
        "SELECT COALESCE(district, 'अज्ञात') AS district, COUNT(*) AS count "
        "FROM grievances GROUP BY district ORDER BY count DESC",
        db,
    )
    urgency_counts = _counter("SELECT urgency, COUNT(*) AS count FROM grievances GROUP BY urgency", db)
    sentiment_counts = _counter("SELECT sentiment, COUNT(*) AS count FROM grievances GROUP BY sentiment", db)

    resolved = sum(c["count"] for c in status_counts if c["status"] == "RESOLVED")
    open_count = total - resolved

    resolved_rows = db.query(
        "SELECT created_at, updated_at FROM grievances WHERE status = 'RESOLVED' AND updated_at IS NOT NULL"
    )
    avg_resolution_hours = 0.0
    if resolved_rows:
        deltas = []
        for row in resolved_rows:
            try:
                created = datetime.fromisoformat(row["created_at"])
                updated = datetime.fromisoformat(row["updated_at"])
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if updated.tzinfo is None:
                    updated = updated.replace(tzinfo=timezone.utc)
                deltas.append(max(0.0, (updated - created).total_seconds() / 3600))
            except (ValueError, TypeError):
                continue
        if deltas:
            avg_resolution_hours = round(sum(deltas) / len(deltas), 1)

    # 14-day timeline
    today = datetime.now(timezone.utc).date()
    timeline_map: dict[str, int] = {}
    for offset in range(13, -1, -1):
        day = today - timedelta(days=offset)
        timeline_map[day.isoformat()] = 0
    timeline_rows = db.query("SELECT created_at FROM grievances")
    for row in timeline_rows:
        raw = row["created_at"]
        if not raw:
            continue
        try:
            day = datetime.fromisoformat(raw).date()
        except ValueError:
            continue
        key = day.isoformat()
        if key in timeline_map:
            timeline_map[key] += 1
    timeline = [{"date": k, "count": v} for k, v in sorted(timeline_map.items())]

    # Scheme interest, derived from the text of every grievance.
    scheme_interest = [
        {"id": "pm-kisan", "label": "PM-KISAN", "icon": "🌾"},
        {"id": "pm-awas-gramin", "label": "PM Awas Gramin", "icon": "🏠"},
        {"id": "kcc", "label": "Kisan Credit Card", "icon": "💳"},
        {"id": "nfsa-ration", "label": "Ration Card", "icon": "🌾"},
        {"id": "kanya-sumangala", "label": "Kanya Sumangala", "icon": "👧"},
        {"id": "mpy-pension", "label": "Mukhyamantri Pension", "icon": "👵"},
        {"id": "pmfby", "label": "Fasal Bima", "icon": "🌧️"},
        {"id": "up-bhulekh", "label": "Bhulekh", "icon": "📋"},
    ]
    mentions = {s["id"]: 0 for s in scheme_interest}
    all_rows = db.query("SELECT issue, summary, transcript FROM grievances")
    haystacks = " ".join(
        " ".join(str(r[k] or "") for k in ("issue", "summary", "transcript")).lower() for r in all_rows
    )
    keys = {
        "pm-kisan": ["pm-kisan", "pm kisan", "किसान सम्मान", "किस्त"],
        "pm-awas-gramin": ["awas", "आवास", "पक्का घर", "ghar"],
        "kcc": ["kcc", "केसीसी", "किसान क्रेडिट"],
        "nfsa-ration": ["ration", "राशन", "अनाज"],
        "kanya-sumangala": ["kanya", "कन्या", "बालिका", "sumangala"],
        "mpy-pension": ["pension", "पेंशन", "widow", "विधवा"],
        "pmfby": ["bima", "बीमा", "pmfby"],
        "up-bhulekh": ["bhulekh", "भूलेख", "खतौनी", "khasra", "खसरा"],
    }
    for scheme_id, needles in keys.items():
        mentions[scheme_id] = sum(1 for needle in needles if needle in haystacks)
    total_mentions = sum(mentions.values()) or 1
    for scheme in scheme_interest:
        scheme["count"] = mentions[scheme["id"]]
        scheme["share"] = round(mentions[scheme["id"]] / total_mentions, 3)

    # Average response quality signals
    citizen_rows = db.query("SELECT COUNT(*) AS c FROM citizens")
    citizen_count = citizen_rows[0]["c"] if citizen_rows else 0

    return {
        "totals": {
            "tickets": total,
            "resolved": resolved,
            "open": open_count,
            "avgResolutionHours": avg_resolution_hours,
            "citizens": citizen_count,
        },
        "byCategory": [
            {
                "category": row["category"],
                "label": _SCHEME_FOCUS.get(row["category"], row["category"]),
                "count": row["count"],
            }
            for row in category_counts
        ],
        "byDistrict": district_counts,
        "byUrgency": urgency_counts,
        "byStatus": status_counts,
        "bySentiment": sentiment_counts,
        "timeline": timeline,
        "schemeInterest": scheme_interest,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def live_feed(db: Database, limit: int = 20) -> list[dict[str, Any]]:
    """The most recent tickets, newest first."""
    rows = db.query(
        "SELECT id, citizen_name, category, category_hi, issue, district, village, urgency, "
        "status, priority, created_at, language, duration_days, summary, summary_en "
        "FROM grievances ORDER BY datetime(created_at) DESC LIMIT ?",
        (limit,),
    )
    from app.services.nlu import CATEGORY_ICON

    feed = []
    for row in rows:
        item = dict(row_to_dict(row) or {})
        item["icon"] = CATEGORY_ICON.get(item.get("category", "others"), "📌")
        feed.append(item)
    return feed
