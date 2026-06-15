"""
评分工具函数：sigmoid、归一化、DualRisk、CausalScore 等。

所有核心公式在此集中定义，与作品报告公式编号对应。
"""

from __future__ import annotations

import math


# ---------------------------------------------------------------------------
# 基础函数
# ---------------------------------------------------------------------------

def sigmoid(x: float) -> float:
    """Sigmoid 激活函数。"""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    else:
        ex = math.exp(x)
        return ex / (1.0 + ex)


def clip(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """将值截断到 [lo, hi] 区间。"""
    return max(lo, min(hi, value))


def normalize(value: float, lo: float, hi: float) -> float:
    """线性归一化到 [0, 1]。"""
    if hi <= lo:
        return 0.0
    return clip((value - lo) / (hi - lo))


# ---------------------------------------------------------------------------
# DualRisk — 双条件候选投毒分
# ---------------------------------------------------------------------------

def compute_dual_risk(ras: float, gis: float, lam: float = 0.7) -> float:
    """
    DualRisk = λ * sqrt(RAS * GIS) + (1 - λ) * (RAS + GIS) / 2

    对应报告公式 (2-5)。
    λ=0.7 使几何项占主导，强调 RAS 与 GIS 同时高值。
    """
    geo = math.sqrt(max(0.0, ras * gis))
    linear = (ras + gis) / 2.0
    return lam * geo + (1.0 - lam) * linear


def risk_level_from_dual_risk(dual_risk: float) -> str:
    """
    DualRisk → risk_level 映射。

    > 0.8 → high
    > 0.5 → medium
    else  → low
    """
    if dual_risk > 0.8:
        return "high"
    elif dual_risk > 0.5:
        return "medium"
    else:
        return "low"


# ---------------------------------------------------------------------------
# CausalScore — 因果分
# ---------------------------------------------------------------------------

def compute_causal_score(
    pO: float,
    pR: float,
    pS: float,
    pT: float,
    alpha: float = 0.4,
    beta: float = 0.3,
    gamma: float = 0.3,
) -> tuple[float, float, float, float]:
    """
    计算因果分及三个效应。

    对应报告公式 (2-6) ~ (2-9):
      E_remove = max(0, pO - pR)
      E_solo   = pS
      E_replace = max(0, pO - pT)
      CausalScore = α·E_remove + β·E_solo + γ·E_replace

    返回: (E_remove, E_solo, E_replace, causal_score)
    """
    e_remove = max(0.0, pO - pR)
    e_solo = pS
    e_replace = max(0.0, pO - pT)
    causal = alpha * e_remove + beta * e_solo + gamma * e_replace
    return e_remove, e_solo, e_replace, causal


# ---------------------------------------------------------------------------
# TrustScore — 可信评分
# ---------------------------------------------------------------------------

def compute_trust_score(
    source_quality: float = 0.0,
    evidence_coverage: float = 0.0,
    source_independence: float = 0.0,
    freshness: float = 0.0,
    retrieval_stability: float = 0.0,
    poison_risk: float = 0.0,
    graph_risk: float = 0.0,
    causal_risk: float = 0.0,
    contradiction_rate: float = 0.0,
) -> float:
    """
    TrustScore 可信评分。

    对应报告公式 (2-13):
      TrustScore = 100 * Clip((
          0.18*SQ + 0.24*EC + 0.12*SI + 0.08*FR + 0.08*RS
        - 0.14*PR - 0.07*GR - 0.06*CR - 0.03*CT
      ) / 0.70,
        0, 1
      )

    正向权重总和为 0.70，因此除以 0.70 映射到完整的 [0, 100] 区间。
    所有子项输入应在 [0, 1] 范围内。
    """
    raw = (
        0.18 * source_quality
        + 0.24 * evidence_coverage
        + 0.12 * source_independence
        + 0.08 * freshness
        + 0.08 * retrieval_stability
        - 0.14 * poison_risk
        - 0.07 * graph_risk
        - 0.06 * causal_risk
        - 0.03 * contradiction_rate
    )
    return 100.0 * clip(raw / 0.70, 0.0, 1.0)


def trust_level_from_score(score: float) -> str:
    """
    TrustScore → 可信等级映射。

    80-100 → high
    60-79  → medium
    40-59  → low
    0-39   → high_risk
    """
    if score >= 80:
        return "high"
    elif score >= 60:
        return "medium"
    elif score >= 40:
        return "low"
    else:
        return "high_risk"


# ---------------------------------------------------------------------------
# 降权 & 重排序
# ---------------------------------------------------------------------------

def downweight_score(
    original_score: float,
    risk: float,
    mu: float = 0.8,
) -> float:
    """
    降权公式 (报告 2-14):
      score'(q,d) = score(q,d) * (1 - μ * Risk(d))
    """
    return original_score * (1.0 - mu * risk)


def rerank_score(
    relevance: float,
    support: float,
    diversity: float,
    risk: float,
    eta1: float = 0.4,
    eta2: float = 0.3,
    eta3: float = 0.2,
    eta4: float = 0.3,
) -> float:
    """
    风险感知重排序公式 (报告 2-15):
      ReRank(d) = η₁·Rel + η₂·Support + η₃·Diversity - η₄·Risk
    """
    return eta1 * relevance + eta2 * support + eta3 * diversity - eta4 * risk
