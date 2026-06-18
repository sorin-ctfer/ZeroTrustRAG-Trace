"""Download and normalize public RAG security datasets.

The normalized format matches ``RagDetectorTrainingService.import_jsonl``:
one JSON object per line with ``query``, ``clean_chunks``, ``poison_chunks``
and optional ``benign_error_chunks``.
"""

from __future__ import annotations

import json
import shutil
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .external_knowledge import external_knowledge_service
from .rag_detector_training import rag_detector_training_service

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PUBLIC_DATA_ROOT = PROJECT_ROOT / "data" / "public_datasets"
RAW_DIR = PUBLIC_DATA_ROOT / "raw"
CONVERTED_DIR = PUBLIC_DATA_ROOT / "converted"


@dataclass(frozen=True)
class PublicDatasetSource:
    key: str
    name: str
    url: str
    raw_path: Path
    converted_path: Path
    default_limit: int
    description: str


SOURCES: dict[str, PublicDatasetSource] = {
    "safe_rag_nctd": PublicDatasetSource(
        key="safe_rag_nctd",
        name="SafeRAG NCTD",
        url="https://raw.githubusercontent.com/IAAR-Shanghai/SafeRAG/main/nctd_datasets/nctd.json",
        raw_path=RAW_DIR / "safe_rag" / "nctd.json",
        converted_path=CONVERTED_DIR / "safe_rag_nctd.jsonl",
        default_limit=120,
        description="SafeRAG security benchmark with silver noise, conflict and DoS-style contexts.",
    ),
    "rgb_zh_fact": PublicDatasetSource(
        key="rgb_zh_fact",
        name="RGB zh_fact",
        url="https://raw.githubusercontent.com/chen700564/RGB/master/data/zh_fact.json",
        raw_path=RAW_DIR / "rgb" / "zh_fact.json",
        converted_path=CONVERTED_DIR / "rgb_zh_fact.jsonl",
        default_limit=120,
        description="Chinese factual-conflict subset from RGB RAG robustness benchmark.",
    ),
}


def _read_json_or_jsonl(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines() if line.strip()]


def _compact_text(value: Any, max_len: int = 1200) -> str:
    text = str(value or "").replace("\u00a0", " ")
    text = " ".join(text.split())
    return text[:max_len].strip()


def _list_texts(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _compact_text(item))]


