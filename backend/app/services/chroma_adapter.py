"""Optional ChromaDB vector backend.

The default retrieval engine (`rag.HybridRetriever`) needs no model download and no
extra dependency. This adapter provides a drop-in alternative for teams that want a
real vector database.

Enable it with::

    VECTOR_BACKEND=chroma
    py -m pip install chromadb

The adapter implements the same `search(query, top_k, scheme_filter)` contract, so
nothing above this layer has to change.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services import rag

log = logging.getLogger(__name__)

COLLECTION = "janvaani_schemes"


class ChromaVectorStore:
    """Thin wrapper around a persistent ChromaDB collection."""

    def __init__(self, path: str = "./.runtime/chroma", model: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        import chromadb  # imported lazily so the default install stays light

        self.client = chromadb.PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        self.model_name = model
        self._embedder = None
        self._seeded = False

    # -- embeddings ----------------------------------------------------------
    def _embed(self, texts: list[str]) -> list[list[float]]:
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer  # type: ignore

            self._embedder = SentenceTransformer(self.model_name)
        vectors = self._embedder.encode(texts, normalize_embeddings=True)
        return [list(map(float, vector)) for vector in vectors]

    # -- indexing ------------------------------------------------------------
    def seed(self, chunks: list[rag.Chunk]) -> None:
        """(Re)build the collection from the local corpus."""
        if not chunks:
            return
        documents = [chunk.searchable_text() for chunk in chunks]
        metadatas = [
            {
                "chunk_id": chunk.chunk_id,
                "scheme_id": chunk.scheme_id,
                "section_id": chunk.section_id,
                "short_name": chunk.short_name,
                "source": chunk.source,
            }
            for chunk in chunks
        ]
        embeddings = self._embed(documents)
        self.collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )
        self._seeded = True
        log.info("Seeded Chroma collection with %s chunks", len(chunks))

    def _ensure_seeded(self) -> None:
        if not self._seeded:
            self.seed(rag.get_retriever().chunks)

    # -- retrieval -----------------------------------------------------------
    def search(
        self, query: str, top_k: int = 3, scheme_filter: str | None = None
    ) -> list[tuple[rag.Chunk, float]]:
        self._ensure_seeded()
        where = {"scheme_id": scheme_filter} if scheme_filter else None
        result = self.collection.query(
            query_embeddings=self._embed([query]),
            n_results=top_k,
            where=where,
        )
        ids = (result.get("ids") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        by_id = {chunk.chunk_id: chunk for chunk in rag.get_retriever().chunks}
        out: list[tuple[rag.Chunk, float]] = []
        for chunk_id, distance in zip(ids, distances):
            chunk = by_id.get(chunk_id)
            if chunk is not None:
                out.append((chunk, max(0.0, 1.0 - float(distance))))
        return out

    def health(self) -> dict[str, Any]:
        return {
            "backend": "chroma",
            "collection": COLLECTION,
            "embeddingModel": self.model_name,
            "count": self.collection.count(),
        }
