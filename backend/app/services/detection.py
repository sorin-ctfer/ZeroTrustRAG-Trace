"""
RAS / GIS / DualRisk 双条件投毒检测。

对应报告公式 (2-2) ~ (2-5) 的 MVP 规则化实现。
"""

from __future__ import annotations

from typing import Protocol

from ..models.schema import Evidence, DetectionResult
from ..utils.text_utils import (
    TfidfRetriever,
    query_term_coverage,
    count_word_matches,
    extract_target_phrases,
    AUTHORITY_WORDS,
    EXCLUSIVE_WORDS,
    INSTRUCTION_WORDS,
)
from ..utils.score_utils import sigmoid, compute_dual_risk, risk_level_from_dual_risk


class DetectionProtocol(Protocol):
    """RAS/GIS/DualRisk 检测实现的可替换接口。"""

    def detect(
        self,
        query: str,
        top_k_evidences: list[Evidence],
        all_evidences: list[Evidence],
        target_wrong_answer: str,
    ) -> list[DetectionResult]:
        """批量检测候选证据。"""
        ...


# ---------------------------------------------------------------------------
# RAS — 检索吸附性分数
# ---------------------------------------------------------------------------

def compute_ras(
    query: str,
    chunk: Evidence,
    all_evidences: list[Evidence],
    hit_count: int = 1,
    total_queries: int = 1,
    rank_variance: float = 0.0,
    total_chunks: int = 1,
) -> tuple[float, list[str]]:
    """
    计算 RAS (Retrieval Attraction Score)。

    MVP 简化特征 (对应报告公式 2-2 的 6 特征缩减):
      1. query_similarity   — TF-IDF 余弦相似度
      2. query_term_coverage — 查询词覆盖率
      3. topk_hit           — 是否在 Top-K 中 (1/0)
      4. rank_gain          — 相对排名提升 (1/rank - 1/N)
      5. rewrite_hit_freq   — 在改写查询中的命中频率
      6. retrieval_instability — 排名波动 (归一化 rank_variance)

    MVP 权重: w1=2.0, w2=1.5, w3=1.0, w4=1.0, w5=1.5, w6=1.0, b=-3.0
    """
    reasons: list[str] = []

    # 1. query_similarity
    retriever = TfidfRetriever()
    doc_ids = [ev.evidence_id for ev in all_evidences]
    doc_texts = [ev.content for ev in all_evidences]
    retriever.index(doc_ids, doc_texts)
    sim = retriever.similarity(query, chunk.content)
    if sim > 0.3:
        reasons.append(f"query_similarity={sim:.3f} (高)")

    # 2. query_term_coverage
    coverage = query_term_coverage(query, chunk.content)
    if coverage > 0.5:
        reasons.append(f"query_term_coverage={coverage:.3f} (高)")

    # 3. topk_hit
    topk_hit = 1.0 if chunk.retrieval_rank is not None else 0.0

    # 4. rank_gain
    rank = chunk.retrieval_rank or len(all_evidences)
    n = max(1, total_chunks)
    rank_gain = max(0.0, (1.0 / rank) - (1.0 / n))
    if rank_gain > 0.1:
        reasons.append(f"rank_gain={rank_gain:.3f} (排名靠前)")

    # 5. rewrite_hit_frequency
    hit_freq = hit_count / max(1, total_queries)
    if hit_freq > 0.7:
        reasons.append(f"rewrite_hit_freq={hit_freq:.3f} (改写命中高)")

    # 6. retrieval_instability
    instability = min(1.0, rank_variance / 5.0)  # 简单归一化

    # 加权 + sigmoid
    w1, w2, w3, w4, w5, w6, b = 2.0, 1.5, 1.0, 1.0, 1.5, 1.0, -3.0
    logit = (
        w1 * sim + w2 * coverage + w3 * topk_hit
        + w4 * rank_gain + w5 * hit_freq + w6 * instability + b
    )
    ras = sigmoid(logit)
    return ras, reasons


# ---------------------------------------------------------------------------
# GIS — 答案诱导性分数
# ---------------------------------------------------------------------------

