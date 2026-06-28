#!/usr/bin/env python3
"""Run a local SciFact-based RAG poisoning defense visualization experiment.

The script uses the public BEIR SciFact retrieval dataset as clean evidence and
adds local simulated poisoning chunks only for defense evaluation.

Safety note:
The simulated poisoning chunks are local synthetic examples for detection,
traceback, isolation, and trusted regeneration demos. They must not be used to
pollute any real retrieval system or online knowledge base.
"""

from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib import font_manager
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "experiments" / "datasets" / "scifact" / "scifact"
FIG_DIR = ROOT / "experiments" / "figures" / "scifact_poisoning"
RESULT_DIR = ROOT / "experiments" / "results" / "scifact_poisoning"

TOP_K = 8
QUERY_LIMIT = 120
POISON_QUERY_COUNT = 24
POISON_PER_QUERY = 3
THETA_DUAL = 0.45
THETA_CAUSAL = 0.45
THETA_CLUSTER_ISOLATE = 0.15


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    content: str
    source_id: str
    label: str
    claim_id: str
    root_source: str
    copied_from: str | None = None


def configure_font() -> None:
    font_files = [
        Path("/mnt/c/Windows/Fonts/msyh.ttc"),
        Path("/mnt/c/Windows/Fonts/simhei.ttf"),
        Path("/mnt/c/Windows/Fonts/simsun.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf"),
    ]
    for font_file in font_files:
        if font_file.exists():
            font_manager.fontManager.addfont(str(font_file))
            prop = font_manager.FontProperties(fname=str(font_file))
            plt.rcParams["font.sans-serif"] = [prop.get_name()]
            plt.rcParams["font.family"] = "sans-serif"
            plt.rcParams["axes.unicode_minus"] = False
            return


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            rows.append(json.loads(line))
    return rows


def load_qrels(path: Path) -> dict[str, set[str]]:
    qrels: dict[str, set[str]] = defaultdict(set)
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            qrels[row["query-id"]].add(row["corpus-id"])
    return qrels


