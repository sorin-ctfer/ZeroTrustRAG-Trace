"""Persistent generation cache for RAG evaluation prompts."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .storage import PROJECT_ROOT


CACHE_ROOT = PROJECT_ROOT / "data" / "cache" / "rag_generation"


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class GenerationCache:
    def __init__(self, cache_root: Path = CACHE_ROOT) -> None:
        self.cache_root = cache_root

    def key(self, model_name: str, query: str, context_hash: str, prompt_template_version: str, generation_parameters: dict[str, Any]) -> str:
        return stable_hash({
            "model_name": model_name,
            "query": query,
            "context_hash": context_hash,
            "prompt_template_version": prompt_template_version,
            "generation_parameters": generation_parameters,
        })

    def get(self, cache_key: str) -> dict[str, Any] | None:
        path = self.cache_root / f"{cache_key}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def set(self, cache_key: str, answer: str, generation_mode: str, model_name: str, latency: float, token_usage: dict[str, Any] | None = None) -> dict[str, Any]:
        self.cache_root.mkdir(parents=True, exist_ok=True)
        record = {
            "cache_key": cache_key,
            "answer": answer,
            "generation_mode": generation_mode,
            "model_name": model_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "latency": latency,
            "token_usage": token_usage or {},
        }
        (self.cache_root / f"{cache_key}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return record

    def get_or_create(self, cache_key: str, producer: Callable[[], tuple[str, str, str, dict[str, Any] | None]]) -> tuple[dict[str, Any], bool]:
        cached = self.get(cache_key)
        if cached:
            return cached, True
        start = time.perf_counter()
        answer, generation_mode, model_name, token_usage = producer()
        return self.set(cache_key, answer, generation_mode, model_name, time.perf_counter() - start, token_usage), False


generation_cache = GenerationCache()
