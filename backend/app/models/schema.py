"""
智源净域 — 统一数据模型定义

所有 Pydantic 模型集中在此文件，供 services / API / tests 共用。
字段命名与 AGENTS.md 及作品报告保持一致。
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional, Literal


# ---------------------------------------------------------------------------
# 1. Evidence — 统一证据对象
# ---------------------------------------------------------------------------

class Evidence(BaseModel):
    """统一证据对象，兼容开放网页和企业 RAG 文档。"""

    evidence_id: str
    source_type: Literal["web", "rag_document"]
    source_name: str = ""
    url: Optional[str] = None
    document_id: str = ""
    chunk_id: str = ""
    title: str = ""
    content: str
    timestamp: Optional[str] = None
    content_hash: str = ""
    parent_id: Optional[str] = None
    retrieval_rank: Optional[int] = None
    retrieval_score: Optional[float] = None
    citation_state: bool = False
    is_poisoned: bool = False
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 2. DemoCase — 演示案例
# ---------------------------------------------------------------------------

class ExpectedClaim(BaseModel):
    """案例中预定义的原子声明及其与证据的预期关系。"""

    claim_id: str
    claim_text: str
    expected_relation: Literal["supports", "contradicts", "neutral"] = "supports"
    supporting_evidence_ids: list[str] = Field(default_factory=list)


class DemoCase(BaseModel):
    """完整的演示案例，包含问题、证据和预期结果。"""

    case_id: str
    title: str
    scenario_type: str
    question: str
    true_answer: str
    target_wrong_answer: str
    original_answer: str = ""
    evidences: list[Evidence] = Field(default_factory=list)
    trusted_evidence_ids: list[str] = Field(default_factory=list)
    poisoned_evidence_ids: list[str] = Field(default_factory=list)
    expected_claims: list[ExpectedClaim] = Field(default_factory=list)
    query_rewrites: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 3. DetectionResult — RAS / GIS / DualRisk 检测结果
# ---------------------------------------------------------------------------

class DetectionResult(BaseModel):
    """单个证据的双条件检测结果。"""

    evidence_id: str
    ras: float = 0.0
    gis: float = 0.0
    dual_risk: float = 0.0
    risk_level: Literal["low", "medium", "high"] = "low"
    reasons: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 4. CounterfactualResult — 四路反事实验证结果
# ---------------------------------------------------------------------------

class CounterfactualResult(BaseModel):
    """四路反事实验证 + 因果分。"""

    suspicious_evidence_id: str
    original_answer: str = ""
    remove_answer: str = ""
    solo_answer: str = ""
    replace_answer: str = ""
    pO: float = 0.0
    pR: float = 0.0
    pS: float = 0.0
    pT: float = 0.0
    E_remove: float = 0.0
    E_solo: float = 0.0
    E_replace: float = 0.0
    causal_score: float = 0.0


# ---------------------------------------------------------------------------
# 5. GraphTrace — 异构投毒传播图谱
# ---------------------------------------------------------------------------

class GraphNode(BaseModel):
    """图谱节点。"""

    node_id: str
    node_type: Literal["page", "document", "chunk", "query", "claim", "answer"]
    label: str = ""
    properties: dict = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """图谱边。"""

    source_id: str
    target_id: str
    edge_type: Literal[
        "contains",
        "retrieved_by",
        "supports",
        "contradicts",
        "similar_to",
        "copied_from",
        "same_claim",
        "caused_error",
        "isolated_in",
    ]
    weight: float = 1.0
    properties: dict = Field(default_factory=dict)


class GraphTrace(BaseModel):
    """完整图谱 + 可疑路径。"""

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    suspicious_paths: list[list[str]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 6. ClaimEvidenceRelation — 声明—证据关系
# ---------------------------------------------------------------------------

class ClaimEvidenceRelation(BaseModel):
    """单条声明与单条证据的 NLI 关系。"""

    claim_id: str
    claim_text: str
    evidence_id: str
    relation: Literal["supports", "contradicts", "neutral"] = "neutral"
    support_score: float = 0.0
    contradict_score: float = 0.0
    neutral_score: float = 0.0


# ---------------------------------------------------------------------------
# 7. TrustScoreDetail — 可信评分明细
# ---------------------------------------------------------------------------

class TrustScoreDetail(BaseModel):
    """
    TrustScore 可信评分明细。

    公式 (报告 2-13 简化版):
      TrustScore = 100 * Clip((
          0.18*SQ + 0.24*EC + 0.12*SI + 0.08*FR + 0.08*RS
        - 0.14*PR - 0.07*GR - 0.06*CR - 0.03*CT
      ) / 0.70,
        0, 1
      )

    正向项: source_quality(SQ), evidence_coverage(EC),
            source_independence(SI), freshness(FR), retrieval_stability(RS)
    风险项: poison_risk(PR), graph_risk(GR),
            causal_risk(CR), contradiction_rate(CT)
    """

    trust_score: float = 0.0
    trust_level: Literal["high", "medium", "low", "high_risk"] = "high"
    source_quality: float = 0.0
    evidence_coverage: float = 0.0
    source_independence: float = 0.0
    freshness: float = 0.0
    retrieval_stability: float = 0.0
    poison_risk: float = 0.0
    graph_risk: float = 0.0
    causal_risk: float = 0.0
    contradiction_rate: float = 0.0


# ---------------------------------------------------------------------------
# 8. RiskReport — 结构化风险报告
# ---------------------------------------------------------------------------

class RiskReport(BaseModel):
    """结构化风险报告。"""

    case_id: str
    risk_level: Literal["safe", "low", "medium", "high"] = "safe"
    affected_claims: list[str] = Field(default_factory=list)
    suspicious_evidences: list[str] = Field(default_factory=list)
    isolated_evidences: list[str] = Field(default_factory=list)
    causal_findings: list[str] = Field(default_factory=list)
    graph_paths: list[list[str]] = Field(default_factory=list)
    trust_score: Optional[TrustScoreDetail] = None
    regenerated_answer: str = ""
    recommendations: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 9. PipelineResult — 完整流水线输出
# ---------------------------------------------------------------------------

class PipelineResult(BaseModel):
    """完整检测闭环输出，对应 POST /api/run_case/{case_id}。"""

    case_info: Optional[DemoCase] = None
    original_topk_evidence: list[Evidence] = Field(default_factory=list)
    detection_results: list[DetectionResult] = Field(default_factory=list)
    suspicious_evidences: list[str] = Field(default_factory=list)
    counterfactual_results: list[CounterfactualResult] = Field(default_factory=list)
    graph_trace: Optional[GraphTrace] = None
    claim_evidence_matrix: list[ClaimEvidenceRelation] = Field(default_factory=list)
    trust_score_before: Optional[TrustScoreDetail] = None
    isolated_evidences: list[str] = Field(default_factory=list)
    trusted_topk_evidence: list[Evidence] = Field(default_factory=list)
    regenerated_answer: str = ""
    trust_score_after: Optional[TrustScoreDetail] = None
    risk_report: Optional[RiskReport] = None