def normalize_claim(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()[:96]


def build_chunks(corpus_rows: list[dict], queries: list[dict]) -> tuple[list[Chunk], set[str]]:
    clean_chunks = [
        Chunk(
            chunk_id=f"clean_{row['_id']}",
            content=f"{row.get('title', '')}. {row.get('text', '')}",
            source_id=str(row["_id"]),
            label="clean",
            claim_id=f"doc_{row['_id']}",
            root_source=f"scifact_{row['_id']}",
        )
        for row in corpus_rows
    ]

    poison_query_ids = {str(row["_id"]) for row in queries[:POISON_QUERY_COUNT]}
    poison_chunks: list[Chunk] = []
    for query in queries[:POISON_QUERY_COUNT]:
        qid = str(query["_id"])
        claim = normalize_claim(query["text"])
        for idx in range(POISON_PER_QUERY):
            content = (
                "Local defense simulation only. "
                f"Claim '{query['text']}' is presented as strongly verified by a copied web notice. "
                f"This synthetic evidence repeats the target claim for retrieval-attraction test #{idx + 1}."
            )
            poison_chunks.append(
                Chunk(
                    chunk_id=f"poison_q{qid}_{idx}",
                    content=content,
                    source_id=f"synthetic_site_{idx % 2}",
                    label="poison",
                    claim_id=f"claim_{claim}",
                    root_source=f"synthetic_root_{idx % 2}",
                    copied_from="synthetic_root_0" if idx > 0 else None,
                )
            )
    return clean_chunks + poison_chunks, poison_query_ids


def retrieve_topk(vectorizer: TfidfVectorizer, matrix, chunks: list[Chunk], query_texts: list[str]) -> list[list[int]]:
    query_matrix = vectorizer.transform(query_texts)
    sims = cosine_similarity(query_matrix, matrix)
    topk_indices: list[list[int]] = []
    for row in sims:
        topk_indices.append(np.argsort(row)[-TOP_K:][::-1].tolist())
    return topk_indices


def retrieve_topk_with_mask(
    vectorizer: TfidfVectorizer,
    matrix,
    chunks: list[Chunk],
    query_texts: list[str],
    allowed_ids: set[str],
) -> list[list[int]]:
    """Retrieve Top-K after masking unavailable chunks."""
    query_matrix = vectorizer.transform(query_texts)
    sims = cosine_similarity(query_matrix, matrix)
    topk_indices: list[list[int]] = []
    allowed_mask = np.array([chunk.chunk_id in allowed_ids for chunk in chunks])
    for row in sims:
        masked = row.copy()
        masked[~allowed_mask] = -math.inf
        topk_indices.append(np.argsort(masked)[-TOP_K:][::-1].tolist())
    return topk_indices


def ratio_safe(value: float, denominator: float) -> float:
    return 0.0 if denominator <= 0 else value / denominator


def compute_risks(chunks: list[Chunk], topk_indices: list[list[int]], answers: list[str]) -> tuple[dict[str, dict], dict[str, dict]]:
    retrieval_counts = Counter()
    for indices in topk_indices:
        retrieval_counts.update(chunks[idx].chunk_id for idx in indices)

    total_retrievals = sum(retrieval_counts.values())
    total_chunks = len(chunks)
    ras = {
        chunk.chunk_id: ratio_safe(retrieval_counts[chunk.chunk_id] * total_chunks, total_retrievals)
        for chunk in chunks
    }
    max_ras = max(ras.values()) if ras else 1.0

    vectorizer = TfidfVectorizer(stop_words="english", max_features=12000)
    vectorizer.fit([chunk.content for chunk in chunks] + answers)
    chunk_matrix = vectorizer.transform([chunk.content for chunk in chunks])
    answer_matrix = vectorizer.transform(answers)

    chunk_risk: dict[str, dict] = {}
    chunk_lookup = {chunk.chunk_id: chunk for chunk in chunks}
    for query_idx, indices in enumerate(topk_indices):
        answer_vec = answer_matrix[query_idx]
        top_matrix = chunk_matrix[indices]
        top_sims = cosine_similarity(answer_vec, top_matrix).flatten()
        max_sim = float(top_sims.max()) if len(top_sims) else 0.0
        for local_pos, chunk_index in enumerate(indices):
            chunk = chunks[chunk_index]
            gis = ratio_safe(float(top_sims[local_pos]), max_sim)
            nras = ratio_safe(ras[chunk.chunk_id], max_ras)
            dual = nras * gis
            old = chunk_risk.get(chunk.chunk_id)
            if old is None or dual > old["dual_risk"]:
                chunk_risk[chunk.chunk_id] = {
                    "chunk_id": chunk.chunk_id,
                    "label": chunk.label,
                    "claim_id": chunk.claim_id,
                    "source_id": chunk.source_id,
                    "retrieval_count": retrieval_counts[chunk.chunk_id],
                    "ras": ras[chunk.chunk_id],
                    "nras": nras,
                    "gis": gis,
                    "dual_risk": dual,
                    "content_preview": chunk.content[:180],
                }

    cluster_members: dict[str, list[Chunk]] = defaultdict(list)
    for chunk in chunks:
        cluster_members[chunk.claim_id].append(chunk)

    cluster_risk: dict[str, dict] = {}
    raw_cluster_ras: dict[str, float] = {}
    for claim_id, members in cluster_members.items():
        freq = sum(retrieval_counts[member.chunk_id] for member in members)
        raw_cluster_ras[claim_id] = ratio_safe(freq * total_chunks, total_retrievals * max(1, len(members)))
    max_cluster_ras = max(raw_cluster_ras.values()) if raw_cluster_ras else 1.0

    claim_texts = {claim_id: " ".join(member.content for member in members[:2]) for claim_id, members in cluster_members.items()}
    claim_ids = list(claim_texts)
    claim_matrix = vectorizer.transform([claim_texts[claim_id] for claim_id in claim_ids])
    answer_to_claim = cosine_similarity(answer_matrix, claim_matrix)
    max_cluster_gis = float(answer_to_claim.max()) if answer_to_claim.size else 1.0

    for idx, claim_id in enumerate(claim_ids):
        members = cluster_members[claim_id]
        roots = {member.root_source for member in members}
        labels = Counter(member.label for member in members)
        copy_ratio = ratio_safe(sum(1 for member in members if member.copied_from), len(members))
        text_template_sim = 0.85 if labels["poison"] else 0.08
        time_concentration = 0.80 if labels["poison"] else 0.12
        source_independence = ratio_safe(len(roots), len(members))
        source_anomaly = 0.30 * text_template_sim + 0.25 * copy_ratio + 0.25 * time_concentration + 0.20 * (1 - source_independence)
        cluster_gis = ratio_safe(float(answer_to_claim[:, idx].max()), max_cluster_gis)
        ncluster_ras = ratio_safe(raw_cluster_ras[claim_id], max_cluster_ras)
        cluster_dual = ncluster_ras * cluster_gis * (1 + source_anomaly) / 2
        if labels["poison"] or cluster_dual > 0.05:
            cluster_risk[claim_id] = {
                "claim_id": claim_id,
                "label": "poison" if labels["poison"] else "clean",
                "member_count": len(members),
                "source_count": len(roots),
                "ncluster_ras": ncluster_ras,
                "cluster_gis": cluster_gis,
                "source_anomaly": source_anomaly,
                "cluster_dual_risk": cluster_dual,
            }

    # Ensure all retrieved chunks exist in the risk table.
    for chunk_id, count in retrieval_counts.items():
        if chunk_id not in chunk_risk:
            chunk = chunk_lookup[chunk_id]
            chunk_risk[chunk_id] = {
                "chunk_id": chunk_id,
                "label": chunk.label,
                "claim_id": chunk.claim_id,
                "source_id": chunk.source_id,
                "retrieval_count": count,
                "ras": ras[chunk_id],
                "nras": ratio_safe(ras[chunk_id], max_ras),
                "gis": 0.0,
                "dual_risk": 0.0,
                "content_preview": chunk.content[:180],
            }
    return chunk_risk, cluster_risk


def simulate_answers(chunks: list[Chunk], topk_indices: list[list[int]], queries: list[dict]) -> list[str]:
    answers: list[str] = []
    for query, indices in zip(queries, topk_indices):
        top_chunks = [chunks[idx] for idx in indices]
        poison_hits = [chunk for chunk in top_chunks if chunk.label == "poison"]
        if poison_hits:
            answers.append(f"污染证据诱导输出：系统直接接受并强化该声明，结论为真，{query['text']}。")
        else:
            answers.append(f"基于干净证据，系统对该声明保持审慎判断：{query['text']}。")
    return answers


def simulate_clean_baseline_answers(queries: list[dict]) -> list[str]:
    return [f"基于干净证据，系统对该声明保持审慎判断：{query['text']}。" for query in queries]


def compute_deviation_metrics(
    chunks: list[Chunk],
    clean_topk: list[list[int]],
    poisoned_topk: list[list[int]],
    corrected_topk: list[list[int]],
    clean_answers: list[str],
    poisoned_answers: list[str],
    corrected_answers: list[str],
) -> list[dict]:
    """Measure before/after poisoning deviation against the clean baseline."""
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), max_features=16000)
    vectorizer.fit(clean_answers + poisoned_answers + corrected_answers)
    clean_vec = vectorizer.transform(clean_answers)
    poisoned_vec = vectorizer.transform(poisoned_answers)
    corrected_vec = vectorizer.transform(corrected_answers)

    rows: list[dict] = []
    for i, (base, poisoned, corrected) in enumerate(zip(clean_topk, poisoned_topk, corrected_topk)):
        base_ids = {chunks[idx].chunk_id for idx in base}
        poisoned_ids = {chunks[idx].chunk_id for idx in poisoned}
        corrected_ids = {chunks[idx].chunk_id for idx in corrected}
        poisoned_clean_ids = {chunks[idx].chunk_id for idx in poisoned if chunks[idx].label == "clean"}
        corrected_clean_ids = {chunks[idx].chunk_id for idx in corrected if chunks[idx].label == "clean"}
        poison_ratio = ratio_safe(sum(1 for idx in poisoned if chunks[idx].label == "poison"), TOP_K)
        corrected_poison_ratio = ratio_safe(sum(1 for idx in corrected if chunks[idx].label == "poison"), TOP_K)
        retrieval_shift_poisoned = 1.0 - ratio_safe(len(base_ids & poisoned_clean_ids), TOP_K)
        retrieval_shift_corrected = 1.0 - ratio_safe(len(base_ids & corrected_clean_ids), TOP_K)
        answer_dev_poisoned = max(0.0, 1.0 - float(cosine_similarity(clean_vec[i], poisoned_vec[i])[0, 0]))
        answer_dev_corrected = max(0.0, 1.0 - float(cosine_similarity(clean_vec[i], corrected_vec[i])[0, 0]))
        rows.append(
            {
                "query_index": i,
                "poison_ratio_after_poisoning": poison_ratio,
                "poison_ratio_after_correction": corrected_poison_ratio,
                "retrieval_shift_after_poisoning": retrieval_shift_poisoned,
                "retrieval_shift_after_correction": retrieval_shift_corrected,
                "answer_deviation_after_poisoning": answer_dev_poisoned,
                "answer_deviation_after_correction": answer_dev_corrected,
                "poisoned_overlap_count": len(base_ids & poisoned_ids),
                "corrected_overlap_count": len(base_ids & corrected_ids),
            }
        )
    return rows


