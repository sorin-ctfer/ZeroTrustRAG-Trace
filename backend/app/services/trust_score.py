"""
声明—证据矩阵 + 启发式 NLI 判断 + TrustScore 可信评分。

对应报告公式 (2-12), (2-13)。
MVP 使用规则判断 supports / contradicts / neutral。
"""

from __future__ import annotations

from typing import Protocol

from ..models.schema import (
    Evidence,
    ClaimEvidenceRelation,
    TrustScoreDetail,
    DetectionResult,
    CounterfactualResult,
)
from ..utils.text_utils import (
    split_claims,
    query_term_coverage,
    has_negation,
    NEGATION_WORDS,
    TfidfRetriever,
    extract_key_terms,
)
from ..utils.score_utils import compute_trust_score, trust_level_from_score, clip


class NLIJudgeProtocol(Protocol):
    """NLI 判断器的可替换接口。"""

    def judge(self, premise: str, hypothesis: str) -> tuple[str, float, float, float]:
        """返回关系及 support/contradict/neutral 分数。"""
        ...


class TrustScoreProtocol(Protocol):
    """可信评分实现的可替换接口。"""

    def compute(
        self,
        matrix: list[ClaimEvidenceRelation],
        evidences: list[Evidence],
    ) -> TrustScoreDetail:
        """计算可信评分明细。"""
        ...


# ---------------------------------------------------------------------------
# 启发式 NLI 判断
# ---------------------------------------------------------------------------

def nli_judge(premise: str, hypothesis: str) -> tuple[str, float, float, float]:
    """
    启发式 NLI 判断：给定证据(premise)和声明(hypothesis)，判断关系。

    规则:
    1. 如果 premise 包含 hypothesis 的关键实体 AND 无否定 → supports
    2. 如果 premise 包含 hypothesis 的关键实体 AND 有否定/矛盾 → contradicts
    3. 否则 → neutral

    返回: (relation, support_score, contradict_score, neutral_score)
    """
    hyp_terms = extract_key_terms(hypothesis)
    if not hyp_terms:
        return "neutral", 0.0, 0.0, 1.0

    # 计算 premise 对 hypothesis 关键术语的覆盖率
    coverage = query_term_coverage(hypothesis, premise)

    # 检查否定/矛盾
    premise_has_neg = has_negation(premise)
    hypothesis_has_neg = has_negation(hypothesis)

    # 矛盾检测：关键实体匹配，但否定极性不同
    is_contradiction = False
    if coverage > 0.2 and (premise_has_neg != hypothesis_has_neg):
        is_contradiction = True

    # 更细粒度的矛盾检测：寻找直接冲突的关键词对
    conflict_pairs = [
        ("必须", "无需"), ("禁止", "允许"), ("不允许", "允许"),
        ("仍", "已"), ("未", "已"), ("仍在", "已彻底"),
        ("必须禁用", "可以使用"), ("不允许", "可以"),
    ]
    for pos_word, neg_word in conflict_pairs:
        if (pos_word in hypothesis and neg_word in premise) or \
           (neg_word in hypothesis and pos_word in premise):
            is_contradiction = True
            break

    if coverage > 0.15 and not is_contradiction:
        # 支持
        support = clip(coverage * 1.5, 0.0, 1.0)
        contradict = 0.0
        neutral = 1.0 - support
        return "supports", round(support, 4), round(contradict, 4), round(neutral, 4)

    elif is_contradiction:
        # 矛盾
        support = 0.0
        contradict = clip(coverage * 1.5, 0.0, 1.0)
        neutral = 1.0 - contradict
        return "contradicts", round(support, 4), round(contradict, 4), round(neutral, 4)

    else:
        # 中立
        return "neutral", 0.0, 0.0, 1.0


# ---------------------------------------------------------------------------
# 声明—证据矩阵
# ---------------------------------------------------------------------------

