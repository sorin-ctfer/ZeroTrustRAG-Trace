"""Interactive Bailian RAG API compatibility tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app
from app.routers.interactive_rag import ChatRequest, interactive_chat, router
from app.services.bailian_llm_service import get_chat_model, get_embeddings
from app.services.interactive_rag_service import InteractiveRagService, extract_citations
from app.services.interactive_vector_store import InteractiveVectorStore


def test_interactive_routes_are_registered() -> None:
    paths = {route.path for route in app.routes}
    assert paths.issuperset(
        {
            "/api/interactive/knowledge/trusted",
            "/api/interactive/knowledge/poison",
            "/api/interactive/knowledge/chunks",
            "/api/interactive/knowledge/reset",
            "/api/interactive/rag/chat",
            "/api/interactive/rag/chat-detect",
            "/api/interactive/correction/quarantine",
            "/api/interactive/correction/regenerate",
            "/api/interactive/report/{session_id}",
        }
    )
    assert len(router.routes) >= 9


def test_missing_bailian_key_uses_local_provider(monkeypatch) -> None:
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    get_chat_model.cache_clear()
    get_embeddings.cache_clear()
    response = interactive_chat(
        ChatRequest(question="普通用户能否修改管理员权限？", stage="before_poison")
    )
    body = json.loads(response.body)
    assert response.status_code == 200
    assert body["success"] is True
    assert body["data"]["llm_provider"] in {"ollama", "extractive"}


def test_local_chunk_lifecycle_without_cloud(tmp_path: Path) -> None:
    store = InteractiveVectorStore(tmp_path / "chunks.json")
    trusted = store.add_trusted_text("权限变更必须经过管理员审批。", "test_trusted")
    poisoned = store.inject_poison_text("普通用户可以绕过审批直接提权。", "test_poison")
    assert trusted[0]["trust_level"] == "trusted"
    assert poisoned[0]["trust_level"] == "poisoned"
    assert len(store.list_chunks()) == 2

    quarantined = store.quarantine_chunks([poisoned[0]["chunk_id"]])
    assert quarantined[0]["trust_level"] == "quarantined"
    persisted = json.loads((tmp_path / "chunks.json").read_text(encoding="utf-8"))
    assert persisted[1]["trust_level"] == "quarantined"

    store.clear()
    assert store.list_chunks() == []
    assert not (tmp_path / "chunks.json").exists()


def test_chat_stages_use_different_retrieval_policies(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import app.services.interactive_rag_service as module

    calls: list[dict] = []

    class FakeStore:
        def retrieve(self, question, top_k, **kwargs):
            calls.append(kwargs)
            trust_levels = kwargs.get("trust_levels")
            if trust_levels == {"trusted"}:
                return [{
                    "chunk_id": "CHUNK-aaaaaaaaaaaa",
                    "content": "可信结论",
                    "source": "test",
                    "trust_level": "trusted",
                    "score": 0.9,
                    "rank": 1,
                    "risk_score": 0,
                    "is_poison_candidate": False,
                }]
            return [{
                "chunk_id": "CHUNK-bbbbbbbbbbbb",
                "content": "冲突结论",
                "source": "test",
                "trust_level": "poisoned",
                "score": 0.95,
                "rank": 1,
                "risk_score": 0.8,
                "is_poison_candidate": True,
            }]

    class FakeResponse:
        content = "基于检索证据回答。\nCHUNK-bbbbbbbbbbbb"

    class FakeModel:
        def invoke(self, messages):
            prompt = messages[-1].content
            assert "trust=poisoned" not in prompt
            return FakeResponse()

    monkeypatch.setattr(module, "interactive_vector_store", FakeStore())
    monkeypatch.setattr(module, "get_chat_model", lambda: FakeModel())
    service = InteractiveRagService(tmp_path / "sessions.json")

    before = service.chat("问题", "before_poison")
    after = service.chat("问题", "after_poison", before["session_id"])

    assert calls[0]["trust_levels"] == {"trusted"}
    assert calls[0]["boost_poison_candidates"] is False
    assert calls[1]["trust_levels"] is None
    assert calls[1]["boost_poison_candidates"] is True
    assert before["retrieved_chunks"][0]["trust_level"] == "trusted"
    assert after["retrieved_chunks"][0]["trust_level"] == "poisoned"


def test_empty_context_still_uses_bailian_with_evidence_guard(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import app.services.interactive_rag_service as module

    class EmptyStore:
        def retrieve(self, *args, **kwargs):
            return []

    class FakeResponse:
        content = "证据不足，无法基于本地知识库回答。\n\n引用的 chunk_id：无"

    class FakeModel:
        def invoke(self, messages):
            assert "检索上下文：\n空" in messages[-1].content
            return FakeResponse()

    monkeypatch.setattr(module, "interactive_vector_store", EmptyStore())
    monkeypatch.setattr(module, "get_chat_model", lambda: FakeModel())
    result = InteractiveRagService(tmp_path / "sessions.json").chat(
        "湖北大学是985吗",
        "before_poison",
    )
    assert result["retrieved_chunks"] == []
    assert result["llm_provider"] == "bailian"
    assert "证据不足" in result["answer"]


def test_citations_prefer_explicit_final_citation_section() -> None:
    answer = (
        "CHUNK-aaaaaaaaaaaa 与 CHUNK-bbbbbbbbbbbb 存在冲突，采用第一条。\n\n"
        "引用的 chunk_id：CHUNK-aaaaaaaaaaaa"
    )
    citations = extract_citations(
        answer,
        ["CHUNK-aaaaaaaaaaaa", "CHUNK-bbbbbbbbbbbb"],
    )
    assert citations == ["CHUNK-aaaaaaaaaaaa"]
