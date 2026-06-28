"""Interactive LangChain RAG poisoning lab endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..services.bailian_llm_service import BailianConfigurationError
from ..services.interactive_correction_service import interactive_correction_service
from ..services.interactive_poison_detector import interactive_poison_detector
from ..services.poison_propagation_graph import poison_propagation_graph_service
from ..services.interactive_rag_service import interactive_rag_service
from ..services.interactive_vector_store import interactive_vector_store

router = APIRouter()


def _response(data=None, error: str | None = None, status_code: int = 200):
    payload = {
        "success": error is None,
        "data": data if error is None else None,
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return JSONResponse(status_code=status_code, content=payload)


def _run(operation):
    try:
        return _response(operation())
    except BailianConfigurationError as exc:
        return _response(error=str(exc), status_code=503)
    except ValueError as exc:
        return _response(error=str(exc), status_code=400)
    except Exception as exc:
        return _response(
            error=f"Interactive RAG operation failed: {exc}",
            status_code=502,
        )


class KnowledgeRequest(BaseModel):
    content: str = Field(min_length=1)
    source: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    stage: str = "before_poison"
    session_id: str | None = None


class AnswerabilityRequest(BaseModel):
    question: str = Field(min_length=1)
    session_id: str


class DetectRequest(BaseModel):
    session_id: str
    question: str
    before_answer: str
    after_answer: str


class QuarantineRequest(BaseModel):
    session_id: str
    chunk_ids: list[str] = Field(default_factory=list)


class RegenerateRequest(BaseModel):
    session_id: str
    question: str


class SessionInjectRequest(BaseModel):
    sample_id: str


@router.post("/knowledge/trusted")
def add_trusted_knowledge(req: KnowledgeRequest):
    # Compatibility endpoint: trusted knowledge is now managed by /api/external-knowledge.
    from ..services.external_knowledge import external_knowledge_service

    return _run(lambda: external_knowledge_service.import_dataset_clean(
        '{"clean_chunks": [' + __import__("json").dumps(req.content, ensure_ascii=False) + ']}',
        req.source,
    ))


@router.post("/knowledge/poison")
def add_poison_knowledge(req: KnowledgeRequest):
    from ..services.poison_samples import poison_sample_service

    return _run(lambda: [poison_sample_service.create(
        target_query="兼容接口投毒样本",
        content=req.content,
        target_wrong_answer="",
        correct_answer="",
        attack_type="policy_bypass",
        source=req.source,
    )])


@router.get("/knowledge/chunks")
def list_chunks():
    from ..services.external_knowledge import external_knowledge_service

    return _response(external_knowledge_service.list_chunks())


@router.post("/knowledge/reset")
def reset_interactive_lab():
    interactive_rag_service.clear_sessions()
    return _response({"sessions_cleared": True})


@router.post("/session/create")
def create_session():
    return _response(interactive_rag_service.create_session())


@router.get("/sessions")
def list_sessions():
    return _response(interactive_rag_service.list_sessions())


@router.get("/session/{session_id}")
def get_session(session_id: str):
    session = interactive_rag_service.get_session(session_id)
    if session is None:
        return _response(error="Interactive session does not exist", status_code=404)
    return _response(session)


@router.post("/session/{session_id}/inject-poison")
def inject_poison_to_session(session_id: str, req: SessionInjectRequest):
    return _run(lambda: interactive_rag_service.inject_poison_sample(session_id, req.sample_id))


@router.get("/session/{session_id}/topk")
def session_topk(session_id: str):
    session = interactive_rag_service.get_session(session_id)
    if session is None:
        return _response(error="Interactive session does not exist", status_code=404)
    return _response({"before": session.get("topk_before", []), "after": session.get("topk_after", [])})


@router.get("/session/{session_id}/risk-summary")
def session_risk_summary(session_id: str):
    return _run(lambda: interactive_rag_service.risk_summary(session_id))


@router.post("/rag/answerability")
def check_answerability(req: AnswerabilityRequest):
    return _run(lambda: interactive_rag_service.check_answerability(req.session_id, req.question))


@router.post("/rag/chat")
def interactive_chat(req: ChatRequest):
    return _run(
        lambda: interactive_rag_service.chat(
            req.question,
            stage=req.stage,
            session_id=req.session_id,
        )
    )


@router.post("/rag/chat-detect")
def detect_interactive_poison(req: DetectRequest):
    return _run(
        lambda: interactive_poison_detector.detect(
            req.session_id,
            req.question,
            req.before_answer,
            req.after_answer,
        )
    )


@router.post("/correction/quarantine")
def quarantine(req: QuarantineRequest):
    return _run(
        lambda: interactive_correction_service.quarantine_risk_chunks(
            req.session_id, req.chunk_ids
        )
    )


@router.post("/correction/regenerate")
def regenerate(req: RegenerateRequest):
    return _run(
        lambda: interactive_correction_service.regenerate_corrected_answer(
            req.session_id, req.question
        )
    )


@router.get("/correction/{session_id}/detail")
def correction_detail(session_id: str):
    return _run(lambda: interactive_correction_service.detail(session_id))


@router.post("/correction/{session_id}/counterfactual")
def correction_counterfactual(session_id: str):
    return _run(lambda: interactive_correction_service.counterfactual(session_id))


@router.post("/correction/{session_id}/quarantine")
def correction_quarantine(session_id: str):
    return _run(lambda: interactive_correction_service.quarantine_risk_chunks(session_id))


@router.post("/correction/{session_id}/regenerate")
def correction_regenerate(session_id: str):
    session = interactive_rag_service.get_session(session_id)
    question = session.get("question", "") if session else ""
    return _run(lambda: interactive_correction_service.regenerate_corrected_answer(session_id, question))


@router.get("/correction/{session_id}/report")
def correction_report(session_id: str):
    return _run(lambda: interactive_correction_service.report(session_id))


@router.get("/propagation/{session_id}")
def poison_propagation_graph(session_id: str):
    return _run(lambda: poison_propagation_graph_service.build(session_id))


@router.get("/report/{session_id}")
def interactive_report(session_id: str):
    session = interactive_rag_service.get_session(session_id)
    if session is None:
        return _response(error="Interactive report does not exist", status_code=404)
    return _response(session)
