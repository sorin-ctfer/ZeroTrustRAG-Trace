"""Web 原型要求的完整 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from ..models.web_models import (
    AgentDemoRequest,
    CascadeRequest,
    CorrectionRequest,
    PoisonDetectRequest,
    PoisonSampleRequest,
    TraceRequest,
    RagAnalyzeRequest,
)
from ..services.web_platform import (
    add_document,
    analyze_rag,
    cascade_detection,
    clear_knowledge,
    correction_run,
    dashboard_stats,
    get_agent_graph,
    get_claims,
    get_report,
    get_web_case,
    list_knowledge,
    list_web_cases,
    load_demo_knowledge,
    run_agent_demo,
    trace_ipjg,
)

router = APIRouter(prefix="/api")


@router.get("/dashboard/stats")
def stats() -> dict:
    return dashboard_stats()


@router.post("/knowledge/upload")
async def upload_knowledge(
    file: UploadFile = File(...),
    is_poisoned: bool = Form(False),
) -> dict:
    suffix = (file.filename or "").lower().rsplit(".", 1)[-1]
    if suffix not in {"txt", "md"}:
        return {"success": False, "error": "仅支持 txt / md 文件"}
    content = (await file.read()).decode("utf-8", errors="ignore")
    return {"success": True, "data": add_document(file.filename or "upload.txt", content, is_poisoned)}


@router.post("/knowledge/add-poison")
def add_poison(req: PoisonSampleRequest) -> dict:
    return {"success": True, "data": add_document(req.title, req.content, True, req.source)}


@router.get("/knowledge/list")
def knowledge_list() -> dict:
    return {"success": True, "data": list_knowledge()}


@router.post("/knowledge/load-demo")
def knowledge_demo() -> dict:
    return {"success": True, "data": load_demo_knowledge()}


@router.post("/knowledge/clear")
def knowledge_clear() -> dict:
    clear_knowledge()
    return {"success": True, "data": []}


@router.post("/rag/analyze")
def rag_analyze(req: RagAnalyzeRequest) -> dict:
    return {"success": True, "data": analyze_rag(req.query, req.original_answer, req.top_k, req.case_id)}


@router.get("/rag/cases")
def rag_cases() -> dict:
    return {"success": True, "data": list_web_cases()}


@router.get("/rag/cases/{case_id}")
def rag_case(case_id: str) -> dict:
    case = get_web_case(case_id)
    return {"success": case is not None, "data": case, "error": None if case else "案例不存在"}


@router.post("/agents/run-demo")
def agents_demo(req: AgentDemoRequest) -> dict:
    return {"success": True, "data": run_agent_demo(req.case_id)}


@router.get("/agents/claims")
def agents_claims() -> dict:
    return {"success": True, "data": get_claims()}


@router.get("/agents/graph")
def agents_graph() -> dict:
    return {"success": True, "data": get_agent_graph()}


@router.post("/detect/cascade")
def detect_cascade(req: CascadeRequest) -> dict:
    return {"success": True, "data": cascade_detection(req.case_id, req.claims)}


@router.post("/detect/poison")
def detect_poison(req: PoisonDetectRequest) -> dict:
    return {"success": True, "data": analyze_rag(req.query, req.answer, req.top_k)}


@router.post("/trace/ipjg")
def ipjg(req: TraceRequest) -> dict:
    return {"success": True, "data": trace_ipjg(req.case_id)}


@router.post("/correction/run")
def correction(req: CorrectionRequest) -> dict:
    return {"success": True, "data": correction_run(req.case_id, req.query, req.original_answer)}


@router.get("/report/{case_id}")
def report(case_id: str) -> dict:
    data = get_report(case_id)
    return {"success": data is not None, "data": data, "error": None if data else "报告不存在"}

