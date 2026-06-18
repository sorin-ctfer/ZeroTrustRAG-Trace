"""Local LangChain document indexing with FAISS/TF-IDF fallback."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from langchain_core.documents import Document
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


REQUIRED_RESULT_FIELDS = (
    "chunk_id",
    "document_id",
    "source",
    "content",
    "trust_label",
    "similarity",
    "rank",
    "retrieval_mode",
)


def chunk_to_document(chunk: dict[str, Any]) -> Document:
    """Convert an application Chunk dict to a LangChain Document."""
    return Document(
        page_content=str(chunk.get("content", "")),
        metadata={
            "chunk_id": chunk.get("chunk_id", ""),
            "document_id": chunk.get("document_id", ""),
            "source": chunk.get("source", ""),
            "trust_label": chunk.get("trust_label") or chunk.get("trust_level", "trusted"),
            "trust_level": chunk.get("trust_level") or chunk.get("trust_label", "trusted"),
            "source_type": chunk.get("source_type", ""),
            "risk_score": chunk.get("risk_score", 0.0),
            "is_poison_candidate": chunk.get("is_poison_candidate", False),
            **{k: v for k, v in chunk.items() if k not in {"content"}},
        },
    )


def document_to_chunk(document: Document) -> dict[str, Any]:
    """Convert a LangChain Document back to the project's Chunk dict shape."""
    metadata = dict(document.metadata)
    trust_label = metadata.get("trust_label") or metadata.get("trust_level", "trusted")
    return {
        **metadata,
        "content": document.page_content,
        "trust_label": trust_label,
        "trust_level": metadata.get("trust_level") or trust_label,
    }


@dataclass
class VectorIndex:
    """A small local index that prefers FAISS over plain TF-IDF search.

    The vectors are produced by local TF-IDF. FAISS is used only as a fast local
    similarity index when installed; otherwise search falls back to TF-IDF
    cosine similarity and returns that fallback state to callers.
    """

    documents: list[Document] = field(default_factory=list)
    preferred_mode: str = "faiss"
    retrieval_mode: str = "empty"
    fallback_reason: str | None = None
    vectorizer: TfidfVectorizer | None = None
    matrix: Any = None
    faiss_index: Any = None

    def build_index(self, chunks: list[dict[str, Any]]) -> "VectorIndex":
        self.documents = [chunk_to_document(chunk) for chunk in chunks if str(chunk.get("content", "")).strip()]
        self.retrieval_mode = "empty"
        self.fallback_reason = None
        self.vectorizer = None
        self.matrix = None
        self.faiss_index = None
        if not self.documents:
            return self

        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
        self.matrix = self.vectorizer.fit_transform([doc.page_content for doc in self.documents])
        if self.preferred_mode != "faiss":
            self.retrieval_mode = "tfidf_fallback"
            self.fallback_reason = "FAISS disabled by configuration"
            return self

        try:
            import faiss  # type: ignore

            dense = self.matrix.astype("float32").toarray()
            faiss.normalize_L2(dense)
            index = faiss.IndexFlatIP(dense.shape[1])
            index.add(dense)
            self.faiss_index = index
            self.retrieval_mode = "faiss_tfidf"
        except Exception as exc:
            self.faiss_index = None
            self.retrieval_mode = "tfidf_fallback"
            self.fallback_reason = f"FAISS unavailable: {exc}"
        return self

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        if not query.strip() or not self.documents or self.vectorizer is None or self.matrix is None:
            return []
        top_k = max(1, min(top_k, len(self.documents)))
        query_vec = self.vectorizer.transform([query])
        if self.faiss_index is not None:
            try:
                import faiss  # type: ignore

                dense_query = query_vec.astype("float32").toarray()
                faiss.normalize_L2(dense_query)
                scores, indexes = self.faiss_index.search(dense_query, top_k)
                order = [int(idx) for idx in indexes[0] if int(idx) >= 0]
                similarities = {int(idx): float(score) for idx, score in zip(indexes[0], scores[0]) if int(idx) >= 0}
                return self._format_results(order, similarities)
            except Exception as exc:
                self.retrieval_mode = "tfidf_fallback"
                self.fallback_reason = f"FAISS search failed: {exc}"
        scores = cosine_similarity(query_vec, self.matrix).ravel()
        order = [int(idx) for idx in np.argsort(scores)[::-1][:top_k]]
        similarities = {idx: float(scores[idx]) for idx in order}
        if self.retrieval_mode == "empty":
            self.retrieval_mode = "tfidf_fallback"
        return self._format_results(order, similarities)

    def status(self) -> dict[str, Any]:
        return {
            "retrieval_mode": self.retrieval_mode,
            "fallback_reason": self.fallback_reason,
            "document_count": len(self.documents),
        }

    def _format_results(self, order: list[int], similarities: dict[int, float]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for rank, idx in enumerate(order, start=1):
            chunk = document_to_chunk(self.documents[idx])
            trust_label = chunk.get("trust_label") or chunk.get("trust_level", "trusted")
            item = {
                **chunk,
                "trust_label": trust_label,
                "trust_level": chunk.get("trust_level") or trust_label,
                "similarity": round(float(similarities.get(idx, 0.0)), 4),
                "score": round(float(similarities.get(idx, 0.0)), 4),
                "rank": rank,
                "retrieval_rank": rank,
                "retrieval_mode": self.retrieval_mode,
                "fallback_reason": self.fallback_reason,
            }
            for field_name in REQUIRED_RESULT_FIELDS:
                item.setdefault(field_name, "")
            results.append(item)
        return results


class VectorIndexService:
    def build_index(self, chunks: list[dict[str, Any]], preferred_mode: str = "faiss") -> VectorIndex:
        return VectorIndex(preferred_mode=preferred_mode).build_index(chunks)

    def search(self, query: str, chunks: list[dict[str, Any]], top_k: int = 5, preferred_mode: str = "faiss") -> tuple[list[dict[str, Any]], dict[str, Any]]:
        index = self.build_index(chunks, preferred_mode=preferred_mode)
        results = index.search(query, top_k)
        return results, index.status()

    def build_temporary_session_index(self, trusted_chunks: list[dict[str, Any]], injected_poison_chunks: list[dict[str, Any]], preferred_mode: str = "faiss") -> VectorIndex:
        return self.build_index(trusted_chunks + injected_poison_chunks, preferred_mode=preferred_mode)


vector_index_service = VectorIndexService()
