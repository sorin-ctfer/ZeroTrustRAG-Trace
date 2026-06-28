"""RAG evaluation API routes."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..services.rag_evaluation.evaluator import rag_evaluation_service
from ..services.rag_evaluation.schemas import EvaluationConfig


router = APIRouter(prefix="/api/rag-evaluation", tags=["rag-evaluation"])


class EvaluationRequest(BaseModel):
    dataset: str = "all"
    mode: str = "sample"
    methods: list[str] = Field(default_factory=lambda: ["ras_only", "gis_only", "dualrisk", "dualrisk_cluster", "dualrisk_causal", "full_method"])
    top_k: list[int] = Field(default_factory=lambda: [3, 5, 10])
    poison_ratios: list[float] = Field(default_factory=lambda: [0.01, 0.03, 0.05, 0.10])
    ras_threshold: float = 0.6
    gis_threshold: float = 0.45
    dualrisk_threshold: float = 0.25
    cluster_threshold: float = 0.35
    causal_threshold: float = 0.5
    cluster_causal_threshold: float = 0.5
    cluster_lambda: float = 0.5
    retrieval_mode: str = "faiss"
    subset_per_dataset: int = 100
    causal_weights: dict[str, float] | None = None
    safe_rerank_weights: dict[str, float] | None = None
    trust_threshold: float = 60.0


def _ok(data=None):
    return {"success": True, "data": data, "error": None}


def _err(message: str):
    return {"success": False, "data": None, "error": message}


def _config(req: EvaluationRequest) -> EvaluationConfig:
    return EvaluationConfig.from_mapping(req.model_dump())


@router.post("/prepare")
def prepare(req: EvaluationRequest):
    try:
        return _ok(rag_evaluation_service.prepare(_config(req)))
    except Exception as exc:
        return _err(str(exc))


@router.post("/run")
def run(req: EvaluationRequest | None = None):
    try:
        config = _config(req) if req else None
        return _ok(rag_evaluation_service.start_run(config))
    except Exception as exc:
        return _err(str(exc))


@router.get("/progress")
def progress():
    return _ok(rag_evaluation_service.progress())


@router.get("/results")
def results():
    return _ok(rag_evaluation_service.results())


@router.get("/cases/{sample_id}")
def case_details(sample_id: str):
    return _ok(rag_evaluation_service.case_details(sample_id))


@router.get("/counterfactual/{scenario_id}")
def counterfactual(scenario_id: str):
    return _ok(rag_evaluation_service.scenario_artifact(scenario_id, "counterfactual"))


@router.get("/trace/{scenario_id}")
def trace(scenario_id: str):
    return _ok(rag_evaluation_service.scenario_artifact(scenario_id, "trace"))


@router.get("/correction/{scenario_id}")
def correction(scenario_id: str):
    return _ok(rag_evaluation_service.scenario_artifact(scenario_id, "correction"))
