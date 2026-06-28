from __future__ import annotations

import json
from pathlib import Path

from app.services.rag_evaluation_datasets import DATASETS, RagEvaluationDatasetService


def test_sample_download_and_prepare_unified_schema(tmp_path: Path) -> None:
    service = RagEvaluationDatasetService(tmp_path / "data")

    downloaded = service.download_sample(force=True)
    manifest = service.prepare(seed=42)

    assert {item["dataset"] for item in downloaded} == set(DATASETS)
    assert manifest["seed"] == 42
    assert set(manifest["datasets"]) == set(DATASETS)
    assert all(count > 0 for count in manifest["datasets"].values())

    rows = []
    for split in ("train", "validation", "test"):
        path = tmp_path / "data" / "processed" / f"{split}.jsonl"
        assert path.exists()
        rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())

    assert {row["dataset"] for row in rows} == set(DATASETS)
    assert {row["task_type"] for row in rows}.issuperset({"single_poison", "hallucination", "clean", "prompt_infection"})
    expected_fields = {
        "sample_id",
        "dataset",
        "split",
        "task_type",
        "query",
        "gold_answer",
        "target_wrong_answer",
        "clean_contexts",
        "poison_contexts",
        "source_ids",
        "labels",
        "metadata",
    }
    assert all(set(row) == expected_fields for row in rows)


def test_build_cases_records_cluster_rewrite_metadata(tmp_path: Path) -> None:
    service = RagEvaluationDatasetService(tmp_path / "data")
    service.download_sample(force=True)
    service.prepare(seed=42)

    manifest = service.build_test_cases(poison_ratios=(0.01,), top_ks=(3,))
    case_file = tmp_path / "data" / "cache" / "rag_evaluation_cases" / "cases_ratio_1_top_3.jsonl"
    cases = [json.loads(line) for line in case_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    cluster_case = next(case for case in cases if case["scenario"] == "cluster_poison" and case["dataset"] == "poisonedrag")
    poison_docs = [doc for doc in cluster_case["documents"] if doc["trust_label"] == "poison"]
    rewrite_types = {doc["metadata"].get("rewrite_type") for doc in poison_docs}
    contents = {doc["content"] for doc in poison_docs}

    assert manifest["case_count"] == len(cases)
    assert len(poison_docs) == 5
    assert len(contents) == 5
    assert rewrite_types == {"hedged", "attributed", "summary", "timeline", "faq"}
    assert all(doc["metadata"].get("cluster_id") for doc in poison_docs)
    assert all(doc["metadata"].get("copied_from") for doc in poison_docs)
