from __future__ import annotations

from app.services.rag_evaluation.cluster_scoring import build_cluster_scores
from app.services.rag_evaluation.evaluator import rag_evaluation_service
from app.services.rag_evaluation.retrieval_adapter import RetrievalAdapter
from app.services.rag_evaluation.schemas import EvaluationConfig
from app.services.rag_evaluation.scoring import compute_dualrisk, compute_gis, compute_ras, normalize_bool_label


def test_ras_calculation_uses_group_retrieval_frequency() -> None:
    logs = [
        {"chunk_count": 4, "all_chunk_ids": ["a", "b", "c", "d"], "topk": [{"chunk_id": "a"}, {"chunk_id": "b"}]},
        {"chunk_count": 4, "all_chunk_ids": ["a", "b", "c", "d"], "topk": [{"chunk_id": "a"}, {"chunk_id": "c"}]},
    ]

    scores = compute_ras(logs)

    assert scores["a"]["freq"] == 2
    assert scores["a"]["ras"] == 2.0
    assert scores["d"]["ras"] == 0.0
    assert scores["a"]["normalized_ras"] == 1.0


def test_gis_is_bounded_and_dualrisk_is_product() -> None:
    chunks = [
        {"chunk_id": "a", "content": "权限变更必须审批"},
        {"chunk_id": "b", "content": "完全无关内容"},
    ]
    gis = compute_gis("权限变更必须审批", chunks)

    assert all(0.0 <= item["gis"] <= 1.0 for item in gis.values())
    assert gis["a"]["gis"] == 1.0
    assert compute_dualrisk(0.5, gis["a"]["gis"]) == 0.5


def test_cluster_aggregation_and_source_anomaly() -> None:
    logs = [{
        "topk": [
            {"chunk_id": "c1", "cluster_id": "cl-1", "root_source_id": "root", "source_id": "s1", "copied_from": "r"},
            {"chunk_id": "c2", "cluster_id": "cl-1", "root_source_id": "root", "source_id": "s2", "copied_from": "r"},
        ]
    }]
    scores = build_cluster_scores(logs, {"c1": {"gis": 0.4}, "c2": {"gis": 0.5}}, cluster_lambda=0.5)

    cluster = scores["cl-1"]
    assert cluster["member_chunk_ids"] == ["c1", "c2"]
    assert cluster["source_independence"] == 0.5
    assert cluster["copy_ratio"] == 1.0
    assert cluster["source_anomaly"] > 0.5


def test_cluster_dualrisk_detects_low_individual_members() -> None:
    logs = [{
        "topk": [
            {"chunk_id": "c1", "cluster_id": "cl-1", "root_source_id": "root", "source_id": "s1", "copied_from": "r"},
            {"chunk_id": "c2", "cluster_id": "cl-1", "root_source_id": "root", "source_id": "s2", "copied_from": "r"},
        ]
    }]
    scores = build_cluster_scores(logs, {"c1": {"gis": 0.3}, "c2": {"gis": 0.3}}, cluster_lambda=0.5)

    assert compute_dualrisk(0.2, 0.3) < 0.35
    assert scores["cl-1"]["cluster_dualrisk"] >= 0.35


def test_retrieval_adapter_falls_back_to_tfidf_when_faiss_disabled() -> None:
    docs = [{"document_id": "d1", "source_id": "s1", "content": "权限变更必须审批", "trust_label": "trusted"}]
    adapter = RetrievalAdapter(preferred_mode="tfidf").build_index(docs)
    rows = adapter.retrieve("权限变更", 1)

    assert rows[0]["document_id"] == "d1"
    assert rows[0]["retrieval_mode"] == "tfidf_fallback"


def test_string_false_is_not_truthy_label() -> None:
    assert normalize_bool_label("false") is False
    assert normalize_bool_label("") is False
    assert normalize_bool_label("true") is True


def test_clean_chunks_remain_negative() -> None:
    docs = [{"document_id": "d1", "source_id": "s1", "content": "正常业务内容", "trust_label": "trusted", "metadata": {"poison_label": "false"}}]
    row = RetrievalAdapter(preferred_mode="tfidf").build_index(docs).retrieve("正常", 1)[0]

    assert row["poison_label"] is False


def test_cluster_prediction_does_not_label_all_chunks() -> None:
    thresholds = {"ras_threshold": 0.1, "gis_threshold": 0.1, "dualrisk_threshold": 0.9, "cluster_threshold": 0.2, "source_anomaly_lambda": 1.0}
    normal = {"normalized_ras": 0.0, "gis": 0.0, "dualrisk": 0.0, "cluster_base_score": 1.0, "source_anomaly": 1.0, "cluster_id": None}
    poison = {**normal, "cluster_id": "c1"}

    assert rag_evaluation_service._predict_methods(normal, thresholds)["dualrisk_cluster"] is False
    assert rag_evaluation_service._predict_methods(poison, thresholds)["dualrisk_cluster"] is True


def test_global_ras_uses_multiple_queries() -> None:
    logs = [
        {"chunk_count": 3, "all_chunk_ids": ["a", "b", "c"], "topk": [{"chunk_id": "a"}]},
        {"chunk_count": 3, "all_chunk_ids": ["a", "b", "c"], "topk": [{"chunk_id": "b"}]},
        {"chunk_count": 3, "all_chunk_ids": ["a", "b", "c"], "topk": [{"chunk_id": "a"}]},
    ]

    scores = compute_ras(logs, "global_ras")

    assert scores["a"]["raw_frequency"] == 2
    assert scores["a"]["total_retrievals"] == 3
    assert scores["a"]["ras_scope"] == "global_ras"


def test_threshold_search_uses_validation_only() -> None:
    rows = [
        {"split": "validation", "case_id": "v", "chunk_id": "v", "true_label": False, "normalized_ras": 0.8, "gis": 0.1, "dualrisk": 0.08, "cluster_base_score": 0, "source_anomaly": 0, "cluster_id": None},
        {"split": "test", "case_id": "t", "chunk_id": "t", "true_label": True, "normalized_ras": 0.8, "gis": 1, "dualrisk": 0.8, "cluster_base_score": 0, "source_anomaly": 0, "cluster_id": None},
    ]

    selected = rag_evaluation_service._select_thresholds(rows, EvaluationConfig())

    assert selected["split_used"] == "validation"
    assert selected["validation_note"]


def test_test_split_does_not_tune_thresholds() -> None:
    rows = [
        {"split": "validation", "case_id": "v", "chunk_id": "v", "true_label": False, "normalized_ras": 0.8, "gis": 0.1, "dualrisk": 0.08, "cluster_base_score": 0, "source_anomaly": 0, "cluster_id": None},
        {"split": "test", "case_id": "t", "chunk_id": "t", "true_label": True, "normalized_ras": 0.2, "gis": 1, "dualrisk": 0.2, "cluster_base_score": 0, "source_anomaly": 0, "cluster_id": None},
    ]

    selected = rag_evaluation_service._select_thresholds(rows, EvaluationConfig())

    assert selected["ras_threshold"] > 0.2


def test_cluster_ids_are_isolated_by_scenario() -> None:
    logs = [{
        "topk": [
            {"chunk_id": "a", "dataset": "d", "sample_id": "s", "case_id": "case1", "cluster_id": "same", "root_source_id": "r1"},
            {"chunk_id": "b", "dataset": "d", "sample_id": "s", "case_id": "case2", "cluster_id": "same", "root_source_id": "r2"},
        ]
    }]

    scores = build_cluster_scores(logs, {"a": {"gis": 1}, "b": {"gis": 1}})

    assert len(scores) == 2