def build_claim_evidence_matrix(
    claims: list[str],
    evidences: list[Evidence],
) -> list[ClaimEvidenceRelation]:
    """
    构建声明—证据矩阵。

    对每对 (claim, evidence) 调用 NLI judge 判断关系。
    对应报告公式 (2-12) 的 MVP 实现。
    """
    relations: list[ClaimEvidenceRelation] = []

    for claim_idx, claim_text in enumerate(claims):
        claim_id = f"C-AUTO-{claim_idx + 1:03d}"
        for ev in evidences:
            relation, sup, con, neu = nli_judge(ev.content, claim_text)
            relations.append(ClaimEvidenceRelation(
                claim_id=claim_id,
                claim_text=claim_text,
                evidence_id=ev.evidence_id,
                relation=relation,
                support_score=sup,
                contradict_score=con,
                neutral_score=neu,
            ))

    return relations


# ---------------------------------------------------------------------------
# TrustScore 计算
# ---------------------------------------------------------------------------

def compute_full_trust_score(
    matrix: list[ClaimEvidenceRelation],
    evidences: list[Evidence],
    detection_results: list[DetectionResult] | None = None,
    causal_results: list[CounterfactualResult] | None = None,
    graph_anomaly: float = 0.0,
) -> TrustScoreDetail:
    """
    计算 TrustScore (报告公式 2-13 简化版)。

    正向项:
      SQ (source_quality)       — 来源质量
      EC (evidence_coverage)    — 声明支持覆盖率
      SI (source_independence)  — 来源独立性
      FR (freshness)            — 时效性
      RS (retrieval_stability)  — 检索稳定性

    风险项:
      PR (poison_risk)          — 投毒风险
      GR (graph_risk)           — 图谱异常
      CR (causal_risk)          — 因果风险
      CT (contradiction_rate)   — 矛盾率
    """
    n_claims = len(set(r.claim_id for r in matrix)) if matrix else 1

    # --- EC: 声明支持覆盖率 ---
    claims_with_support = set()
    claims_with_contradict = set()
    for r in matrix:
        if r.relation == "supports":
            claims_with_support.add(r.claim_id)
        if r.relation == "contradicts":
            claims_with_contradict.add(r.claim_id)

    ec = len(claims_with_support) / max(1, n_claims)

    # --- CT: 矛盾率 ---
    ct = len(claims_with_contradict) / max(1, n_claims)

    # --- SQ: 来源质量 (clean 证据比例) ---
    clean_count = sum(1 for ev in evidences if not ev.is_poisoned)
    sq = clean_count / max(1, len(evidences))

    # --- SI: 来源独立性 (不同 document_id 的比例) ---
    unique_docs = len(set(ev.document_id for ev in evidences))
    si = min(1.0, unique_docs / max(1, len(evidences)))

    # --- FR: 时效性 (MVP: 简化为 0.7，因为数据集中时间差异不大) ---
    fr = 0.7

    # --- RS: 检索稳定性 (MVP: 简化为平均 rank 的倒数) ---
    ranks = [ev.retrieval_rank for ev in evidences if ev.retrieval_rank is not None]
    if ranks:
        avg_rank = sum(ranks) / len(ranks)
        rs = 1.0 / max(1, avg_rank)
    else:
        rs = 0.5

    # --- PR: 投毒风险 (DualRisk 均值) ---
    if detection_results:
        pr = sum(d.dual_risk for d in detection_results) / len(detection_results)
    else:
        pr = sum(1 for ev in evidences if ev.is_poisoned) / max(1, len(evidences))

    # --- GR: 图谱异常 ---
    gr = clip(graph_anomaly, 0.0, 1.0)

    # --- CR: 因果风险 (CausalScore 均值) ---
    if causal_results:
        cr = sum(c.causal_score for c in causal_results) / len(causal_results)
    else:
        cr = 0.0

    # --- 综合 TrustScore (公式 2-13) ---
    ts = compute_trust_score(
        source_quality=sq,
        evidence_coverage=ec,
        source_independence=si,
        freshness=fr,
        retrieval_stability=rs,
        poison_risk=pr,
        graph_risk=gr,
        causal_risk=cr,
        contradiction_rate=ct,
    )

    return TrustScoreDetail(
        trust_score=round(ts, 2),
        trust_level=trust_level_from_score(ts),
        source_quality=round(sq, 4),
        evidence_coverage=round(ec, 4),
        source_independence=round(si, 4),
        freshness=round(fr, 4),
        retrieval_stability=round(rs, 4),
        poison_risk=round(pr, 4),
        graph_risk=round(gr, 4),
        causal_risk=round(cr, 4),
        contradiction_rate=round(ct, 4),
    )
