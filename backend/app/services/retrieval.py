"""
模拟 RAG 检索：TF-IDF + Top-K + Query Rewrites。

MVP 使用字符 n-gram TF-IDF，记录 rank、score、hit frequency、rank variance。
"""

from __future__ import annotations

import statistics
from typing import Optional, Protocol

from ..models.schema import Evidence
from ..utils.text_utils import TfidfRetriever


class RetrievalProtocol(Protocol):
    """检索实现的可替换接口。"""

    def search(
        self,
        query: str,
        evidences: list[Evidence],
        top_k: int = 5,
        rewrites: Optional[list[str]] = None,
    ) -> "RetrievalResult":
        """返回 Top-K 及跨查询改写统计。"""
        ...


class RetrievalResult:
    """检索结果，附带统计信息。"""

    def __init__(self) -> None:
        self.top_k_evidences: list[Evidence] = []
        # 每条 evidence 在不同 rewrite 下的排名
        self.rank_history: dict[str, list[int]] = {}
        # 每条 evidence 在不同 rewrite 下的命中次数
        self.hit_counts: dict[str, int] = {}

    @property
    def hit_frequency(self) -> dict[str, float]:
        """每条 evidence 的命中频率 = hit_count / 查询总数。"""
        n_queries = 1 + max(
            (len(ranks) for ranks in self.rank_history.values()), default=1
        )
        return {eid: cnt / max(1, n_queries) for eid, cnt in self.hit_counts.items()}

    @property
    def rank_variance(self) -> dict[str, float]:
        """每条 evidence 在不同查询下的排名方差。"""
        result: dict[str, float] = {}
        for eid, ranks in self.rank_history.items():
            if len(ranks) >= 2:
                result[eid] = float(statistics.variance(ranks))
            else:
                result[eid] = 0.0
        return result


def search(
    query: str,
    evidences: list[Evidence],
    top_k: int = 5,
    rewrites: Optional[list[str]] = None,
) -> RetrievalResult:
    """
    执行检索：原始 query + 所有 rewrites，汇总 Top-K 和统计信息。
    """
    result = RetrievalResult()

    if not evidences:
        return result

    doc_ids = [ev.evidence_id for ev in evidences]
    doc_texts = [ev.content for ev in evidences]

    retriever = TfidfRetriever()
    retriever.index(doc_ids, doc_texts)

    # 所有查询（原始 + 改写）
    all_queries = [query] + (rewrites or [])

    # 收集所有查询的检索结果
    all_hits: dict[str, list[tuple[int, float]]] = {}  # eid -> [(rank, score)]

    for q in all_queries:
        hits = retriever.search(q, top_k=top_k)
        for rank_0, (eid, score) in enumerate(hits):
            if eid not in all_hits:
                all_hits[eid] = []
            all_hits[eid].append((rank_0 + 1, score))

    # 选择最终 Top-K（按平均得分排序）
    avg_scores: dict[str, float] = {}
    for eid, hits_list in all_hits.items():
        avg_scores[eid] = sum(s for _, s in hits_list) / len(hits_list)

    sorted_eids = sorted(avg_scores.keys(), key=lambda x: avg_scores[x], reverse=True)[
        :top_k
    ]

    # 构建结果
    eid_to_ev = {ev.evidence_id: ev for ev in evidences}
    for final_rank, eid in enumerate(sorted_eids, 1):
        ev = eid_to_ev[eid]
        ev.retrieval_rank = final_rank
        ev.retrieval_score = avg_scores[eid]
        result.top_k_evidences.append(ev.model_copy())

    # 统计 rank_history 和 hit_counts
    for eid in all_hits:
        result.rank_history[eid] = [r for r, _ in all_hits[eid]]
        result.hit_counts[eid] = len(all_hits[eid])

    return result
