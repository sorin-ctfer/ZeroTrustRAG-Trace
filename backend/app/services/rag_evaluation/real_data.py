"""Real-subset dataset preparation helpers for RAG evaluation.

The downloader intentionally fails when public upstream files are unavailable;
it does not inflate a tiny sample by changing ids. Tests exercise the splitter
with temporary unique records so the no-leak guarantees stay deterministic.
"""

from __future__ import annotations

import hashlib
import json
import random
import urllib.request
from pathlib import Path
from typing import Any

from ..rag_evaluation_datasets import DATASETS, PROJECT_ROOT, RagEvaluationDatasetService


REAL_RAW_ROOT = PROJECT_ROOT / "data" / "raw"
REAL_PROCESSED = PROJECT_ROOT / "data" / "processed" / "real_subset.jsonl"
SPLIT_MANIFEST = PROJECT_ROOT / "data" / "processed" / "split_manifest.json"


PUBLIC_SOURCES: dict[str, list[str]] = {
    "ragtruth": [
        "https://huggingface.co/datasets/ParticleMedia/RAGTruth/resolve/main/dataset.jsonl",
        "https://raw.githubusercontent.com/ParticleMedia/RAGTruth/main/dataset.jsonl",
    ],
    "agentdojo": [
        "https://raw.githubusercontent.com/ethz-spylab/agentdojo/main/data/suites/v1/suite.json",
    ],
    "alce": [
        "https://raw.githubusercontent.com/princeton-nlp/ALCE/main/data/asqa_eval_gtr_top100.json",
        "https://raw.githubusercontent.com/princeton-nlp/ALCE/main/data/qampari_eval_gtr_top100.json",
        "https://raw.githubusercontent.com/princeton-nlp/ALCE/main/data/eli5_eval_gtr_top100.json",
    ],
    "poisonedrag": [
        "https://raw.githubusercontent.com/sleeepeer/PoisonedRAG/main/data/hotpotqa_poisoned.jsonl",
        "https://raw.githubusercontent.com/sleeepeer/PoisonedRAG/main/data/nq_poisoned.jsonl",
    ],
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def query_hash(record: dict[str, Any]) -> str:
    return sha256_text(str(record.get("query", "")).strip().lower())


def source_hash(record: dict[str, Any]) -> str:
    payload = "\n".join(record.get("clean_contexts", []) + record.get("poison_contexts", []))
    return sha256_text(payload)


class RealSubsetService:
    def __init__(self, processed_path: Path = REAL_PROCESSED) -> None:
        self.processed_path = processed_path
        self.adapter = RagEvaluationDatasetService(PROJECT_ROOT / "data")

    def download_subset(self, per_dataset: int = 100) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        summary: dict[str, Any] = {}
        for dataset in DATASETS:
            records = self._download_dataset(dataset, per_dataset)
            if len(records) < per_dataset:
                raise RuntimeError(f"{dataset} only yielded {len(records)} real records; required {per_dataset}")
            summary[dataset] = len(records)
            rows.extend(records[:per_dataset])
        self.processed_path.parent.mkdir(parents=True, exist_ok=True)
        self.processed_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        return {"path": str(self.processed_path.relative_to(PROJECT_ROOT)), "datasets": summary}

    def split_records(self, records: list[dict[str, Any]], seed: int = 42) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        by_dataset: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            by_dataset.setdefault(record["dataset"], []).append(record)
        rng = random.Random(seed)
        output: list[dict[str, Any]] = []
        for dataset, dataset_rows in by_dataset.items():
            unique = {row["original_dataset_id"]: row for row in dataset_rows}
            ids = sorted(unique)
            rng.shuffle(ids)
            n = len(ids)
            train_end = int(n * 0.6)
            validation_end = train_end + int(n * 0.2)
            split_for = {}
            for index, original_id in enumerate(ids):
                split_for[original_id] = "train" if index < train_end else "validation" if index < validation_end else "test"
            for row in dataset_rows:
                copied = dict(row)
                copied["split"] = split_for[row["original_dataset_id"]]
                output.append(copied)
        manifest = self.manifest(output)
        self._assert_no_leakage(output)
        SPLIT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        SPLIT_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return output, manifest

    def manifest(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        rows: dict[str, dict[str, Any]] = {}
        for row in records:
            split = row.get("split", "unknown")
            bucket = rows.setdefault(split, {
                "real_sample_count": set(),
                "derived_scenario_count": 0,
                "unique_query_count": set(),
                "unique_source_count": set(),
                "single_poison": 0,
                "cluster_poison": 0,
                "clean": 0,
                "hallucination": 0,
                "prompt_infection": 0,
            })
            bucket["real_sample_count"].add(row["original_dataset_id"])
            bucket["unique_query_count"].add(row["query_hash"])
            bucket["unique_source_count"].add(row["source_hash"])
            task = row.get("task_type", "clean")
            if task in bucket:
                bucket[task] += 1
            bucket["derived_scenario_count"] += 3
        return {
            split: {
                **data,
                "real_sample_count": len(data["real_sample_count"]),
                "unique_query_count": len(data["unique_query_count"]),
                "unique_source_count": len(data["unique_source_count"]),
            }
            for split, data in rows.items()
        }

    def _assert_no_leakage(self, records: list[dict[str, Any]]) -> None:
        for field in ("original_dataset_id", "query_hash", "source_hash"):
            seen: dict[str, str] = {}
            for row in records:
                value = row[field]
                split = row["split"]
                if value in seen and seen[value] != split:
                    raise ValueError(f"{field} leaked across splits: {value}")
                seen[value] = split

    def _download_dataset(self, dataset: str, per_dataset: int) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        last_error = ""
        for url in PUBLIC_SOURCES.get(dataset, []):
            try:
                raw = urllib.request.urlopen(url, timeout=30).read().decode("utf-8")
                path = REAL_RAW_ROOT / dataset / Path(url).name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(raw, encoding="utf-8")
                records = self.adapter.convert_dataset(dataset, self._read_raw(raw))
                converted.extend(self._realize(dataset, records, str(path.relative_to(PROJECT_ROOT)), raw))
                if len({row["original_dataset_id"] for row in converted}) >= per_dataset:
                    break
            except Exception as exc:  # pragma: no cover - depends on network/upstream
                last_error = str(exc)
        unique = {row["original_dataset_id"]: row for row in converted}
        if not unique and last_error:
            raise RuntimeError(f"failed to download {dataset}: {last_error}")
        return list(unique.values())[:per_dataset]

    def _read_raw(self, raw: str) -> list[dict[str, Any]]:
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
            if isinstance(data, dict):
                for key in ("data", "examples", "samples", "records", "tasks", "injections"):
                    if isinstance(data.get(key), list):
                        return [item for item in data[key] if isinstance(item, dict)]
                return [data]
        except json.JSONDecodeError:
            return [json.loads(line) for line in raw.splitlines() if line.strip()]
        return []

    def _realize(self, dataset: str, records: list[dict[str, Any]], source_file: str, raw: str) -> list[dict[str, Any]]:
        rows = []
        for index, record in enumerate(records):
            original_id = f"{dataset}:{record.get('sample_id') or index}"
            row = {
                **record,
                "original_dataset_id": original_id,
                "official_split": record.get("split"),
                "source_file": source_file,
                "source_hash": source_hash(record),
                "query_hash": query_hash(record),
                "source_file_hash": sha256_text(raw),
            }
            rows.append(row)
        return rows


real_subset_service = RealSubsetService()
