"""Persistent local knowledge store and FAISS index for interactive RAG."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from .bailian_llm_service import get_embeddings

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "interactive_chunks.json"
ACTIVE_TRUST_LEVELS = {"trusted", "unknown", "suspicious", "poisoned"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _split_text(content: str, chunk_size: int = 700, overlap: int = 80) -> list[str]:
    content = content.strip()
    if not content:
        return []
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            separators=["\n\n", "\n", "。", "；", "，", " ", ""],
        )
        return [part.strip() for part in splitter.split_text(content) if part.strip()]
    except ImportError:
        step = max(1, chunk_size - overlap)
        return [content[i:i + chunk_size] for i in range(0, len(content), step)]


class InteractiveVectorStore:
    """Manage trusted and locally injected knowledge chunks."""

    def __init__(self, data_file: Path = DATA_FILE) -> None:
        self.data_file = data_file
        self._lock = threading.RLock()
        self._chunks: list[dict[str, Any]] = []
        self._vector_store = None
        self._load()

    def _load(self) -> None:
        with self._lock:
            if not self.data_file.exists():
                self._chunks = []
                return
            try:
                data = json.loads(self.data_file.read_text(encoding="utf-8"))
                self._chunks = data if isinstance(data, list) else []
            except (OSError, json.JSONDecodeError):
                self._chunks = []

    def _save(self) -> None:
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        self.data_file.write_text(
            json.dumps(self._chunks, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _add_text(
        self,
        content: str,
        source: str,
        trust_level: str,
        is_poison_candidate: bool,
    ) -> list[dict[str, Any]]:
        parts = _split_text(content)
        if not parts:
            raise ValueError("Knowledge content cannot be empty")
        created: list[dict[str, Any]] = []
        with self._lock:
            for part in parts:
                chunk = {
                    "chunk_id": f"CHUNK-{uuid.uuid4().hex[:12]}",
                    "content": part,
                    "source": source.strip() or "manual",
                    "trust_level": trust_level,
                    "created_at": _now(),
                    "is_poison_candidate": is_poison_candidate,
                    "risk_score": 0.75 if is_poison_candidate else 0.0,
                    "metadata": {"local_demo_only": True},
                }
                self._chunks.append(chunk)
                created.append(dict(chunk))
            self._save()
            self._vector_store = None
        return created

    def add_trusted_text(self, content: str, source: str = "manual_trusted") -> list[dict[str, Any]]:
        return self._add_text(content, source, "trusted", False)

    def inject_poison_text(self, content: str, source: str = "manual_poison") -> list[dict[str, Any]]:
        return self._add_text(content, source, "poisoned", True)

    def list_chunks(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(chunk) for chunk in self._chunks]

    def clear(self) -> None:
        with self._lock:
            self._chunks = []
            self._vector_store = None
            if self.data_file.exists():
                self.data_file.unlink()

    def update_risk_scores(self, scores: dict[str, float]) -> None:
        with self._lock:
            for chunk in self._chunks:
                if chunk["chunk_id"] in scores:
                    chunk["risk_score"] = round(float(scores[chunk["chunk_id"]]), 4)
                    if chunk["trust_level"] == "unknown" and chunk["risk_score"] >= 0.6:
                        chunk["trust_level"] = "suspicious"
            self._save()

    def quarantine_chunks(self, chunk_ids: list[str]) -> list[dict[str, Any]]:
        selected = set(chunk_ids)
        quarantined: list[dict[str, Any]] = []
        with self._lock:
            for chunk in self._chunks:
                if chunk["chunk_id"] in selected:
                    chunk["trust_level"] = "quarantined"
                    chunk["metadata"]["quarantined_at"] = _now()
                    quarantined.append(dict(chunk))
            self._save()
            self._vector_store = None
        return quarantined

    def rebuild_vector_store(self):
        from langchain_community.vectorstores import FAISS

        with self._lock:
            documents = [
                Document(page_content=chunk["content"], metadata=dict(chunk))
                for chunk in self._chunks
                if chunk["trust_level"] in ACTIVE_TRUST_LEVELS
            ]
            self._vector_store = (
                FAISS.from_documents(documents, get_embeddings()) if documents else None
            )
            return self._vector_store

    def retrieve(
        self,
        question: str,
        top_k: int = 5,
        include_quarantined: bool = False,
        trust_levels: set[str] | None = None,
        boost_poison_candidates: bool = False,
    ) -> list[dict[str, Any]]:
        if not question.strip():
            raise ValueError("Question cannot be empty")
        with self._lock:
            if trust_levels is not None:
                documents = [
                    Document(page_content=chunk["content"], metadata=dict(chunk))
                    for chunk in self._chunks
                    if chunk["trust_level"] in trust_levels
                ]
                if not documents:
                    return []
                from langchain_community.vectorstores import FAISS

                store = FAISS.from_documents(documents, get_embeddings())
                available_count = len(documents)
            elif include_quarantined:
                documents = [
                    Document(page_content=chunk["content"], metadata=dict(chunk))
                    for chunk in self._chunks
                ]
                if not documents:
                    return []
                from langchain_community.vectorstores import FAISS

                store = FAISS.from_documents(documents, get_embeddings())
                available_count = len(documents)
            else:
                store = self._vector_store or self.rebuild_vector_store()
                available_count = sum(
                    chunk["trust_level"] in ACTIVE_TRUST_LEVELS for chunk in self._chunks
                )
            if store is None:
                return []
            count = min(
                max(1, top_k * 3 if boost_poison_candidates else top_k),
                available_count,
            )
            pairs = store.similarity_search_with_score(question, k=count)

        results: list[dict[str, Any]] = []
        for document, distance in pairs:
            metadata = document.metadata
            similarity = 1.0 / (1.0 + max(0.0, float(distance)))
            results.append(
                {
                    "chunk_id": metadata["chunk_id"],
                    "content": document.page_content,
                    "source": metadata.get("source", "unknown"),
                    "trust_level": metadata.get("trust_level", "unknown"),
                    "score": round(similarity, 4),
                    "rank": 0,
                    "risk_score": metadata.get("risk_score", 0.0),
                    "is_poison_candidate": metadata.get("is_poison_candidate", False),
                }
            )
        if boost_poison_candidates:
            results.sort(
                key=lambda item: (
                    item["score"] + (0.25 if item["is_poison_candidate"] else 0.0)
                ),
                reverse=True,
            )
        for rank, item in enumerate(results[:top_k], start=1):
            item["rank"] = rank
        return results[:top_k]


interactive_vector_store = InteractiveVectorStore()
