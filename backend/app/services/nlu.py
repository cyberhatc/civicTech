"""Dialect-aware intent and entity extraction for Hindi / Bhojpuri / Awadhi.

Two stages run in sequence:

1. **Lexicon pass** - a hand-built dialect lexicon (``data/synonyms.json``) scores every
   intent and pulls out entities. This always works, offline, in microseconds.
2. **LLM pass** - when Groq is configured the transcript is also sent to the model with
   a strict JSON schema; the result is merged over the lexicon result.

The merge is deliberately conservative: the LLM may *add* entities or *override* the
intent, but it can never introduce an intent that the lexicon does not know about.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.guardrails import contains_injection, safe_user_text
from app.core.logging_conf import get_logger
from app.services.llm import LLMUnavailable, get_llm

log = get_logger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

INTENTS = [
    "greeting",
    "scheme_list",
    "scheme_eligibility",
    "scheme_documents",
    "grievance_file",
    "status_track",
    "contact_human",
    "help",
    "unknown",
]

# Categories used by the grievance flow.
CATEGORIES = [
    "electricity",
    "roads",
    "water",
    "sanitation",
    "health",
    "education",
    "agriculture",
    "housing",
    "policing",
    "others",
]

CATEGORY_HI = {
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

CATEGORY_ICON = {
    "electricity": "⚡",
    "roads": "🛣️",
    "water": "💧",
    "sanitation": "🧹",
    "health": "🏥",
    "education": "🎓",
    "agriculture": "🌾",
    "housing": "🏠",
    "policing": "🚓",
    "others": "📌",
}

_DAYS_PER_UNIT = {"din": 1, "day": 1, "days": 1, "हफ्ता": 7, "हफ्ते": 7, "हफ्तों": 7, "hafta": 7,
                  "week": 7, "weeks": 7, "mahine": 30, "mahina": 30, "month": 30, "months": 30,
                  "saal": 365, "year": 365, "years": 365}

# Words that can never be a place name.
_PLACE_STOPWORDS = {
    "hamare", "hamar", "hamra", "hamko", "mera", "meri", "mere", "hum", "hume", "apne", "apna",
    "us", "is", "jo", "jis", "har", "ek", "our", "the", "this", "that", "my", "your", "ke", "ki",
    "ka", "ko", "me", "se", "aur", "ya", "to", "nahi", "nai", "hai", "hain", "ho", "kaun", "kya",
    "yahan", "wahan", "idhar", "udhar", "yaha", "waha", "bhi", "hi", "waala", "wala", "vala",
}

_LANG_CODE = {"bho": "bho", "awd": "awd", "hin": "hin", "hinglish": "hinglish"}


@dataclass
class Intent:
    """Structured understanding of one user utterance."""

    name: str = "unknown"
    confidence: float = 0.0
    language: str = "hin"
    entities: dict[str, Any] = field(default_factory=dict)
    source: str = "lexicon"
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "confidence": round(self.confidence, 3),
            "language": self.language,
            "entities": self.entities,
            "source": self.source,
        }


@lru_cache(maxsize=1)
def load_lexicon() -> dict[str, Any]:
    with (DATA_DIR / "synonyms.json").open("r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Lexicon pass
# ---------------------------------------------------------------------------


def _count_phrases(text: str, phrases: list[str]) -> tuple[int, list[str]]:
    """Count phrase hits; longer phrases score higher (they are more specific)."""
    hits: list[str] = []
    score = 0.0
    for phrase in phrases:
        if not phrase:
            continue
        occurrences = text.count(phrase)
        if occurrences:
            hits.append(phrase)
            score += occurrences * (1.0 + 0.25 * len(phrase.split()))
    return score, hits


def detect_language(text: str) -> tuple[str, float]:
    """Guess the language of the transcript from dialect markers."""
    lex = load_lexicon()
    lowered = (text or "").lower()
    scores: dict[str, float] = {}
    for lang, markers in lex["lang_markers"].items():
        score, _ = _count_phrases(lowered, markers)
        scores[lang] = score

    # Hinglish is written in Latin script with English loanwords; treat it as a
    # fallback for Latin-script transcripts that contain no Devanagari.
    has_devanagari = bool(re.search(r"[\u0900-\u097F]", text or ""))
    if not has_devanagari:
        scores["hinglish"] = scores.get("hinglish", 0) + 0.6

    best = max(scores.items(), key=lambda kv: kv[1])
    if best[1] <= 0:
        return ("hin" if has_devanagari else "hinglish"), 0.0
    total = sum(scores.values()) or 1.0
    return _LANG_CODE.get(best[0], "hin"), round(best[1] / total, 3)


def _extract_place(lowered: str, pattern: str) -> str | None:
    """Pull a place name out of a "<name> <keyword>" pattern."""
    for match in re.finditer(pattern, lowered):
        candidate = match.group(1).strip()
        if len(candidate) < 3:
            continue
        if candidate in _PLACE_STOPWORDS:
            continue
        if candidate.isdigit():
            continue
        return candidate.title()
    return None


def _parse_numbers(text: str) -> list[float]:
    lex = load_lexicon()
    values: list[float] = []
    for match in re.finditer(r"(\d+(?:\.\d+)?)", text):
        try:
            values.append(float(match.group(1)))
        except ValueError:
            continue
    for word, digit in lex.get("number_words", {}).items():
        if digit.isdigit() and re.search(rf"\b{re.escape(word)}\b", text):
            values.append(float(digit))
    return values


def extract_entities(text: str, lowered: str) -> dict[str, Any]:
    """Pull structured entities out of the transcript."""
    lex = load_lexicon()
    entities: dict[str, Any] = {}

    # --- land holding ------------------------------------------------------
    bigha = None
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(?:bigha|biga|bega|bewaa|बिघा|बीघा)", lowered):
        bigha = float(match.group(1))
        break
    if bigha is None:
        # "do bigha" style - number word followed by bigha
        for word, digit in lex.get("number_words", {}).items():
            if digit.isdigit() and re.search(rf"\b{re.escape(word)}\s*(?:bigha|biga|बिघा)", lowered):
                bigha = float(digit)
                break
    if bigha is not None:
        entities["landBigha"] = bigha

    # --- duration ----------------------------------------------------------
    duration = None
    unit_hits = _DAYS_PER_UNIT
    for match in re.finditer(r"(\d+)\s*(din|dins|day|days|हफ्त[ाोें]*|हफ्ते|hafta|hafton|week|mahine|mahina|month|saal|year)", lowered):
        unit = match.group(2)
        unit = next((u for u in unit_hits if u.startswith(unit[:3])), unit)
        days = unit_hits.get(unit)
        if days is None:
            days = 1 if unit.startswith(("din", "day")) else 30
        duration = max(duration or 0, int(match.group(1)) * days)
    if duration is None:
        for word, digit in lex.get("number_words", {}).items():
            if not digit.isdigit():
                continue
            for unit, days in unit_hits.items():
                if re.search(rf"\b{re.escape(word)}\s*{re.escape(unit)}\b", lowered):
                    duration = max(duration or 0, int(digit) * days)
    if duration is None:
        # "kai din se" / "bahut din se" - indefinite but meaningful
        if re.search(r"\b(kai|bahut|char|saikde)\s+(din|hafta|mahine|week)", lowered):
            duration = 7 if "hafta" in lowered or "week" in lowered else 7
    if duration is not None:
        entities["durationDays"] = duration

    # --- grievance category -------------------------------------------------
    category_scores: dict[str, float] = {}
    for cat, words in lex["category_map"].items():
        score, _ = _count_phrases(lowered, words)
        if score:
            category_scores[cat] = score
    if category_scores:
        best_cat = max(category_scores.items(), key=lambda kv: kv[1])
        entities["category"] = best_cat[0]
        entities["categoryHi"] = CATEGORY_HI[best_cat[0]]
        entities["categoryIcon"] = CATEGORY_ICON[best_cat[0]]
        entities["categoryConfidence"] = round(min(0.99, best_cat[1] / 3.0), 3)

    # --- urgency ------------------------------------------------------------
    urgency_score, urgency_hits = _count_phrases(lowered, lex["entities"].get("urgency_high", []))
    if urgency_score:
        entities["urgency"] = "high"
        entities["urgencyHits"] = urgency_hits[:3]
    elif duration and duration >= 7:
        entities["urgency"] = "medium"

    # --- district -----------------------------------------------------------
    for district in lex["entities"].get("district", []):
        if re.search(rf"\b{re.escape(district)}\b", lowered):
            entities["district"] = district.title()
            break

    # --- block / village ----------------------------------------------------
    block = _extract_place(lowered, r"([\w\u0900-\u097F]+)\s+(?:block|tehsil|thana|यूपी)")
    if block:
        entities["block"] = block
    village = _extract_place(lowered, r"([\w\u0900-\u097F]+)\s+(?:gaon|village|mohalla|colony|गाँव|गांव|मोहल्ला)")
    if village:
        entities["village"] = village

    # --- documents asked for -------------------------------------------------
    doc_hits, _ = _count_phrases(lowered, lex["entities"].get("documents", []))
    if doc_hits:
        entities["asksDocuments"] = True

    # --- numbers of people / family -----------------------------------------
    if re.search(r"\b(\d+)\s*(log|logo|member|logon)", lowered):
        entities["familyMembers"] = int(re.search(r"\b(\d+)\s*(log|logo|member|logon)", lowered).group(1))

    # --- identifiers ---------------------------------------------------------
    aadhaar = re.search(r"\b(\d{4})\s*(\d{4})\s*(\d{4})\b", text or "")
    if aadhaar:
        entities["aadhaarLast4"] = aadhaar.group(3)
    mobile = re.search(r"(?<!\d)([6-9]\d{4}[\s\-]?\d{5})(?!\d)", text or "")
    if mobile:
        entities["mobile"] = re.sub(r"\D", "", mobile.group(1))

    # --- sentiment -----------------------------------------------------------
    negative_words = ["kharab", "bharbad", "bighad", "kharab hai", "koi nahi", "nahi sun", "pareshan",
                      "dukhi", "gussa", "shikayat", "problem", "kharabi", "bigha", "jala"]
    positive_words = ["theek", "shukriya", "badhiya", "accha", "help kiya", "jaldi"]
    neg_score, _ = _count_phrases(lowered, negative_words)
    pos_score, _ = _count_phrases(lowered, positive_words)
    if neg_score > pos_score:
        entities["sentiment"] = "negative"
    elif pos_score > neg_score:
        entities["sentiment"] = "positive"
    else:
        entities["sentiment"] = "neutral"

    return entities


def lexicon_analyze(text: str) -> Intent:
    """Rule-based understanding. Always succeeds."""
    raw = text or ""
    lowered = raw.lower()
    lex = load_lexicon()

    scores: dict[str, float] = {}
    evidence: dict[str, list[str]] = {}
    for intent, phrases in lex["intents"].items():
        score, hits = _count_phrases(lowered, phrases)
        if score:
            scores[intent] = score
            evidence[intent] = hits[:4]

    language, lang_conf = detect_language(raw)
    entities = extract_entities(raw, lowered)

    # --- strong status signals -------------------------------------------
    # "paisa kahan tak pahuncha", "kab aayega", "kya haal hai" -> status, not a
    # generic scheme question.
    if re.search(
        r"\b(kahan\s*tak|kab\s*(aayega|milega|aay|ayega)|kya\s*haal|ra\s*ka\s*haal|"
        r"pahunch|pahu[nñ]ch|installment|instolment|bandi\s*(aa|aa\s*gayi)|"
        r"paisa\s*aaya|aaya\s*ya\s*nahi|jama\s*hua|credited)\b",
        lowered,
    ):
        scores["status_track"] = scores.get("status_track", 0) + 2.4

    # --- strong eligibility signals ---------------------------------------
    if re.search(
        r"\b(kaun\s*s[ai]\s*yojana|konsi\s*yojana|kaun\s*si\s*yojana|kya\s*yojana\s*milega|"
        r"kya\s*scheme\s*milega|eligible\s*(hu|ho|hain)|patra\s*(h[ou]|hai|hun|hung)|"
        r"mukhyamantri|kaun\s*si\s*help|kaun\s*s[ai]\s*help)\b",
        lowered,
    ):
        scores["scheme_eligibility"] = scores.get("scheme_eligibility", 0) + 2.0

    # --- generic first-person + scheme-word hint (weak) -------------------
    if re.search(r"\b(mer[ae]|hamar|hamare|mujhe|mere)\b", lowered) and re.search(
        r"(yojana|scheme|paisa|subsidy|patra|eligible|mil|lag)", lowered
    ):
        scores["scheme_eligibility"] = scores.get("scheme_eligibility", 0) + 0.7

    # --- complaint markers: past-tense damage + authority mention --------
    if re.search(r"\b(ja[a]?gaya|jal[a]? (pada|para|gaya)|big[a]?d|toot|tod|gayab|band kar)", lowered):
        scores["grievance_file"] = scores.get("grievance_file", 0) + 1.4

    if not scores:
        # No intent matched, but entities (district, phone number, duration) may
        # still be present - a slot-filling turn often looks like this.
        return Intent(
            name="unknown",
            confidence=0.25,
            language=language,
            entities=entities,
            source="lexicon",
            raw_text=raw,
        )

    best_intent = max(scores.items(), key=lambda kv: kv[1])
    total = sum(scores.values()) or 1.0
    confidence = min(0.95, 0.35 + (best_intent[1] / total) * 0.6)

    # Scheme-question heuristics.
    if best_intent[0] == "scheme_eligibility" and "landBigha" in entities:
        entities["askType"] = "land_based"
    elif best_intent[0] == "scheme_eligibility":
        entities["askType"] = "general"

    return Intent(
        name=best_intent[0],
        confidence=round(confidence, 3),
        language=language,
        entities=entities,
        source="lexicon",
        raw_text=raw,
    )


# ---------------------------------------------------------------------------
# LLM pass
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are the intent parser for JanVaani UP, a voice assistant for Indian government "
    "schemes in Uttar Pradesh. The user speaks Hindi, Bhojpuri, Awadhi or Hinglish.\n"
    "Extract the intent and entities. Reply with a single JSON object and nothing else.\n"
    "Allowed intents: greeting, scheme_list, scheme_eligibility, scheme_documents, "
    "grievance_file, status_track, contact_human, help, unknown.\n"
    "Allowed grievance categories: electricity, roads, water, sanitation, health, "
    "education, agriculture, housing, policing, others.\n"
    "Entities to return when present (use null when absent): "
    "category, issue (short description of the problem in Hindi), district, block, village, "
    "durationDays (integer), landBigha (number), urgency (low|medium|high), sentiment "
    "(positive|neutral|negative), citizenName, contact, schemeName, asksDocuments (boolean).\n"
    "Bhojpuri/Awadhi spellings are normal spellings of Hindi - map them to standard terms."
)

_INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": INTENTS},
        "confidence": {"type": "number"},
        "language": {"type": "string", "enum": ["hin", "bho", "awd", "hinglish"]},
        "entities": {
            "type": "object",
            "properties": {
                "category": {"type": ["string", "null"]},
                "issue": {"type": ["string", "null"]},
                "district": {"type": ["string", "null"]},
                "block": {"type": ["string", "null"]},
                "village": {"type": ["string", "null"]},
                "durationDays": {"type": ["integer", "null"]},
                "landBigha": {"type": ["number", "null"]},
                "urgency": {"type": ["string", "null"]},
                "sentiment": {"type": ["string", "null"]},
                "citizenName": {"type": ["string", "null"]},
                "contact": {"type": ["string", "null"]},
                "schemeName": {"type": ["string", "null"]},
                "asksDocuments": {"type": ["boolean", "null"]},
            },
        },
    },
    "required": ["intent", "confidence", "language", "entities"],
}


def llm_analyze(text: str) -> Intent | None:
    """Ask Groq to parse the utterance. Returns None when unavailable."""
    llm = get_llm()
    if not llm.available:
        return None

    if contains_injection(text):
        log.warning("Rejected a transcript containing a prompt-injection attempt")
        return None

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"Transcript: {safe_user_text(text, 600)}"},
    ]
    try:
        payload = llm.chat_json(messages, temperature=0.0, max_tokens=600)
    except LLMUnavailable:
        return None

    if not isinstance(payload, dict):
        return None

    intent_name = str(payload.get("intent") or "unknown").strip()
    if intent_name not in INTENTS:
        intent_name = "unknown"

    entities = payload.get("entities") or {}
    if not isinstance(entities, dict):
        entities = {}

    clean: dict[str, Any] = {}
    for key, value in entities.items():
        if value in (None, "", []):
            continue
        clean[key] = value

    language = _LANG_CODE.get(str(payload.get("language") or "").lower(), "hin")

    try:
        confidence = float(payload.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0

    return Intent(
        name=intent_name,
        confidence=max(0.0, min(1.0, confidence)),
        language=language,
        entities=clean,
        source="llm",
        raw_text=text,
    )


def merge_intents(lexicon: Intent, llm: Intent | None) -> Intent:
    """Combine the two passes. The LLM refines, it does not hallucinate intents."""
    if llm is None:
        return lexicon

    name = llm.name if llm.name != "unknown" else lexicon.name
    if lexicon.name != "unknown" and llm.name != "unknown" and llm.name != lexicon.name:
        # Trust the LLM only when it is clearly more confident.
        name = llm.name if llm.confidence >= lexicon.confidence + 0.05 else lexicon.name

    entities = dict(lexicon.entities)
    for key, value in llm.entities.items():
        if value in (None, "", []):
            continue
        entities[key] = value

    # Re-derive category metadata after a merge.
    category = entities.get("category")
    if category in CATEGORY_HI:
        entities["categoryHi"] = CATEGORY_HI[category]
        entities["categoryIcon"] = CATEGORY_ICON[category]
    elif category:
        entities.pop("category", None)

    return Intent(
        name=name,
        confidence=max(lexicon.confidence, llm.confidence) if name == llm.name else lexicon.confidence,
        language=llm.language if llm.language != "hin" else lexicon.language,
        entities=entities,
        source="lexicon+llm",
        raw_text=lexicon.raw_text,
    )


def analyze(text: str, use_llm: bool = True) -> Intent:
    """Full two-stage understanding of an utterance."""
    lexicon = lexicon_analyze(text)
    if not use_llm:
        return lexicon
    return merge_intents(lexicon, llm_analyze(text))