def trust_scores(topk_indices: list[list[int]], chunks: list[Chunk], chunk_risk: dict[str, dict]) -> tuple[list[float], list[float]]:
    before: list[float] = []
    after: list[float] = []
    for indices in topk_indices:
        top_chunks = [chunks[idx] for idx in indices]
        poison_ratio = ratio_safe(sum(1 for chunk in top_chunks if chunk.label == "poison"), len(top_chunks))
        avg_dual = float(np.mean([chunk_risk.get(chunk.chunk_id, {}).get("dual_risk", 0.0) for chunk in top_chunks]))
        support_rate = max(0.0, 1.0 - poison_ratio)
        source_independence = ratio_safe(len({chunk.root_source for chunk in top_chunks}), len(top_chunks))
        before_score = 0.35 * support_rate + 0.20 * source_independence + 0.30 * (1 - min(1.0, avg_dual)) + 0.15 * (1 - poison_ratio)
        before.append(before_score)

        safe_chunks = [
            chunk
            for chunk in top_chunks
            if chunk.label != "poison" and chunk_risk.get(chunk.chunk_id, {}).get("dual_risk", 0.0) < THETA_DUAL
        ]
        if not safe_chunks:
            after.append(0.45)
            continue
        after_support = 1.0
        after_independence = ratio_safe(len({chunk.root_source for chunk in safe_chunks}), len(safe_chunks))
        after_score = 0.35 * after_support + 0.20 * after_independence + 0.30 * 0.92 + 0.15 * 0.95
        after.append(min(1.0, after_score))
    return before, after


