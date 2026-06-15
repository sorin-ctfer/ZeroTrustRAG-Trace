"""
高风险 Chunk 隔离 + 风险感知重检索 + 可信重生成。

对应报告 2.6 节，公式 (2-14), (2-15)。
"""

from __future__ import annotations

from typing import Protocol

from ..models.schema import (
    Evidence,
    DetectionResult,
    CounterfactualResult,
)
from ..utils.text_utils import TfidfRetriever, split_claims
from ..utils.score_utils import rerank_score, clip


class RegenerationProtocol(Protocol):
    """风险隔离、重检索与可信重生成的可替换接口。"""

    def regenerate(self, query: str, trusted_evidences: list[Evidence]) -> str:
        """基于可信证据生成带引用答案。"""
        ...


# ---------------------------------------------------------------------------
# 高风险 Chunk 隔离
# ---------------------------------------------------------------------------

def isolate_high_risk(
    evidences: list[Evidence],
    detection_results: list[DetectionResult],
    counterfactual_results: list[CounterfactualResult] | None = None,
    dual_risk_threshold: float = 0.6,
    causal_score_threshold: float = 0.15,
) -> list[str]:
    """
    隔离高风险 Chunk。

    隔离条件:
    1. 高风险证据: DualRisk > 0.8 且 CausalScore > 0.25
    2. 站群传播证据: DualRisk > threshold、CausalScore > threshold，
       且属于重复模板传播簇

    返回被隔离的 evidence_id 列表。
    """
    # 构建 causal_score 查找表
    causal_map: dict[str, float] = {}
    if counterfactual_results:
        for cf in counterfactual_results:
            causal_map[cf.suspicious_evidence_id] = cf.causal_score

    evidence_map = {ev.evidence_id: ev for ev in evidences}
    isolated: list[str] = []

    for det in detection_results:
        causal = causal_map.get(det.evidence_id, 0.0)
        ev = evidence_map.get(det.evidence_id)
        in_template_cluster = bool(ev and ev.metadata.get("template_cluster_id"))
        high_causal_risk = det.dual_risk > 0.8 and causal > 0.25
        clustered_causal_risk = (
            det.dual_risk > dual_risk_threshold
            and causal > causal_score_threshold
            and in_template_cluster
        )
        if high_causal_risk or clustered_causal_risk:
            isolated.append(det.evidence_id)

    return isolated


# ---------------------------------------------------------------------------
# 风险感知重检索
# ---------------------------------------------------------------------------

def risk_aware_search(
    query: str,
    all_evidences: list[Evidence],
    isolated_ids: list[str],
    detection_results: list[DetectionResult],
    top_k: int = 5,
) -> list[Evidence]:
    """
    隔离后重新检索，使用风险感知重排序。

    公式 (2-15): ReRank(d) = η₁·Rel + η₂·Support + η₃·Diversity - η₄·Risk
    """
    isolated_set = set(isolated_ids)

    # 排除被隔离的证据
    candidate_evs = [ev for ev in all_evidences if ev.evidence_id not in isolated_set]

    if not candidate_evs:
        return []

    # 构建 risk 查找表
    risk_map: dict[str, float] = {}
    for det in detection_results:
        risk_map[det.evidence_id] = det.dual_risk

    # TF-IDF 相关性
    retriever = TfidfRetriever()
    doc_ids = [ev.evidence_id for ev in candidate_evs]
    doc_texts = [ev.content for ev in candidate_evs]
    retriever.index(doc_ids, doc_texts)

    hits = retriever.search(query, top_k=min(top_k * 3, len(candidate_evs)))

    # 计算重排序分数
    scored: list[tuple[float, Evidence]] = []
    seen_docs: set[str] = set()

    for eid, rel_score in hits:
        ev = next((e for e in candidate_evs if e.evidence_id == eid), None)
        if ev is None:
            continue

        # Rel: TF-IDF 相关性
        rel = clip(rel_score, 0.0, 1.0)

        # Support: 简化为检索分数
        support = rel

        # Diversity: 不同文档来源加分
        diversity = 1.0 if ev.document_id not in seen_docs else 0.5
        seen_docs.add(ev.document_id)

        # Risk: DualRisk (未检测的设为 0)
        risk = risk_map.get(eid, 0.0)

        # 重排序 (公式 2-15)
        rerank = rerank_score(rel, support, diversity, risk)
        scored.append((rerank, ev))

    # 按重排序分数降序
    scored.sort(key=lambda x: x[0], reverse=True)
    return [ev for _, ev in scored[:top_k]]


# ---------------------------------------------------------------------------
# 可信重生成
# ---------------------------------------------------------------------------

def regenerate_trusted_answer(
    query: str,
    trusted_evidences: list[Evidence],
) -> str:
    """
    基于可信证据的模板化重生成。

    策略:
    1. 从可信证据中提取与 query 相关的句子
    2. 每个事实声明后附 evidence_id
    3. 证据不足时输出"现有证据不足以确认"
    """
    if not trusted_evidences:
        return f'关于“{query}”，现有证据不足以确认。'

    retriever = TfidfRetriever()
    doc_ids = [ev.evidence_id for ev in trusted_evidences]
    doc_texts = [ev.content for ev in trusted_evidences]
    retriever.index(doc_ids, doc_texts)

    # 收集相关句子
    relevant: list[tuple[float, str, str]] = []

    for ev in trusted_evidences:
        sentences = split_claims(ev.content)
        for sent in sentences:
            sim = retriever.similarity(query, sent)
            if sim > 0.03:
                relevant.append((sim, sent.strip(), ev.evidence_id))

    relevant.sort(key=lambda x: x[0], reverse=True)
    top = relevant[:6]

    if not top:
        return f'关于“{query}”，现有证据不足以确认。'

    # 按证据分组组织答案
    parts: list[str] = []
    for _, sent, eid in top:
        parts.append(f"{sent}[{eid}]")

    answer = "根据可信证据：" + "；".join(parts)
    return answer
