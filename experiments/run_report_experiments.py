#!/usr/bin/env python3
"""运行报告所需的本地受控实验并生成可复核结果与图表。"""

from __future__ import annotations

import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
RESULT_DIR = ROOT / "experiments" / "results"
FIGURE_DIR = ROOT / "experiments" / "figures"
sys.path.insert(0, str(BACKEND))

from app.services.counterfactual import run_counterfactual
from app.services.pipeline import run_pipeline
from app.utils.score_utils import compute_dual_risk

CASE_IDS = [
    "case_enterprise_rag_poisoning",
    "case_ai_search_linkfarm_poisoning",
]


def metric_counts(labels: list[int], scores: list[float], threshold: float) -> dict[str, float]:
    predictions = [int(score >= threshold) for score in scores]
    tp = sum(y == 1 and p == 1 for y, p in zip(labels, predictions))
    fp = sum(y == 0 and p == 1 for y, p in zip(labels, predictions))
    fn = sum(y == 1 and p == 0 for y, p in zip(labels, predictions))
    tn = sum(y == 0 and p == 0 for y, p in zip(labels, predictions))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "threshold": threshold,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fpr": fp / (fp + tn) if fp + tn else 0.0,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def run_rag_experiments() -> dict:
    labels: list[int] = []
    ras_scores: list[float] = []
    gis_scores: list[float] = []
    dual_scores: list[float] = []
    case_rows: list[dict] = []
    causal_labels: list[int] = []
    causal_scores: list[float] = []

    for case_id in CASE_IDS:
        result = run_pipeline(case_id)
        if result is None or result.case_info is None:
            raise RuntimeError(f"案例运行失败: {case_id}")
        poisoned = set(result.case_info.poisoned_evidence_ids)
        detection_by_id = {item.evidence_id: item for item in result.detection_results}
        for evidence in result.original_topk_evidence:
            detection = detection_by_id[evidence.evidence_id]
            labels.append(int(evidence.evidence_id in poisoned))
            ras_scores.append(detection.ras)
            gis_scores.append(detection.gis)
            dual_scores.append(detection.dual_risk)
            counterfactual = run_counterfactual(
                query=result.case_info.question,
                suspicious_evidence=evidence,
                top_k_evidences=result.original_topk_evidence,
                all_evidences=result.case_info.evidences,
                target_wrong_answer=result.case_info.target_wrong_answer,
                trusted_evidence_ids=result.case_info.trusted_evidence_ids,
            )
            causal_labels.append(int(evidence.evidence_id in poisoned))
            causal_scores.append(counterfactual.causal_score)

        case_rows.append(
            {
                "case_id": case_id,
                "trust_before": result.trust_score_before.trust_score,
                "trust_after": result.trust_score_after.trust_score,
                "trust_gain": result.trust_score_after.trust_score
                - result.trust_score_before.trust_score,
                "isolated_count": len(result.isolated_evidences),
                "poison_count": len(poisoned),
            }
        )

    thresholds = [round(value / 20, 2) for value in range(2, 19)]
    threshold_rows = [metric_counts(labels, dual_scores, threshold) for threshold in thresholds]
    causal_rows = [metric_counts(causal_labels, causal_scores, threshold) for threshold in thresholds]

    lambda_rows: list[dict] = []
    for lam in [0.0, 0.25, 0.5, 0.7, 0.9, 1.0]:
        scores = [compute_dual_risk(ras, gis, lam=lam) for ras, gis in zip(ras_scores, gis_scores)]
        candidates = [metric_counts(labels, scores, threshold) for threshold in thresholds]
        best = max(candidates, key=lambda row: (row["f1"], row["recall"], -row["fpr"]))
        lambda_rows.append({"lambda": lam, **best})

    baselines = {}
    for name, scores in (("RAS", ras_scores), ("GIS", gis_scores), ("DualRisk", dual_scores)):
        candidates = [metric_counts(labels, scores, threshold) for threshold in thresholds]
        baselines[name] = max(candidates, key=lambda row: (row["f1"], row["recall"], -row["fpr"]))

    return {
        "sample_count": len(labels),
        "poison_count": sum(labels),
        "threshold_sweep": threshold_rows,
        "causal_threshold_sweep": causal_rows,
        "lambda_sweep": lambda_rows,
        "best_baselines": baselines,
        "case_results": case_rows,
    }