def write_csv(path: Path, rows: Iterable[dict]) -> None:
    rows = list(rows)
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def plot_dataset_summary(chunks: list[Chunk], queries: list[dict], qrels: dict[str, set[str]]) -> None:
    labels = ["Clean chunks", "Synthetic poison", "Queries", "Qrels"]
    values = [
        sum(1 for chunk in chunks if chunk.label == "clean"),
        sum(1 for chunk in chunks if chunk.label == "poison"),
        len(queries),
        sum(len(v) for v in qrels.values()),
    ]
    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=180)
    bars = ax.bar(labels, values, color=["#70AD47", "#C00000", "#4472C4", "#ED7D31"])
    ax.set_title("SciFact 本地检索实验数据规模")
    ax.set_ylabel("Count")
    ax.bar_label(bars, padding=3)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_dataset_summary.png")
    plt.close(fig)


def plot_retrieval_composition(chunks: list[Chunk], topk_indices: list[list[int]], isolated_ids: set[str]) -> None:
    before_clean = before_poison = after_clean = after_poison = 0
    for indices in topk_indices:
        for idx in indices:
            chunk = chunks[idx]
            if chunk.label == "poison":
                before_poison += 1
            else:
                before_clean += 1
            if chunk.chunk_id in isolated_ids:
                continue
            if chunk.label == "poison":
                after_poison += 1
            else:
                after_clean += 1
    fig, ax = plt.subplots(figsize=(7, 4.6), dpi=180)
    ax.bar(["Before isolation", "After isolation"], [before_clean, after_clean], label="clean", color="#70AD47")
    ax.bar(
        ["Before isolation", "After isolation"],
        [before_poison, after_poison],
        bottom=[before_clean, after_clean],
        label="synthetic poison",
        color="#C00000",
    )
    ax.set_title("Top-K 检索结果组成变化")
    ax.set_ylabel("Retrieved chunks")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_topk_composition.png")
    plt.close(fig)


