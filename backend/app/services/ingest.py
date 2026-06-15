"""
证据入库与预处理：补全哈希、设置初始检索字段。
"""

from __future__ import annotations

from typing import Protocol

from ..models.schema import Evidence
from ..utils.text_utils import sha256_hash


class EvidenceIngestProtocol(Protocol):
    """证据预处理实现的可替换接口。"""

    def process(self, evidences: list[Evidence]) -> list[Evidence]:
        """标准化证据并返回独立副本。"""
        ...


def process_evidences(evidences: list[Evidence]) -> list[Evidence]:
    """
    对证据列表进行预处理：
    1. 补全 content_hash
    2. 确保字段完整性
    """
    processed = [ev.model_copy(deep=True) for ev in evidences]
    for ev in processed:
        if not ev.content_hash:
            ev.content_hash = sha256_hash(ev.content)
        if not ev.chunk_id:
            ev.chunk_id = f"CHUNK-{ev.evidence_id}"
        if not ev.document_id:
            ev.document_id = f"DOC-{ev.evidence_id}"
    return processed
