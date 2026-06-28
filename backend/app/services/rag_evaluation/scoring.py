"""RAS, GIS and DualRisk scoring utilities."""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def minmax(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    low = min(values.values())
    high = max(values.values())
    if high <= low:
        return {key: 1.0 if value > 0 else 0.0 for key, value in values.items()}
    return {key: (value - low) / (high - low) for key, value in values.items()}


def normalize_bool_label(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "poison", "poisoned"}
    return False


def compute_ras(retrieval_logs: list[dict[str, Any]], ras_scope: str = "group_ras") -> dict[str, dict[str, float]]:
    freq: Counter[str] = Counter()
    chunk_totals: dict[str, int] = {}
    for log in retrieval_logs:
        total_chunks = max(1, int(log.get("chunk_count", 0)))
        for result in log.get("topk", []):
            chunk_id = result["chunk_id"]
            freq[chunk_id] += 1
            chunk_totals[chunk_id] = total_chunks
        for chunk_id in log.get("all_chunk_ids", []):
            chunk_totals.setdefault(chunk_id, total_chunks)
    total_retrievals = sum(freq.values())
    raw: dict[str, float] = {}
    for chunk_id, total_chunks in chunk_totals.items():
        if total_retrievals <= 0:
            raw[chunk_id] = 0.0
        else:
            raw[chunk_id] = (freq[chunk_id] / total_retrievals) / (1.0 / max(1, total_chunks))
    normalized = minmax(raw)
    return {
        chunk_id: {
            "raw_frequency": float(freq[chunk_id]),
            "freq": float(freq[chunk_id]),
            "total_retrievals": float(total_retrievals),
            "chunk_count": float(chunk_totals[chunk_id]),
            "raw_ras": raw[chunk_id],
            "ras": raw[chunk_id],
            "normalized_ras": normalized.get(chunk_id, 0.0),
            "ras_scope": ras_scope,
        }
        for chunk_id in chunk_totals
    }


def compute_gis(answer: str, chunks: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    if not chunks:
        return {}
    texts = [answer or ""] + [str(chunk.get("content", "")) for chunk in chunks]
    try:
        matrix = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4)).fit_transform(texts)
        similarities = cosine_similarity(matrix[0], matrix[1:]).ravel()
    except ValueError:
        similarities = np.zeros(len(chunks), dtype=float)
    max_sim = max(float(sim) for sim in similarities) if len(similarities) else 0.0
    rows: dict[str, dict[str, float]] = {}
    for chunk, sim in zip(chunks, similarities):
        raw = max(0.0, float(sim))
        gis = 0.0 if max_sim <= 0 else max(0.0, min(1.0, raw / max_sim))
        rows[chunk["chunk_id"]] = {"answer_similarity": raw, "gis": gis}
    return rows


def compute_dualrisk(normalized_ras: float, gis: float) -> float:
    return max(0.0, min(1.0, float(normalized_ras) * float(gis)))


def deterministic_answer(query: str, topk: list[dict[str, Any]], target_wrong_answer: str | None = None) -> dict[str, str]:
    if not topk:
        return {"answer": "证据不足，无法基于本地知识库回答。", "generation_mode": "deterministic_fallback"}
    poison_hits = [item for item in topk if item.get("poison_label")]
    chosen = poison_hits[0] if poison_hits else topk[0]
    answer = chosen.get("content", "")
    if target_wrong_answer and poison_hits and target_wrong_answer not in answer:
        answer = f"{answer} {target_wrong_answer}"
    return {
        "answer": f"针对问题“{query}”，检索证据显示：{answer}",
        "generation_mode": "deterministic_fallback",
    }