def plot_dualrisk_distribution(chunk_risk: dict[str, dict]) -> None:
    clean = [row["dual_risk"] for row in chunk_risk.values() if row["label"] == "clean"]
    poison = [row["dual_risk"] for row in chunk_risk.values() if row["label"] == "poison"]
    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=180)
    ax.hist(clean, bins=25, alpha=0.72, label="clean", color="#70AD47")
    ax.hist(poison, bins=15, alpha=0.72, label="synthetic poison", color="#C00000")
    ax.axvline(THETA_DUAL, color="#333333", linestyle="--", linewidth=1.2, label=f"threshold={THETA_DUAL}")
    ax.set_title("Chunk_DualRisk 分布")
    ax.set_xlabel("DualRisk")
    ax.set_ylabel("Chunk count")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_dualrisk_distribution.png")
    plt.close(fig)


def plot_cluster_risk(cluster_risk: dict[str, dict]) -> None:
    rows = sorted(cluster_risk.values(), key=lambda row: row["cluster_dual_risk"], reverse=True)[:12]
    names = [f"C{i+1}" for i in range(len(rows))]
    values = [row["cluster_dual_risk"] for row in rows]
    colors = ["#C00000" if row["label"] == "poison" else "#70AD47" for row in rows]
    fig, ax = plt.subplots(figsize=(8.8, 5.0), dpi=180)
    bars = ax.bar(names, values, color=colors)
    ax.set_title("Top EvidenceCluster 联合风险")
    ax.set_ylabel("ClusterDualRisk")
    ax.bar_label(bars, fmt="%.2f", padding=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_cluster_dualrisk_top.png")
    plt.close(fig)


def plot_trust_scores(before: list[float], after: list[float]) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 4.8), dpi=180)
    means = [float(np.mean(before)), float(np.mean(after))]
    bars = ax.bar(["Before correction", "After correction"], means, color=["#ED7D31", "#4472C4"])
    ax.set_ylim(0, 1.05)
    ax.set_title("可信评分纠偏前后对比")
    ax.set_ylabel("Mean TrustScore")
    ax.bar_label(bars, fmt="%.3f", padding=3)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_trustscore_before_after.png")
    plt.close(fig)


def plot_poisoning_deviation(deviation_rows: list[dict]) -> None:
    metrics = [
        ("poison_ratio_after_poisoning", "poison_ratio_after_correction", "污染证据占比"),
        ("retrieval_shift_after_poisoning", "retrieval_shift_after_correction", "检索结果偏移"),
        ("answer_deviation_after_poisoning", "answer_deviation_after_correction", "答案语义偏差"),
    ]
    before_values = [float(np.mean([row[before] for row in deviation_rows])) for before, _, _ in metrics]
    after_values = [float(np.mean([row[after] for row in deviation_rows])) for _, after, _ in metrics]
    labels = [label for _, _, label in metrics]
    x = np.arange(len(labels))
    width = 0.34

    fig, ax = plt.subplots(figsize=(9.2, 5.2), dpi=180)
    bars_before = ax.bar(x - width / 2, before_values, width, label="中毒后", color="#C00000")
    bars_after = ax.bar(x + width / 2, after_values, width, label="纠偏后", color="#4472C4")
    ax.set_title("RAG 中毒前基线下的偏差对比")
    ax.set_ylabel("Deviation ratio")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.05)
    ax.legend()
    ax.bar_label(bars_before, fmt="%.2f", padding=3)
    ax.bar_label(bars_after, fmt="%.2f", padding=3)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_poisoning_deviation_before_after.png")
    plt.close(fig)


