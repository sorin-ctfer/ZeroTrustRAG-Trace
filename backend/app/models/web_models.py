"""Web 原型新增的数据模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PoisonSampleRequest(BaseModel):
    """手动添加本地模拟投毒样本。"""

    content: str
    source: str = "手动模拟投毒样本"
    source_type: str = "rag_document"
    title: str = "本地模拟投毒样本"


class RagAnalyzeRequest(BaseModel):
    """RAG 投毒分析请求。"""

    query: str
    original_answer: str
    top_k: int = Field(default=5, ge=1, le=20)
    case_id: str | None = None


class AgentDemoRequest(BaseModel):
    """多 Agent 演示请求。"""

    case_id: str = "case_threat_intel_false_consensus"


class CaseRequest(BaseModel):
    """仅包含案例 ID 的通用请求。"""

    case_id: str


class CascadeRequest(BaseModel):
    """级联错误检测请求。"""

    case_id: str = "case_threat_intel_false_consensus"
    claims: list[dict] | None = None


class PoisonDetectRequest(BaseModel):
    """知识投毒检测请求。"""

    query: str
    answer: str
    top_k: int = Field(default=5, ge=1, le=20)


class TraceRequest(BaseModel):
    """IPJG 联合溯源请求。"""

    case_id: str = "case_threat_intel_false_consensus"


class CorrectionRequest(BaseModel):
    """可信纠偏请求。"""

    case_id: str
    query: str | None = None
    original_answer: str | None = None

