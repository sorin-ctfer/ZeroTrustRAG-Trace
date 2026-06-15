"""完整 Web 原型 API 与服务集成测试。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app, health
from app.models.web_models import AgentDemoRequest, CascadeRequest, CorrectionRequest, RagAnalyzeRequest, TraceRequest
from app.routers.platform import router as platform_router
from app.routers.platform import (
    agents_demo,
    correction,
    detect_cascade,
    ipjg,
    rag_analyze,
    report,
)
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
    assert paths.issuperset(
        {
            "/api/dashboard/stats",
            "/api/knowledge/upload",
            "/api/knowledge/list",
            "/api/knowledge/load-demo",
            "/api/knowledge/clear",
            "/api/rag/analyze",
            "/api/rag/cases",
            "/api/rag/cases/{case_id}",
            "/api/agents/run-demo",
            "/api/agents/claims",
            "/api/agents/graph",
            "/api/detect/cascade",
            "/api/detect/poison",
            "/api/trace/ipjg",
            "/api/correction/run",
            "/api/report/{case_id}",
        }
    )


def test_three_web_cases() -> None:
    cases = list_web_cases()
    assert len(cases) >= 6
    assert {item["case_id"] for item in cases}.issuperset(
        {
            "case_enterprise_policy_approval",
            "case_threat_intel_false_consensus",
            "case_prompt_infection",
            "case_vulnerability_status_poisoning",
            "case_security_certification_poisoning",
            "case_benign_outdated_information",
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


def test_new_poison_cases_and_benign_false_positive_control() -> None:
    expected = {
        "case_vulnerability_status_poisoning": "E-VUL-003",
        "case_security_certification_poisoning": "E-CERT-003",
    }
    for case_id, evidence_id in expected.items():
        case = get_web_case(case_id)
        assert case is not None
        result = analyze_rag(case["question"], case["original_answer"], 5, case_id)
        assert evidence_id in result["suspicious_evidence"]
        correction = correction_run(case_id)
        assert correction["before_after_comparison"]["improvement"] > 0

    benign = get_web_case("case_benign_outdated_information")
    assert benign is not None
    result = analyze_rag(benign["question"], benign["original_answer"], 5, benign["case_id"])
    assert result["suspicious_evidence"] == []
    assert result["benign_error_evidence"] == ["E-BEN-003"]
    row = next(item for item in result["top_k"] if item["evidence_id"] == "E-BEN-003")
    assert row["risk_category"] == "benign_error"
    agent_result = run_agent_demo(benign["case_id"])
    assert all(claim["risk_score"] < 0.6 for claim in agent_result["claims"])
    assert cascade_detection(benign["case_id"])["suspicious_agents"] == []


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


def test_rag_analyze_http() -> None:
    response = rag_analyze(
        RagAnalyzeRequest(
            case_id="case_vulnerability_status_poisoning",
            query="CVE-2026-41001 是否已经修复，当前是否还需要升级？",
            original_answer="漏洞已经修复，无需升级。",
            top_k=5,
        )
    )
    assert response["success"] is True
    assert "E-VUL-003" in response["data"]["suspicious_evidence"]


def test_agent_and_cascade_http() -> None:
    demo = agents_demo(AgentDemoRequest(case_id="case_threat_intel_false_consensus"))
    assert demo["success"] is True
    assert len(demo["data"]["agents"]) == 6

    cascade = detect_cascade(CascadeRequest(case_id="case_threat_intel_false_consensus"))
    assert cascade["success"] is True
    assert cascade["data"]["false_consensus_rate"] > 0


def test_trace_correction_and_report_http() -> None:
    trace = ipjg(TraceRequest(case_id="case_security_certification_poisoning"))
    assert trace["success"] is True
    assert trace["data"]["pollution_sources"] == ["E-CERT-003"]

    correction_result = correction(CorrectionRequest(case_id="case_security_certification_poisoning"))
    assert correction_result["success"] is True
    comparison = correction_result["data"]["before_after_comparison"]
    assert comparison["after_trust_score"] > comparison["before_trust_score"]

    report_result = report("case_security_certification_poisoning")
    assert report_result["success"] is True
    assert report_result["data"]["case_id"] == "case_security_certification_poisoning"
