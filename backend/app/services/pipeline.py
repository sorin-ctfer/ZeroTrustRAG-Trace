"""
完整检测流水线编排。

按顺序执行 14 步闭环：
  用户查询 → 检索 → RAS/GIS/DualRisk → 反事实验证 → 因果分
  → 传播图谱 → 声明-证据矩阵 → TrustScore → 隔离
  → 重检索 → 可信重生成 → 风险报告
"""

from __future__ import annotations

from typing import Protocol

from ..models.schema import (
    DemoCase,
    PipelineResult,
    RiskReport,
)
from ..services.case_loader import load_case
from ..services.ingest import process_evidences
from ..services.retrieval import search
from ..services.detection import detect
from ..services.counterfactual import run_all_counterfactuals
from ..services.graph_trace import build_graph
from ..services.trust_score import (
    build_claim_evidence_matrix,
    compute_full_trust_score,
)
from ..services.regeneration import (
    isolate_high_risk,
    risk_aware_search,
    regenerate_trusted_answer,
)
from ..utils.text_utils import split_claims
from ..utils.score_utils import clip


class PipelineProtocol(Protocol):
    """完整检测流水线的可替换编排接口。"""

    def run(self, case_id: str) -> PipelineResult | None:
        """按固定顺序执行检测、溯源、隔离与重生成。"""
        ...


