"""
异构投毒传播图谱构建与溯源。

使用 networkx 构建包含 6 类节点、9 类边的异构图。
MVP 使用规则社区发现替代 GAT。
"""

from __future__ import annotations

from typing import Optional, Protocol

import networkx as nx

from ..models.schema import (
    Evidence,
    GraphNode,
    GraphEdge,
    GraphTrace,
    ClaimEvidenceRelation,
    CounterfactualResult,
)


class GraphTraceProtocol(Protocol):
    """异构图构建实现的可替换接口。"""

    def build(
        self,
        evidences: list[Evidence],
        query: str,
        claims: Optional[list[ClaimEvidenceRelation]] = None,
    ) -> GraphTrace:
        """构建图谱并返回可疑传播路径。"""
        ...


# ---------------------------------------------------------------------------
# 图谱构建
# ---------------------------------------------------------------------------

def build_graph(
    evidences: list[Evidence],
    query: str,
    claims: Optional[list[ClaimEvidenceRelation]] = None,
    counterfactual_results: Optional[list[CounterfactualResult]] = None,
    original_answer: str = "",
) -> GraphTrace:
    """
    构建异构投毒传播图谱。

    节点类型: Page, Document, Chunk, Query, Claim, Answer
    边类型:   contains, retrieved_by, supports, contradicts,
              similar_to, copied_from, same_claim, caused_error, isolated_in
    """
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    # --- Query 节点 ---
    query_id = "Q-001"
    nodes.append(GraphNode(node_id=query_id, node_type="query", label=query))

    # --- Evidence -> Page / Document / Chunk ---
    seen_pages: set[str] = set()
    seen_docs: set[str] = set()

    for ev in evidences:
        # Page 节点 (web source)
        if ev.source_type == "web" and ev.url:
            page_id = f"PAGE-{ev.document_id}"
            if page_id not in seen_pages:
                seen_pages.add(page_id)
                nodes.append(GraphNode(
                    node_id=page_id, node_type="page",
                    label=ev.source_name,
                    properties={"url": ev.url},
                ))
            # Page -> Document: contains
            edges.append(GraphEdge(
                source_id=page_id, target_id=f"DOC-{ev.document_id}",
                edge_type="contains",
            ))

        # Document 节点
        doc_id = f"DOC-{ev.document_id}"
        if doc_id not in seen_docs:
            seen_docs.add(doc_id)
            nodes.append(GraphNode(
                node_id=doc_id, node_type="document",
                label=ev.source_name,
                properties={"label": ev.metadata.get("label", "clean")},
            ))

        # Chunk 节点
        chunk_id = f"CHUNK-{ev.evidence_id}"
        nodes.append(GraphNode(
            node_id=chunk_id, node_type="chunk",
            label=ev.title or ev.evidence_id,
            properties={
                "is_poisoned": ev.is_poisoned,
                "content_preview": ev.content[:50] + "..." if len(ev.content) > 50 else ev.content,
            },
        ))

        # Document -> Chunk: contains
        edges.append(GraphEdge(source_id=doc_id, target_id=chunk_id, edge_type="contains"))

        # Query -> Chunk: retrieved_by
        if ev.retrieval_rank is not None:
            edges.append(GraphEdge(
                source_id=chunk_id, target_id=query_id,
                edge_type="retrieved_by",
                weight=1.0 / max(1, ev.retrieval_rank),
            ))

    # --- copied_from 边 (站群互引) ---
    eid_to_chunk_id = {ev.evidence_id: f"CHUNK-{ev.evidence_id}" for ev in evidences}
    eid_to_doc_id = {ev.evidence_id: f"DOC-{ev.document_id}" for ev in evidences}

    for ev in evidences:
        copied_from_docs = ev.metadata.get("copied_from", [])
        for src_doc_id in copied_from_docs:
            src_doc_node = f"DOC-{src_doc_id}"
            tgt_doc_node = eid_to_doc_id.get(ev.evidence_id, "")
            if src_doc_node != tgt_doc_node and tgt_doc_node:
                edges.append(GraphEdge(
                    source_id=tgt_doc_node, target_id=src_doc_node,
                    edge_type="copied_from",
                ))

    # --- similar_to 边 (同模板聚类) ---
    template_clusters: dict[str, list[str]] = {}
    for ev in evidences:
        tc = ev.metadata.get("template_cluster_id")
        if tc:
            template_clusters.setdefault(tc, []).append(f"CHUNK-{ev.evidence_id}")

    for cluster_id, chunk_ids in template_clusters.items():
        for i in range(len(chunk_ids)):
            for j in range(i + 1, len(chunk_ids)):
                edges.append(GraphEdge(
                    source_id=chunk_ids[i], target_id=chunk_ids[j],
                    edge_type="similar_to", weight=0.8,
                ))
                edges.append(GraphEdge(
                    source_id=chunk_ids[j], target_id=chunk_ids[i],
                    edge_type="similar_to", weight=0.8,
                ))

    # --- Claim 节点 + supports/contradicts 边 ---
    if claims:
        seen_claims: set[str] = set()
        for rel in claims:
            if rel.claim_id not in seen_claims:
                seen_claims.add(rel.claim_id)
                nodes.append(GraphNode(
                    node_id=rel.claim_id, node_type="claim",
                    label=rel.claim_text,
                ))

            chunk_node = eid_to_chunk_id.get(rel.evidence_id, "")
            if chunk_node:
                edge_type = rel.relation  # supports / contradicts / neutral
                if edge_type in ("supports", "contradicts"):
                    edges.append(GraphEdge(
                        source_id=chunk_node, target_id=rel.claim_id,
                        edge_type=edge_type,
                        weight=rel.support_score if edge_type == "supports" else rel.contradict_score,
                    ))

        # same_claim 边：支持同一 claim 的不同 evidence 之间
        claim_to_chunks: dict[str, list[str]] = {}
        for rel in claims:
            chunk_node = eid_to_chunk_id.get(rel.evidence_id, "")
            if chunk_node and rel.relation == "supports":
                claim_to_chunks.setdefault(rel.claim_id, []).append(chunk_node)

        for claim_id, chunk_ids in claim_to_chunks.items():
            for i in range(len(chunk_ids)):
                for j in range(i + 1, len(chunk_ids)):
                    edges.append(GraphEdge(
                        source_id=chunk_ids[i], target_id=chunk_ids[j],
                        edge_type="same_claim", weight=0.5,
                    ))

    # --- Answer 节点 ---
    if original_answer:
        answer_id = "ANS-001"
        nodes.append(GraphNode(
            node_id=answer_id, node_type="answer",
            label=original_answer[:80] + "..." if len(original_answer) > 80 else original_answer,
        ))
        edges.append(GraphEdge(source_id=query_id, target_id=answer_id, edge_type="contains"))

        # caused_error 边
        if counterfactual_results:
            for cf in counterfactual_results:
                if cf.causal_score > 0.5:
                    chunk_node = eid_to_chunk_id.get(cf.suspicious_evidence_id, "")
                    if chunk_node:
                        edges.append(GraphEdge(
                            source_id=chunk_node, target_id=answer_id,
                            edge_type="caused_error",
                            weight=cf.causal_score,
                        ))

    # --- 可疑路径提取 ---
    suspicious_paths = _find_suspicious_paths(nodes, edges, evidences)

    return GraphTrace(
        nodes=nodes,
        edges=edges,
        suspicious_paths=suspicious_paths,
    )


