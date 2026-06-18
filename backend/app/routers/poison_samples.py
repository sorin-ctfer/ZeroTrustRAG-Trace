"""Local defensive poison sample library API."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..services.interactive_rag_service import interactive_rag_service
from ..services.poison_samples import poison_sample_service

router = APIRouter(prefix="/api/poison-samples", tags=["poison-samples"])


class PoisonSampleRequest(BaseModel):
    target_query: str
    content: str
    target_wrong_answer: str
    correct_answer: str
    attack_type: str
    source: str = "本地演示投毒样本"
    enabled: bool = True


class InjectRequest(BaseModel):
    session_id: str
    sample_id: str


class LoadFromTrainingRequest(BaseModel):
    limit: int = 80


def _ok(data=None):
    return {"success": True, "data": data, "error": None}


def _err(message: str):
    return {"success": False, "data": None, "error": message}


@router.post("/create")
def create(req: PoisonSampleRequest):
    try:
        return _ok(poison_sample_service.create(**req.model_dump()))
    except ValueError as exc:
        return _err(str(exc))


@router.post("/load-demo")
def load_demo():
    try:
        return _ok(poison_sample_service.load_demo())
    except ValueError as exc:
        return _err(str(exc))


@router.post("/load-from-training")
def load_from_training(req: LoadFromTrainingRequest):
    return _ok(poison_sample_service.load_from_training_datasets(req.limit))


@router.get("/list")
def list_samples():
    return _ok(poison_sample_service.list_samples())


@router.post("/{sample_id}/enable")
def enable(sample_id: str):
    try:
        return _ok(poison_sample_service.set_enabled(sample_id, True))
    except ValueError as exc:
        return _err(str(exc))


@router.post("/{sample_id}/disable")
def disable(sample_id: str):
    try:
        return _ok(poison_sample_service.set_enabled(sample_id, False))
    except ValueError as exc:
        return _err(str(exc))


@router.delete("/{sample_id}")
def delete(sample_id: str):
    try:
        poison_sample_service.delete(sample_id)
        return _ok({"deleted": sample_id})
    except ValueError as exc:
        return _err(str(exc))


@router.post("/inject-to-session")
def inject_to_session(req: InjectRequest):
    try:
        return _ok(interactive_rag_service.inject_poison_sample(req.session_id, req.sample_id))
    except ValueError as exc:
        return _err(str(exc))