def run_pipeline(case_id: str) -> PipelineResult | None:
    """
    执行完整检测闭环。

    返回 PipelineResult 或 None（案例不存在时）。
    """
    # ---- 加载案例 ----
    loaded_case = load_case(case_id)
    if loaded_case is None:
        return None
    case = loaded_case.model_copy(deep=True)

    result = PipelineResult(case_info=case)

    # ---- Step 1: 证据预处理 ----
    all_evidences = process_evidences(case.evidences)

    # ---- Step 2: 模拟检索 Top-K ----
    retrieval_result = search(
        query=case.question,
        evidences=all_evidences,
        top_k=min(5, len(all_evidences)),
        rewrites=case.query_rewrites,
    )
    top_k_evidences = retrieval_result.top_k_evidences
    result.original_topk_evidence = top_k_evidences

    # 计算总查询数（原始 + 改写）
    total_queries = 1 + len(case.query_rewrites)

    # ---- Step 3: 模拟原始答案 ----
    from ..services.counterfactual import _template_generate
    original_answer = _template_generate(case.question, top_k_evidences)
    case.original_answer = original_answer

    # ---- Step 4: RAS + GIS + DualRisk 检测 ----
    detection_results = detect(
        query=case.question,
        top_k_evidences=top_k_evidences,
        all_evidences=all_evidences,
        target_wrong_answer=case.target_wrong_answer,
        hit_counts=retrieval_result.hit_counts,
        total_queries=total_queries,
        rank_variances=retrieval_result.rank_variance,
    )
    result.detection_results = detection_results

    # 标记可疑证据
    suspicious_ids = [d.evidence_id for d in detection_results if d.dual_risk > 0.5]
    result.suspicious_evidences = suspicious_ids

    # ---- Step 5: 四路反事实验证 ----
    suspicious_evs = [ev for ev in top_k_evidences if ev.evidence_id in suspicious_ids]
    if not suspicious_evs:
        # 如果没有可疑证据（阈值太高），降低阈值取 top-1
        suspicious_evs = top_k_evidences[:1] if top_k_evidences else []

    cf_results = run_all_counterfactuals(
        query=case.question,
        suspicious_evidences=suspicious_evs,
        top_k_evidences=top_k_evidences,
        all_evidences=all_evidences,
        target_wrong_answer=case.target_wrong_answer,
        trusted_evidence_ids=case.trusted_evidence_ids,
    )
    result.counterfactual_results = cf_results

    # ---- Step 6: 构建投毒传播图谱 ----
    # 先做声明拆分 + NLI 矩阵（图谱需要 claim 节点）
    claims = split_claims(original_answer)
    matrix = build_claim_evidence_matrix(claims, top_k_evidences)

    graph_trace = build_graph(
        evidences=all_evidences,
        query=case.question,
        claims=matrix,
        counterfactual_results=cf_results,
        original_answer=original_answer,
    )
    result.graph_trace = graph_trace
    result.claim_evidence_matrix = matrix

    # ---- Step 7: TrustScore (before) ----
    # 图谱异常：有 copied_from 边的比例
    copied_edges = sum(1 for e in graph_trace.edges if e.edge_type == "copied_from")
    graph_anomaly = clip(copied_edges / max(1, len(graph_trace.edges)), 0.0, 1.0)

    trust_before = compute_full_trust_score(
        matrix=matrix,
        evidences=top_k_evidences,
        detection_results=detection_results,
        causal_results=cf_results,
        graph_anomaly=graph_anomaly,
    )
    result.trust_score_before = trust_before

    # ---- Step 8: 隔离高风险 Chunk ----
    isolated_ids = isolate_high_risk(
        evidences=top_k_evidences,
        detection_results=detection_results,
        counterfactual_results=cf_results,
    )
    result.isolated_evidences = isolated_ids

    # ---- Step 9: 风险感知重检索 ----
    trusted_top_k = risk_aware_search(
        query=case.question,
        all_evidences=all_evidences,
        isolated_ids=isolated_ids,
        detection_results=detection_results,
        top_k=min(5, len(all_evidences) - len(isolated_ids)),
    )
    result.trusted_topk_evidence = trusted_top_k

    # ---- Step 10: 可信重生成 ----
    regenerated = regenerate_trusted_answer(
        query=case.question,
        trusted_evidences=trusted_top_k,
    )
    result.regenerated_answer = regenerated

    # ---- Step 11: TrustScore (after) ----
    # 用重生成答案的声明重新计算
    regen_claims = split_claims(regenerated)
    regen_matrix = build_claim_evidence_matrix(regen_claims, trusted_top_k)

    # 重生成后无检测结果，风险项降低
    trust_after = compute_full_trust_score(
        matrix=regen_matrix,
        evidences=trusted_top_k,
        detection_results=None,  # 重生成后无投毒检测
        causal_results=None,
        graph_anomaly=0.0,  # 隔离后图谱异常降低
    )
    result.trust_score_after = trust_after

    # ---- Step 12: 风险报告 ----
    # 受影响声明
    affected_claims = [
        r.claim_text for r in matrix if r.relation == "contradicts"
    ]

    # 因果发现
    causal_findings = []
    for cf in cf_results:
        if cf.causal_score > 0.3:
            causal_findings.append(
                f"证据 {cf.suspicious_evidence_id}: "
                f"E_remove={cf.E_remove:.2f}, E_solo={cf.E_solo:.2f}, "
                f"E_replace={cf.E_replace:.2f}, CausalScore={cf.causal_score:.2f}"
            )

    # 建议
    recommendations = []
    if isolated_ids:
        recommendations.append(f"建议隔离 {len(isolated_ids)} 条高风险证据并重新检索")
    if trust_before.trust_score < 60:
        recommendations.append("原始答案可信度低，建议以重生成答案为准")
    if trust_after.trust_score > trust_before.trust_score:
        recommendations.append(
            f"可信重生成后 TrustScore 提升: "
            f"{trust_before.trust_score:.1f} → {trust_after.trust_score:.1f}"
        )

    # 风险等级
    if trust_before.trust_score < 40:
        risk_level = "high"
    elif trust_before.trust_score < 60:
        risk_level = "medium"
    elif trust_before.trust_score < 80:
        risk_level = "low"
    else:
        risk_level = "safe"

    result.risk_report = RiskReport(
        case_id=case_id,
        risk_level=risk_level,
        affected_claims=affected_claims,
        suspicious_evidences=suspicious_ids,
        isolated_evidences=isolated_ids,
        causal_findings=causal_findings,
        graph_paths=graph_trace.suspicious_paths,
        trust_score=trust_before,
        regenerated_answer=regenerated,
        recommendations=recommendations,
    )

    return result