def simulate_multi_agent_trial(
    rng: random.Random,
    malicious_ratio: float,
    risk_threshold: float,
) -> dict[str, int]:
    """固定规则的本地受控仿真，不调用任何在线模型。"""
    agent_count = 7
    malicious_count = round(agent_count * malicious_ratio)
    malicious_ids = set(rng.sample(range(agent_count), malicious_count))
    poisoned_source = rng.random() < 0.55
    votes: list[int] = []
    weights: list[float] = []
    risks: list[float] = []

    for agent_id in range(agent_count):
        malicious = agent_id in malicious_ids
        shares_poison = poisoned_source and rng.random() < 0.48
        if malicious:
            correct = rng.random() < 0.08
            signature_valid = rng.random() >= 0.45
            evidence_support = rng.uniform(0.05, 0.35)
            claim_risk = rng.uniform(0.65, 0.98)
        else:
            correct_probability = 0.86 if not shares_poison else 0.42
            correct = rng.random() < correct_probability
            signature_valid = rng.random() >= 0.02
            evidence_support = rng.uniform(0.70, 0.98) if not shares_poison else rng.uniform(0.25, 0.55)
            claim_risk = rng.uniform(0.03, 0.25) if not shares_poison else rng.uniform(0.55, 0.82)

        vote = int(correct)
        zero_trust = 1.0 if signature_valid else 0.0
        independence = 0.45 if shares_poison else 1.0
        risk_gate = 0.0 if claim_risk >= risk_threshold else 1.0
        weight = zero_trust * independence * risk_gate * evidence_support
        votes.append(vote)
        weights.append(weight)
        risks.append(claim_risk)

    no_defense = votes[0]
    majority = int(sum(votes) > agent_count / 2)
    verifier = int(rng.random() < (0.84 if not poisoned_source else 0.68))
    weighted_total = sum(weights)
    proposed = int(sum(v * w for v, w in zip(votes, weights)) >= weighted_total / 2) if weighted_total else verifier

    suspicious = {idx for idx, risk in enumerate(risks) if risk >= risk_threshold}
    localization = int(bool(malicious_ids) and bool(suspicious & malicious_ids))
    correction = int(proposed == 1 and (majority == 0 or no_defense == 0))
    return {
        "no_defense": no_defense,
        "majority": majority,
        "single_verifier": verifier,
        "proposed": proposed,
        "localized": localization,
        "corrected": correction,
    }


def run_multi_agent_experiments() -> dict:
    ratios = [0.0, 0.14, 0.29, 0.43]
    thresholds = [0.35, 0.45, 0.55, 0.65, 0.75]
    repetitions = 500
    rows: list[dict] = []

    for threshold in thresholds:
        for ratio in ratios:
            rng = random.Random(20260614 + int(threshold * 1000) + int(ratio * 100))
            totals: defaultdict[str, int] = defaultdict(int)
            for _ in range(repetitions):
                trial = simulate_multi_agent_trial(rng, ratio, threshold)
                for key, value in trial.items():
                    totals[key] += value
            rows.append(
                {
                    "risk_threshold": threshold,
                    "malicious_ratio": ratio,
                    "repetitions": repetitions,
                    "no_defense_accuracy": totals["no_defense"] / repetitions,
                    "majority_accuracy": totals["majority"] / repetitions,
                    "single_verifier_accuracy": totals["single_verifier"] / repetitions,
                    "proposed_accuracy": totals["proposed"] / repetitions,
                    "source_localization_rate": (
                        totals["localized"] / repetitions if ratio > 0 else 1.0
                    ),
                    "correction_rate": totals["corrected"] / repetitions,
                }
            )
    return {"rows": rows, "repetitions": repetitions}


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def configure_plot() -> None:
    font = Path("/mnt/c/Windows/Fonts/simsun.ttc")
    if font.exists():
        from matplotlib import font_manager

        font_manager.fontManager.addfont(str(font))
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(font)).get_name()
    plt.rcParams["axes.unicode_minus"] = False


