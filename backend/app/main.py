"""
智源净域 — FastAPI 后端入口。

提供 9 个 API 端点，支持完整检测闭环。
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict

from .services.case_loader import load_case, load_all_cases, list_case_ids
from .services.ingest import process_evidences
from .services.retrieval import search
from .services.detection import detect
from .services.counterfactual import run_counterfactual
from .services.graph_trace import build_graph
from .services.trust_score import build_claim_evidence_matrix, compute_full_trust_score
from .services.regeneration import (
    isolate_high_risk,
    risk_aware_search,
    regenerate_trusted_answer,
)
from .services.pipeline import run_pipeline
from .utils.text_utils import split_claims


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="智源净域：多 Agent 零信任协同与 RAG 知识投毒因果验证系统",
    version="1.0.0-mvp",
    description="本地可复现的多 Agent 零信任、知识投毒检测、联合溯源与可信纠偏原型。",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .routers.platform import router as platform_router
from .routers import interactive_rag
from .routers.external_knowledge import router as external_knowledge_router
from .routers.poison_samples import router as poison_samples_router
from .routers.rag_training import router as rag_training_router
from .routers.rag_evaluation import router as rag_evaluation_router

app.include_router(platform_router)
app.include_router(external_knowledge_router)
app.include_router(poison_samples_router)
app.include_router(rag_training_router)
app.include_router(rag_evaluation_router)
app.include_router(
    interactive_rag.router,
    prefix="/api/interactive",
    tags=["interactive-rag"],
)


# ---------------------------------------------------------------------------
# 统一响应包装
# ---------------------------------------------------------------------------

class ApiResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    success: bool
    data: object = None
    error: str | None = None
    timestamp: str = ""


def _ok(data=None) -> dict:
    return {
        "success": True,
        "data": data,
        "error": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _err(msg: str) -> dict:
    return {
        "success": False,
        "data": None,
        "error": msg,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    """健康检查。"""
    return _ok({"status": "ok", "version": "1.0.0-mvp"})


@app.get("/api/cases")
def get_cases():
    """获取所有案例列表。"""
    cases = load_all_cases()
    summaries = []
    for c in cases:
        summaries.append({
            "case_id": c.case_id,
            "title": c.title,
            "scenario_type": c.scenario_type,
            "question": c.question,
            "n_evidences": len(c.evidences),
            "n_poisoned": len(c.poisoned_evidence_ids),
        })
    return _ok(summaries)


@app.post("/api/run_case/{case_id}")
def run_case(case_id: str):
    """运行完整检测闭环。"""
    if case_id not in list_case_ids():
        return _err(f"案例不存在: {case_id}")

    result = run_pipeline(case_id)
    if result is None:
        return _err(f"流水线执行失败: {case_id}")

    return _ok(result.model_dump())


class SearchRequest(BaseModel):
    question: str
    case_id: str
    top_k: int = 5


@app.post("/api/search")
def api_search(req: SearchRequest):
    """模拟 RAG 检索 Top-K。"""
    case = load_case(req.case_id)
    if case is None:
        return _err(f"案例不存在: {req.case_id}")

    evidences = process_evidences(case.evidences)
    result = search(req.question, evidences, top_k=req.top_k, rewrites=case.query_rewrites)

    topk = []
    for ev in result.top_k_evidences:
        topk.append({
            "evidence_id": ev.evidence_id,
            "rank": ev.retrieval_rank,
            "score": round(ev.retrieval_score or 0, 4),
            "is_poisoned": ev.is_poisoned,
            "content_preview": ev.content[:80] + "..." if len(ev.content) > 80 else ev.content,
        })
    return _ok({
        "top_k": topk,
        "hit_counts": result.hit_counts,
        "rank_variance": {k: round(v, 4) for k, v in result.rank_variance.items()},
    })


class DetectRequest(BaseModel):
    case_id: str
    top_k: list[str] | None = None
    evidence_ids: list[str] | None = None


@app.post("/api/detect")
def api_detect(req: DetectRequest):
    """计算 RAS/GIS/DualRisk。"""
    case = load_case(req.case_id)
    if case is None:
        return _err(f"案例不存在: {req.case_id}")

    evidences = process_evidences(case.evidences)
    result = search(case.question, evidences, top_k=min(5, len(evidences)),
                    rewrites=case.query_rewrites)
    top_k = result.top_k_evidences

    selected_ids = req.top_k or req.evidence_ids
    if selected_ids:
        top_k = [ev for ev in top_k if ev.evidence_id in selected_ids]

    det = detect(
        query=case.question,
        top_k_evidences=top_k,
        all_evidences=evidences,
        target_wrong_answer=case.target_wrong_answer,
        hit_counts=result.hit_counts,
        total_queries=1 + len(case.query_rewrites),
        rank_variances=result.rank_variance,
    )
    return _ok([d.model_dump() for d in det])


class CounterfactualRequest(BaseModel):
    case_id: str
    suspicious_evidence_id: str


@app.post("/api/counterfactual")
def api_counterfactual(req: CounterfactualRequest):
    """四路反事实验证。"""
    case = load_case(req.case_id)
    if case is None:
        return _err(f"案例不存在: {req.case_id}")

    evidences = process_evidences(case.evidences)
    result = search(case.question, evidences, top_k=min(5, len(evidences)),
                    rewrites=case.query_rewrites)

    suspicious = next(
        (ev for ev in result.top_k_evidences if ev.evidence_id == req.suspicious_evidence_id),
        None,
    )
    if suspicious is None:
        return _err(f"证据不在 Top-K 中: {req.suspicious_evidence_id}")

    cf = run_counterfactual(
        query=case.question,
        suspicious_evidence=suspicious,
        top_k_evidences=result.top_k_evidences,
        all_evidences=evidences,
        target_wrong_answer=case.target_wrong_answer,
        trusted_evidence_ids=case.trusted_evidence_ids,
    )
    return _ok(cf.model_dump())


class GraphRequest(BaseModel):
    case_id: str


@app.post("/api/graph")
def api_graph(req: GraphRequest):
    """构建投毒传播图谱。"""
    case = load_case(req.case_id)
    if case is None:
        return _err(f"案例不存在: {req.case_id}")

    evidences = process_evidences(case.evidences)
    result = search(case.question, evidences, top_k=min(5, len(evidences)),
                    rewrites=case.query_rewrites)
    top_k = result.top_k_evidences

    from .services.counterfactual import _template_generate
    original_answer = _template_generate(case.question, top_k)

    claims_text = split_claims(original_answer)
    matrix = build_claim_evidence_matrix(claims_text, top_k)

    graph = build_graph(
        evidences=evidences,
        query=case.question,
        claims=matrix,
        original_answer=original_answer,
    )
    return _ok(graph.model_dump())


class TrustRequest(BaseModel):
    case_id: str
    answer: str | None = None


@app.post("/api/trust")
def api_trust(req: TrustRequest):
    """计算声明—证据矩阵和 TrustScore。"""
    case = load_case(req.case_id)
    if case is None:
        return _err(f"案例不存在: {req.case_id}")

    evidences = process_evidences(case.evidences)
    result = search(case.question, evidences, top_k=min(5, len(evidences)),
                    rewrites=case.query_rewrites)
    top_k = result.top_k_evidences

    from .services.counterfactual import _template_generate
    answer = req.answer or _template_generate(case.question, top_k)

    claims_text = split_claims(answer)
    matrix = build_claim_evidence_matrix(claims_text, top_k)

    det = detect(
        query=case.question,
        top_k_evidences=top_k,
        all_evidences=evidences,
        target_wrong_answer=case.target_wrong_answer,
    )

    trust = compute_full_trust_score(
        matrix=matrix,
        evidences=top_k,
        detection_results=det,
    )

    return _ok({
        "claims": claims_text,
        "matrix": [r.model_dump() for r in matrix],
        "trust_score": trust.model_dump(),
    })


class RegenerateRequest(BaseModel):
    case_id: str
    isolated_ids: list[str] | None = None


@app.post("/api/regenerate")
def api_regenerate(req: RegenerateRequest):
    """隔离后可信重生成。"""
    case = load_case(req.case_id)
    if case is None:
        return _err(f"案例不存在: {req.case_id}")

    pipeline_result = run_pipeline(req.case_id)
    if pipeline_result is None:
        return _err(f"流水线执行失败: {req.case_id}")

    evidences = process_evidences(case.evidences)
    det = pipeline_result.detection_results
    isolated = (
        req.isolated_ids
        if req.isolated_ids is not None
        else pipeline_result.isolated_evidences
    )

    trusted_top_k = risk_aware_search(
        query=case.question,
        all_evidences=evidences,
        isolated_ids=isolated,
        detection_results=det,
    )

    regenerated = regenerate_trusted_answer(case.question, trusted_top_k)

    return _ok({
        "isolated_evidences": isolated,
        "trusted_evidence_ids": [ev.evidence_id for ev in trusted_top_k],
        "regenerated_answer": regenerated,
    })