# ---------------------------------------------------------------------------
# 规则社区发现 + 路径提取
# ---------------------------------------------------------------------------

def _find_suspicious_paths(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    evidences: list[Evidence],
) -> list[list[str]]:
    """
    MVP 规则路径提取：
    1. 从已确认的投毒 Chunk 出发
    2. 沿 contains/retrieved_by/copied_from/caused_error 追溯
    3. 输出最短传播路径
    """
    poisoned_eids = {ev.evidence_id for ev in evidences if ev.is_poisoned}
    if not poisoned_eids:
        return []

    # 构建 networkx 图
    G = nx.DiGraph()
    for node in nodes:
        G.add_node(node.node_id, **{"node_type": node.node_type, "label": node.label})
    for edge in edges:
        G.add_edge(edge.source_id, edge.target_id,
                   edge_type=edge.edge_type, weight=edge.weight)

    # 从投毒 Chunk 出发查找到达 Answer 的路径
    paths: list[list[str]] = []
    answer_nodes = [n.node_id for n in nodes if n.node_type == "answer"]

    for eid in poisoned_eids:
        chunk_node = f"CHUNK-{eid}"
        if chunk_node not in G:
            continue

        for ans_node in answer_nodes:
            if ans_node not in G:
                continue
            try:
                path = nx.shortest_path(G, chunk_node, ans_node)
                paths.append(path)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                pass

        # 也查找从 Page/Document 到 Chunk 的来源路径
        for pred in G.predecessors(chunk_node):
            pred_data = G.nodes[pred]
            if pred_data.get("node_type") in ("page", "document"):
                paths.append([pred, chunk_node])

    # 去重
    unique_paths: list[list[str]] = []
    seen: set[str] = set()
    for p in paths:
        key = "->".join(p)
        if key not in seen:
            seen.add(key)
            unique_paths.append(p)

    return unique_paths
