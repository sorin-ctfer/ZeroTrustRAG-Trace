"""完整 Web 原型 API 与服务集成测试。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import health
from app.routers.platform import router as platform_router
from app.services.web_platform import (
    analyze_rag,
    cascade_detection,
    correction_run,
    get_report,
    get_web_case,
    list_knowledge,
    list_web_cases,
    load_demo_knowledge,
    run_agent_demo,
    trace_ipjg,
)


def test_health() -> None:
    assert health()["data"]["status"] == "ok"
    paths = {route.path for route in platform_router.routes}
    assert "/api/knowledge/upload" in paths
    assert "/api/correction/run" in paths
    assert "/api/report/{case_id}" in paths


def test_three_web_cases() -> None:
    cases = list_web_cases()
    assert len(cases) >= 3
    assert {item["case_id"] for item in cases}.issuperset(
        {
            "case_enterprise_policy_approval",
            "case_threat_intel_false_consensus",
            "case_prompt_infection",
        }
    )


def test_knowledge_demo_and_list() -> None:
    loaded = load_demo_knowledge()
    assert len(loaded) >= 9
    assert len(list_knowledge()) >= 9


def test_rag_analyze_detects_prompt_infection() -> None:
    case = get_web_case("case_prompt_infection")
    assert case is not None
    data = analyze_rag(
        case["question"],
        case["original_answer"],
        top_k=5,
        case_id=case["case_id"],
    )
    assert "E-PI-003" in data["suspicious_evidence"]


def test_agent_zero_trust_and_cascade() -> None:
    demo = run_agent_demo("case_threat_intel_false_consensus")
    assert len(demo["agents"]) == 6
    assert all("zero_trust_checks" in claim for claim in demo["claims"])
    cascade = cascade_detection("case_threat_intel_false_consensus")
    assert cascade["false_consensus_rate"] > 0
    assert cascade["suspicious_agents"]


def test_ipjg_has_four_layers() -> None:
    run_agent_demo("case_threat_intel_false_consensus")
    data = trace_ipjg("case_threat_intel_false_consensus")
    assert len(data["categories"]) == 4
    assert data["pollution_sources"] == ["E-TI-003"]
    assert data["propagation_paths"]


def test_all_cases_correction_improves_trust() -> None:
    for case_id in (
        "case_enterprise_policy_approval",
        "case_threat_intel_false_consensus",
        "case_prompt_infection",
    ):
        report = correction_run(case_id)
        comparison = report["before_after_comparison"]
        assert comparison["after_trust_score"] > comparison["before_trust_score"]
        assert report["suspicious_evidence"]
        assert report["trusted_answer"]
        if case_id == "case_prompt_infection":
            assert all("203.0.113.42" not in item["content"] for item in report["bft_consensus"])


def test_report_endpoint() -> None:
    data = get_report("case_enterprise_policy_approval")
    assert data is not None
    assert data["case_id"] == "case_enterprise_policy_approval"
    assert "before_after_comparison" in data