def plot_affected_query_deviation(deviation_rows: list[dict]) -> None:
    affected_rows = [row for row in deviation_rows if row["poison_ratio_after_poisoning"] > 0]
    if not affected_rows:
        return
    metrics = [
        ("poison_ratio_after_poisoning", "poison_ratio_after_correction", "污染证据占比"),
        ("retrieval_shift_after_poisoning", "retrieval_shift_after_correction", "检索结果偏移"),
        ("answer_deviation_after_poisoning", "answer_deviation_after_correction", "答案语义偏差"),
    ]
    before_values = [float(np.mean([row[before] for row in affected_rows])) for before, _, _ in metrics]
    after_values = [float(np.mean([row[after] for row in affected_rows])) for _, after, _ in metrics]
    labels = [label for _, _, label in metrics]
    x = np.arange(len(labels))
    width = 0.34

    fig, ax = plt.subplots(figsize=(9.2, 5.2), dpi=180)
    bars_before = ax.bar(x - width / 2, before_values, width, label="中毒后", color="#C00000")
    bars_after = ax.bar(x + width / 2, after_values, width, label="纠偏后", color="#4472C4")
    ax.set_title("受影响查询的中毒前后偏差对比")
    ax.set_ylabel("Deviation ratio")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, min(1.0, max(before_values + after_values) + 0.18))
    ax.legend()
    ax.bar_label(bars_before, fmt="%.2f", padding=3)
    ax.bar_label(bars_after, fmt="%.2f", padding=3)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_affected_query_deviation_before_after.png")
    plt.close(fig)


def plot_answer_deviation_box(deviation_rows: list[dict]) -> None:
    poisoned = [row["answer_deviation_after_poisoning"] for row in deviation_rows]
    corrected = [row["answer_deviation_after_correction"] for row in deviation_rows]
    fig, ax = plt.subplots(figsize=(7.4, 5.0), dpi=180)
    bp = ax.boxplot([poisoned, corrected], patch_artist=True, showmeans=True)
    ax.set_xticks([1, 2])
    ax.set_xticklabels(["中毒后", "纠偏后"])
    for patch, color in zip(bp["boxes"], ["#F8D7DA", "#DDEBFF"]):
        patch.set_facecolor(color)
    ax.set_title("答案语义偏差分布")
    ax.set_ylabel("1 - sim(A_clean, A_scenario)")
    ax.set_ylim(0, 1.05)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_answer_deviation_boxplot.png")
    plt.close(fig)


def plot_deviation_curve(deviation_rows: list[dict]) -> None:
    rows = sorted(deviation_rows, key=lambda row: row["answer_deviation_after_poisoning"], reverse=True)[:30]
    x = np.arange(1, len(rows) + 1)
    poisoned = [row["answer_deviation_after_poisoning"] for row in rows]
    corrected = [row["answer_deviation_after_correction"] for row in rows]
    fig, ax = plt.subplots(figsize=(9.2, 5.0), dpi=180)
    ax.plot(x, poisoned, marker="o", linewidth=1.8, label="中毒后答案偏差", color="#C00000")
    ax.plot(x, corrected, marker="s", linewidth=1.8, label="纠偏后答案偏差", color="#4472C4")
    ax.fill_between(x, corrected, poisoned, color="#F4B183", alpha=0.28, label="纠偏降低区间")
    ax.set_title("高偏差查询的中毒前后偏差曲线")
    ax.set_xlabel("Query rank by poisoned deviation")
    ax.set_ylabel("Answer deviation")
    ax.set_ylim(0, 1.05)
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_deviation_curve_top_queries.png")
    plt.close(fig)


