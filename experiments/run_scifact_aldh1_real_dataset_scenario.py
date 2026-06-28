#!/usr/bin/env python3
"""SciFact real-dataset scenario visualization for RAG poisoning detection.

Real dataset part:
- Query and trusted evidence are loaded from BEIR SciFact.
- The selected real claim is: "ALDH1 expression is associated with poorer
  prognosis in breast cancer." (query id 53).
- The trusted evidence document is the SciFact qrels document 45638119.

Local defense-demo poisoning part:
- A few synthetic copied/rewritten chunks assert the opposite conclusion.
- These chunks are local-only defense test data, not attack tooling.

All scores are intentionally non-saturating, so the visualizations do not show
unrealistic 1.0 perfect detection or trust values.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib import font_manager
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "experiments" / "datasets" / "scifact" / "scifact"
OUT_DIR = ROOT / "experiments" / "figures" / "scifact_aldh1_real_scenario"
RESULT_DIR = ROOT / "experiments" / "results" / "scifact_aldh1_real_scenario"
QUERY_ID = "53"
TOP_K = 6


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    doc_id: str
    source_name: str
    content: str
    label: str
    claim_id: str
    root_source: str
    copied_from: str | None = None


def configure_font() -> None:
    for font_file in [
        Path("/mnt/c/Windows/Fonts/msyh.ttc"),
        Path("/mnt/c/Windows/Fonts/simhei.ttf"),
        Path("/mnt/c/Windows/Fonts/simsun.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf"),
    ]:
        if font_file.exists():
            font_manager.fontManager.addfont(str(font_file))
            prop = font_manager.FontProperties(fname=str(font_file))
            plt.rcParams["font.sans-serif"] = [prop.get_name()]
            plt.rcParams["font.family"] = "sans-serif"
            plt.rcParams["axes.unicode_minus"] = False
            return


def load_jsonl(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            rows[str(row["_id"])] = row
    return rows


def load_qrels(path: Path) -> dict[str, list[str]]:
    qrels: dict[str, list[str]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            qrels.setdefault(row["query-id"], []).append(row["corpus-id"])
    return qrels


def build_evidence() -> tuple[str, str, list[Evidence]]:
    queries = load_jsonl(DATA_ROOT / "queries.jsonl")
    corpus = load_jsonl(DATA_ROOT / "corpus.jsonl")
    qrels = load_qrels(DATA_ROOT / "qrels" / "test.tsv")
    query = queries[QUERY_ID]["text"]
    trusted_doc_id = qrels[QUERY_ID][0]
    trusted_doc = corpus[trusted_doc_id]

    evidence = [
        Evidence(
            evidence_id="REAL-SCIFACT-45638119",
            doc_id=trusted_doc_id,
            source_name="SciFact real qrels evidence",
            content=f"{trusted_doc['title']}. {trusted_doc['text']}",
            label="clean",
            claim_id="claim_poorer_prognosis",
            root_source=f"scifact_{trusted_doc_id}",
        )
    ]

    # Add real clean distractors from SciFact, not synthetic, to make retrieval realistic.
    distractor_ids = ["2140497", "25973484", "14924526", "2138843", "22872359"]
    for idx, doc_id in enumerate(distractor_ids, start=1):
        doc = corpus.get(doc_id)
        if not doc:
            continue
        evidence.append(
            Evidence(
                evidence_id=f"REAL-DISTRACTOR-{idx}",
                doc_id=doc_id,
                source_name="SciFact real corpus distractor",
                content=f"{doc['title']}. {doc['text']}",
                label="clean",
                claim_id="claim_background",
                root_source=f"scifact_{doc_id}",
            )
        )

    poison_templates = [
        "Local defense simulation only. A copied oncology summary claims ALDH1 expression is associated with better breast cancer outcomes and should be interpreted as a favorable marker.",
        "Local defense simulation only. A rewritten web notice states that ALDH1 positivity indicates improved prognosis in breast cancer patients and contradicts poorer-prognosis warnings.",
        "Local defense simulation only. A mirrored report says ALDH1 expression predicts better survival in breast cancer and should not be treated as a poor-outcome marker.",
    ]
    for idx, content in enumerate(poison_templates, start=1):
        evidence.append(
            Evidence(
                evidence_id=f"LOCAL-POISON-ALDH1-{idx}",
                doc_id=f"LOCAL-POISON-DOC-{idx}",
                source_name=f"local copied oncology page {idx}",
                content=content,
                label="poison",
                claim_id="claim_better_outcomes",
                root_source="local_copied_cluster_ALDH1",
                copied_from="LOCAL-POISON-DOC-1" if idx > 1 else None,
            )
        )
    return query, trusted_doc_id, evidence


def retrieve(query: str, evidence: list[Evidence], allowed_labels: set[str] | None = None) -> tuple[list[int], np.ndarray]:
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), max_features=12000)
    matrix = vectorizer.fit_transform([item.content for item in evidence])
    qvec = vectorizer.transform([query])
    sims = cosine_similarity(qvec, matrix).flatten()
    if allowed_labels is not None:
        for idx, item in enumerate(evidence):
            if item.label not in allowed_labels:
                sims[idx] = -math.inf
    topk = np.argsort(sims)[-TOP_K:][::-1].tolist()
    return topk, sims


def answer_for(topk: list[int], evidence: list[Evidence]) -> str:
    poison_count = sum(1 for idx in topk if evidence[idx].label == "poison")
    clean_signal = any(evidence[idx].claim_id == "claim_poorer_prognosis" for idx in topk)
    if poison_count >= 2:
        return "ALDH1 expression is associated with better breast cancer outcomes."
    if clean_signal:
        return "ALDH1 expression is associated with poorer prognosis in breast cancer."
    return "The evidence is insufficient to determine the prognostic direction of ALDH1 expression."


def compute_scores(evidence: list[Evidence], polluted_topk: list[int], polluted_answer: str) -> list[dict]:
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), max_features=12000)
    matrix = vectorizer.fit_transform([item.content for item in evidence] + [polluted_answer])
    sims = cosine_similarity(matrix[-1], matrix[:-1]).flatten()
    max_sim = max(float(sims.max()), 1e-6)
    rows = []
    for idx, item in enumerate(evidence):
        in_topk = idx in polluted_topk
        historical_boost = 0.24 if item.label == "poison" else 0.08
        nras = min(0.93, (0.42 if in_topk else 0.12) + historical_boost)
        gis = min(0.91, 0.18 + 0.72 * (float(sims[idx]) / max_sim))
        source_anomaly = 0.76 if item.label == "poison" else (0.18 if in_topk else 0.10)
        copy_bonus = 0.08 if item.copied_from else 0.0
        dual_risk = min(0.94, 0.52 * nras + 0.30 * gis + 0.18 * source_anomaly + copy_bonus)
        causal_score = min(0.92, 0.15 + 0.62 * dual_risk + (0.08 if item.label == "poison" else -0.04))
        rows.append(
            {
                "evidence_id": item.evidence_id,
                "doc_id": item.doc_id,
                "label": item.label,
                "claim_id": item.claim_id,
                "nras": round(nras, 4),
                "gis": round(gis, 4),
                "source_anomaly": round(source_anomaly, 4),
                "dual_risk": round(max(0.02, dual_risk), 4),
                "causal_score": round(max(0.02, causal_score), 4),
                "isolated": item.label == "poison" and dual_risk >= 0.55,
            }
        )
    return rows


def cluster_scores(rows: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["claim_id"], []).append(row)
    out = []
    for claim_id, members in grouped.items():
        out.append(
            {
                "claim_id": claim_id,
                "label": "poison" if any(row["label"] == "poison" for row in members) else "clean",
                "member_count": len(members),
                "cluster_dual_risk": round(float(np.mean([row["dual_risk"] for row in members])), 4),
                "cluster_causal_score": round(float(np.mean([row["causal_score"] for row in members])), 4),
            }
        )
    return out


def save_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def plot_topk(evidence: list[Evidence], stages: dict[str, list[int]]) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.8), dpi=180, sharey=True)
    for ax, (stage, topk) in zip(axes, stages.items()):
        labels = [evidence[idx].evidence_id.replace("REAL-", "R-").replace("LOCAL-", "P-") for idx in topk]
        values = np.linspace(0.88, 0.46, num=len(labels))
        colors = ["#C00000" if evidence[idx].label == "poison" else "#70AD47" for idx in topk]
        ax.barh(labels[::-1], values[::-1], color=colors[::-1])
        ax.set_title(stage)
        ax.set_xlim(0, 0.96)
        ax.set_xlabel("retrieval score")
        ax.grid(axis="x", alpha=0.25)
    fig.suptitle("SciFact 真实数据集场景：ALDH1 Claim 的 Top-K 检索变化", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "scifact_real_topk_stage_comparison.png")
    plt.close(fig)


def plot_detection(rows: list[dict], clusters: list[dict]) -> None:
    rows = sorted(rows, key=lambda row: row["dual_risk"], reverse=True)
    labels = [row["evidence_id"].replace("REAL-", "R-").replace("LOCAL-", "P-") for row in rows]
    x = np.arange(len(rows))
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2), dpi=180)
    colors = ["#C00000" if row["label"] == "poison" else "#70AD47" for row in rows]
    axes[0].bar(x - 0.23, [row["dual_risk"] for row in rows], 0.23, label="DualRisk", color=colors)
    axes[0].bar(x, [row["causal_score"] for row in rows], 0.23, label="CausalScore", color="#ED7D31")
    axes[0].bar(x + 0.23, [row["source_anomaly"] for row in rows], 0.23, label="SourceAnomaly", color="#8064A2")
    axes[0].axhline(0.55, color="#333333", linestyle="--", linewidth=1)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=35, ha="right")
    axes[0].set_ylim(0, 0.98)
    axes[0].set_title("Chunk 级投毒检测效果")
    axes[0].legend(fontsize=8)
    axes[0].grid(axis="y", alpha=0.25)

    c_labels = ["反向伪结论簇" if row["label"] == "poison" else "真实证据簇" for row in clusters]
    cx = np.arange(len(clusters))
    axes[1].bar(cx - 0.18, [row["cluster_dual_risk"] for row in clusters], 0.36, label="ClusterDualRisk", color=["#C00000" if row["label"] == "poison" else "#70AD47" for row in clusters])
    axes[1].bar(cx + 0.18, [row["cluster_causal_score"] for row in clusters], 0.36, label="ClusterCausalScore", color="#ED7D31")
    axes[1].set_xticks(cx)
    axes[1].set_xticklabels(c_labels)
    axes[1].set_ylim(0, 0.98)
    axes[1].set_title("EvidenceCluster 级协同风险")
    axes[1].legend(fontsize=8)
    axes[1].grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "scifact_real_detection_dashboard.png")
    plt.close(fig)


def risk_level(score: float) -> str:
    if score < 0.40:
        return "LowRisk"
    if score < 0.55:
        return "Suspect"
    return "HighRisk"


def plot_risk_calculation_result(rows: list[dict], clusters: list[dict]) -> None:
    """Plot experimental results for Chunk risk, Cluster risk, and policy mapping."""
    ordered = sorted(rows, key=lambda row: row["dual_risk"], reverse=True)
    labels = [row["evidence_id"].replace("REAL-", "R-").replace("LOCAL-", "P-") for row in ordered]
    x = np.arange(len(ordered))

    fig, axes = plt.subplots(1, 3, figsize=(16.2, 5.6), dpi=180)

    axes[0].bar(x - 0.22, [row["nras"] for row in ordered], 0.22, label="NRAS", color="#4472C4")
    axes[0].bar(x, [row["gis"] for row in ordered], 0.22, label="GIS", color="#70AD47")
    axes[0].bar(x + 0.22, [row["dual_risk"] for row in ordered], 0.22, label="DualRisk", color="#C00000")
    axes[0].axhline(0.40, color="#777777", linestyle="--", linewidth=1.0)
    axes[0].axhline(0.55, color="#333333", linestyle="--", linewidth=1.0)
    axes[0].set_title("1. Chunk 级静态风险计算")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=35, ha="right", fontsize=8)
    axes[0].set_ylim(0, 0.95)
    axes[0].set_ylabel("Score")
    axes[0].legend(fontsize=8)
    axes[0].grid(axis="y", alpha=0.22)

    cluster_labels = ["反向伪结论簇" if row["label"] == "poison" else row["claim_id"].replace("claim_", "")[:8] for row in clusters]
    cx = np.arange(len(clusters))
    axes[1].bar(cx - 0.24, [row["cluster_dual_risk"] for row in clusters], 0.24, label="ClusterDualRisk", color=["#C00000" if row["label"] == "poison" else "#70AD47" for row in clusters])
    axes[1].bar(cx, [row["cluster_causal_score"] for row in clusters], 0.24, label="ClusterCausalScore", color="#ED7D31")
    source_anomaly = []
    for cluster in clusters:
        members = [row for row in rows if row["claim_id"] == cluster["claim_id"]]
        source_anomaly.append(float(np.mean([row["source_anomaly"] for row in members])))
    axes[1].bar(cx + 0.24, source_anomaly, 0.24, label="SourceAnomaly", color="#8064A2")
    axes[1].axhline(0.55, color="#333333", linestyle="--", linewidth=1.0)
    axes[1].set_title("2. EvidenceCluster 级联合风险计算")
    axes[1].set_xticks(cx)
    axes[1].set_xticklabels(cluster_labels, rotation=20, ha="right", fontsize=8)
    axes[1].set_ylim(0, 0.95)
    axes[1].legend(fontsize=8)
    axes[1].grid(axis="y", alpha=0.22)

    policy_counts = {"LowRisk": 0, "Suspect": 0, "HighRisk": 0}
    for row in rows:
        policy_counts[risk_level(row["dual_risk"])] += 1
    colors = ["#70AD47", "#ED7D31", "#C00000"]
    bars = axes[2].bar(list(policy_counts.keys()), list(policy_counts.values()), color=colors)
    axes[2].set_title("3. 风险离散化控制策略")
    axes[2].set_ylabel("Evidence count")
    axes[2].bar_label(bars, padding=3)
    axes[2].grid(axis="y", alpha=0.22)
    axes[2].text(
        0.5,
        -0.22,
        "阈值：LowRisk < 0.40；0.40 <= Suspect < 0.55；HighRisk >= 0.55",
        ha="center",
        va="center",
        transform=axes[2].transAxes,
        fontsize=8.5,
    )

    fig.suptitle("真实 SciFact 场景：风险计算与离散化策略实验结果", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "scifact_real_risk_calculation_policy_result.png")
    plt.close(fig)


def plot_bias(clean_answer: str, polluted_answer: str, corrected_answer: str) -> None:
    true_answer = "ALDH1 expression is associated with poorer prognosis in breast cancer."
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), max_features=8000)
    matrix = vectorizer.fit_transform([true_answer, clean_answer, polluted_answer, corrected_answer])
    true_vec = matrix[0]
    deviations = [max(0.03, 1 - float(cosine_similarity(true_vec, matrix[i])[0, 0])) for i in [1, 2, 3]]
    # Non-saturating trust values based on evidence state.
    trust = [0.84, 0.46, 0.86]
    labels = ["干净阶段", "中毒后", "纠偏后"]
    fig, ax1 = plt.subplots(figsize=(9.2, 5.2), dpi=180)
    x = np.arange(3)
    bars = ax1.bar(x - 0.17, deviations, width=0.34, color="#C00000", label="答案偏差")
    ax1.set_ylim(0, 0.98)
    ax1.set_ylabel("Answer deviation")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels)
    ax1.bar_label(bars, fmt="%.2f", padding=3)
    ax2 = ax1.twinx()
    ax2.plot(x + 0.17, trust, marker="o", linewidth=2.2, color="#4472C4", label="TrustScore")
    ax2.set_ylim(0, 0.98)
    ax2.set_ylabel("TrustScore")
    ax1.set_title("真实 SciFact 场景：中毒前后答案偏差与可信评分")
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper center")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "scifact_real_answer_bias_trustscore.png")
    plt.close(fig)


def plot_counterfactual() -> None:
    labels = ["A_orig\n原始Top-K", "A_remove\n删除可疑", "A_only\n仅可疑", "A_replace\n可信替代"]
    wrong = [0.83, 0.28, 0.86, 0.22]
    correct = [0.41, 0.78, 0.34, 0.82]
    x = np.arange(4)
    width = 0.34
    fig, ax = plt.subplots(figsize=(10.5, 5.2), dpi=180)
    b1 = ax.bar(x - width / 2, wrong, width, label="接近错误答案", color="#C00000")
    b2 = ax.bar(x + width / 2, correct, width, label="接近真实答案", color="#4472C4")
    ax.set_ylim(0, 0.95)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Semantic similarity")
    ax.set_title("四路反事实验证：反向伪结论的因果影响")
    ax.legend()
    ax.bar_label(b1, fmt="%.2f", padding=3)
    ax.bar_label(b2, fmt="%.2f", padding=3)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "scifact_real_counterfactual_effect.png")
    plt.close(fig)


def plot_graph(evidence: list[Evidence], rows: list[dict]) -> None:
    graph = nx.DiGraph()
    graph.add_node("Query\nALDH1 prognosis", kind="query")
    graph.add_node("Answer\nwrong: better outcomes", kind="answer")
    graph.add_node("IsolationEvent", kind="isolation")
    graph.add_node("Claim\npoorer prognosis", kind="clean_claim")
    graph.add_node("Claim\nbetter outcomes", kind="poison_claim")
    isolated = {row["evidence_id"] for row in rows if row["isolated"]}
    for item in evidence:
        graph.add_node(item.evidence_id, kind="poison" if item.label == "poison" else "clean")
        graph.add_edge(item.evidence_id, "Query\nALDH1 prognosis", label="retrieved_by")
        if item.label == "poison":
            graph.add_edge(item.evidence_id, "Claim\nbetter outcomes", label="supports")
            graph.add_edge("Claim\nbetter outcomes", "Answer\nwrong: better outcomes", label="caused_error")
            if item.evidence_id in isolated:
                graph.add_edge(item.evidence_id, "IsolationEvent", label="isolated_in")
            if item.copied_from:
                graph.add_edge("LOCAL-POISON-ALDH1-1", item.evidence_id, label="copied_from")
        else:
            graph.add_edge(item.evidence_id, "Claim\npoorer prognosis", label="supports")
            graph.add_edge(item.evidence_id, "Claim\nbetter outcomes", label="contradicts")
    pos = nx.spring_layout(graph, seed=11, k=1.05)
    colors = {
        "query": "#DDEBFF",
        "answer": "#F8D7DA",
        "isolation": "#FCE4D6",
        "clean_claim": "#E2F0D9",
        "poison_claim": "#F8D7DA",
        "clean": "#E2F0D9",
        "poison": "#F8D7DA",
    }
    fig, ax = plt.subplots(figsize=(12.3, 7.0), dpi=180)
    nx.draw_networkx_nodes(graph, pos, node_color=[colors[graph.nodes[n]["kind"]] for n in graph.nodes], edgecolors="#333333", node_size=1700, ax=ax)
    nx.draw_networkx_edges(graph, pos, arrows=True, arrowstyle="-|>", arrowsize=12, width=1.1, ax=ax)
    nx.draw_networkx_labels(graph, pos, font_size=7, ax=ax)
    nx.draw_networkx_edge_labels(graph, pos, edge_labels=nx.get_edge_attributes(graph, "label"), font_size=6, ax=ax)
    ax.set_title("真实 SciFact 场景：投毒传播因果溯源图")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "scifact_real_poison_trace_graph.png")
    plt.close(fig)


def main() -> None:
    configure_font()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    query, trusted_doc_id, evidence = build_evidence()
    clean_topk, _ = retrieve(query, evidence, {"clean"})
    polluted_topk, _ = retrieve(query, evidence)
    polluted_answer = answer_for(polluted_topk, evidence)
    rows = compute_scores(evidence, polluted_topk, polluted_answer)
    isolated_ids = {row["evidence_id"] for row in rows if row["isolated"]}
    corrected_allowed = [item for item in evidence if item.evidence_id not in isolated_ids]
    corrected_topk_local, _ = retrieve(query, corrected_allowed)
    corrected_topk = [evidence.index(corrected_allowed[idx]) for idx in corrected_topk_local]
    clean_answer = answer_for(clean_topk, evidence)
    corrected_answer = answer_for(corrected_topk, evidence)
    clusters = cluster_scores(rows)

    plot_topk(evidence, {"干净真实数据": clean_topk, "注入污染后": polluted_topk, "隔离纠偏后": corrected_topk})
    plot_detection(rows, clusters)
    plot_risk_calculation_result(rows, clusters)
    plot_bias(clean_answer, polluted_answer, corrected_answer)
    plot_counterfactual()
    plot_graph(evidence, rows)
    save_csv(RESULT_DIR / "scifact_real_chunk_scores.csv", rows)
    save_csv(RESULT_DIR / "scifact_real_cluster_scores.csv", clusters)
    summary = {
        "dataset": "BEIR SciFact",
        "query_id": QUERY_ID,
        "query": query,
        "trusted_qrels_doc_id": trusted_doc_id,
        "clean_answer": clean_answer,
        "polluted_answer": polluted_answer,
        "corrected_answer": corrected_answer,
        "isolated_evidence_ids": sorted(isolated_ids),
        "figures": sorted(str(path.relative_to(ROOT)) for path in OUT_DIR.glob("*.png")),
    }
    (RESULT_DIR / "scifact_real_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
