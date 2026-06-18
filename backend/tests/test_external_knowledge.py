from __future__ import annotations

import json
from pathlib import Path

from app.services.external_knowledge import ExternalKnowledgeService


def test_external_knowledge_can_import_and_stats(tmp_path: Path) -> None:
    service = ExternalKnowledgeService(tmp_path / "external.json")
    created = service.import_dataset_clean(
        json.dumps({"clean_chunks": ["权限变更必须审批。", "漏洞状态必须复核。"]}, ensure_ascii=False),
        "unit_dataset",
    )

    assert len(created) == 2
    assert all(item["trust_label"] == "trusted" for item in created)
    stats = service.stats()
    assert stats["chunk_count"] == 2
    assert stats["embedding_ready"] == 2
    assert service.retrieve("权限变更是否审批？", top_k=1)[0]["trust_label"] == "trusted"


def test_external_knowledge_upload_does_not_create_poison(tmp_path: Path) -> None:
    service = ExternalKnowledgeService(tmp_path / "external.json")
    chunks = service.upload_document("policy.txt", "普通用户不得修改管理员权限。".encode())

    assert chunks[0]["source_type"] == "external_knowledge"
    assert chunks[0]["trust_label"] == "trusted"
    assert "hash" in chunks[0]["content_hash"] or chunks[0]["content_hash"]
