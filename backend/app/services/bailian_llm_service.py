"""LangChain adapters for local Ollama and Alibaba Cloud Bailian."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from langchain_core.embeddings import Embeddings

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"


class BailianConfigurationError(RuntimeError):
    """Raised when Bailian credentials are unavailable."""


class OllamaConfigurationError(RuntimeError):
    """Raised when local Ollama is requested but unavailable."""


class _ChatResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class OllamaChatModel:
    """Small LangChain-compatible local chat adapter.

    Existing services only call ``invoke(messages).content``. Keeping this
    narrow interface avoids a hard dependency on langchain-ollama while still
    using the local Ollama HTTP API.
    """

    def __init__(self, base_url: str, model: str, timeout: float, options: dict[str, Any] | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.options = options or {}

    def invoke(self, messages: list[Any]) -> _ChatResponse:
        payload_messages = []
        for message in messages:
            message_type = getattr(message, "type", "")
            role = "system" if message_type == "system" else "user"
            if message_type == "ai":
                role = "assistant"
            payload_messages.append({"role": role, "content": str(getattr(message, "content", message))})
        with httpx.Client(timeout=self.timeout, trust_env=False) as client:
            response = client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": payload_messages,
                    "stream": False,
                    "keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", "30m"),
                    "options": self.options,
                },
            )
            response.raise_for_status()
            data = response.json()
        return _ChatResponse(str(data.get("message", {}).get("content", "")))


class OllamaEmbeddings(Embeddings):
    """LangChain Embeddings adapter backed by Ollama's local HTTP API."""

    def __init__(self, base_url: str, model: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def _embed_one(self, text: str) -> list[float]:
        with httpx.Client(timeout=self.timeout, trust_env=False) as client:
            response = client.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": text},
            )
            if response.status_code == 404:
                response = client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
            response.raise_for_status()
            data = response.json()
        if "embeddings" in data:
            embeddings = data["embeddings"]
            return [float(value) for value in (embeddings[0] if embeddings else [])]
        return [float(value) for value in data.get("embedding", [])]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text)


class EvidenceExtractiveChatModel:
    """Last-resort deterministic answer from supplied retrieved evidence.

    This is intentionally extractive: it does not invent sample content or
    template questions, and exists only when no configured LLM provider is
    reachable.
    """

    def invoke(self, messages: list[Any]) -> _ChatResponse:
        user_text = "\n\n".join(str(getattr(message, "content", message)) for message in messages)
        chunk_ids = []
        contents = []
        for block in user_text.split("["):
            if "chunk_id=" not in block:
                continue
            head, _, tail = block.partition("]")
            chunk_id = head.split("chunk_id=", 1)[1].split("|", 1)[0].strip()
            content = tail.strip()
            if chunk_id and content:
                chunk_ids.append(chunk_id)
                contents.append(content)
        if contents:
            return _ChatResponse(f"{contents[0]}\n\n引用的 chunk_id：{', '.join(chunk_ids[:5])}")
        return _ChatResponse("证据不足。")


class ResilientChatModel:
    """Try configured providers in order, then fall back to evidence extraction."""

    def __init__(self, providers: list[tuple[str, Any]]) -> None:
        self.providers = providers
        self.fallback = EvidenceExtractiveChatModel()
        self.last_provider = "unknown"
        self.last_error = ""

    def invoke(self, messages: list[Any]) -> Any:
        for provider, model in self.providers:
            try:
                response = model.invoke(messages)
                self.last_provider = provider
                self.last_error = ""
                return response
            except Exception as exc:
                self.last_error = f"{provider}: {exc}"
        self.last_provider = "extractive"
        return self.fallback.invoke(messages)


def _truthy(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).strip().rstrip("/")


def _ollama_available() -> bool:
    try:
        with httpx.Client(timeout=float(os.getenv("OLLAMA_STATUS_TIMEOUT", "2")), trust_env=False) as client:
            response = client.get(f"{_ollama_base_url()}/api/tags")
            response.raise_for_status()
        return True
    except Exception:
        return False


def _prefer_ollama() -> bool:
    provider = os.getenv("LLM_PROVIDER", "auto").strip().lower()
    if provider == "ollama":
        return True
    if provider == "bailian":
        return False
    return _truthy("OLLAMA_ENABLED", "true") and _ollama_available()


def _bailian_configured() -> bool:
    return _truthy("BAILIAN_ENABLED") and bool(os.getenv("DASHSCOPE_API_KEY", "").strip())


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _ollama_chat_options() -> dict[str, Any]:
    return {
        "num_predict": max(32, min(2048, _int_env("OLLAMA_NUM_PREDICT", 256))),
        "num_ctx": max(512, min(8192, _int_env("OLLAMA_NUM_CTX", 2048))),
        "temperature": max(0.0, min(2.0, _float_env("OLLAMA_TEMPERATURE", 0.1))),
    }


