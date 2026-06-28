from __future__ import annotations

from app.services.rag_evaluation.metrics import confusion_metrics


def test_confusion_metrics_and_fpr() -> None:
    rows = [
        {"case_id": "1", "chunk_id": "a", "true_label": True, "predictions": {"dualrisk": True}},
        {"case_id": "1", "chunk_id": "b", "true_label": False, "predictions": {"dualrisk": True}},
        {"case_id": "2", "chunk_id": "c", "true_label": False, "predictions": {"dualrisk": False}},
        {"case_id": "2", "chunk_id": "d", "true_label": True, "predictions": {"dualrisk": False}},
    ]

    metrics = confusion_metrics(rows, "dualrisk")

    assert metrics["TP"] == 1
    assert metrics["FP"] == 1
    assert metrics["TN"] == 1
    assert metrics["FN"] == 1
    assert metrics["False Positive Rate"] == 0.5


def test_clean_rows_are_not_default_poison_predictions() -> None:
    rows = [
        {"case_id": "clean", "chunk_id": "a", "true_label": False, "predictions": {"ras_only": False}},
        {"case_id": "clean", "chunk_id": "b", "true_label": False, "predictions": {"ras_only": False}},
    ]

    metrics = confusion_metrics(rows, "ras_only")

    assert metrics["FP"] == 0
    assert metrics["TN"] == 2


def test_confusion_matrix_exact_values() -> None:
    rows = [
        {"case_id": str(i), "chunk_id": str(i), "true_label": truth, "predictions": {"m": pred}}
        for i, (truth, pred) in enumerate([(True, True), (True, False), (False, True), (False, False), (False, False)])
    ]

    metrics = confusion_metrics(rows, "m")

    assert metrics["TP"] == 1
    assert metrics["FN"] == 1
    assert metrics["FP"] == 1
    assert metrics["TN"] == 2
    assert metrics["Precision"] == 0.5
    assert metrics["Recall"] == 0.5
    assert metrics["F1"] == 0.5
    assert metrics["False Positive Rate"] == 1 / 3


def test_fpr_differs_for_different_predictions() -> None:
    rows = [
        {"case_id": "1", "chunk_id": "a", "true_label": False, "predictions": {"a": True, "b": False}},
        {"case_id": "1", "chunk_id": "b", "true_label": False, "predictions": {"a": False, "b": False}},
    ]

    assert confusion_metrics(rows, "a")["False Positive Rate"] == 0.5
    assert confusion_metrics(rows, "b")["False Positive Rate"] == 0.0
