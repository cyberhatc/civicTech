"""Conversation orchestrator: one citizen utterance in, one grounded reply out.

The orchestrator owns the session state (which slot of a grievance are we still
missing, which identifier has the user given for a status lookup) and routes every
intent to the right service. Replies are written in simple spoken Hindi because they
are read aloud by the TTS engine.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.guardrails import mask_all
from app.core.logging_conf import get_logger
from app.db.database import Database, get_db, json_loads, utcnow
from app.services import analytics, grievances, nlu, rag, schemes, status
from app.services.llm import LLMUnavailable, get_llm

log = get_logger(__name__)

# Slots we need before a grievance can be filed.
_GRIEVANCE_SLOTS = ("district", "location", "contact")

_SLOT_QUESTIONS = {
    "district": "आप किस जिले में हैं? जिले का नाम बोलिए।",
    "location": "आपके गाँव या मोहल्ले का नाम और ब्लॉक बताइए।",
    "contact": "शिकायत की सूचना देने के लिए आपका मोबाइल नंबर बताइए।",
}

_INTENT_FALLBACK = (
    "मैं आपकी बात समझ गया। आप बोल सकते हैं - 'मुझे कौन सी योजना मिलेगी', "
    "'मेरा राशन कार्ड कहाँ है', या 'शिकायत करानी है'।"
)


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------


def _new_session() -> str:
    return f"ses_{uuid.uuid4().hex[:16]}"


def ensure_session(db: Database, session_id: str | None) -> tuple[str, dict[str, Any]]:
    """Return (session_id, state) creating the session when required."""
    if not session_id:
        session_id = _new_session()
    row = db.query_one("SELECT * FROM sessions WHERE id = ?", (session_id,))
    if row is None:
        db.insert(
            "sessions",
            {"id": session_id, "created_at": utcnow(), "language": "hi", "state_json": "{}"},
        )
        return session_id, {}
    return session_id, json_loads(row["state_json"], {})


def save_state(db: Database, session_id: str, state: dict[str, Any]) -> None:
    import json

    db.update("sessions", {"state_json": json.dumps(state, ensure_ascii=False)}, "id = ?", (session_id,))


def record_turn(
    db: Database, session_id: str, index: int, role: str, text: str, intent: str, language: str
) -> None:
    db.insert(
        "turns",
        {
            "session_id": session_id,
            "turn_index": index,
            "role": role,
            "text": mask_all(text)[:800],
            "intent": intent,
            "language": language,
            "created_at": utcnow(),
        },
    )


def history(db: Database, session_id: str) -> dict[str, Any]:
    row = db.query_one("SELECT * FROM sessions WHERE id = ?", (session_id,))
    if row is None:
        return {"id": session_id, "exists": False, "turns": []}
    turns = db.query(
        "SELECT turn_index, role, text, intent, language, created_at FROM turns "
        "WHERE session_id = ? ORDER BY turn_index ASC",
        (session_id,),
    )
    return {
        "id": session_id,
        "exists": True,
        "language": row["language"],
        "createdAt": row["created_at"],
        "turns": [dict(r) for r in turns],
    }


# ---------------------------------------------------------------------------
# Intent handlers
# ---------------------------------------------------------------------------


def _handle_greeting(intent: nlu.Intent) -> dict[str, Any]:
    return {
        "reply": "नमस्ते! मैं जनवाणी यूपी हूँ। मैं आपकी योजनाएँ दिखा सकता हूँ, आपके आवेदन की स्थिति बता सकता हूँ "
        "और आपकी शिकायत दर्ज करा सकता हूँ। बोलिए, क्या मदद करूँ?",
        "cards": [],
        "quickReplies": ["मुझे कौन सी योजना मिलेगी?", "मेरा राशन कार्ड कहाँ है?", "शिकायत करानी है"],
    }


def _handle_help(intent: nlu.Intent) -> dict[str, Any]:
    return {
        "reply": "मैं ये काम कर सकता हूँ - एक, आपकी जमीन और परिवार के हिसाब से सही सरकारी योजना बताना। "
        "दो, आपके आवेदन की स्थति बताना। तीन, बिजली, पानी, सड़क जैसी शिकायत दर्ज करना और ट्रैकिंग नंबर देना। "
        "बस माइक बटन दबाकर अपनी बात बोलिए।",
        "cards": [],
        "quickReplies": ["योजनाएँ दिखाओ", "मेरा आवेदन", "शिकायत करानी है"],
    }


def _handle_contact_human(intent: nlu.Intent) -> dict[str, Any]:
    return {
        "reply": "आपकी बात सीधे जिला कलेक्टर कार्यालय के जनसंपर्क केंद्र को भेज दी गई है। "
        "आपका शिकायत क्रमांक जनवाणी ऐप पर दिखेगा। अगर यह जरूरी है तो 1076 पर कॉल भी कर सकते हैं।",
        "cards": [
            {
                "type": "escalation",
                "icon": "📞",
                "title": "मानव सहायता से जुड़ाया गया",
                "subtitle": "Jansunwai Helpline 1076",
                "body": "आपकी बात जिला जनसंपर्क केंद्र में भेजी गई है।",
                "fields": [],
            }
        ],
        "quickReplies": ["शिकायत दर्ज करें"],
    }


def _handle_scheme_list(intent: nlu.Intent) -> dict[str, Any]:
    cards = schemes.list_cards()
    reply = (
        f"उत्तर प्रदेश में आपके लिए {len(cards)} मुख्य योजनाएँ हैं - किसान सम्मान निधि, किसान क्रेडिट कार्ड, "
        "आवास योजना, कन्या सुमंगला, मुख्यमंत्री पेंशन, राशन कार्ड, फसल बीमा और भूलेख। "
        "नीचे देखिए और जो आपके काम का हो उस पर बोलिए।"
    )
    return {"reply": reply, "cards": cards, "quickReplies": ["पात्रता पूछें", "दस्तावेज़ चाहिए"]}


def _handle_scheme_question(intent: nlu.Intent) -> dict[str, Any]:
    query = intent.raw_text
    scheme_id = schemes.resolve_scheme_name(query)
    result = schemes.answer_question(
        query, intent_entities=intent.entities, top_k=3, scheme_filter=scheme_id
    )
    card = schemes.scheme_card(scheme_id) if scheme_id else None
    return {
        "reply": result["answer"],
        "answerEn": result["answerEn"],
        "cards": [card] if card else [],
        "citations": result["citations"],
        "quickReplies": ["दस्तावेज़ कौन से चाहिए?", "आवेदन कैसे करें?"],
    }


def _handle_scheme_documents(intent: nlu.Intent) -> dict[str, Any]:
    scheme_id = schemes.resolve_scheme_name(intent.raw_text)
    chunks = rag.get_retriever().search(
        intent.raw_text, top_k=2, scheme_filter=scheme_id if scheme_id else None
    )
    if not chunks:
        chunks = rag.get_retriever().search("documents required " + intent.raw_text, top_k=2)
    if not chunks:
        return {
            "reply": "दस्तावेज़ों की सूची मुझे नहीं मिली। कृपया योजना का नाम बताइए।",
            "cards": [],
        }
    chunk = chunks[0][0]
    docs = chunk.documents_hi or chunk.documents
    reply = f"{chunk.scheme_name_hi} के लिए ये दस्तावेज़ चाहिए - " + "; ".join(docs[:5]) + "।"
    return {
        "reply": reply,
        "cards": [
            {
                "type": "documents",
                "icon": "📄",
                "title": f"{chunk.scheme_name_hi} - दस्तावेज़",
                "subtitle": chunk.short_name,
                "body": chunk.body_hi,
                "fields": [{"label": f"दस्तावेज़ {i + 1}", "value": d} for i, d in enumerate(docs[:6])],
            }
        ],
        "citations": [c.to_dict() for c in rag.build_citations([chunk], limit=1)],
        "quickReplies": ["पात्रता पूछें"],
    }


def _handle_status(intent: nlu.Intent, state: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    aadhaar = intent.entities.get("aadhaarLast4") or state.get("status", {}).get("aadhaarLast4")
    mobile = intent.entities.get("mobile") or state.get("status", {}).get("mobile")

    if not aadhaar and not mobile:
        state.setdefault("status", {})
        state["status"]["awaiting"] = True
        save_state(db, state["_session_id"], state)
        return {
            "reply": "आपके आवेदन की स्थिति देखने के लिए अपने आधार के आखिरी 4 अंक या पंजीकृत मोबाइल नंबर बताइए।",
            "cards": [],
            "awaiting": "status_identifier",
            "quickReplies": [],
        }

    result = status.lookup(db, aadhaar_last4=aadhaar, mobile=mobile)
    state.setdefault("status", {})
    state["status"].pop("awaiting", None)
    save_state(db, state["_session_id"], state)

    if not result["found"]:
        return {
            "reply": result["message"],
            "cards": [],
            "awaiting": "status_identifier",
            "quickReplies": [],
        }

    cards = []
    for app in result["applications"]:
        cards.append(
            {
                "type": "application",
                "icon": app.get("icon", "📄"),
                "title": app.get("schemeNameHi") or app.get("schemeName", ""),
                "subtitle": app.get("shortName", ""),
                "body": app.get("statusLabelHi", ""),
                "status": app.get("status"),
                "fields": [
                    {"label": "स्थिति", "value": app.get("statusLabelHi", "")},
                    {"label": "राशि", "value": app.get("amountLabel", "—")},
                    {"label": "अंतिम अद्यतन", "value": app.get("last_updated", "—")},
                    {"label": "संदर्भ", "value": app.get("reference", "—")},
                    {"label": "अगला कदम", "value": app.get("nextStep", "") or "—"},
                ],
                "timeline": app.get("events", []),
            }
        )

    return {
        "reply": status.spoken_summary(result),
        "cards": cards,
        "citizen": result.get("citizen"),
        "quickReplies": ["दूसरा आवेदन भी दिखाओ", "शिकायत करानी है"],
    }


def _handle_grievance(intent: nlu.Intent, state: dict[str, Any]) -> dict[str, Any]:
    """Create a ticket or ask for the next missing slot."""
    db = get_db()
    pending = state.get("grievance") or {}

    # Merge freshly detected entities into the pending grievance.
    for key in ("category", "issue", "district", "block", "village", "durationDays", "urgency",
                "sentiment", "citizenName", "contact"):
        value = intent.entities.get(key)
        if value not in (None, "", 0):
            pending[key] = value

    # A bare place name ("Barabanki") is a district answer.
    if not pending.get("district") and intent.entities.get("district"):
        pending["district"] = intent.entities["district"]

    missing: list[str] = []
    for slot in _GRIEVANCE_SLOTS:
        if slot == "location":
            # A village OR a block is enough to locate the complaint.
            if not (pending.get("village") or pending.get("block")):
                missing.append(slot)
        elif not pending.get(slot):
            missing.append(slot)

    # A contact number is only required if the citizen has not given one.
    if missing and "contact" in missing and pending.get("skipContact"):
        missing.remove("contact")

    # If the location slot was already asked and the answer did not match the
    # "<name> gaon" pattern, use the raw answer as the place name so the
    # conversation never loops on the same question.
    if "location" in missing and pending.get("locationAsked") and intent.raw_text:
        pending.setdefault("village", intent.raw_text.strip()[:80])
        missing.remove("location")

    if missing:
        state["grievance"] = pending
        state["pending"] = "grievance"
        if missing[0] == "location":
            pending["locationAsked"] = True
        save_state(db, state["_session_id"], state)
        slot = missing[0]
        question = _SLOT_QUESTIONS[slot]
        if slot == "contact":
            question = (
                "शिकायत की सूचना भेजने के लिए आपका मोबाइल नंबर बताइए। "
                "अगर नहीं देना चाहते तो 'स्किप' कहिए।"
            )
        return {
            "reply": question,
            "cards": [],
            "awaiting": f"grievance_{slot}",
            "quickReplies": ["स्किप"] if slot == "contact" else [],
            "pendingGrievance": pending,
        }

    # Everything is collected -> file the ticket.
    transcript = intent.raw_text
    ticket = grievances.create_ticket(
        db,
        pending,
        transcript=transcript,
        language=intent.language,
        channel=state.get("channel", "voice"),
    )
    state.pop("grievance", None)
    state.pop("pending", None)
    save_state(db, state["_session_id"], state)

    reply = (
        f"आपकी शिकायत दर्ज हो गई है। शिकायत संख्या {ticket['id']} है। "
        f"{ticket['categoryLabel']} विभाग को यह तुरंत भेज दी गई है। "
        "आप इसी नंबर पर स्थिति देख सकते हैं।"
    )
    return {
        "reply": reply,
        "cards": [
            {
                "type": "ticket",
                "icon": ticket.get("icon", "📌"),
                "title": f"शिकायत {ticket['id']}",
                "subtitle": f"{ticket['categoryLabel']} • {ticket.get('district') or 'जिला अज्ञात'}",
                "body": ticket.get("summary", ""),
                "ticketId": ticket["id"],
                "fields": [
                    {"label": "शिकायत संख्या", "value": ticket["id"]},
                    {"label": "विभाग", "value": ticket.get("categoryLabel", "")},
                    {"label": "स्थान", "value": ", ".join(
                        [p for p in [ticket.get("village"), ticket.get("block"), ticket.get("district")] if p]
                    ) or "—"},
                    {"label": "कितने दिन से", "value": str(ticket.get("duration_days", 0))},
                    {"label": "प्राथमिकता", "value": ticket.get("priority", "P2")},
                    {"label": "स्थिति", "value": ticket.get("status", "NEW")},
                ],
            }
        ],
        "tickets": [ticket],
        "quickReplies": ["और शिकायत करानी है", "योजनाएँ दिखाओ"],
    }


def _detect_contact(text: str) -> str | None:
    digits = re.sub(r"\D", "", text or "")
    for i in range(len(digits)):
        chunk = digits[i : i + 10]
        if len(chunk) == 10 and chunk[0] in "6789":
            return chunk
    return None


def _handle_skip(intent: nlu.Intent, state: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    pending = state.get("grievance") or {}
    pending["skipContact"] = True
    pending.setdefault("contact", "—")
    state["grievance"] = pending
    save_state(db, state["_session_id"], state)
    return _handle_grievance(intent, state)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def handle_turn(
    text: str,
    *,
    session_id: str | None = None,
    language_hint: str | None = None,
    channel: str = "voice",
    db: Database | None = None,
) -> dict[str, Any]:
    """Process one citizen utterance end-to-end."""
    db = db or get_db()
    session_id, state = ensure_session(db, session_id)
    state["_session_id"] = session_id
    state["channel"] = channel

    text = (text or "").strip()
    if not text:
        return {
            "sessionId": session_id,
            "transcript": {"text": "", "lang": language_hint or "hi", "confidence": 0, "provider": "none"},
            "intent": nlu.Intent().to_dict(),
            "reply": {"text": "मैं सुन नहीं पाया। कृपया फिर से बोलिए।", "lang": "hin", "speech": "hi-IN-SwaraNeural"},
            "cards": [],
            "citations": [],
            "tickets": [],
            "quickReplies": [],
        }

    intent = nlu.analyze(text)
    if language_hint:
        intent.language = language_hint

    # A pending slot takes priority over re-classifying the utterance.
    pending_kind = state.get("pending")
    if pending_kind == "grievance":
        contact = _detect_contact(text)
        if contact:
            state.setdefault("grievance", {})["contact"] = contact
        if re.search(r"\b(skip|स्किप|chhod|rehne do|mat)\b", text.lower()):
            result = _handle_skip(intent, state)
        else:
            result = _handle_grievance(intent, state)
    elif pending_kind == "status" or state.get("status", {}).get("awaiting"):
        state["pending"] = "status"
        result = _handle_status(intent, state)
    else:
        name = intent.name
        if name == "greeting":
            result = _handle_greeting(intent)
        elif name == "help":
            result = _handle_help(intent)
        elif name == "contact_human":
            result = _handle_contact_human(intent)
        elif name == "scheme_list":
            result = _handle_scheme_list(intent)
        elif name == "scheme_documents":
            result = _handle_scheme_documents(intent)
        elif name in ("scheme_eligibility", "unknown"):
            # An unknown utterance that mentions a complaint is treated as a grievance.
            if intent.entities.get("category") and intent.entities.get("category") != "agriculture" and intent.confidence < 0.5:
                result = _handle_grievance(intent, state)
            elif intent.name == "scheme_eligibility":
                result = _handle_scheme_question(intent)
            else:
                result = {
                    "reply": _INTENT_FALLBACK,
                    "cards": [],
                    "quickReplies": ["मुझे कौन सी योजना मिलेगी?", "शिकायत करानी है", "मेरा आवेदन"],
                }
        elif name == "grievance_file":
            result = _handle_grievance(intent, state)
        elif name == "status_track":
            result = _handle_status(intent, state)
        else:
            result = {
                "reply": _INTENT_FALLBACK,
                "cards": [],
                "quickReplies": ["मुझे कौन सी योजना मिलेगी?", "शिकायत करानी है", "मेरा आवेदन"],
            }

    # Persist the turn.
    try:
        row = db.query_one("SELECT COALESCE(MAX(turn_index), 0) AS m FROM turns WHERE session_id = ?", (session_id,))
        index = (row["m"] if row else 0) + 1
        record_turn(db, session_id, index, "user", text, intent.name, intent.language)
        record_turn(db, session_id, index + 1, "assistant", result.get("reply", ""), intent.name, intent.language)
        db.update("sessions", {"language": intent.language}, "id = ?", (session_id,))
    except Exception as exc:  # pragma: no cover - never break a turn on logging
        log.warning("Could not persist turn: %s", exc)

    return {
        "sessionId": session_id,
        "transcript": {
            "text": text,
            "lang": intent.language,
            "confidence": intent.confidence,
            "provider": "nlu",
        },
        "intent": intent.to_dict(),
        "reply": {
            "text": result.get("reply", ""),
            "lang": intent.language,
            "speech": "hi-IN-SwaraNeural",
        },
        "answerEn": result.get("answerEn"),
        "cards": result.get("cards", []),
        "citations": result.get("citations", []),
        "tickets": result.get("tickets", []),
        "quickReplies": result.get("quickReplies", []),
        "awaiting": result.get("awaiting"),
        "pendingGrievance": result.get("pendingGrievance"),
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
