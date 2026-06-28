"""Report table export and consistency checks."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .metrics import confusion_metrics
from .storage import PROJECT_ROOT


RESULT_ROOT = PROJECT_ROOT / "data" / "results" / "rag_evaluation"
TABLE_ROOT = RESULT_ROOT / "report_tables"


def export_report_tables(result_root: Path = RESULT_ROOT) -> dict[str, str]:
    TABLE_ROOT.mkdir(parents=True, exist_ok=True)
    latest = json.loads((result_root / "latest.json").read_text(encoding="utf-8"))
    details = [json.loads(line) for line in (result_root / "detailed_records.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    paths = {
        "table_detection_methods.csv": _write_detection(latest),
        "table_scenario_results.csv": _write_scenario(latest),
        "table_correction_results.csv": _write_correction(latest),
        "table_ablation_results.csv": _write_detection(latest, "table_ablation_results.csv"),
        "table_cluster_detection.csv": _write_cluster(latest),
        "table_counterfactual_cases.csv": _write_counterfactual(details),
        "table_latency.csv": _write_latency(latest),
    }
    return {name: str(path.relative_to(PROJECT_ROOT)) for name, path in paths.items()}


def verify_report_metrics(result_root: Path = RESULT_ROOT) -> dict[str, Any]:
    latest = json.loads((result_root / "latest.json").read_text(encoding="utf-8"))
    details = [json.loads(line) for line in (result_root / "detailed_records.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [chunk for record in details for chunk in record.get("chunk_scores", [])]
    errors = []
    for method, expected in latest.get("metrics_by_method", {}).items():
        actual = confusion_metrics(rows, method)
        for key in ("TP", "FP", "TN", "FN"):
            if actual[key] != expected[key]:
                errors.append(f"{method} {key} mismatch: {actual[key]} != {expected[key]}")
    for record in details:
        if record.get("correction", {}).get("safe_refusal") and record.get("correction", {}).get("trusted_answer"):
            errors.append(f"safe refusal counted as trusted answer: {record.get('case_id')}")
        if not record.get("generation_mode"):
            errors.append(f"missing generation mode: {record.get('case_id')}")
    return {"ok": not errors, "errors": errors, "detail_count": len(details)}


def _write_detection(latest: dict[str, Any], filename: str = "table_detection_methods.csv") -> Path:
    path = TABLE_ROOT / filename
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["method", "TP", "FP", "TN", "FN", "Precision", "Recall", "F1", "FPR"])
        writer.writeheader()
        for method, row in latest.get("metrics_by_method", {}).items():
            writer.writerow({"method": method, "TP": row["TP"], "FP": row["FP"], "TN": row["TN"], "FN": row["FN"], "Precision": row["Precision"], "Recall": row["Recall"], "F1": row["F1"], "FPR": row["False Positive Rate"]})
    return path


def _write_scenario(latest: dict[str, Any]) -> Path:
    path = TABLE_ROOT / "table_scenario_results.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["scenario", "method", "TP", "FP", "TN", "FN", "Precision", "Recall", "F1", "FPR", "sample_count", "chunk_count"])
        for scenario, data in latest.get("metrics_by_scenario", {}).items():
            for method, row in data.get("chunk_metrics", {}).items():
                writer.writerow([scenario, method, row["TP"], row["FP"], row["TN"], row["FN"], row["Precision"], row["Recall"], row["F1"], row["False Positive Rate"], data.get("sample_count"), data.get("chunk_count")])
    return path


def _write_correction(latest: dict[str, Any]) -> Path:
    path = TABLE_ROOT / "table_correction_results.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["scenario", "ASR_before", "ASR_after", "ASR_reduction", "CorrectRecoveryRate", "SafeRefusalRate", "TRS", "IsolationCoverage", "Latency"])
        for scenario, row in latest.get("correction_metrics", {}).items():
            before = row.get("Attack Success Rate", 0)
            after = row.get("Residual Attack Success Rate", 0)
            writer.writerow([scenario, before, after, before - after, row.get("Correct Recovery Rate"), row.get("Safe Refusal Rate"), row.get("TRS"), row.get("Isolation Coverage"), row.get("Latency")])
    return path


def _write_cluster(latest: dict[str, Any]) -> Path:
    path = TABLE_ROOT / "table_cluster_detection.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["scenario", "Cluster Detection Rate"])
        for scenario, data in latest.get("metrics_by_scenario", {}).items():
            writer.writerow([scenario, data.get("scenario_metrics", {}).get("Cluster Detection Rate")])
    return path


def _write_counterfactual(details: list[dict[str, Any]]) -> Path:
    path = TABLE_ROOT / "table_counterfactual_cases.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["case_id", "causal_score", "replacement_status", "remove_change", "only_reproduce", "replace_recovery"])
        for row in details[:100]:
            cf = row.get("counterfactual", {})
            writer.writerow([row.get("case_id"), cf.get("causal_score"), cf.get("replacement_status"), cf.get("remove_change"), cf.get("only_reproduce"), cf.get("replace_recovery")])
    return path


def _write_latency(latest: dict[str, Any]) -> Path:
    path = TABLE_ROOT / "table_latency.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        for key, value in latest.get("generation_cache", {}).items():
            writer.writerow([key, value])
    return path
