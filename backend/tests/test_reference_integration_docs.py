from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_reference_integration_docs_exist() -> None:
    assert (ROOT / "docs" / "reference_integration_notes.md").exists()
    assert (ROOT / "docs" / "rag_workflow_reference_mapping.md").exists()
    assert (ROOT / "docs" / "dev_audit_rag_reference.md").exists()


def test_readme_mentions_reference_langchain_mapping() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "参考 LangChain RAG 工程实现的系统改造" in readme
    assert "FAISS 或 TF-IDF 索引" in readme


def test_docs_do_not_contain_real_secrets() -> None:
    files = [
        ROOT / "README.md",
        ROOT / "docs" / "reference_integration_notes.md",
        ROOT / "docs" / "rag_workflow_reference_mapping.md",
        ROOT / "backend" / "tests" / "test_reference_integration_docs.py",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in files)

    assert not re.search(r"sk-[A-Za-z0-9]{20,}", text)
    forbidden_pg = "postgresql://" + "postgres:123456"
    forbidden_key_assignment = "DASHSCOPE_API_KEY" + "="
    assert forbidden_pg not in text
    assert forbidden_key_assignment not in text