def compute_gis(
    query: str,
    chunk: Evidence,
    target_wrong_answer: str,
    original_answer: str = "",
) -> tuple[float, list[str]]:
    """
    计算 GIS (Generation Inducement Score)。

    MVP 简化特征 (对应报告公式 2-4 的 6 特征缩减):
      1. target_wrong_answer_alignment — 与攻击目标答案的 TF-IDF 相似度
      2. fake_authority_expression     — 伪权威表达词计数
      3. exclusive_conclusion          — 排他性结论词计数
      4. instruction_inducement        — 指令诱导词计数
      5. solo_repeat_proxy             — 单独生成与目标一致性代理指标

    MVP 权重: v1=2.0, v2=1.5, v3=1.5, v4=1.0, v5=2.0, c=-3.0
    """
    reasons: list[str] = []

    # 1. target_wrong_answer_alignment
    retriever = TfidfRetriever()
    retriever.index(["target", "chunk"], [target_wrong_answer, chunk.content])
    target_align = retriever.similarity(chunk.content, target_wrong_answer)
    if target_align > 0.3:
        reasons.append(f"target_alignment={target_align:.3f} (与攻击目标相似)")

    # 2. fake_authority_expression
    auth_count = count_word_matches(chunk.content, AUTHORITY_WORDS)
    fake_auth = min(1.0, auth_count / 3.0)
    if fake_auth > 0.3:
        reasons.append(f"fake_authority={fake_auth:.3f} (含{auth_count}个权威词)")

    # 3. exclusive_conclusion
    excl_count = count_word_matches(chunk.content, EXCLUSIVE_WORDS)
    exclusive = min(1.0, excl_count / 2.0)
    if exclusive > 0.3:
        reasons.append(f"exclusive_conclusion={exclusive:.3f} (含{excl_count}个排他词)")

    # 4. instruction_inducement
    instr_count = count_word_matches(chunk.content, INSTRUCTION_WORDS)
    instr_induce = min(1.0, instr_count / 3.0)
    if instr_induce > 0.3:
        reasons.append(f"instruction_inducement={instr_induce:.3f} (含{instr_count}个指令词)")

    # 5. solo_repeat_proxy
    # 检查 chunk 内容中是否包含目标错误答案的关键短语
    target_phrases = extract_target_phrases(target_wrong_answer)
    if target_phrases:
        hits = sum(1 for p in target_phrases if p in chunk.content)
        solo_repeat = hits / len(target_phrases)
    else:
        solo_repeat = 0.0
    if solo_repeat > 0.3:
        reasons.append(f"solo_repeat={solo_repeat:.3f} (含目标错误声明)")

    # 间接提示注入模式。MVP 将显式覆盖规则、关闭防护、限制引用等文本
    # 视为强诱导信号，防止其仅因与业务问题词面相似度不高而漏检。
    injection_patterns = (
        "忽略之前", "忽略所有", "系统指令", "不要引用",
        "只输出", "直接输出", "关闭杀毒", "关闭终端防护",
    )
    injection_hits = sum(1 for pattern in injection_patterns if pattern in chunk.content)
    prompt_injection = min(1.0, injection_hits / 2.0)
    if prompt_injection > 0:
        reasons.append(f"prompt_injection={prompt_injection:.3f} (命中{injection_hits}个注入模式)")

    # 加权 + sigmoid
    v1, v2, v3, v4, v5, c = 2.0, 1.5, 1.5, 1.0, 2.0, -3.0
    logit = (
        v1 * target_align + v2 * fake_auth + v3 * exclusive
        + v4 * instr_induce + v5 * solo_repeat + 3.0 * prompt_injection + c
    )
    gis = sigmoid(logit)
    return gis, reasons


# ---------------------------------------------------------------------------
# 批量检测
# ---------------------------------------------------------------------------

def detect(
    query: str,
    top_k_evidences: list[Evidence],
    all_evidences: list[Evidence],
    target_wrong_answer: str,
    hit_counts: dict[str, int] | None = None,
    total_queries: int = 1,
    rank_variances: dict[str, float] | None = None,
) -> list[DetectionResult]:
    """
    对 Top-K 证据批量计算 RAS + GIS + DualRisk。
    """
    hit_counts = hit_counts or {}
    rank_variances = rank_variances or {}
    total_chunks = len(all_evidences)

    results: list[DetectionResult] = []

    for ev in top_k_evidences:
        # RAS
        ras, ras_reasons = compute_ras(
            query=query,
            chunk=ev,
            all_evidences=all_evidences,
            hit_count=hit_counts.get(ev.evidence_id, 1),
            total_queries=total_queries,
            rank_variance=rank_variances.get(ev.evidence_id, 0.0),
            total_chunks=total_chunks,
        )

        # GIS
        gis, gis_reasons = compute_gis(
            query=query,
            chunk=ev,
            target_wrong_answer=target_wrong_answer,
        )

        # DualRisk (公式 2-5)
        dual = compute_dual_risk(ras, gis)
        risk_lvl = risk_level_from_dual_risk(dual)

        all_reasons = ras_reasons + gis_reasons
        if dual > 0.5:
            all_reasons.append(f"DualRisk={dual:.3f} (双条件风险)")
        if dual > 0.8:
            all_reasons.append("高风险：RAS+GIS 双条件同时满足")

        results.append(
            DetectionResult(
                evidence_id=ev.evidence_id,
                ras=round(ras, 4),
                gis=round(gis, 4),
                dual_risk=round(dual, 4),
                risk_level=risk_lvl,
                reasons=all_reasons,
            )
        )

    return results
