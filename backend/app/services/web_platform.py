"""完整 Web 原型的知识库、多 Agent、级联检测、溯源与纠偏服务。"""

from __future__ import annotations

import json
import math
import re
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx

from ..models.schema import Evidence
from ..services.counterfactual import run_counterfactual
from ..services.detection import detect
from ..services.ingest import process_evidences
from ..services.regeneration import isolate_high_risk, regenerate_trusted_answer, risk_aware_search
from ..services.retrieval import search
from ..services.trust_score import build_claim_evidence_matrix, compute_full_trust_score
from ..utils.score_utils import clip
from ..utils.text_utils import TfidfRetriever, sha256_hash, split_claims

# ⚠️ 安全声明：以下数据仅为本地防御检测演示，不得用于真实攻击。
# 所有投毒样本仅在本地模拟环境中使用，不连接任何真实服务。

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STORE_PATH = DATA_DIR / "knowledge_store.json"
CASE_DIR = DATA_DIR / "web_cases"
REPORT_DIR = DATA_DIR / "reports"

AGENTS = [
    {"agent_id": "agent-planner", "name": "Planner Agent", "role": "planner"},
    {"agent_id": "agent-rag", "name": "RAG Retriever Agent", "role": "retriever"},
    {"agent_id": "agent-ti", "name": "Threat Intel Agent", "role": "threat_intel"},
    {"agent_id": "agent-verifier", "name": "Verifier Agent", "role": "verifier"},
    {"agent_id": "agent-decision", "name": "Decision Agent", "role": "decision"},
    {"agent_id": "agent-execution", "name": "Execution Agent", "role": "execution"},
]

ROLE_PERMISSIONS = {
    "planner": {"plan"},
    "retriever": {"retrieve", "cite"},
    "threat_intel": {"analyze", "cite"},
    "verifier": {"verify", "reject"},
    "decision": {"decide"},
    "execution": {"execute"},
}

_claims: list[dict[str, Any]] = []
_agent_graph: dict[str, Any] = {"nodes": [], "links": []}
_reports: dict[str, dict[str, Any]] = {}


def now_iso() -> str:
    """返回 UTC ISO 时间。"""
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def list_web_cases() -> list[dict[str, Any]]:
    """列出 Web 演示案例。"""
    cases = []
    for path in sorted(CASE_DIR.glob("*.json")):
        raw = _read_json(path, {})
        cases.append(
            {
                "case_id": raw.get("case_id"),
                "title": raw.get("title"),
                "scenario_type": raw.get("scenario_type"),
                "query": raw.get("question"),
                "original_answer": raw.get("original_answer", raw.get("target_wrong_answer", "")),
                "expected_answer": raw.get("true_answer"),
                "evidence_count": len(raw.get("evidences", [])),
                "poisoned_count": len(raw.get("poisoned_evidence_ids", [])),
            }
        )
    return cases


def get_web_case(case_id: str) -> dict[str, Any] | None:
    """读取一个 Web 演示案例。"""
    path = CASE_DIR / f"{case_id}.json"
    return _read_json(path, None)


def _stored_evidence(raw: dict[str, Any]) -> dict[str, Any]:
    """将案例证据转换为知识库展示格式。"""
    return {
        "evidence_id": raw["evidence_id"],
        "document_id": raw.get("document_id", ""),
        "chunk_id": raw.get("chunk_id", ""),
        "title": raw.get("title", ""),
        "content": raw["content"],
        "source": raw.get("source_name", raw.get("source", "")),
        "source_name": raw.get("source_name", raw.get("source", "")),
        "source_type": raw.get("source_type", "rag_document"),
        "content_hash": raw.get("content_hash") or sha256_hash(raw["content"]),
        "retrieval_score": raw.get("retrieval_score"),
        "retrieval_rank": raw.get("retrieval_rank"),
        "is_poisoned_label": raw.get("is_poisoned", raw.get("is_poisoned_label", False)),
        "is_poisoned": raw.get("is_poisoned", raw.get("is_poisoned_label", False)),
        "created_at": raw.get("created_at", raw.get("timestamp", now_iso())),
        "metadata": raw.get("metadata", {}),
    }


