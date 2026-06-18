"""Dataset and trainable detector API."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..services.public_dataset_ingestion import public_dataset_ingestion_service
from ..services.rag_detector_training import rag_detector_training_service

router = APIRouter(prefix="/api", tags=["rag-training"])


class JsonlRequest(BaseModel):
    jsonl: str
    name: str = "imported_jsonl"


class TrainRequest(BaseModel):
    model_type: str = "logistic_regression"


class PredictRequest(BaseModel):
    texts: list[str]
    query: str = ""
    correct_answer: str = ""
    target_wrong_answer: str = ""


class PublicDatasetRequest(BaseModel):
    source_keys: list[str] | None = None
    source_key: str | None = None
    limit: int | None = None
    force: bool = False


def _ok(data=None):
    return {"success": True, "data": data, "error": None}


def _err(message: str):
    return {"success": False, "data": None, "error": message}


@router.post("/datasets/import")
def import_dataset(req: JsonlRequest):
    try:
        return _ok(rag_detector_training_service.import_jsonl(req.jsonl, req.name))
    except Exception as exc:
        return _err(str(exc))


@router.get("/datasets/list")
def list_datasets():
    return _ok(rag_detector_training_service.list_datasets())


@router.get("/datasets/stats")
def dataset_stats():
    return _ok(rag_detector_training_service.stats())


@router.get("/datasets/samples")
def dataset_samples():
    return _ok(rag_detector_training_service.samples())


@router.post("/datasets/reset")
def reset_datasets():
    rag_detector_training_service.reset()
    return _ok([])


@router.post("/datasets/load-demo")
def load_demo_dataset():
    return _ok(rag_detector_training_service.load_demo())


@router.post("/training/rag-detector/train")
def train(req: TrainRequest):
    try:
        return _ok(rag_detector_training_service.train(req.model_type))
    except ValueError as exc:
        return _err(str(exc))


@router.get("/training/rag-detector/status")
def status():
    return _ok(rag_detector_training_service.status())


@router.get("/training/rag-detector/metrics")
def metrics():
    return _ok(rag_detector_training_service.metrics())


@router.post("/training/rag-detector/evaluate")
def evaluate(req: JsonlRequest):
    try:
        return _ok(rag_detector_training_service.evaluate(req.jsonl))
    except Exception as exc:
        return _err(str(exc))


@router.post("/training/rag-detector/predict")
def predict(req: PredictRequest):
    return _ok(rag_detector_training_service.predict(req.texts, req.query, req.correct_answer, req.target_wrong_answer))


@router.get("/datasets/public/sources")
def public_sources():
    return _ok(public_dataset_ingestion_service.sources())


@router.post("/datasets/public/download")
def public_download(req: PublicDatasetRequest):
    try:
        return _ok(public_dataset_ingestion_service.download(req.source_keys, req.force))
    except Exception as exc:
        return _err(str(exc))


@router.post("/datasets/public/convert")
def public_convert(req: PublicDatasetRequest):
    try:
        if req.source_key:
            return _ok(public_dataset_ingestion_service.convert(req.source_key, req.limit))
        return _ok(public_dataset_ingestion_service.convert_all(req.limit))
    except Exception as exc:
        return _err(str(exc))


@router.post("/datasets/public/import-training")
def public_import_training(req: PublicDatasetRequest):
    try:
        if req.source_key:
            return _ok(public_dataset_ingestion_service.import_training(req.source_key, req.limit))
        return _ok(public_dataset_ingestion_service.import_all_training(req.limit))
    except Exception as exc:
        return _err(str(exc))


@router.post("/datasets/public/import-clean-knowledge")
def public_import_clean_knowledge(req: PublicDatasetRequest):
    try:
        if not req.source_key:
            return _err("source_key is required")
        return _ok(public_dataset_ingestion_service.import_clean_knowledge(req.source_key, req.limit))
    except Exception as exc:
        return _err(str(exc))
