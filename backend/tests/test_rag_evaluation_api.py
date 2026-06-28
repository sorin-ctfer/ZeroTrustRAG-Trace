from __future__ import annotations

from app.routers.rag_evaluation import EvaluationRequest, case_details, prepare, progress, results
from app.services.rag_evaluation.evaluator import rag_evaluation_service


def test_rag_evaluation_api_can_prepare_run_and_read_results(monkeypatch) -> None:
    monkeypatch.setenv("BAILIAN_ENABLED", "false")
    monkeypatch.setenv("OLLAMA_ENABLED", "false")
    payload = EvaluationRequest(
        dataset="poisonedrag",
        mode="sample",
        methods=["ras_only", "gis_only", "dualrisk", "dualrisk_cluster"],
        top_k=[3],
        poison_ratios=[0.01],
        retrieval_mode="tfidf",
    )

    prepared = prepare(payload)
    assert prepared["success"] is True
    assert prepared["data"]["case_count"] > 0

    result = rag_evaluation_service.run_sync(rag_evaluation_service._prepared_config)
    assert result["status"] == "completed"

    progress_response = progress()
    results_response = results()
    sample_id = results_response["data"]["run_id"] and "poisonedrag-poisonedrag-sample-002"
    details = case_details(sample_id)

    assert progress_response["success"] is True
    assert progress_response["data"]["status"] == "completed"
    assert results_response["success"] is True
    assert "metrics_by_method" in results_response["data"]
    assert details["success"] is True
    assert details["data"]["records"]
