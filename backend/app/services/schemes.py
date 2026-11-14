"""Grounded scheme Q&A over the RAG corpus.

Every factual claim in the answer is traceable to a retrieved chunk. When the LLM is
unavailable the answer is assembled deterministically from the same chunks, so the
citation chips on the UI always match the spoken reply.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.guardrails import strip_ungrounded_claims
from app.core.logging_conf import get_logger
from app.services import rag
from app.services.llm import LLMUnavailable, get_llm

log = get_logger(__name__)

_ANSWER_SYSTEM = (
    "You are JanVaani UP, a helpful assistant for Uttar Pradesh government schemes.\n"
    "Answer ONLY from the CONTEXT sections provided. Never invent an amount, a "
    "criterion, a document or a deadline that is not present in the context.\n"
    "Reply in simple spoken Hindi (Devanagari) that a rural user can understand, in "
    "3-5 short sentences, then a line starting with 'Documents:' if documents are "
    "relevant.\n"
    "If the context does not answer the question, say so plainly and mention which "
    "scheme is closest.\n"
    "Never promise that the user will definitely receive any benefit."
)

_CARD_SYSTEM = (
    "You convert a scheme explanation into a compact visual card for a phone screen. "
    "Reply with a single JSON object with keys: title, subtitle, bullets (array of "
    "max 4 short strings), cta. No prose outside the JSON."
)


def _fmt_amounts(scheme: dict[str, Any]) -> str:
    return scheme.get("amount", "")


def _offline_answer(query: str, chunks: list[rag.Chunk], intent_entities: dict[str, Any]) -> tuple[str, str]:
    """Deterministic bilingual answer built straight from the retrieved chunks."""
    if not chunks:
        return (
            "मुझे इस बारे में विश्वसनीय जानकारी नहीं मिली। कृपया कलेक्टर कार्यालय से संपर्क करें।",
            "I could not find reliable information on this. Please contact the district office.",
        )

    top = chunks[0]
    bigha = intent_entities.get("landBigha")

    parts: list[str] = []
    if top.scheme_id == "pm-kisan" and bigha:
        parts.append(f"आपके {bigha} बीघा जमीन के लिए सबसे उपयुक्त योजना {top.scheme_name_hi} ({top.short_name}) है।")
    else:
        parts.append(f"आपके सवाल के लिए सबसे उपयुक्त योजना {top.scheme_name_hi} ({top.short_name}) है।")

    if top.eligibility_hi:
        parts.append("मुख्य पात्रता शर्तें: " + "; ".join(top.eligibility_hi[:3]) + "।")
    elif top.body_hi:
        parts.append(top.body_hi)

    if intent_entities.get("asksDocuments") or True:
        docs = top.documents_hi[:3]
        if docs:
            parts.append("ज़रूरी दस्तावेज़: " + "; ".join(docs) + "।")

    extra = [c for c in chunks[1:] if c.scheme_id != top.scheme_id][:2]
    if extra:
        names = ", ".join({c.short_name for c in extra})
        parts.append(f"इसके अलावा आप {names} के लिए भी पात्र हो सकते हैं।")

    parts.append(f"पूरी जानकारी का स्रोत: {top.source}।")

    hindi = " ".join(parts)

    english_parts = [f"Best match: {top.scheme_name} ({top.short_name})."]
    if top.eligibility:
        english_parts.append("Key criteria: " + "; ".join(top.eligibility[:3]) + ".")
    if top.documents:
        english_parts.append("Documents: " + "; ".join(top.documents[:3]) + ".")
    english = " ".join(english_parts)

    return hindi, english


def _llm_answer(query: str, chunks: list[rag.Chunk]) -> tuple[str, str] | None:
    llm = get_llm()
    if not llm.available or not chunks:
        return None

    context_blocks = []
    for chunk in chunks:
        context_blocks.append(
            f"[{chunk.section_id}] {chunk.scheme_name} - {chunk.title}\n"
            f"{chunk.body}\n"
            f"Amount: {chunk.amounts}\n"
            f"Eligibility: {'; '.join(chunk.eligibility[:5])}\n"
            f"Documents: {'; '.join(chunk.documents[:5])}"
        )
    context = "\n\n".join(context_blocks)

    messages = [
        {"role": "system", "content": _ANSWER_SYSTEM},
        {
            "role": "user",
            "content": f"CONTEXT:\n{context}\n\nQUESTION (spoken by a citizen):\n{query}",
        },
    ]
    try:
        text = llm.chat(messages, temperature=0.2, max_tokens=700)
    except LLMUnavailable:
        return None
    if not text:
        return None

    allowed = [a for chunk in chunks for a in chunk.amounts]
    text = strip_ungrounded_claims(text, allowed)

    # Keep the English line short and derived from the same context.
    english = _offline_answer(query, chunks, {})[1]
    return text, english


def search(query: str, top_k: int = 3) -> list[tuple[rag.Chunk, float]]:
    return rag.get_retriever().search(query, top_k=top_k)


def search_chunks(query: str, top_k: int = 3) -> list[rag.Chunk]:
    """Retrieved chunks without their scores."""
    return [chunk for chunk, _ in search(query, top_k=top_k)]


def answer_question(
    query: str,
    *,
    intent_entities: dict[str, Any] | None = None,
    top_k: int = 3,
    scheme_filter: str | None = None,
) -> dict[str, Any]:
    """Answer a scheme question with citations and a set of visual cards."""
    intent_entities = intent_entities or {}
    if scheme_filter:
        ranked = rag.get_retriever().search(query, top_k=top_k, scheme_filter=scheme_filter)
        if not ranked:
            ranked = rag.get_retriever().search(query, top_k=top_k)
    else:
        ranked = search(query, top_k=top_k)
    if not ranked:
        # Broaden the search - drop to the whole corpus.
        ranked = rag.get_retriever().search(query, top_k=5)
    chunks = [chunk for chunk, _ in ranked]
    scores = {chunk.scheme_id: score for chunk, score in ranked}

    llm_result = _llm_answer(query, chunks) if chunks else None
    if llm_result:
        hindi, english = llm_result
        source = "llm+rag"
    else:
        hindi, english = _offline_answer(query, chunks, intent_entities)
        source = "rag"

    citations = rag.build_citations(chunks, limit=3)
    schemes = []
    seen: set[str] = set()
    for chunk in chunks:
        if chunk.scheme_id in seen:
            continue
        seen.add(chunk.scheme_id)
        scheme = rag.get_scheme(chunk.scheme_id)
        if scheme:
            schemes.append(
                {
                    "id": scheme["id"],
                    "name": scheme["name"],
                    "nameHi": scheme.get("name_hi", ""),
                    "shortName": scheme.get("short_name", scheme["name"]),
                    "icon": scheme.get("icon", "📄"),
                    "categoryHi": scheme.get("category_hi", ""),
                    "amount": scheme.get("amount", ""),
                    "summaryHi": scheme.get("summary_hi", ""),
                    "score": round(scores.get(chunk.scheme_id, 0.0), 3),
                }
            )

    return {
        "answer": hindi,
        "answerHi": hindi,
        "answerEn": english,
        "citations": [c.to_dict() for c in citations],
        "schemes": schemes,
        "source": source,
    }


def list_cards() -> list[dict[str, Any]]:
    """Cards describing every scheme in the corpus (used by the schemes tab)."""
    cards = []
    for scheme in rag.load_schemes():
        cards.append(
            {
                "type": "scheme",
                "id": scheme["id"],
                "icon": scheme.get("icon", "📄"),
                "title": scheme.get("name_hi", scheme["name"]),
                "subtitle": scheme.get("short_name", scheme["name"]),
                "category": scheme.get("category_hi", ""),
                "body": scheme.get("summary_hi", ""),
                "amount": scheme.get("amount", ""),
                "fields": [
                    {"label": "योजना", "value": scheme.get("short_name", scheme["name"])},
                    {"label": "किसने शुरू की", "value": scheme.get("authority", "")},
                    {"label": "कहाँ लागू", "value": scheme.get("state", "")},
                    {"label": "लाभ", "value": scheme.get("amount", "")},
                ],
                "actions": [
                    {"label": "पात्रता पूछें", "action": "ask_eligibility", "payload": scheme.get("short_name", "")},
                    {"label": "दस्तावेज़", "action": "ask_documents", "payload": scheme.get("short_name", "")},
                ],
            }
        )
    return cards


def scheme_card(scheme_id: str) -> dict[str, Any] | None:
    scheme = rag.get_scheme(scheme_id)
    if not scheme:
        return None
    sections = scheme.get("sections", [])
    elig = sections[0].get("eligibility_hi", []) if sections else []
    docs = sections[0].get("documents_hi", []) if sections else []
    return {
        "type": "scheme",
        "id": scheme["id"],
        "icon": scheme.get("icon", "📄"),
        "title": scheme.get("name_hi", scheme["name"]),
        "subtitle": scheme.get("short_name", scheme["name"]),
        "category": scheme.get("category_hi", ""),
        "body": scheme.get("summary_hi", ""),
        "amount": scheme.get("amount", ""),
        "fields": [
            {"label": "पात्रता", "value": " • ".join(elig[:4])},
            {"label": "दस्तावेज़", "value": " • ".join(docs[:4])},
            {"label": "किसने शुरू की", "value": scheme.get("authority", "")},
            {"label": "कहाँ लागू", "value": scheme.get("state", "")},
        ],
        "actions": [
            {"label": "आवेदन कैसे करें", "action": "ask_apply", "payload": scheme.get("short_name", "")},
        ],
    }


def resolve_scheme_name(text: str) -> str | None:
    """Map a spoken scheme name to a scheme id."""
    lowered = (text or "").lower()
    best: tuple[str, int] | None = None
    for scheme in rag.load_schemes():
        candidates = [
            scheme["id"].replace("-", " "),
            scheme.get("short_name", ""),
            scheme.get("name", ""),
        ]
        for candidate in candidates:
            if candidate and candidate.lower() in lowered:
                if best is None or len(candidate) > best[1]:
                    best = (scheme["id"], len(candidate))
    return best[0] if best else None


_WHITESPACE = re.compile(r"\s+")


def tidy(text: str) -> str:
    return _WHITESPACE.sub(" ", (text or "").strip())
