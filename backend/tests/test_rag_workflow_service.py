from __future__ import annotations

from pathlib import Path

from app.services.external_knowledge import ExternalKnowledgeService
from app.services.rag_workflow_service import RagWorkflowService


def test_workflow_analyze_and_retrieve_trusted(monkeypatch, tmp_path: Path) -> None:
    import app.services.external_knowledge as external_module

    external = ExternalKnowledgeService(tmp_path / "external.json")
    external.import_dataset_clean('{"clean_chunks":["生产系统权限变更必须经过主管审批。"]}', "unit")
    monkeypatch.setattr(external_module, "external_knowledge_service", external)

    workflow = RagWorkflowService().create("SESSION-unit", "生产系统权限变更是否需要审批？")
    result = workflow.retrieve_trusted(top_k=1)
    snapshot = workflow.snapshot()

    assert result["topk_before"][0]["trust_label"] == "trusted"
    assert snapshot["security_intent"] == "permission_change"
    assert [item["node"] for item in snapshot["trace"]] == ["analyze_query", "retrieve_trusted"]


def test_trace_event_has_node_input_output() -> None:
    event = RagWorkflowService().trace_event("detect_poison", {"query": "q"}, {"risk_level": "low"})

    assert event["node"] == "detect_poison"
    assert event["input"]["query"] == "q"
    assert event["output"]["risk_level"] == "low"
    assert event["timestamp"]