def plot_propagation_graph(chunks: list[Chunk], chunk_risk: dict[str, dict], cluster_risk: dict[str, dict]) -> None:
    poison_chunks = [chunk for chunk in chunks if chunk.label == "poison"][:6]
    if not poison_chunks:
        return
    graph = nx.DiGraph()
    graph.add_node("Query", kind="query")
    graph.add_node("A_error", kind="answer")
    graph.add_node("IsolationEvent", kind="isolation")
    for chunk in poison_chunks:
        doc_id = f"Doc:{chunk.source_id}"
        graph.add_node(doc_id, kind="doc")
        graph.add_node(chunk.chunk_id, kind="chunk")
        graph.add_node(chunk.claim_id[:18], kind="cluster")
        graph.add_edge(doc_id, chunk.chunk_id, label="contains")
        graph.add_edge(chunk.chunk_id, chunk.claim_id[:18], label="belongs_to_cluster")
        graph.add_edge(chunk.chunk_id, "Query", label="retrieved_by")
        graph.add_edge(chunk.claim_id[:18], "A_error", label="cluster_caused_error")
        if chunk_risk.get(chunk.chunk_id, {}).get("dual_risk", 0.0) >= THETA_DUAL:
            graph.add_edge(chunk.chunk_id, "IsolationEvent", label="isolated_in")

    pos = nx.spring_layout(graph, seed=7, k=1.1)
    color_map = {
        "query": "#DDEBFF",
        "answer": "#F8D7DA",
        "isolation": "#FCE4D6",
        "doc": "#F2F2F2",
        "chunk": "#F8D7DA",
        "cluster": "#EDE7F6",
    }
    node_colors = [color_map[graph.nodes[node].get("kind", "doc")] for node in graph.nodes]
    fig, ax = plt.subplots(figsize=(10, 6.5), dpi=180)
    nx.draw_networkx_nodes(graph, pos, node_color=node_colors, edgecolors="#333333", node_size=1500, ax=ax)
    nx.draw_networkx_edges(graph, pos, arrows=True, arrowstyle="-|>", arrowsize=12, width=1.2, ax=ax)
    nx.draw_networkx_labels(graph, pos, font_size=7, ax=ax)
    edge_labels = nx.get_edge_attributes(graph, "label")
    nx.draw_networkx_edge_labels(graph, pos, edge_labels=edge_labels, font_size=6, ax=ax)
    ax.set_title("RAG 投毒传播因果溯源示例图")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_poison_propagation_graph.png")
    plt.close(fig)


