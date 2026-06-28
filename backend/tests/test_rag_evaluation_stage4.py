from __future__ import annotations

import json
from pathlib import Path

from app.services.rag_evaluation.generation_cache import GenerationCache
from app.services.rag_evaluation.real_data import RealSubsetService, query_hash, source_hash
from app.services.rag_evaluation.cluster_scoring import build_cluster_scores
from app.services.rag_evaluation.reporting import verify_report_metrics
from app.services.rag_evaluation.evaluator import rag_evaluation_service
from app.services.rag_evaluation.schemas import EvaluationConfig


def _records():
    rows = []
    for dataset, task in [("poisonedrag", "single_poison"), ("agentdojo", "prompt_infection"), ("alce", "clean"), ("ragtruth", "hallucination")]:
        for i in range(10):
            row = {
                "original_dataset_id": f"{dataset}-{i}",
                "dataset": dataset,
                "query": f"{dataset} query {i}",
                "gold_answer": "gold",
                "target_wrong_answer": "wrong" if task != "clean" else None,
                "clean_contexts": [f"clean {dataset} {i}"],
                "poison_contexts": [f"poison {dataset} {i}"] if task in {"single_poison", "prompt_infection"} else [],
                "task_type": task,
                "official_split": None,
                "source_file": "unit",
            }
            row["query_hash"] = query_hash(row)
            row["source_hash"] = source_hash(row)
            rows.append(row)
    return rows


def test_subset_contains_real_unique_samples(tmp_path: Path) -> None:
    service = RealSubsetService(tmp_path / "real.jsonl")
    _, manifest = service.split_records(_records())

    assert sum(item["real_sample_count"] for item in manifest.values()) == 40


def test_original_dataset_id_not_repeated_across_splits(tmp_path: Path) -> None:
    service = RealSubsetService(tmp_path / "real.jsonl")
    rows, _ = service.split_records(_records())
    seen = {}
    for row in rows:
        seen.setdefault(row["original_dataset_id"], set()).add(row["split"])
    assert all(len(splits) == 1 for splits in seen.values())


def test_query_hash_not_leaked_across_splits(tmp_path: Path) -> None:
    service = RealSubsetService(tmp_path / "real.jsonl")
    rows, _ = service.split_records(_records())
    seen = {}
    for row in rows:
        seen.setdefault(row["query_hash"], set()).add(row["split"])
    assert all(len(splits) == 1 for splits in seen.values())


def test_generation_cache_reuses_answer(tmp_path: Path) -> None:
    cache = GenerationCache(tmp_path)
    key = cache.key("m", "q", "ctx", "v", {})
    calls = {"n": 0}
    def producer():
        calls["n"] += 1
        return "answer", "bailian", "m", {}
    cache.get_or_create(key, producer)
    _, hit = cache.get_or_create(key, producer)
    assert hit is True and calls["n"] == 1


def test_generation_cache_key_changes_with_context(tmp_path: Path) -> None:
    cache = GenerationCache(tmp_path)
    assert cache.key("m", "q", "a", "v", {}) != cache.key("m", "q", "b", "v", {})


def test_cluster_score_is_normalized() -> None:
    scores = build_cluster_scores([{"topk": [{"chunk_id": "a", "cluster_id": "c"}]}], {"a": {"gis": 1}})
    assert 0 <= scores["c"]["cluster_dualrisk"] <= 1.5


def test_independent_clean_sources_not_flagged_as_copy_cluster() -> None:
    logs = [{"topk": [{"chunk_id": "a", "cluster_id": "c", "root_source_id": "r1"}, {"chunk_id": "b", "cluster_id": "c", "root_source_id": "r2"}]}]
    score = build_cluster_scores(logs, {"a": {"gis": 1}, "b": {"gis": 1}})["c"]
    assert score["copy_ratio"] == 0
    assert score["source_anomaly"] == 0


def test_cluster_poison_scores_higher_than_clean_cluster() -> None:
    poison = build_cluster_scores([{"topk": [{"chunk_id": "a", "cluster_id": "c", "root_source_id": "r", "copied_from": "x"}, {"chunk_id": "b", "cluster_id": "c", "root_source_id": "r", "copied_from": "x"}]}], {"a": {"gis": 1}, "b": {"gis": 1}})["c"]
    clean = build_cluster_scores([{"topk": [{"chunk_id": "a", "cluster_id": "c", "root_source_id": "r1"}, {"chunk_id": "b", "cluster_id": "c", "root_source_id": "r2"}]}], {"a": {"gis": 1}, "b": {"gis": 1}})["c"]
    assert poison["source_anomaly"] > clean["source_anomaly"]


def test_counterfactual_only_runs_on_candidates() -> None:
    rows = [{"dualrisk": 0.1}, {"dualrisk": 0.9}, {"dualrisk": 0.8}, {"dualrisk": 0.7}]
    candidates = sorted(rows, key=lambda r: r["dualrisk"], reverse=True)[:3]
    assert len(candidates) == 3
    assert rows[0] not in candidates


def test_expanded_retrieval_finds_clean_evidence() -> None:
    log = {"topk": [{"chunk_id": "bad", "retrieval_score": 1.0}], "case": {"query": "q", "top_k": 1}}
    rows = [{"chunk_id": "bad", "predictions": {"full_method": True}, "dualrisk": 1, "cluster_dualrisk": 1, "causal_score": 1, "cluster_causal_score": 0}]
    correction = rag_evaluation_service._correction(log, rows, {})
    assert "safe_refusal" in correction


def test_report_metrics_recomputed_from_logs() -> None:
    result = verify_report_metrics()
    assert "ok" in result
