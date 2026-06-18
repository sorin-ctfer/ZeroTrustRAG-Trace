"""External trusted knowledge API."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel

from ..services.external_knowledge import external_knowledge_service

router = APIRouter(prefix="/api/external-knowledge", tags=["external-knowledge"])


class DatasetCleanRequest(BaseModel):
    jsonl: str
    dataset_name: str = "JSONL 数据集"


def _ok(data=None):
    return {"success": True, "data": data, "error": None}


def _err(message: str):
    return {"success": False, "data": None, "error": message}


@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    try:
        return _ok(external_knowledge_service.upload_document(file.filename or "upload.txt", await file.read()))
    except ValueError as exc:
        return _err(str(exc))


@router.post("/import-dataset-clean")
def import_dataset_clean(req: DatasetCleanRequest):
    try:
        return _ok(external_knowledge_service.import_dataset_clean(req.jsonl, req.dataset_name))
    except Exception as exc:
        return _err(str(exc))


@router.post("/load-demo")
def load_demo():
    return _ok(external_knowledge_service.load_demo())


@router.get("/chunks")
def chunks():
    return _ok(external_knowledge_service.list_chunks())


@router.get("/stats")
def stats():
    return _ok(external_knowledge_service.stats())


@router.post("/rebuild-index")
def rebuild_index():
    return _ok(external_knowledge_service.rebuild_index())


@router.post("/clear")
def clear():
    external_knowledge_service.clear()
    return _ok([])