def _api_key() -> str:
    enabled = _truthy("BAILIAN_ENABLED")
    if not enabled:
        raise BailianConfigurationError(
            "BAILIAN_ENABLED is not true. Bailian is required for AI generation."
        )
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        raise BailianConfigurationError(
            "DASHSCOPE_API_KEY is not configured. "
            "Please configure it in backend/.env and restart the backend."
        )
    return api_key


def bailian_status() -> dict[str, object]:
    """Return local configuration status without making a network request."""
    enabled = _truthy("BAILIAN_ENABLED")
    has_api_key = bool(os.getenv("DASHSCOPE_API_KEY", "").strip())
    ollama_available = _ollama_available()
    prefer_ollama = _prefer_ollama()
    bailian_ready = _bailian_configured()
    provider = "ollama" if prefer_ollama else "bailian" if bailian_ready else "extractive"
    fallback_chain = []
    if prefer_ollama:
        fallback_chain.append("ollama")
    if bailian_ready:
        fallback_chain.append("bailian")
    fallback_chain.append("extractive")
    return {
        "provider": provider,
        "fallback_chain": fallback_chain,
        "ollama_enabled": _truthy("OLLAMA_ENABLED", "true"),
        "ollama_available": ollama_available,
        "ollama_base_url": _ollama_base_url(),
        "ollama_chat_model": os.getenv("OLLAMA_CHAT_MODEL", "qwen3.5:9b"),
        "ollama_embedding_model": os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text:latest"),
        "enabled": enabled,
        "configured": enabled and has_api_key,
        "has_api_key": has_api_key,
        "chat_model": os.getenv("BAILIAN_CHAT_MODEL", "qwen-plus"),
        "embedding_model": os.getenv("BAILIAN_EMBEDDING_MODEL", "text-embedding-v4"),
        "base_url": os.getenv("BAILIAN_BASE_URL", DEFAULT_BASE_URL),
        "mode": "本地 Ollama 优先 / 百炼兜底" if provider == "ollama" and bailian_ready else (
            "本地 Ollama" if provider == "ollama" else ("百炼大模型" if enabled and has_api_key else "本地证据抽取")
        ),
    }


@lru_cache(maxsize=1)
def get_chat_model():
    """Return a local Ollama chat model or Bailian OpenAI-compatible model."""
    providers: list[tuple[str, Any]] = []
    if _prefer_ollama():
        providers.append(("ollama", OllamaChatModel(
            base_url=_ollama_base_url(),
            model=os.getenv("OLLAMA_CHAT_MODEL", "qwen3.5:9b"),
            timeout=float(os.getenv("OLLAMA_CHAT_TIMEOUT", "120")),
            options=_ollama_chat_options(),
        )))
    if _bailian_configured():
        from langchain_openai import ChatOpenAI

        providers.append(("bailian", ChatOpenAI(
            api_key=_api_key(),
            base_url=os.getenv("BAILIAN_BASE_URL", DEFAULT_BASE_URL),
            model=os.getenv("BAILIAN_CHAT_MODEL", "qwen-plus"),
            temperature=0.2,
            timeout=float(os.getenv("BAILIAN_CHAT_TIMEOUT", "45")),
            max_retries=int(os.getenv("BAILIAN_CHAT_MAX_RETRIES", "2")),
        )))
    if not providers:
        return EvidenceExtractiveChatModel()
    return ResilientChatModel(providers)


@lru_cache(maxsize=1)
def get_embeddings():
    """Return local Ollama embeddings or DashScope embeddings."""
    if _prefer_ollama():
        return OllamaEmbeddings(
            base_url=_ollama_base_url(),
            model=os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text:latest"),
            timeout=float(os.getenv("OLLAMA_EMBEDDING_TIMEOUT", "60")),
        )
    if not _bailian_configured():
        raise BailianConfigurationError("No embedding provider is configured.")

    from langchain_community.embeddings import DashScopeEmbeddings

    return DashScopeEmbeddings(
        dashscope_api_key=_api_key(),
        model=os.getenv("BAILIAN_EMBEDDING_MODEL", "text-embedding-v4"),
    )


def rag_top_k() -> int:
    """Read and constrain the configured retrieval depth."""
    try:
        return max(1, min(20, int(os.getenv("RAG_TOP_K", "5"))))
    except ValueError:
        return 5
