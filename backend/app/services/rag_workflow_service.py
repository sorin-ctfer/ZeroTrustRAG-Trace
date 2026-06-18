"""Traceable safety RAG workflow orchestration.

The workflow mirrors LangGraph-style state nodes while remaining a plain Python
fallback. LangGraph is optional; existing API routes keep using the current
services and can attach these trace events to session state.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WorkflowTraceEvent:
    node: str
    input: dict[str, Any]
    output: dict[str, Any]
    timestamp: str = field(default_factory=now_iso)


@dataclass
class SafetyRagWorkflowState:
    session_id: str
    query: str
    normalized_query: str = ""
    keywords: list[str] = field(default_factory=list)
    security_intent: str = "general"
    selected_sample_id: str | None = None
    topk_before: list[dict[str, Any]] = field(default_factory=list)
    injected_poison_chunk: dict[str, Any] | None = None
    topk_after: list[dict[str, Any]] = field(default_factory=list)
    pre_poison_answer: str = ""
    post_poison_answer: str = ""
    detection_result: dict[str, Any] | None = None
    counterfactual_result: dict[str, Any] | None = None
    quarantined_chunks: list[dict[str, Any]] = field(default_factory=list)
    correction_result: dict[str, Any] | None = None
    report: dict[str, Any] | None = None
    trace: list[dict[str, Any]] = field(default_factory=list)


class SafetyRagWorkflow:
    """Plain Python workflow with explicit node inputs, outputs, and trace."""

    def __init__(self, state: SafetyRagWorkflowState) -> None:
        self.state = state

    def _record(self, node: str, input_data: dict[str, Any], output_data: dict[str, Any]) -> dict[str, Any]:
        event = asdict(WorkflowTraceEvent(node=node, input=input_data, output=output_data))
        self.state.trace.append(event)
        return output_data

    def analyze_query(self, query: str | None = None) -> dict[str, Any]:
        query = query if query is not None else self.state.query
        normalized = re.sub(r"\s+", " ", query.strip())
        keywords = list(dict.fromkeys(re.findall(r"[\u4e00-\u9fffA-Za-z0-9_]{2,}", normalized)))[:12]
        intent_terms = {
            "permission_change": ("权限", "审批", "授权", "管理员", "提权"),
            "vulnerability_status": ("漏洞", "修复", "补丁", "升级"),
            "prompt_injection": ("忽略", "规则", "提示", "关闭"),
            "credential_policy": ("口令", "MFA", "钓鱼", "邮件"),
        }
        security_intent = "general"
        for intent, terms in intent_terms.items():
            if any(term in normalized for term in terms):
                security_intent = intent
                break
        self.state.normalized_query = normalized
        self.state.keywords = keywords
        self.state.security_intent = security_intent
        return self._record(
            "analyze_query",
            {"query": query},
            {"normalized_query": normalized, "keywords": keywords, "security_intent": security_intent},
        )

    def retrieve_trusted(self, top_k: int = 5) -> dict[str, Any]:
        from .external_knowledge import external_knowledge_service

        query = self.state.normalized_query or self.state.query
        topk = external_knowledge_service.retrieve(query, top_k=top_k)
        self.state.topk_before = topk
        return self._record(
            "retrieve_trusted",
            {"query": query, "top_k": top_k, "source": "external_trusted_chunks"},
            {"topk_before": topk, "retrieval_mode": topk[0].get("retrieval_mode") if topk else "empty"},
        )

    def inject_session_poison(self, sample_id: str) -> dict[str, Any]:
        from .interactive_rag_service import interactive_rag_service

        injected = interactive_rag_service.inject_poison_sample(self.state.session_id, sample_id)
        self.state.selected_sample_id = sample_id
        self.state.injected_poison_chunk = injected
        return self._record(
            "inject_session_poison",
            {"session_id": self.state.session_id, "sample_id": sample_id},
            {"injected_poison_chunk": injected, "scope": "session_only"},
        )

    def retrieve_with_session_poison(self, top_k: int = 5) -> dict[str, Any]:
        from .interactive_rag_service import interactive_rag_service

        query = self.state.normalized_query or self.state.query
        topk = interactive_rag_service.retrieve_for_session(self.state.session_id, query, "after_poison", top_k)
        self.state.topk_after = topk
        return self._record(
            "retrieve_with_session_poison",
            {"query": query, "top_k": top_k, "source": "trusted_plus_session_poison"},
            {"topk_after": topk, "retrieval_mode": topk[0].get("retrieval_mode") if topk else "empty"},
        )

    def generate_answer(self, stage: str) -> dict[str, Any]:
        from .interactive_rag_service import interactive_rag_service

        query = self.state.normalized_query or self.state.query
        result = interactive_rag_service.chat(query, stage, self.state.session_id)
        if stage in {"before_poison", "normal_chat"}:
            self.state.pre_poison_answer = result.get("answer", "")
            key = "pre_poison_answer"
        else:
            self.state.post_poison_answer = result.get("answer", "")
            key = "post_poison_answer"
        return self._record(
            "generate_answer",
            {"query": query, "stage": stage},
            {key: result.get("answer", ""), "cited_chunk_ids": result.get("cited_chunk_ids", [])},
        )

    def detect_poison(self) -> dict[str, Any]:
        from .interactive_poison_detector import interactive_poison_detector

        detection = interactive_poison_detector.detect(
            self.state.session_id,
            self.state.normalized_query or self.state.query,
            self.state.pre_poison_answer,
            self.state.post_poison_answer,
        )
        self.state.detection_result = detection
        return self._record(
            "detect_poison",
            {"session_id": self.state.session_id},
            {
                "risk_chunks": detection.get("risk_chunks", []),
                "risk_level": detection.get("risk_level"),
                "detection_mode": detection.get("detection_mode"),
                "metrics": detection.get("metrics", {}),
            },
        )

    def causal_verify(self) -> dict[str, Any]:
        from .interactive_correction_service import interactive_correction_service

        counterfactual = interactive_correction_service.counterfactual(self.state.session_id)
        self.state.counterfactual_result = counterfactual
        return self._record(
            "causal_verify",
            {"session_id": self.state.session_id},
            {
                "E_remove": counterfactual.get("E_remove"),
                "E_solo": counterfactual.get("E_solo"),
                "E_replace": counterfactual.get("E_replace"),
                "CausalScore": counterfactual.get("CausalScore"),
            },
        )

    def quarantine(self) -> dict[str, Any]:
        from .interactive_correction_service import interactive_correction_service

        quarantined = interactive_correction_service.quarantine_risk_chunks(self.state.session_id)
        self.state.quarantined_chunks = quarantined
        return self._record(
            "quarantine",
            {"session_id": self.state.session_id},
            {"quarantined_chunks": quarantined, "scope": "session_only"},
        )

    def regenerate_trusted_answer(self) -> dict[str, Any]:
        from .interactive_correction_service import interactive_correction_service

        correction = interactive_correction_service.regenerate_corrected_answer(self.state.session_id, self.state.normalized_query or self.state.query)
        self.state.correction_result = correction
        return self._record(
            "regenerate_trusted_answer",
            {"session_id": self.state.session_id},
            {
                "TrustScore_after": correction.get("TrustScore_after"),
                "corrected_answer": correction.get("corrected_answer"),
                "cited_chunk_ids": correction.get("cited_chunk_ids", []),
            },
        )

    def build_report(self) -> dict[str, Any]:
        from .interactive_correction_service import interactive_correction_service

        report = interactive_correction_service.report(self.state.session_id)
        report["workflow_trace"] = self.state.trace
        self.state.report = report
        return self._record(
            "build_report",
            {"session_id": self.state.session_id},
            {"report": report},
        )

    def snapshot(self) -> dict[str, Any]:
        return asdict(self.state)


class RagWorkflowService:
    """Factory and trace helper used by existing services."""

    def create(self, session_id: str, query: str) -> SafetyRagWorkflow:
        workflow = SafetyRagWorkflow(SafetyRagWorkflowState(session_id=session_id, query=query))
        workflow.analyze_query(query)
        return workflow

    def trace_event(self, node: str, input_data: dict[str, Any], output_data: dict[str, Any]) -> dict[str, Any]:
        return asdict(WorkflowTraceEvent(node=node, input=input_data, output=output_data))


rag_workflow_service = RagWorkflowService()