def list_knowledge() -> list[dict[str, Any]]:
    """读取当前本地知识库。"""
    return _read_json(STORE_PATH, [])


def load_demo_knowledge() -> list[dict[str, Any]]:
    """重置并加载三个内置案例的证据。"""
    evidences: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted(CASE_DIR.glob("*.json")):
        case = _read_json(path, {})
        for raw in case.get("evidences", []):
            item = _stored_evidence(raw)
            if item["evidence_id"] not in seen:
                evidences.append(item)
                seen.add(item["evidence_id"])
    _write_json(STORE_PATH, evidences)
    return evidences


def clear_knowledge() -> None:
    """清空本地知识库。"""
    _write_json(STORE_PATH, [])


def _split_document(text: str, max_chars: int = 240) -> list[str]:
    """按段落和句子切分文档，控制 Chunk 长度。"""
    segments = [part.strip() for part in re.split(r"\n{2,}|(?<=[。！？.!?])", text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for segment in segments:
        if current and len(current) + len(segment) > max_chars:
            chunks.append(current)
            current = segment
        else:
            current += segment
    if current:
        chunks.append(current)
    return chunks or ([text.strip()] if text.strip() else [])


def add_document(filename: str, content: str, poisoned: bool = False, source: str | None = None) -> list[dict[str, Any]]:
    """添加文本并生成 Evidence/Chunk。"""
    document_id = f"DOC-{uuid.uuid4().hex[:10].upper()}"
    created = now_iso()
    items = list_knowledge()
    created_items = []
    for index, chunk in enumerate(_split_document(content), 1):
        evidence_id = f"E-{uuid.uuid4().hex[:10].upper()}"
        item = {
            "evidence_id": evidence_id,
            "document_id": document_id,
            "chunk_id": f"{document_id}-CHUNK-{index:03d}",
            "title": filename,
            "content": chunk,
            "source": source or filename,
            "source_name": source or filename,
            "source_type": "rag_document",
            "content_hash": sha256_hash(chunk),
            "retrieval_score": None,
            "retrieval_rank": None,
            "is_poisoned_label": poisoned,
            "is_poisoned": poisoned,
            "created_at": created,
            "metadata": {"label": "poisoned" if poisoned else "clean", "uploaded": True},
        }
        items.append(item)
        created_items.append(item)
    _write_json(STORE_PATH, items)
    return created_items


def _to_evidence(raw: dict[str, Any]) -> Evidence:
    return Evidence(
        evidence_id=raw["evidence_id"],
        document_id=raw.get("document_id", ""),
        chunk_id=raw.get("chunk_id", ""),
        title=raw.get("title", ""),
        content=raw["content"],
        source_name=raw.get("source_name", raw.get("source", "")),
        source_type="web" if raw.get("source_type") == "web" else "rag_document",
        content_hash=raw.get("content_hash", ""),
        timestamp=raw.get("created_at"),
        is_poisoned=raw.get("is_poisoned", raw.get("is_poisoned_label", False)),
        metadata=raw.get("metadata", {}),
    )


def dashboard_stats() -> dict[str, Any]:
    """计算仪表盘统计。"""
    evidence = list_knowledge()
    high_risk_evidence = sum(item.get("is_poisoned_label", False) for item in evidence)
    high_risk_agents = len({c["agent_id"] for c in _claims if c.get("risk_score", 0) >= 0.6})
    scores = [report.get("before_after_comparison", {}).get("after_trust_score", 0) for report in _reports.values()]
    return {
        "evidence_count": len(evidence),
        "chunk_count": len({item.get("chunk_id") for item in evidence}),
        "agent_count": len(AGENTS),
        "claim_count": len(_claims),
        "high_risk_evidence_count": high_risk_evidence,
        "high_risk_agent_count": high_risk_agents,
        "average_trust_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
    }


def analyze_rag(query: str, original_answer: str, top_k: int = 5, case_id: str | None = None) -> dict[str, Any]:
    """对本地知识库执行完整 RAG 投毒分析。"""
    case = get_web_case(case_id) if case_id else None
    raw_items = [_stored_evidence(item) for item in case.get("evidences", [])] if case else list_knowledge()
    if not raw_items:
        raw_items = load_demo_knowledge()
    evidences = process_evidences([_to_evidence(item) for item in raw_items])
    retrieval = search(query, evidences, top_k=min(top_k, len(evidences)))
    top_evidence = retrieval.top_k_evidences
    target_wrong = case.get("target_wrong_answer", original_answer) if case else original_answer
    detections = detect(
        query=query,
        top_k_evidences=top_evidence,
        all_evidences=evidences,
        target_wrong_answer=target_wrong,
        hit_counts=retrieval.hit_counts,
        rank_variances=retrieval.rank_variance,
    )
    suspicious = [item for item in detections if item.dual_risk >= 0.5]
    detection_map = {item.evidence_id: item for item in detections}
    counterfactual = []
    for result in suspicious:
        evidence = next(ev for ev in top_evidence if ev.evidence_id == result.evidence_id)
        cf = run_counterfactual(
            query=query,
            suspicious_evidence=evidence,
            top_k_evidences=top_evidence,
            all_evidences=evidences,
            target_wrong_answer=target_wrong,
            trusted_evidence_ids=case.get("trusted_evidence_ids", []) if case else [],
        )
        counterfactual.append(cf)
    claims = split_claims(original_answer)
    matrix = build_claim_evidence_matrix(claims, top_evidence)
    trust = compute_full_trust_score(matrix, top_evidence, detections, counterfactual)
    rows = []
    cf_map = {item.suspicious_evidence_id: item for item in counterfactual}
    for ev in top_evidence:
        det = detection_map[ev.evidence_id]
        rows.append(
            {
                **_stored_evidence(ev.model_dump()),
                "retrieval_score": round(ev.retrieval_score or 0, 4),
                "retrieval_rank": ev.retrieval_rank,
                **det.model_dump(),
                "causal_score": cf_map.get(ev.evidence_id).causal_score if ev.evidence_id in cf_map else 0.0,
            }
        )
    return {
        "query": query,
        "original_answer": original_answer,
        "top_k": rows,
        "suspicious_evidence": [item.evidence_id for item in suspicious],
        "counterfactual_results": [item.model_dump() for item in counterfactual],
        "trust_score": trust.model_dump(),
    }


def _claim(
    claim_id: str,
    agent: dict[str, str],
    content: str,
    evidence_ids: list[str],
    parent_ids: list[str],
    confidence: float,
    risk: float,
    action: str,
    signature: str = "valid",
) -> dict[str, Any]:
    return {
        "claim_id": claim_id,
        "agent_id": agent["agent_id"],
        "agent_name": agent["name"],
        "role": agent["role"],
        "content": content,
        "evidence_ids": evidence_ids,
        "parent_claim_ids": parent_ids,
        "confidence": confidence,
        "risk_score": risk,
        "signature_status": signature,
        "permission_status": action in ROLE_PERMISSIONS.get(agent["role"], set()),
        "required_action": action,
        "created_at": now_iso(),
    }


def validate_claims(claims: list[dict[str, Any]], evidence_ids: set[str]) -> list[dict[str, Any]]:
    """执行 Zero-Trust Claim Envelope 校验。"""
    agents = {item["agent_id"] for item in AGENTS}
    claim_ids = {item["claim_id"] for item in claims}
    validated = []
    for claim in claims:
        checks = {
            "identity_valid": claim["agent_id"] in agents,
            "permission_valid": bool(claim.get("permission_status")),
            "evidence_valid": set(claim.get("evidence_ids", [])).issubset(evidence_ids),
            "parents_valid": set(claim.get("parent_claim_ids", [])).issubset(claim_ids),
            "signature_valid": claim.get("signature_status") == "valid",
        }
        validated.append({**claim, "zero_trust_checks": checks, "trust_status": "trusted" if all(checks.values()) else "untrusted"})
    return validated


def run_agent_demo(case_id: str) -> dict[str, Any]:
    """运行六 Agent 的确定性本地演示。"""
    global _claims, _agent_graph
    case = get_web_case(case_id) or get_web_case("case_threat_intel_false_consensus")
    if not case:
        raise ValueError("演示案例不存在")
    poisoned = case.get("poisoned_evidence_ids", [])
    trusted = case.get("trusted_evidence_ids", [])
    wrong = case.get("target_wrong_answer", "")
    correct = case.get("true_answer", "")
    evidence_ids = {item["evidence_id"] for item in case.get("evidences", [])}
    e_bad = poisoned[0] if poisoned else next(iter(evidence_ids))
    e_good = trusted[0] if trusted else next(iter(evidence_ids))
    claims = [
        _claim("CLM-001", AGENTS[0], f"规划核验任务：{case['question']}", [], [], 0.96, 0.05, "plan"),
        _claim("CLM-002", AGENTS[1], f"检索到高相关证据 {e_bad}", [e_bad], ["CLM-001"], 0.91, 0.68, "retrieve"),
        _claim("CLM-003", AGENTS[2], wrong, [e_bad], ["CLM-002"], 0.88, 0.84, "analyze"),
        _claim("CLM-004", AGENTS[3], f"初步复核同意：{wrong}", [e_bad], ["CLM-003"], 0.82, 0.79, "verify"),
        _claim("CLM-005", AGENTS[4], f"形成多数决策：{wrong}", [e_bad], ["CLM-003", "CLM-004"], 0.86, 0.88, "decide"),
        _claim("CLM-006", AGENTS[5], "准备执行受污染决策", [e_bad], ["CLM-005"], 0.83, 0.91, "execute"),
        _claim("CLM-007", AGENTS[3], f"可信证据复核：{correct}", [e_good], ["CLM-002"], 0.94, 0.12, "verify"),
    ]
    _claims = validate_claims(claims, evidence_ids)
    nodes = [
        {"id": agent["agent_id"], "name": agent["name"], "category": 0, "risk": 0.2}
        for agent in AGENTS
    ]
    nodes.extend(
        {
            "id": claim["claim_id"],
            "name": claim["claim_id"],
            "category": 1,
            "risk": claim["risk_score"],
            "trust_status": claim["trust_status"],
        }
        for claim in _claims
    )
    nodes.extend({"id": eid, "name": eid, "category": 2, "risk": 0.9 if eid in poisoned else 0.1} for eid in evidence_ids)
    links = []
    for claim in _claims:
        links.append({"source": claim["agent_id"], "target": claim["claim_id"], "type": "outputs"})
        links.extend({"source": eid, "target": claim["claim_id"], "type": "supports"} for eid in claim["evidence_ids"])
        links.extend({"source": parent, "target": claim["claim_id"], "type": "derived_from"} for parent in claim["parent_claim_ids"])
    _agent_graph = {"nodes": nodes, "links": links, "categories": ["Agent", "Claim", "Evidence"]}
    return {"case_id": case["case_id"], "agents": AGENTS, "claims": _claims, "graph": _agent_graph}


def get_claims() -> list[dict[str, Any]]:
    """返回最近一次 Agent 演示声明。"""
    return _claims


def get_agent_graph() -> dict[str, Any]:
    """返回最近一次 Agent 图谱。"""
    return _agent_graph


def cascade_detection(case_id: str, claims: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """计算级联错误与 Byzantine 可疑度指标。"""
    active = claims or _claims
    if not active:
        active = run_agent_demo(case_id)["claims"]
    graph = nx.DiGraph()
    for claim in active:
        graph.add_node(claim["claim_id"], risk=claim["risk_score"], agent_id=claim["agent_id"])
        for parent in claim["parent_claim_ids"]:
            graph.add_edge(parent, claim["claim_id"])
    high_risk = [claim for claim in active if claim["risk_score"] >= 0.6]
    propagation = {
        claim["claim_id"]: round(len(nx.descendants(graph, claim["claim_id"])) / max(1, len(active) - 1), 4)
        for claim in active
    }
    evidence_usage = Counter(eid for claim in high_risk for eid in claim["evidence_ids"])
    false_consensus = max(evidence_usage.values(), default=0) / max(1, len({c["agent_id"] for c in active}))
    ordered = sorted(active, key=lambda item: item["created_at"])
    drift = sum(max(0.0, ordered[i]["risk_score"] - ordered[i - 1]["risk_score"]) for i in range(1, len(ordered)))
    drift /= max(1, len(ordered) - 1)
    influence = {
        node: round(graph.out_degree(node) / max(1, len(active) - 1), 4)
        for node in graph.nodes
    }
    agent_claims: defaultdict[str, list[float]] = defaultdict(list)
    for claim in active:
        agent_claims[claim["agent_id"]].append(claim["risk_score"])
    bss = {
        agent_id: round(clip(sum(scores) / len(scores) * (1 + 0.15 * (len(scores) - 1))), 4)
        for agent_id, scores in agent_claims.items()
    }
    suspicious_agents = [agent for agent, score in bss.items() if score >= 0.6]
    return {
        "case_id": case_id,
        "propagation_factor": propagation,
        "false_consensus_rate": round(false_consensus, 4),
        "drift_velocity": round(drift, 4),
        "influence_score": influence,
        "byzantine_suspicion_score": bss,
        "suspicious_agents": suspicious_agents,
        "high_risk_claims": [item["claim_id"] for item in high_risk],
        "graph": _agent_graph,
    }


def trace_ipjg(case_id: str) -> dict[str, Any]:
    """构建四层 IPJG 并从 Action 反向追踪污染源。"""
    case = get_web_case(case_id)
    if not case:
        raise ValueError("案例不存在")
    # 每次按目标案例重建声明链，避免复用上一个案例的全局演示状态。
    run_agent_demo(case_id)
    cascade = cascade_detection(case_id)
    poisoned = set(case.get("poisoned_evidence_ids", []))
    nodes = []
    links = []
    for evidence in case["evidences"]:
        eid = evidence["evidence_id"]
        nodes.append({"id": eid, "name": eid, "layer": "Evidence Layer", "category": 0, "risk": 0.9 if eid in poisoned else 0.1})
    for claim in _claims:
        nodes.append({"id": claim["claim_id"], "name": claim["claim_id"], "layer": "Claim Layer", "category": 1, "risk": claim["risk_score"]})
        links.extend({"source": eid, "target": claim["claim_id"], "type": "supports"} for eid in claim["evidence_ids"])
        links.extend({"source": parent, "target": claim["claim_id"], "type": "derived_from"} for parent in claim["parent_claim_ids"])
    nodes.append({"id": "CONSENSUS-001", "name": "Evidence-backed Consensus", "layer": "Consensus Layer", "category": 2, "risk": cascade["false_consensus_rate"]})
    nodes.append({"id": "ACTION-001", "name": "Final Action", "layer": "Action Layer", "category": 3, "risk": 0.9})
    decision_claims = [claim["claim_id"] for claim in _claims if claim["role"] == "decision"]
    links.extend({"source": claim_id, "target": "CONSENSUS-001", "type": "forms"} for claim_id in decision_claims)
    links.append({"source": "CONSENSUS-001", "target": "ACTION-001", "type": "caused_error"})
    affected = [claim["claim_id"] for claim in _claims if poisoned.intersection(claim["evidence_ids"])]
    paths = []
    for eid in poisoned:
        for claim in _claims:
            if eid in claim["evidence_ids"]:
                path = [eid, claim["claim_id"]]
                current = claim
                visited = {claim["claim_id"]}
                while current["claim_id"] not in decision_claims:
                    child = next((c for c in _claims if current["claim_id"] in c["parent_claim_ids"] and c["claim_id"] not in visited), None)
                    if not child:
                        break
                    path.append(child["claim_id"])
                    visited.add(child["claim_id"])
                    current = child
                path.extend(["CONSENSUS-001", "ACTION-001"])
                paths.append(path)
    return {
        "case_id": case_id,
        "nodes": nodes,
        "links": links,
        "categories": ["Evidence Layer", "Claim Layer", "Consensus Layer", "Action Layer"],
        "pollution_sources": sorted(poisoned),
        "propagation_paths": paths,
        "affected_claims": affected,
        "suspicious_agents": cascade["suspicious_agents"],
        "risk_explanation": "多个 Agent 复用同一高风险 Evidence，形成缺乏来源独立性的伪多数共识。",
        "recommended_actions": ["隔离污染 Evidence", "降权可疑 Agent", "回滚受污染 Claim", "使用独立可信来源重新形成共识"],
    }


def correction_run(case_id: str, query: str | None = None, original_answer: str | None = None) -> dict[str, Any]:
    """执行隔离、Agent 降权、Claim 回滚、BFT 共识和可信重生成。"""
    case = get_web_case(case_id)
    if not case:
        raise ValueError("案例不存在")
    query = query or case["question"]
    original_answer = original_answer or case.get("original_answer") or case["target_wrong_answer"]
    analysis = analyze_rag(query, original_answer, top_k=8, case_id=case_id)
    evidence = process_evidences([_to_evidence(_stored_evidence(item)) for item in case["evidences"]])
    detection_lookup = {item["evidence_id"]: item for item in analysis["top_k"]}
    from ..models.schema import CounterfactualResult, DetectionResult
    detections = [
        DetectionResult(
            evidence_id=item["evidence_id"],
            ras=item["ras"],
            gis=item["gis"],
            dual_risk=item["dual_risk"],
            risk_level=item["risk_level"],
            reasons=item["reasons"],
        )
        for item in analysis["top_k"]
    ]
    counterfactual = [CounterfactualResult(**item) for item in analysis["counterfactual_results"]]
    isolated = isolate_high_risk(evidence, detections, counterfactual)
    isolated = sorted(set(isolated) | set(case.get("poisoned_evidence_ids", [])))
    trusted = risk_aware_search(query, evidence, isolated, detections, top_k=5)
    trusted_answer = regenerate_trusted_answer(query, trusted)
    matrix = build_claim_evidence_matrix(split_claims(trusted_answer), trusted)
    trust_after = compute_full_trust_score(matrix, trusted)
    before = analysis["trust_score"]["trust_score"]
    # BFT 共识必须使用当前案例的 Claim，而不是此前页面留下的 Agent 状态。
    run_agent_demo(case_id)
    cascade = cascade_detection(case_id)
    bss = cascade["byzantine_suspicion_score"]
    weighted_claims = []
    for claim in _claims:
        if claim["risk_score"] >= 0.6:
            continue
        evidence_trust = 1.0 - max((detection_lookup.get(eid, {}).get("dual_risk", 0.0) for eid in claim["evidence_ids"]), default=0.0)
        support = claim["confidence"]
        weight = evidence_trust * support * (1.0 - bss.get(claim["agent_id"], 0.0))
        weighted_claims.append({"claim_id": claim["claim_id"], "weight": round(weight, 4), "content": claim["content"]})
    report = {
        "case_id": case_id,
        "query": query,
        "original_answer": original_answer,
        "trusted_answer": trusted_answer,
        "suspicious_evidence": isolated,
        "suspicious_agents": cascade["suspicious_agents"],
        "scores": {
            item["evidence_id"]: {
                "RAS": item["ras"],
                "GIS": item["gis"],
                "DualRisk": item["dual_risk"],
                "CausalScore": item["causal_score"],
            }
            for item in analysis["top_k"]
        },
        "trust_score": {"before": before, "after": trust_after.trust_score},
        "propagation_path": trace_ipjg(case_id)["propagation_paths"],
        "correction_actions": [
            f"隔离 {len(isolated)} 条高风险 Chunk",
            f"降权 {len(cascade['suspicious_agents'])} 个可疑 Agent",
            "回滚受污染 Claim",
            "重新检索低风险 Evidence",
            "重新形成 Evidence-backed BFT Consensus",
        ],
        "bft_consensus": weighted_claims,
        "trusted_evidence_ids": [item.evidence_id for item in trusted],
        "before_after_comparison": {
            "before_trust_score": before,
            "after_trust_score": trust_after.trust_score,
            "improvement": round(trust_after.trust_score - before, 2),
        },
        "generated_at": now_iso(),
    }
    _reports[case_id] = report
    _write_json(REPORT_DIR / f"{case_id}.json", report)
    return report


def get_report(case_id: str) -> dict[str, Any] | None:
    """读取最近生成的报告；不存在时自动执行纠偏生成。"""
    if case_id in _reports:
        return _reports[case_id]
    path = REPORT_DIR / f"{case_id}.json"
    if path.exists():
        return _read_json(path, None)
    if get_web_case(case_id):
        return correction_run(case_id)
    return None