class PublicDatasetIngestionService:
    def sources(self) -> list[dict[str, Any]]:
        return [
            {
                "key": item.key,
                "name": item.name,
                "url": item.url,
                "raw_path": str(item.raw_path.relative_to(PROJECT_ROOT)),
                "converted_path": str(item.converted_path.relative_to(PROJECT_ROOT)),
                "downloaded": item.raw_path.exists(),
                "converted": item.converted_path.exists(),
                "default_limit": item.default_limit,
                "description": item.description,
            }
            for item in SOURCES.values()
        ]

    def clear(self) -> None:
        if PUBLIC_DATA_ROOT.exists():
            shutil.rmtree(PUBLIC_DATA_ROOT)

    def download(self, source_keys: list[str] | None = None, force: bool = False) -> list[dict[str, Any]]:
        selected = self._select_sources(source_keys)
        results = []
        for source in selected:
            source.raw_path.parent.mkdir(parents=True, exist_ok=True)
            if force or not source.raw_path.exists():
                urllib.request.urlretrieve(source.url, source.raw_path)
            results.append({
                "key": source.key,
                "raw_path": str(source.raw_path.relative_to(PROJECT_ROOT)),
                "bytes": source.raw_path.stat().st_size,
            })
        return results

    def convert(self, source_key: str, limit: int | None = None) -> dict[str, Any]:
        source = SOURCES[source_key]
        if not source.raw_path.exists():
            self.download([source_key])
        limit = limit or source.default_limit
        rows = (
            self._convert_safe_rag(source.raw_path, limit)
            if source_key == "safe_rag_nctd"
            else self._convert_rgb_fact(source.raw_path, limit)
        )
        if not rows:
            raise ValueError(f"No rows converted from {source_key}")
        source.converted_path.parent.mkdir(parents=True, exist_ok=True)
        source.converted_path.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
            encoding="utf-8",
        )
        return {
            "key": source.key,
            "converted_path": str(source.converted_path.relative_to(PROJECT_ROOT)),
            "row_count": len(rows),
            "sample": rows[0],
        }

    def convert_all(self, limit_per_source: int | None = None) -> list[dict[str, Any]]:
        return [self.convert(key, limit_per_source) for key in SOURCES]

    def import_training(self, source_key: str, limit: int | None = None) -> dict[str, Any]:
        converted = self.convert(source_key, limit)
        source = SOURCES[source_key]
        raw_jsonl = source.converted_path.read_text(encoding="utf-8")
        dataset = rag_detector_training_service.import_jsonl(raw_jsonl, source.name)
        return {"converted": converted, "dataset": dataset}

    def import_all_training(self, limit_per_source: int | None = None) -> list[dict[str, Any]]:
        return [self.import_training(key, limit_per_source) for key in SOURCES]

    def import_clean_knowledge(self, source_key: str, limit: int | None = None) -> dict[str, Any]:
        converted = self.convert(source_key, limit)
        source = SOURCES[source_key]
        chunks = external_knowledge_service.import_dataset_clean(
            source.converted_path.read_text(encoding="utf-8"),
            source.name,
        )
        return {"converted": converted, "created_chunks": len(chunks)}

    def _select_sources(self, source_keys: list[str] | None) -> list[PublicDatasetSource]:
        if not source_keys:
            return list(SOURCES.values())
        unknown = [key for key in source_keys if key not in SOURCES]
        if unknown:
            raise ValueError(f"Unknown public dataset source: {', '.join(unknown)}")
        return [SOURCES[key] for key in source_keys]

    def _convert_safe_rag(self, path: Path, limit: int) -> list[dict[str, Any]]:
        data = _read_json_or_jsonl(path)
        rows: list[dict[str, Any]] = []
        if not isinstance(data, dict):
            return rows
        for category, items in data.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if len(rows) >= limit:
                    return rows
                if not isinstance(item, dict):
                    continue
                query = _compact_text(item.get("questions") or item.get("query"))
                clean_chunks = _list_texts(item.get("enhanced_contexts"))
                poison_chunks = []
                for key, value in item.items():
                    if not (key.startswith("enhanced_") and key.endswith("_contexts")):
                        continue
                    if key == "enhanced_contexts":
                        continue
                    attack_type = key.removeprefix("enhanced_").removesuffix("_contexts").lower()
                    for text in _list_texts(value):
                        poison_chunks.append({
                            "content": text,
                            "attack_type": f"safe_rag_{attack_type}",
                            "target_wrong_answer": "、".join(_list_texts(item.get("attack_kws")))[:300],
                            "correct_answer": "",
                            "source_dataset": "SafeRAG",
                            "source_category": category,
                        })
                if query and clean_chunks and poison_chunks:
                    rows.append({
                        "query": query,
                        "clean_chunks": clean_chunks,
                        "poison_chunks": poison_chunks,
                        "correct_answer": "",
                        "target_wrong_answer": "、".join(_list_texts(item.get("attack_kws")))[:300],
                        "source_dataset": "SafeRAG",
                        "source_category": category,
                    })
        return rows

    def _convert_rgb_fact(self, path: Path, limit: int) -> list[dict[str, Any]]:
        data = _read_json_or_jsonl(path)
        rows: list[dict[str, Any]] = []
        if not isinstance(data, list):
            return rows
        for item in data:
            if len(rows) >= limit:
                break
            if not isinstance(item, dict):
                continue
            query = _compact_text(item.get("query"))
            clean_chunks = _list_texts(item.get("positive"))
            poison_chunks = [
                {
                    "content": text,
                    "attack_type": "rgb_factual_conflict",
                    "target_wrong_answer": _compact_text(item.get("fakeanswer"), 300),
                    "correct_answer": _compact_text(item.get("answer"), 300),
                    "source_dataset": "RGB",
                }
                for text in _list_texts(item.get("positive_wrong"))
            ]
            benign_error_chunks = _list_texts(item.get("negative"))[:3]
            if query and clean_chunks and poison_chunks:
                rows.append({
                    "query": query,
                    "clean_chunks": clean_chunks,
                    "poison_chunks": poison_chunks,
                    "benign_error_chunks": benign_error_chunks,
                    "correct_answer": _compact_text(item.get("answer"), 300),
                    "target_wrong_answer": _compact_text(item.get("fakeanswer"), 300),
                    "source_dataset": "RGB",
                })
        return rows


public_dataset_ingestion_service = PublicDatasetIngestionService()