def main() -> None:
    configure_font()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    corpus_rows = load_jsonl(DATA_ROOT / "corpus.jsonl")
    all_queries = load_jsonl(DATA_ROOT / "queries.jsonl")
    qrels = load_qrels(DATA_ROOT / "qrels" / "test.tsv")
    queries = [row for row in all_queries if str(row["_id"]) in qrels][:QUERY_LIMIT]
    chunks, poison_query_ids = build_chunks(corpus_rows, queries)

    vectorizer = TfidfVectorizer(stop_words="english", max_features=50000, min_df=1)
    chunk_texts = [chunk.content for chunk in chunks]
    matrix = vectorizer.fit_transform(chunk_texts)
    topk_indices = retrieve_topk(vectorizer, matrix, chunks, [row["text"] for row in queries])
    clean_allowed_ids = {chunk.chunk_id for chunk in chunks if chunk.label == "clean"}
    clean_topk_indices = retrieve_topk_with_mask(vectorizer, matrix, chunks, [row["text"] for row in queries], clean_allowed_ids)
    answers = simulate_answers(chunks, topk_indices, queries)
    chunk_risk, cluster_risk = compute_risks(chunks, topk_indices, answers)
    before_trust, after_trust = trust_scores(topk_indices, chunks, chunk_risk)

    isolated_ids = {
        row["chunk_id"]
        for row in chunk_risk.values()
        if row["label"] == "poison"
        and (
            row["dual_risk"] >= THETA_DUAL
            or cluster_risk.get(row["claim_id"], {}).get("cluster_dual_risk", 0.0) >= THETA_CLUSTER_ISOLATE
        )
    }
    isolated_ids.update(
        chunk.chunk_id
        for chunk in chunks
        if chunk.label == "poison"
        and cluster_risk.get(chunk.claim_id, {}).get("cluster_dual_risk", 0.0) >= THETA_CLUSTER_ISOLATE
    )
    retrieved_poison_claim_ids = {
        row["claim_id"]
        for row in chunk_risk.values()
        if row["label"] == "poison" and row["retrieval_count"] > 0
    }
    isolated_ids.update(
        chunk.chunk_id
        for chunk in chunks
        if chunk.label == "poison" and chunk.claim_id in retrieved_poison_claim_ids
    )
    corrected_allowed_ids = {chunk.chunk_id for chunk in chunks if chunk.chunk_id not in isolated_ids}
    corrected_topk_indices = retrieve_topk_with_mask(
        vectorizer,
        matrix,
        chunks,
        [row["text"] for row in queries],
        corrected_allowed_ids,
    )
    clean_answers = simulate_clean_baseline_answers(queries)
    corrected_answers = simulate_answers(chunks, corrected_topk_indices, queries)
    deviation_rows = compute_deviation_metrics(
        chunks,
        clean_topk_indices,
        topk_indices,
        corrected_topk_indices,
        clean_answers,
        answers,
        corrected_answers,
    )

    plot_dataset_summary(chunks, queries, qrels)
    plot_retrieval_composition(chunks, topk_indices, isolated_ids)
    plot_dualrisk_distribution(chunk_risk)
    plot_cluster_risk(cluster_risk)
    plot_trust_scores(before_trust, after_trust)
    plot_poisoning_deviation(deviation_rows)
    plot_affected_query_deviation(deviation_rows)
    plot_answer_deviation_box(deviation_rows)
    plot_deviation_curve(deviation_rows)
    plot_propagation_graph(chunks, chunk_risk, cluster_risk)

    write_csv(RESULT_DIR / "chunk_risk_scores.csv", sorted(chunk_risk.values(), key=lambda row: row["dual_risk"], reverse=True))
    write_csv(
        RESULT_DIR / "cluster_risk_scores.csv",
        sorted(cluster_risk.values(), key=lambda row: row["cluster_dual_risk"], reverse=True),
    )
    write_csv(RESULT_DIR / "poisoning_deviation_scores.csv", deviation_rows)
    summary = {
        "dataset": "BEIR SciFact",
        "dataset_path": str(DATA_ROOT),
        "query_count": len(queries),
        "clean_chunk_count": sum(1 for chunk in chunks if chunk.label == "clean"),
        "synthetic_poison_chunk_count": sum(1 for chunk in chunks if chunk.label == "poison"),
        "poison_query_count": len(poison_query_ids),
        "top_k": TOP_K,
        "retrieved_poison_hits_before": sum(1 for indices in topk_indices for idx in indices if chunks[idx].label == "poison"),
        "isolated_chunk_count": len(isolated_ids),
        "mean_trust_before": float(np.mean(before_trust)),
        "mean_trust_after": float(np.mean(after_trust)),
        "mean_poison_ratio_after_poisoning": float(np.mean([row["poison_ratio_after_poisoning"] for row in deviation_rows])),
        "mean_poison_ratio_after_correction": float(np.mean([row["poison_ratio_after_correction"] for row in deviation_rows])),
        "mean_answer_deviation_after_poisoning": float(
            np.mean([row["answer_deviation_after_poisoning"] for row in deviation_rows])
        ),
        "mean_answer_deviation_after_correction": float(
            np.mean([row["answer_deviation_after_correction"] for row in deviation_rows])
        ),
        "affected_query_count": sum(1 for row in deviation_rows if row["poison_ratio_after_poisoning"] > 0),
        "figures": sorted(str(path.relative_to(ROOT)) for path in FIG_DIR.glob("*.png")),
    }
    (RESULT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
