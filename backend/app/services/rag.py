"""Hybrid retrieval over the official scheme corpus.

No heavyweight model download is required: the retriever combines

  * **BM25** lexical scoring (good for rare terms like `khasra`, `chauthai`)
  * **Character n-gram cosine** (good for dialect spellings: *bijli / bijlee / bhiJli*)

and both are computed over a normalised token stream that keeps Devanagari intact.
Swapping in a real vector database is a one-line change - see `chroma_adapter.py`.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_WORD_RE = re.compile(r"[\w\u0900-\u097F]+", re.UNICODE)

# Light Hindi/English suffix stripping - improves recall without an external stemmer.
_SUFFIXES = ("ियाँ", "ियों", "िया", "िए", "ां", "ाँ", "ें", "ो", "ी", "ू", "ु", "े", "ा", "ीं", "ें")

_STOPWORDS = {
    "hai", "hain", "ho", "h", "ka", "ki", "ke", "ko", "me", "se", "par", "aur", "ya", "to",
    "the", "and", "for", "with", "that", "this", "from", "are", "was", "have", "has", "not",
    "में", "है", "हैं", "का", "की", "के", "को", "से", "और", "या", "पर", "हो", "था", "थी", "थे",
    "कि", "जो", "यह", "वह", "एक", "भी", "ही", "तो", "अपने", "आप", "हम", "मैं",
}

# Dialect -> canonical expansions. Used to bridge Bhojpuri/Awadhi vocabulary.
_EXPANSION_MAP: dict[str, list[str]] = {
    "bijli": ["bijli", "electricity", "power", "transformer", "current", "light", "bijli bill"],
    "bijlee": ["bijli", "electricity"],
    "bhiJli": ["bijli", "electricity"],
    "zameen": ["zameen", "land", "khatauni", "khasra", "bigha"],
    "zamin": ["zameen", "land"],
    "bigha": ["bigha", "land", "zameen", "land holding"],
    "bighai": ["bigha", "land", "zameen"],
    "kisan": ["kisan", "farmer", "pm kisan", "kisan credit card"],
    "khata": ["khatauni", "khasra", "land record"],
    "khatauni": ["khatauni", "khasra", "land record"],
    "khasra": ["khasra", "khatauni", "land record"],
    "gaon": ["village", "gaon"],
    "paisa": ["paisa", "money", "instalment", "benefit", "subsidy"],
    "yaojana": ["yojana", "scheme"],
    "yogana": ["yojana", "scheme"],
    "keemat": ["eligibility", "patra", "qualify"],
    "jala": ["burnt", "transformer", "electricity", "fire"],
    "mor": ["dead", "burnt", "transformer"],
    "suno": ["complaint", "grievance", "listen"],
    "suna": ["complaint", "grievance"],
    "paani": ["paani", "water", "drinking water"],
    "pani": ["paani", "water"],
    "ration": ["ration", "nfsa", "food grain", "rashan"],
    "rashan": ["ration", "nfsa", "food grain"],
    "pension": ["pension", "old age", "widow", "disabled"],
    "awas": ["awas", "housing", "house", "ghar"],
    "ghar": ["ghar", "house", "housing", "awas"],
    "sarkari": ["sarkari", "government", "yojana"],
    "kanya": ["kanya", "girl child", "sumangala"],
    "ladki": ["kanya", "girl child", "sumangala"],
    "kcc": ["kcc", "kisan credit card", "loan"],
    "bima": ["bima", "insurance", "pmfby"],
    "naukari": ["employment", "rozgaar"],
    "naukar": ["employment", "rozgaar"],
}


def normalise_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace - keeps Devanagari."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^\w\u0900-\u097F\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(normalise_text(text))


def light_stem(token: str) -> str:
    """Very conservative suffix stripper - only for tokens long enough to be safe."""
    if len(token) <= 4 or not token.isalpha():
        return token
    for suf in _SUFFIXES:
        if token.endswith(suf) and len(token) - len(suf) >= 3:
            return token[: -len(suf)]
    return token


def expand_query(query: str) -> str:
    """Append canonical synonyms for dialect tokens found in the query."""
    extra: list[str] = []
    tokens = tokenize(query)
    for tok in tokens:
        for key, values in _EXPANSION_MAP.items():
            if tok == key or tok.startswith(key) or key.startswith(tok):
                extra.extend(values)
                break
    if not extra:
        return query
    return f"{query} {' '.join(extra)}"


@dataclass
class Chunk:
    """One retrievable unit of scheme knowledge."""

    chunk_id: str
    scheme_id: str
    scheme_name: str
    scheme_name_hi: str
    short_name: str
    category: str
    category_hi: str
    icon: str
    section_id: str
    title: str
    title_hi: str
    body: str
    body_hi: str
    eligibility: list[str] = field(default_factory=list)
    eligibility_hi: list[str] = field(default_factory=list)
    documents: list[str] = field(default_factory=list)
    documents_hi: list[str] = field(default_factory=list)
    source: str = ""
    page: int = 0
    amounts: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @property
    def citation(self) -> str:
        return f"{self.short_name} §{self.section_id.split('.')[-1]}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunkId": self.chunk_id,
            "schemeId": self.scheme_id,
            "schemeName": self.scheme_name,
            "schemeNameHi": self.scheme_name_hi,
            "shortName": self.short_name,
            "category": self.category,
            "categoryHi": self.category_hi,
            "icon": self.icon,
            "sectionId": self.section_id,
            "title": self.title,
            "titleHi": self.title_hi,
            "body": self.body,
            "bodyHi": self.body_hi,
            "eligibility": self.eligibility,
            "eligibilityHi": self.eligibility_hi,
            "documents": self.documents,
            "documentsHi": self.documents_hi,
            "source": self.source,
            "page": self.page,
            "amounts": self.amounts,
            "citation": self.citation,
        }

    def searchable_text(self) -> str:
        parts = [
            self.scheme_name,
            self.scheme_name_hi,
            self.short_name,
            self.category,
            self.category_hi,
            self.title,
            self.title_hi,
            self.body,
            self.body_hi,
            " ".join(self.eligibility),
            " ".join(self.eligibility_hi),
            " ".join(self.documents),
            " ".join(self.documents_hi),
            " ".join(self.tags),
        ]
        return " \n".join(p for p in parts if p)


@dataclass
class Citation:
    scheme_id: str
    scheme_name: str
    short_name: str
    section_id: str
    title: str
    title_hi: str
    quote: str
    quote_hi: str
    source: str
    page: int
    icon: str = "📄"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemeId": self.scheme_id,
            "schemeName": self.scheme_name,
            "shortName": self.short_name,
            "sectionId": self.section_id,
            "title": self.title,
            "titleHi": self.title_hi,
            "quote": self.quote,
            "quoteHi": self.quote_hi,
            "source": self.source,
            "page": self.page,
            "icon": self.icon,
            "citation": f"{self.short_name} §{self.section_id.split('.')[-1]}",
        }


class HybridRetriever:
    """BM25 + character n-gram cosine retriever over the scheme corpus."""

    K1 = 1.5
    B = 0.75

    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self._tokenised: list[list[str]] = []
        self._ngrams: list[Counter[str]] = []
        self._doc_freq: Counter[str] = Counter()
        self._avg_len = 0.0
        self._build()

    # -- index ---------------------------------------------------------------
    def _build(self) -> None:
        for chunk in self.chunks:
            tokens = tokenize(chunk.searchable_text())
            self._tokenised.append(tokens)
            for tok in tokens:
                self._doc_freq[tok] += 1
            self._ngrams.append(self._char_ngrams(chunk.searchable_text()))
        lengths = [len(t) for t in self._tokenised] or [1]
        self._avg_len = sum(lengths) / len(lengths)

    @staticmethod
    def _char_ngrams(text: str, sizes: Iterable[int] = (3, 4)) -> Counter[str]:
        norm = normalise_text(text)
        grams: Counter[str] = Counter()
        for size in sizes:
            for i in range(max(0, len(norm) - size + 1)):
                grams[norm[i : i + size]] += 1
        return grams

    @staticmethod
    def _cosine(a: Counter[str], b: Counter[str]) -> float:
        if not a or not b:
            return 0.0
        common = set(a) & set(b)
        if not common:
            return 0.0
        num = sum(a[g] * b[g] for g in common)
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        return num / (na * nb) if na and nb else 0.0

    # -- scoring -------------------------------------------------------------
    def _bm25(self, query_tokens: list[str], doc_index: int) -> float:
        doc = self._tokenised[doc_index]
        if not doc:
            return 0.0
        doc_counts = Counter(doc)
        total_docs = len(self._tokenised)
        score = 0.0
        for token in query_tokens:
            if token in _STOPWORDS or len(token) < 2:
                continue
            df = self._doc_freq.get(token, 0)
            if df == 0:
                # try the light stem as a fallback
                stem = light_stem(token)
                df = self._doc_freq.get(stem, 0)
                if df == 0:
                    continue
                token = stem
            idf = math.log(1 + (total_docs - df + 0.5) / (df + 0.5))
            tf = doc_counts.get(token, 0)
            if not tf:
                continue
            denom = tf + self.K1 * (1 - self.B + self.B * len(doc) / self._avg_len)
            score += idf * (tf * (self.K1 + 1)) / denom
        return score

    def search(self, query: str, top_k: int = 3, scheme_filter: str | None = None) -> list[tuple[Chunk, float]]:
        """Return the top-k chunks with a normalised hybrid score."""
        if not query or not query.strip():
            return []

        expanded = expand_query(query)
        query_tokens = tokenize(expanded)
        query_grams = self._char_ngrams(expanded)

        raw: list[tuple[int, float]] = []
        for idx in range(len(self.chunks)):
            if scheme_filter and self.chunks[idx].scheme_id != scheme_filter:
                continue
            bm25 = self._bm25(query_tokens, idx)
            cos = self._cosine(query_grams, self._ngrams[idx])
            raw.append((idx, bm25 + 0.85 * cos))

        if not raw:
            return []
        max_score = max(s for _, s in raw) or 1.0
        ranked = sorted(raw, key=lambda kv: kv[1], reverse=True)
        results = [(self.chunks[i], (s / max_score)) for i, s in ranked if s > 0]
        return results[:top_k]

    def chunks_for_scheme(self, scheme_id: str) -> list[Chunk]:
        return [c for c in self.chunks if c.scheme_id == scheme_id]


# ---------------------------------------------------------------------------
# Corpus loading
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def load_schemes() -> list[dict[str, Any]]:
    path = DATA_DIR / "schemes.json"
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def get_retriever() -> HybridRetriever:
    chunks: list[Chunk] = []
    for scheme in load_schemes():
        for section in scheme.get("sections", []):
            chunks.append(
                Chunk(
                    chunk_id=f"{scheme['id']}::{section['id']}",
                    scheme_id=scheme["id"],
                    scheme_name=scheme["name"],
                    scheme_name_hi=scheme.get("name_hi", ""),
                    short_name=scheme.get("short_name", scheme["name"]),
                    category=scheme.get("category", "general"),
                    category_hi=scheme.get("category_hi", ""),
                    icon=scheme.get("icon", "📄"),
                    section_id=section["id"],
                    title=section.get("title", ""),
                    title_hi=section.get("title_hi", ""),
                    body=section.get("body", ""),
                    body_hi=section.get("body_hi", ""),
                    eligibility=section.get("eligibility", []),
                    eligibility_hi=section.get("eligibility_hi", []),
                    documents=section.get("documents", []),
                    documents_hi=section.get("documents_hi", []),
                    source=section.get("source", ""),
                    page=section.get("page", 0),
                    amounts=scheme.get("amounts", []),
                    tags=scheme.get("tags", []),
                )
            )
    return HybridRetriever(chunks)


def get_scheme(scheme_id: str) -> dict[str, Any] | None:
    for scheme in load_schemes():
        if scheme["id"] == scheme_id:
            return scheme
    return None


def all_schemes_summary() -> list[dict[str, Any]]:
    out = []
    for scheme in load_schemes():
        out.append(
            {
                "id": scheme["id"],
                "name": scheme["name"],
                "nameHi": scheme.get("name_hi", ""),
                "shortName": scheme.get("short_name", scheme["name"]),
                "category": scheme.get("category", ""),
                "categoryHi": scheme.get("category_hi", ""),
                "authority": scheme.get("authority", ""),
                "state": scheme.get("state", ""),
                "launched": scheme.get("launched", ""),
                "summary": scheme.get("summary", ""),
                "summaryHi": scheme.get("summary_hi", ""),
                "amount": scheme.get("amount", ""),
                "icon": scheme.get("icon", "📄"),
                "tags": scheme.get("tags", []),
                "sectionCount": len(scheme.get("sections", [])),
            }
        )
    return out


def build_citations(chunks: list[Chunk], limit: int = 3) -> list[Citation]:
    citations: list[Citation] = []
    for chunk in chunks[:limit]:
        citations.append(
            Citation(
                scheme_id=chunk.scheme_id,
                scheme_name=chunk.scheme_name,
                short_name=chunk.short_name,
                section_id=chunk.section_id,
                title=chunk.title,
                title_hi=chunk.title_hi,
                quote=chunk.body,
                quote_hi=chunk.body_hi,
                source=chunk.source,
                page=chunk.page,
                icon=chunk.icon,
            )
        )
    return citations
