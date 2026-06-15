"""
Pipeline 集成测试。

验证完整闭环运行、投毒 Chunk 检测能力、TrustScore 提升。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 确保可以导入 app 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.case_loader import load_case, list_case_ids
from app.services.pipeline import run_pipeline


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def case_ids():
    return list_case_ids()


@pytest.fixture(scope="module")
def enterprise_result():
    return run_pipeline("case_enterprise_rag_poisoning")


@pytest.fixture(scope="module")
def linkfarm_result():
    return run_pipeline("case_ai_search_linkfarm_poisoning")


# ---------------------------------------------------------------------------
# 基础测试
# ---------------------------------------------------------------------------

class TestCaseLoader:
    def test_list_case_ids(self, case_ids):
        assert len(case_ids) >= 2, "至少应有 2 个案例"
        assert "case_enterprise_rag_poisoning" in case_ids
        assert "case_ai_search_linkfarm_poisoning" in case_ids

    def test_load_case(self):
        case = load_case("case_enterprise_rag_poisoning")
        assert case is not None
        assert case.question != ""
        assert len(case.evidences) >= 3

    def test_load_nonexistent(self):
        case = load_case("nonexistent_case")
        assert case is None


# ---------------------------------------------------------------------------
# 企业 RAG 投毒案例测试
# ---------------------------------------------------------------------------

class TestEnterprisePipeline:
    def test_pipeline_runs(self, enterprise_result):
        assert enterprise_result is not None

    def test_has_topk(self, enterprise_result):
        assert len(enterprise_result.original_topk_evidence) > 0

    def test_detection_results(self, enterprise_result):
        assert len(enterprise_result.detection_results) > 0
        for d in enterprise_result.detection_results:
            assert 0.0 <= d.ras <= 1.0
            assert 0.0 <= d.gis <= 1.0
            assert 0.0 <= d.dual_risk <= 1.0

    def test_poisoned_chunk_higher_risk(self, enterprise_result):
        """投毒 Chunk 的 DualRisk 应明显高于正常 Chunk。"""
        case = enterprise_result.case_info
        poisoned_ids = set(case.poisoned_evidence_ids) if case else set()

        poisoned_risks = [
            d.dual_risk for d in enterprise_result.detection_results
            if d.evidence_id in poisoned_ids
        ]
        clean_risks = [
            d.dual_risk for d in enterprise_result.detection_results
            if d.evidence_id not in poisoned_ids
        ]

        if poisoned_risks and clean_risks:
            avg_poisoned = sum(poisoned_risks) / len(poisoned_risks)
            avg_clean = sum(clean_risks) / len(clean_risks)
            # 投毒 Chunk 平均 DualRisk 应 > 正常 Chunk
            assert avg_poisoned > avg_clean, (
                f"投毒平均风险({avg_poisoned:.4f})应 > 正常平均风险({avg_clean:.4f})"
            )

    def test_counterfactual_results(self, enterprise_result):
        assert len(enterprise_result.counterfactual_results) > 0
        for cf in enterprise_result.counterfactual_results:
            assert 0.0 <= cf.causal_score <= 1.0

    def test_graph_trace(self, enterprise_result):
        gt = enterprise_result.graph_trace
        assert gt is not None
        assert len(gt.nodes) > 0
        assert len(gt.edges) > 0

    def test_trust_score_before(self, enterprise_result):
        tsb = enterprise_result.trust_score_before
        assert tsb is not None
        assert 0 <= tsb.trust_score <= 100

    def test_isolated_evidences(self, enterprise_result):
        """企业投毒证据必须被隔离。"""
        assert "E-EP-003" in enterprise_result.isolated_evidences

    def test_regenerated_answer(self, enterprise_result):
        assert enterprise_result.regenerated_answer != ""

    def test_trust_score_after(self, enterprise_result):
        tsa = enterprise_result.trust_score_after
        assert tsa is not None
        assert 0 <= tsa.trust_score <= 100

    def test_trust_score_improves(self, enterprise_result):
        """重生成后 TrustScore 应严格提升。"""
        tsb = enterprise_result.trust_score_before
        tsa = enterprise_result.trust_score_after
        if tsb and tsa:
            assert tsa.trust_score > tsb.trust_score, (
                f"重生成后({tsa.trust_score:.1f})应 > 检测前({tsb.trust_score:.1f})"
            )

    def test_regeneration_removes_wrong_claim(self, enterprise_result):
        assert "允许使用admin/admin" not in enterprise_result.regenerated_answer

    def test_risk_report(self, enterprise_result):
        rr = enterprise_result.risk_report
        assert rr is not None
        assert rr.case_id == "case_enterprise_rag_poisoning"
        assert rr.risk_level in ("safe", "low", "medium", "high")


# ---------------------------------------------------------------------------
# AI 搜索站群投毒案例测试
# ---------------------------------------------------------------------------

class TestLinkfarmPipeline:
    def test_pipeline_runs(self, linkfarm_result):
        assert linkfarm_result is not None

    def test_detection_results(self, linkfarm_result):
        assert len(linkfarm_result.detection_results) > 0

    def test_poisoned_chunk_higher_risk(self, linkfarm_result):
        """站群投毒 Chunk 的 DualRisk 应高于正常 Chunk。"""
        case = linkfarm_result.case_info
        poisoned_ids = set(case.poisoned_evidence_ids) if case else set()

        poisoned_risks = [
            d.dual_risk for d in linkfarm_result.detection_results
            if d.evidence_id in poisoned_ids
        ]
        clean_risks = [
            d.dual_risk for d in linkfarm_result.detection_results
            if d.evidence_id not in poisoned_ids
        ]

        if poisoned_risks and clean_risks:
            avg_poisoned = sum(poisoned_risks) / len(poisoned_risks)
            avg_clean = sum(clean_risks) / len(clean_risks)
            assert avg_poisoned > avg_clean, (
                f"站群投毒平均风险({avg_poisoned:.4f})应 > 正常平均风险({avg_clean:.4f})"
            )

    def test_graph_has_copied_from(self, linkfarm_result):
        """站群案例图谱应包含 copied_from 边。"""
        gt = linkfarm_result.graph_trace
        if gt:
            copied = [e for e in gt.edges if e.edge_type == "copied_from"]
            assert len(copied) > 0, "站群案例应有 copied_from 边"

    def test_trust_score_improves(self, linkfarm_result):
        tsb = linkfarm_result.trust_score_before
        tsa = linkfarm_result.trust_score_after
        if tsb and tsa:
            assert tsa.trust_score > tsb.trust_score

    def test_linkfarm_poison_isolated(self, linkfarm_result):
        assert set(linkfarm_result.case_info.poisoned_evidence_ids).issubset(
            set(linkfarm_result.isolated_evidences)
        )

    def test_regeneration_removes_wrong_claim(self, linkfarm_result):
        assert "无需继续更新" not in linkfarm_result.regenerated_answer

    def test_regenerated_answer(self, linkfarm_result):
        assert linkfarm_result.regenerated_answer != ""


# ---------------------------------------------------------------------------
# 公式验证测试
# ---------------------------------------------------------------------------

class TestFormulas:
    def test_dual_risk_formula(self):
        from app.utils.score_utils import compute_dual_risk
        # λ=0.7: DualRisk = 0.7*sqrt(RAS*GIS) + 0.3*(RAS+GIS)/2
        ras, gis = 0.8, 0.6
        expected = 0.7 * (0.8 * 0.6) ** 0.5 + 0.3 * (0.8 + 0.6) / 2
        result = compute_dual_risk(ras, gis)
        assert abs(result - expected) < 1e-6

    def test_causal_score_formula(self):
        from app.utils.score_utils import compute_causal_score
        # α=0.4, β=0.3, γ=0.3
        e_remove, e_solo, e_replace, cs = compute_causal_score(
            pO=0.9, pR=0.2, pS=0.8, pT=0.1
        )
        assert abs(e_remove - max(0, 0.9 - 0.2)) < 1e-6
        assert abs(e_solo - 0.8) < 1e-6
        assert abs(e_replace - max(0, 0.9 - 0.1)) < 1e-6
        expected_cs = 0.4 * e_remove + 0.3 * e_solo + 0.3 * e_replace
        assert abs(cs - expected_cs) < 1e-6

    def test_trust_score_formula(self):
        from app.utils.score_utils import compute_trust_score
        # TrustScore = 100 * Clip(0.18*0.8 + 0.24*0.9 + ..., 0, 1)
        ts = compute_trust_score(
            source_quality=0.8,
            evidence_coverage=0.9,
            source_independence=0.7,
            freshness=0.7,
            retrieval_stability=0.5,
            poison_risk=0.1,
            graph_risk=0.0,
            causal_risk=0.05,
            contradiction_rate=0.1,
        )
        assert 0 <= ts <= 100
        # 全正项高 + 低风险 → 应 > 60
        assert ts > 60

    def test_sigmoid(self):
        from app.utils.score_utils import sigmoid
        assert abs(sigmoid(0) - 0.5) < 1e-6
        assert sigmoid(10) > 0.99
        assert sigmoid(-10) < 0.01
