"""Optional ChromaDB vector backend.

The default retriever (`services/rag.py`) needs no downloads and starts instantly,
which is the right trade-off for a demo. When a real vector database is wanted -
for a larger corpus, or when hybrid retrieval is replaced by pure embeddings -
set `VECTOR_BACKEND=chroma` and install `chromadb`.

This module implements the same interface the orchestrator uses, so switching is a
one-line environment change and nothing else in the codebase moves.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

log = logging.getLogger(__name__)


class ChromaVectorStore:
    """Thin wrapper around a persistent Chroma collection.

    Falls back to the built-in hybrid retriever when `chromadb` is not installed,
    so a misconfigured environment degrades instead of failing.
    """

    def __init__(self, persist_dir: str = "./.runtime/chroma", collection: str = "janvaani_schemes"):
        self.persist_dir = persist_dir
        self.collection_name = collection
        self._client: Any = None
        self._collection: Any = None
        self.available = False
        self._init()

    def _init(self) -> None:
        try:
            import chromadb  # type: ignore

            self._client = chromadb.PersistentClient(path=self.persist_dir)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            self.available = True
            log.info("ChromaDB vector store ready at %s", self.persist_dir)
        except Exception as exc:
            log.warning(
                "ChromaDB is unavailable (%s) - falling back to the built-in hybrid retriever",
                exc,
            )
            self.available = False

    # -- corpus -------------------------------------------------------------
    def upsert(self, documents: list[dict[str, Any]]) -> None:
        """Index chunks. Each document must carry a unique `chunkId`."""
        if not self.available or not documents:
            return
        ids = [doc["chunkId"] for doc in documents]
        texts = [doc.get("text", "") for doc in documents]
        metadatas = [{k: v for k, v in doc.items() if k != "text"} for doc in documents]
        self._collection.upsert(ids=ids, documents=texts, metadatas=metadatas)

    # -- retrieval ----------------------------------------------------------
    def query(self, query: str, top_k: int = 3) -> list[tuple[str, float]]:
        """Return `(chunk_id, score)` pairs, best first."""
        if not self.available:
            return []
        result = self._collection.query(query_texts=[query], n_results=top_k)
        ids = (result.get("ids") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        return [(chunk_id, 1.0 - float(distance)) for chunk_id, distance in zip(ids, distances)]

    def get(self, chunk_id: str) -> dict[str, Any] | None:
        if not self.available:
            return None
        result = self._collection.get(ids=[chunk_id])
        metadatas = result.get("metadatas") or []
        documents = result.get("documents") or []
        if not metadatas:
            return None
        return {**metadatas[0], "text": documents[0] if documents else ""}

    def reset(self) -> None:
        if self.available:
            self._client.delete_collection(self.collection_name)


def chunk_id_for(scheme_id: str, section_id: str) -> str:
    """Stable id for a chunk - Chroma requires unique string ids."""
    digest = hashlib.sha1(f"{scheme_id}::{section_id}".encode("utf-8")).hexdigest()[:16]
    return f"{scheme_id}-{section_id}-{digest}"
