"""Isolated retrieval adapter backed by the existing vector index service."""

from __future__ import annotations

from typing import Any

from ..vector_index_service import vector_index_service
from .scoring import normalize_bool_label


class RetrievalAdapter:
    def __init__(self, preferred_mode: str = "faiss") -> None:
        self.preferred_mode = preferred_mode
        self.index = None
        self.status: dict[str, Any] = {"retrieval_mode": "empty", "document_count": 0}

    def build_index(self, documents: list[dict[str, Any]]) -> "RetrievalAdapter":
        chunks = [self._to_chunk(index, document) for index, document in enumerate(documents, start=1)]
        self.index = vector_index_service.build_index(chunks, preferred_mode=self.preferred_mode)
        self.status = self.index.status()
        return self

    def retrieve(self, query: str, top_k: int) -> list[dict[str, Any]]:
        if self.index is None:
            return []
        rows = self.index.search(query, top_k)
        self.status = self.index.status()
        return [self._to_result(row) for row in rows]

    def _to_chunk(self, index: int, document: dict[str, Any]) -> dict[str, Any]:
        metadata = dict(document.get("metadata") or {})
        trust_label = document.get("trust_label") or metadata.get("trust_label") or "trusted"
        source_id = str(document.get("source_id") or metadata.get("source_id") or document.get("document_id") or f"source-{index}")
        document_id = str(document.get("document_id") or f"doc-{index}")
        return {
            "chunk_id": str(document.get("chunk_id") or document_id),
            "document_id": document_id,
            "source": source_id,
            "source_id": source_id,
            "content": str(document.get("content", "")),
            "trust_label": trust_label,
            "trust_level": trust_label,
            "poison_label": normalize_bool_label(metadata.get("poison_label")) or trust_label == "poison",
            "cluster_id": metadata.get("cluster_id"),
            "claim_id": metadata.get("claim_id"),
            "root_source_id": metadata.get("root_source_id") or source_id,
            "copied_from": metadata.get("copied_from"),
            "metadata": metadata,
        }

    def _to_result(self, row: dict[str, Any]) -> dict[str, Any]:
        metadata = dict(row.get("metadata") or {})
        trust_label = row.get("trust_label") or row.get("trust_level")
        return {
            "chunk_id": str(row.get("chunk_id") or row.get("document_id")),
            "document_id": str(row.get("document_id") or row.get("chunk_id")),
            "source_id": str(row.get("source_id") or row.get("source") or row.get("document_id")),
            "content": str(row.get("content", "")),
            "rank": int(row.get("rank") or row.get("retrieval_rank") or 0),
            "retrieval_score": float(row.get("retrieval_score") or row.get("score") or row.get("similarity") or 0.0),
            "poison_label": normalize_bool_label(row.get("poison_label")) or trust_label == "poison" or normalize_bool_label(metadata.get("poison_label")),
            "cluster_id": row.get("cluster_id") or metadata.get("cluster_id"),
            "claim_id": row.get("claim_id") or metadata.get("claim_id"),
            "root_source_id": row.get("root_source_id") or metadata.get("root_source_id") or row.get("source_id") or row.get("source"),
            "copied_from": row.get("copied_from") or metadata.get("copied_from"),
            "retrieval_mode": row.get("retrieval_mode") or self.status.get("retrieval_mode"),
            "fallback_reason": row.get("fallback_reason") or self.status.get("fallback_reason"),
        }
