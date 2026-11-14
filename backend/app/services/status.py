"""Mock application status lookup (NFSA ration card, PM-KISAN, PMAY, pension...)."""

from __future__ import annotations

from typing import Any

from app.core.guardrails import mask_aadhaar, mask_phone
from app.db.database import Database, row_to_dict
from app.services import rag

_STATUS_HI = {
    "INSTALLMENT_CREDITED": "किस्त जमा",
    "INSTALLMENT_PENDING": "किस्त सत्यापन में",
    "PENSION_ACTIVE": "पेंशन सक्रिय",
    "RATION_ACTIVE": "राशन सक्रिय",
    "ACTIVE": "सक्रिय",
    "UNDER_CONSTRUCTION": "निर्माणाधीन",
    "PARTIAL_DISBURSED": "आंशिक राशि जमा",
    "APPROVED_AWAITING_RELEASE": "स्वीकृत, राशि जारी होने की प्रतीक्षा में",
    "UNDER_VERIFICATION": "सत्यापन में",
    "CLAIM_APPROVED": "दावा स्वीकृत",
    "APPLICATION_UNDER_REVIEW": "आवेदन की समीक्षा में",
    "CREDIT_LIMIT_EXPIRED": "क्रेडिट सीमा समाप्त",
    "RECORD_AVAILABLE": "रिकॉर्ड उपलब्ध",
}

_NEXT_STEP = {
    "INSTALLMENT_PENDING": "भूमि रिकॉर्ड सत्यापन के बाद अगली किस्त जमा की जाएगी।",
    "UNDER_VERIFICATION": "दस्तावेज़ों की जाँच चल रही है, जल्द ही अपडेट होगा।",
    "APPROVED_AWAITING_RELEASE": "राशि स्वीकृत हो चुकी है और खाते में भेजी जा रही है।",
    "APPLICATION_UNDER_REVIEW": "जिला कार्यालय में समीक्षा चल रही है।",
    "CREDIT_LIMIT_EXPIRED": "नवीनीकरण के बाद क्रेडिट सीमा फिर से उपलब्ध होगी।",
    "UNDER_CONSTRUCTION": "निर्माण की अगली किस्त कार्य की प्रगति पर निर्भर है।",
}


def lookup(
    db: Database,
    *,
    aadhaar_last4: str | None = None,
    mobile: str | None = None,
    scheme_id: str | None = None,
) -> dict[str, Any]:
    """Find a citizen's applications by Aadhaar last-4 or registered mobile."""
    citizen = None
    matched_by = ""

    if aadhaar_last4:
        digits = "".join(ch for ch in aadhaar_last4 if ch.isdigit())
        if digits:
            row = db.query_one("SELECT * FROM citizens WHERE aadhaar_last4 = ?", (digits[-4:],))
            if row is not None:
                citizen = dict(row_to_dict(row) or {})
                matched_by = "aadhaar"

    if citizen is None and mobile:
        digits = "".join(ch for ch in mobile if ch.isdigit())
        if digits:
            row = db.query_one("SELECT * FROM citizens WHERE mobile = ?", (digits[-10:],))
            if row is not None:
                citizen = dict(row_to_dict(row) or {})
                matched_by = "mobile"

    if citizen is None:
        return {
            "found": False,
            "matchedBy": matched_by or None,
            "message": "इस पहचान से कोई रिकॉर्ड नहीं मिला। कृपया आधार के अंतिम 4 अंक या पंजीकृत मोबाइल दोबारा बताएँ।",
            "messageEn": "No record found for this identifier. Please provide the last 4 digits of your Aadhaar or your registered mobile number.",
            "applications": [],
        }

    clauses = ["citizen_id = ?"]
    params: list[Any] = [citizen["id"]]
    if scheme_id:
        clauses.append("scheme_id = ?")
        params.append(scheme_id)
    rows = db.query(
        f"SELECT * FROM applications WHERE {' AND '.join(clauses)} ORDER BY last_updated DESC",
        tuple(params),
    )

    applications: list[dict[str, Any]] = []
    for row in rows:
        app = dict(row_to_dict(row) or {})
        scheme = rag.get_scheme(app["scheme_id"]) or {}
        events = db.query(
            "SELECT date, label, label_hi, status FROM application_events WHERE application_id = ? ORDER BY seq ASC",
            (app["id"],),
        )
        app["schemeName"] = scheme.get("name", app["scheme_id"])
        app["schemeNameHi"] = scheme.get("name_hi", "")
        app["shortName"] = scheme.get("short_name", app["scheme_id"])
        app["icon"] = scheme.get("icon", "📄")
        app["statusLabelHi"] = app.get("status_hi") or _STATUS_HI.get(app["status"], app["status"])
        app["nextStep"] = _NEXT_STEP.get(app["status"], "")
        app["amountLabel"] = f"₹{app['amount']:,}" if app.get("amount") else "—"
        app["events"] = [dict(row_to_dict(e) or {}) for e in events]
        applications.append(app)

    return {
        "found": True,
        "matchedBy": matched_by,
        "citizen": {
            "name": citizen.get("name"),
            "nameHi": citizen.get("name_hi"),
            "district": citizen.get("district"),
            "block": citizen.get("block"),
            "village": citizen.get("village"),
            "language": citizen.get("language"),
            "aadhaar": mask_aadhaar(f"XXXX-XXXX-{citizen.get('aadhaar_last4', '')}"),
            "mobile": mask_phone(citizen.get("mobile", "")),
        },
        "applications": applications,
        "message": (
            f"{citizen.get('name_hi') or citizen.get('name')} जी के {len(applications)} आवेदन मिले।"
            if applications
            else "इस नागरिक का कोई आवेदन नहीं मिला।"
        ),
        "messageEn": f"Found {len(applications)} application(s) for {citizen.get('name')}.",
    }


def spoken_summary(result: dict[str, Any]) -> str:
    """A short Hindi line suitable for TTS."""
    if not result.get("found"):
        return result.get("message", "")
    applications = result.get("applications", [])
    if not applications:
        return "इस नागरिक का कोई आवेदन नहीं मिला।"

    lines = []
    for app in applications[:3]:
        label = app.get("statusLabelHi") or app.get("status")
        amount = app.get("amount") or 0
        money = f", राशि {amount:,} रुपये" if amount else ""
        lines.append(f"{app.get('shortName')} - {label}{money}")
    header = f"{result['citizen'].get('nameHi') or result['citizen'].get('name')} जी के {len(applications)} आवेदन हैं।"
    return header + " " + "; ".join(lines) + "।"
