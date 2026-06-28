"""Metrics for chunk-level and scenario-level RAG evaluation."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def confusion_metrics(rows: list[dict[str, Any]], method: str) -> dict[str, Any]:
    tp = fp = tn = fn = 0
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (row.get("case_id", ""), row.get("chunk_id", ""))
        if key in seen:
            continue
        seen.add(key)
        truth = bool(row.get("true_label"))
        pred = bool(row.get("predictions", {}).get(method))
        if truth and pred:
            tp += 1
        elif not truth and pred:
            fp += 1
        elif not truth and not pred:
            tn += 1
        else:
            fn += 1
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
    fpr = fp / (fp + tn) if fp + tn else None
    return {
        "TP": tp,
        "FP": fp,
        "TN": tn,
        "FN": fn,
        "Precision": precision,
        "Recall": recall,
        "F1": f1,
        "False Positive Rate": fpr,
        "undefined": {
            "Precision": "TP+FP is zero" if tp + fp == 0 else None,
            "Recall": "TP+FN is zero" if tp + fn == 0 else None,
            "False Positive Rate": "FP+TN is zero" if fp + tn == 0 else None,
        },
    }


def scenario_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    retrieval_success = sum(1 for item in records if item.get("retrieval_attack_success"))
    answer_success = sum(1 for item in records if item.get("answer_attack_success"))
    cluster_total = sum(1 for item in records if item.get("has_true_cluster"))
    cluster_detected = sum(1 for item in records if item.get("cluster_detected"))
    return {
        "scenario_count": total,
        "Retrieval Attack Success": retrieval_success / total if total else None,
        "Answer Attack Success": answer_success / total if total else None,
        "Cluster Detection Rate": cluster_detected / cluster_total if cluster_total else None,
    }


def aggregate_metrics(chunk_rows: list[dict[str, Any]], scenario_rows: list[dict[str, Any]], methods: list[str]) -> dict[str, Any]:
    by_method = {method: confusion_metrics(chunk_rows, method) for method in methods}
    by_scenario: dict[str, Any] = {}
    grouped_chunks: dict[str, list[dict[str, Any]]] = defaultdict(list)
    grouped_scenarios: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in chunk_rows:
        grouped_chunks[str(row.get("scenario_group", "overall"))].append(row)
    for row in scenario_rows:
        grouped_scenarios[str(row.get("scenario_group", "overall"))].append(row)
    for group in sorted(set(grouped_chunks) | set(grouped_scenarios)):
        by_scenario[group] = {
            "chunk_metrics": {method: confusion_metrics(grouped_chunks[group], method) for method in methods},
            "scenario_metrics": scenario_metrics(grouped_scenarios[group]),
            "sample_count": len({row.get("case_id") for row in grouped_scenarios[group]}),
            "chunk_count": len({(row.get("case_id"), row.get("chunk_id")) for row in grouped_chunks[group]}),
        }
    by_scenario["overall"] = {
        "chunk_metrics": by_method,
        "scenario_metrics": scenario_metrics(scenario_rows),
        "sample_count": len({row.get("case_id") for row in scenario_rows}),
        "chunk_count": len({(row.get("case_id"), row.get("chunk_id")) for row in chunk_rows}),
    }
    return {
        "metrics_by_method": by_method,
        "metrics_by_scenario": by_scenario,
        "micro_average": by_method,
        "macro_average": macro_average(by_scenario, methods),
    }


def macro_average(by_scenario: dict[str, Any], methods: list[str]) -> dict[str, Any]:
    scenario_items = [value for key, value in by_scenario.items() if key != "overall"]
    averaged: dict[str, Any] = {}
    for method in methods:
        method_rows = [item["chunk_metrics"].get(method, {}) for item in scenario_items]
        averaged[method] = {}
        for metric in ("Precision", "Recall", "F1", "False Positive Rate"):
            values = [float(row[metric]) for row in method_rows if row.get(metric) is not None]
            averaged[method][metric] = sum(values) / len(values) if values else 0.0
    return averaged