def plot_results(rag: dict, multi_agent: dict) -> None:
    configure_plot()

    rows = rag["threshold_sweep"]
    plt.figure(figsize=(8.5, 5))
    plt.plot([r["threshold"] for r in rows], [r["precision"] for r in rows], marker="o", label="Precision")
    plt.plot([r["threshold"] for r in rows], [r["recall"] for r in rows], marker="s", label="Recall")
    plt.plot([r["threshold"] for r in rows], [r["f1"] for r in rows], marker="^", label="F1")
    plt.xlabel("DualRisk 阈值")
    plt.ylabel("指标值")
    plt.ylim(0, 1.05)
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURE_DIR / "exp_dualrisk_threshold.png", dpi=220)
    plt.close()

    rows = rag["lambda_sweep"]
    plt.figure(figsize=(8.5, 5))
    plt.plot([r["lambda"] for r in rows], [r["f1"] for r in rows], marker="o", color="#C55A11")
    for row in rows:
        plt.text(row["lambda"], row["f1"] + 0.025, f'{row["f1"]:.2f}', ha="center")
    plt.xlabel("几何项权重 λ")
    plt.ylabel("最优 F1")
    plt.ylim(0, 1.08)
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(FIGURE_DIR / "exp_dualrisk_lambda.png", dpi=220)
    plt.close()

    cases = rag["case_results"]
    x = range(len(cases))
    width = 0.34
    plt.figure(figsize=(8.5, 5))
    plt.bar([i - width / 2 for i in x], [r["trust_before"] for r in cases], width, label="纠偏前")
    plt.bar([i + width / 2 for i in x], [r["trust_after"] for r in cases], width, label="纠偏后")
    plt.xticks(list(x), ["企业制度投毒", "站群投毒"])
    plt.ylabel("TrustScore")
    plt.ylim(0, 105)
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURE_DIR / "exp_trust_before_after.png", dpi=220)
    plt.close()

    selected = [r for r in multi_agent["rows"] if r["risk_threshold"] == 0.55]
    plt.figure(figsize=(8.5, 5))
    for key, label, marker in (
        ("no_defense_accuracy", "无防护", "o"),
        ("majority_accuracy", "多数投票", "s"),
        ("single_verifier_accuracy", "单验证 Agent", "^"),
        ("proposed_accuracy", "本文融合方法", "D"),
    ):
        plt.plot(
            [r["malicious_ratio"] for r in selected],
            [r[key] for r in selected],
            marker=marker,
            label=label,
        )
    plt.xlabel("异常 Agent 比例")
    plt.ylabel("任务正确率")
    plt.ylim(0, 1.05)
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURE_DIR / "exp_multi_agent_robustness.png", dpi=220)
    plt.close()

    threshold_summary = []
    for threshold in sorted({r["risk_threshold"] for r in multi_agent["rows"]}):
        relevant = [r for r in multi_agent["rows"] if r["risk_threshold"] == threshold and r["malicious_ratio"] > 0]
        threshold_summary.append(
            {
                "threshold": threshold,
                "accuracy": sum(r["proposed_accuracy"] for r in relevant) / len(relevant),
                "localization": sum(r["source_localization_rate"] for r in relevant) / len(relevant),
            }
        )
    plt.figure(figsize=(8.5, 5))
    plt.plot(
        [r["threshold"] for r in threshold_summary],
        [r["accuracy"] for r in threshold_summary],
        marker="o",
        label="平均任务正确率",
    )
    plt.plot(
        [r["threshold"] for r in threshold_summary],
        [r["localization"] for r in threshold_summary],
        marker="s",
        label="平均源头定位率",
    )
    plt.xlabel("联合风险阈值")
    plt.ylabel("指标值")
    plt.ylim(0, 1.05)
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURE_DIR / "exp_multi_agent_threshold.png", dpi=220)
    plt.close()


def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    rag = run_rag_experiments()
    multi_agent = run_multi_agent_experiments()
    payload = {
        "experiment_type": "local_controlled_reproducible",
        "seed": 20260614,
        "rag": rag,
        "multi_agent": multi_agent,
    }
    (RESULT_DIR / "report_experiments.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_csv(RESULT_DIR / "rag_threshold_sweep.csv", rag["threshold_sweep"])
    write_csv(RESULT_DIR / "rag_lambda_sweep.csv", rag["lambda_sweep"])
    write_csv(RESULT_DIR / "multi_agent_simulation.csv", multi_agent["rows"])
    plot_results(rag, multi_agent)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
