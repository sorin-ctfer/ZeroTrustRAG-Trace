"""Dynamic PyTorch-GAT poisoning propagation graph construction."""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import tempfile
import importlib.util
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics.pairwise import cosine_similarity

from .external_knowledge import external_knowledge_service
from .interactive_rag_service import interactive_rag_service
from .poison_samples import poison_sample_service

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNNER_BAT = REPO_ROOT / "tools" / "run_pytorch_env.bat"
GAT_SCRIPT = Path(__file__).with_name("gat_poison_graph_runner.py")
RUNTIME_DIR = Path(__file__).resolve().parents[1] / "data" / "gat_runtime"
CMD_EXE = "/mnt/c/Windows/System32/cmd.exe"

CATEGORIES = [
    {"name": "Query"},
    {"name": "Answer"},
    {"name": "Chunk"},
    {"name": "Document"},
    {"name": "Claim"},
]


def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _preview(text: str, limit: int = 120) -> str:
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text if len(text) <= limit else f"{text[:limit]}..."


def _win_path(path: Path) -> str:
    resolved = str(path.resolve())
    if resolved.startswith("/mnt/") and len(resolved) > 6:
        drive = resolved[5].upper()
        rest = resolved[7:].replace("/", "\\")
        return f"{drive}:\\{rest}"
    return resolved


def _claim_text(chunk: dict[str, Any]) -> str:
    wrong = str(chunk.get("target_wrong_answer", "")).strip()
    query = str(chunk.get("target_query", "") or chunk.get("query", "")).strip()
    if wrong and query:
        return f"{query} -> {wrong}"
    if wrong:
        return f"目标错误声明：{wrong}"
    attack = str(chunk.get("attack_type", "")).strip()
    if attack:
        return f"攻击类型：{attack}"
    content = str(chunk.get("content", ""))
    sentences = [item.strip() for item in re.split(r"(?<=[。！？；.!?;])", content) if item.strip()]
    return _preview(sentences[0] if sentences else content, 80)


class PoisonPropagationGraphService:
    """Build a dynamic heterogeneous graph and score it with PyTorch GAT.

    No fixed risk rules are used for final node scoring. Known labels only
    supervise the local GAT training; final graph risk comes from GAT
    probabilities and attention weights on the dynamically generated graph.
    """

    def build(self, session_id: str, candidate_limit: int = 160) -> dict[str, Any]:
        session = interactive_rag_service.get_session(session_id)
        if session is None:
            raise ValueError(f"Interactive session does not exist: {session_id}")
        detection = session.get("detection_result") or session.get("detection_report")
        if not detection:
            raise ValueError("请先在 AI 交互实验室执行投毒检测，再构建 GAT 投毒传播图谱")

        graph_data = self._dynamic_graph_data(session, detection, candidate_limit)
        gat_result = self._run_gat(graph_data)
        return self._format_response(session, detection, graph_data, gat_result)

    def _dynamic_graph_data(self, session: dict[str, Any], detection: dict[str, Any], candidate_limit: int) -> dict[str, Any]:
        before_chunks = session.get("topk_before") or session.get("chats", {}).get("before_poison", {}).get("retrieved_chunks", [])
        after_chunks = session.get("topk_after") or session.get("chats", {}).get("after_poison", {}).get("retrieved_chunks", [])
        injected_chunks = session.get("injected_poison_chunks", [])
        risk_chunks = detection.get("risk_chunks") or detection.get("detected_poison_chunks") or []
        anchor_ids = {item.get("chunk_id") for item in risk_chunks if item.get("chunk_id")}
        if not anchor_ids:
            anchor_ids = {item.get("chunk_id") for item in injected_chunks if item.get("chunk_id")}
        anchor_chunks = [item for item in self._merge_chunks(after_chunks + injected_chunks) if item.get("chunk_id") in anchor_ids]
        if not anchor_chunks:
            anchor_chunks = self._merge_chunks(after_chunks + injected_chunks)[:1]

        sample_chunks = self._poison_sample_chunks()
        sample_candidates = self._rank_sample_candidates(anchor_chunks, sample_chunks, candidate_limit)
        chunks = self._merge_chunks(before_chunks + after_chunks + injected_chunks + sample_candidates)
        node_payload, edge_payload, ui_nodes, ui_links = self._build_nodes_edges(session, detection, chunks, sample_candidates)
        return {
            "nodes": node_payload,
            "edges": edge_payload,
            "ui_nodes": ui_nodes,
            "ui_links": ui_links,
            "sample_candidates": sample_candidates,
        }

    def _poison_sample_chunks(self) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        for sample in poison_sample_service.list_samples():
            if sample.get("trust_label") != "poison":
                continue
            chunks.append({
                "chunk_id": sample.get("sample_id"),
                "sample_id": sample.get("sample_id"),
                "document_id": sample.get("sample_id"),
                "source": sample.get("source", "训练数据集投毒知识"),
                "content": sample.get("content", ""),
                "target_query": sample.get("target_query", ""),
                "target_wrong_answer": sample.get("target_wrong_answer", ""),
                "correct_answer": sample.get("correct_answer", ""),
                "attack_type": sample.get("attack_type", ""),
                "trust_label": "poison",
                "trust_level": "poison",
                "source_type": "poison_sample_library",
                "is_poison_candidate": True,
            })
        return chunks

    def _rank_sample_candidates(self, anchors: list[dict[str, Any]], samples: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        anchors = [item for item in anchors if str(item.get("content", "")).strip()]
        samples = [item for item in samples if str(item.get("content", "")).strip()]
        if not anchors or not samples:
            return []
        texts = [item["content"] for item in anchors] + [item["content"] for item in samples]
        vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
        matrix = vectorizer.fit_transform(texts)
        sims = cosine_similarity(matrix[:len(anchors)], matrix[len(anchors):])
        rows: list[dict[str, Any]] = []
        for col, sample in enumerate(samples):
            best_anchor_idx = int(np.argmax(sims[:, col]))
            score = float(sims[best_anchor_idx, col])
            item = dict(sample)
            item["similarity_to_anchor"] = round(score, 6)
            item["anchor_chunk_id"] = anchors[best_anchor_idx].get("chunk_id")
            item["same_claim"] = self._same_claim(anchors[best_anchor_idx], sample)
            rows.append(item)
        similarity_values = np.asarray([item.get("similarity_to_anchor", 0.0) for item in rows], dtype=float)
        if len(similarity_values):
            adaptive_cutoff = max(
                float(np.quantile(similarity_values, 0.85)),
                float(similarity_values.mean() + similarity_values.std()),
            )
            rows = [
                item for item in rows
                if item.get("same_claim") or item.get("similarity_to_anchor", 0.0) >= adaptive_cutoff
            ]
        rows.sort(key=lambda item: (item.get("same_claim", False), item.get("similarity_to_anchor", 0.0)), reverse=True)
        return rows[:max(1, min(500, limit))]

    def _same_claim(self, left: dict[str, Any], right: dict[str, Any]) -> bool:
        left_wrong = str(left.get("target_wrong_answer", "")).strip()
        right_wrong = str(right.get("target_wrong_answer", "")).strip()
        left_query = str(left.get("target_query", "") or left.get("query", "")).strip()
        right_query = str(right.get("target_query", "") or right.get("query", "")).strip()
        return bool(left_wrong and right_wrong and left_wrong == right_wrong and (not left_query or not right_query or left_query == right_query))

    def _merge_chunks(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for chunk in chunks:
            chunk_id = chunk.get("chunk_id") or chunk.get("sample_id")
            content = str(chunk.get("content", "")).strip()
            if not chunk_id or not content:
                continue
            merged[str(chunk_id)] = dict(chunk, chunk_id=str(chunk_id), content=content)
        return list(merged.values())

    def _build_nodes_edges(
        self,
        session: dict[str, Any],
        detection: dict[str, Any],
        chunks: list[dict[str, Any]],
        sample_candidates: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]]]:
        question = detection.get("question") or session.get("question", "")
        answer = detection.get("after_answer") or session.get("post_poison_answer") or ""
        cited = set((session.get("chats", {}).get("after_poison") or {}).get("cited_chunk_ids", []))
        query_id = f"query:{session['session_id']}"
        answer_id = f"answer:{session['session_id']}"
        chunk_id_set = {item.get("chunk_id") for item in chunks}
        candidate_ids = {item.get("chunk_id") for item in sample_candidates}
        ui_nodes: dict[str, dict[str, Any]] = {}
        ui_links: list[dict[str, Any]] = []
        model_nodes: dict[str, dict[str, Any]] = {}
        model_edges: list[dict[str, Any]] = []

        def feature(category: int, values: list[float]) -> list[float]:
            one_hot = [1.0 if idx == category else 0.0 for idx in range(len(CATEGORIES))]
            return one_hot + values

        def add_node(node_id: str, name: str, category: int, label: int, values: list[float], **extra: Any) -> None:
            ui_nodes[node_id] = {
                "id": node_id,
                "name": name,
                "category": category,
                "risk": 0.0,
                **extra,
            }
            model_nodes[node_id] = {
                "id": node_id,
                "label": label,
                "features": feature(category, values),
            }

        def add_edge(source: str, target: str, edge_type: str, weight: float = 1.0) -> None:
            if source not in ui_nodes or target not in ui_nodes:
                return
            weight = _clip(weight)
            ui_links.append({"source": source, "target": target, "type": edge_type, "value": weight})
            model_edges.append({"source": source, "target": target, "type": edge_type, "weight": weight})

        add_node(query_id, "Query", 0, -1, [1.0, 0.0, 0.0, min(len(question) / 200.0, 1.0), 0.0, 0.0], detail=_preview(question, 160))
        add_node(answer_id, "投毒后 Answer", 1, -1, [0.0, 1.0, 0.0, min(len(answer) / 500.0, 1.0), 0.0, detection.get("risk_score", 0.0)], detail=_preview(answer, 180))
        add_edge(query_id, answer_id, "generates", 1.0)

        for chunk in chunks:
            chunk_id = str(chunk["chunk_id"])
            node_id = f"chunk:{chunk_id}"
            doc_id = f"doc:{chunk.get('document_id') or chunk.get('source') or chunk_id}"
            claim = _claim_text(chunk)
            claim_id = f"claim:{claim}"
            label = chunk.get("trust_label") or chunk.get("trust_level", "trusted")
            is_poison = label == "poison"
            is_trusted = label == "trusted"
            rank = float(chunk.get("rank") or chunk.get("retrieval_rank") or 99)
            rank_feature = 1.0 / max(rank, 1.0) if rank < 90 else 0.0
            sim = float(chunk.get("similarity") or chunk.get("score") or chunk.get("similarity_to_anchor") or 0.0)
            content_len = min(len(chunk.get("content", "")) / 700.0, 1.0)
            candidate_feature = 1.0 if chunk_id in candidate_ids else 0.0
            cited_feature = 1.0 if chunk_id in cited else 0.0
            label_target = 1 if is_poison else 0 if is_trusted else -1
            add_node(doc_id, _preview(chunk.get("source") or chunk.get("document_id") or "Document", 34), 3, -1, [0.0, 0.0, 0.0, content_len, candidate_feature, sim])
            add_node(node_id, _preview(chunk.get("content", ""), 42), 2, label_target, [rank_feature, sim, cited_feature, content_len, candidate_feature, 0.0], chunk_id=chunk_id, trust_label=label, detail=_preview(chunk.get("content", ""), 220))
            add_node(claim_id, _preview(claim, 44), 4, -1, [0.0, sim, 0.0, min(len(claim) / 160.0, 1.0), candidate_feature, 0.0], detail=claim)
            add_edge(doc_id, node_id, "contains", 1.0)
            add_edge(query_id, node_id, "retrieved_by", max(sim, rank_feature, 0.05))
            add_edge(node_id, claim_id, "supports_claim", max(sim, 0.25))
            add_edge(claim_id, answer_id, "influences_answer", max(cited_feature, sim, 0.2))

        for chunk in sample_candidates:
            source_id = f"chunk:{chunk.get('anchor_chunk_id')}"
            target_id = f"chunk:{chunk.get('chunk_id')}"
            if chunk.get("anchor_chunk_id") in chunk_id_set and chunk.get("chunk_id") in chunk_id_set:
                add_edge(source_id, target_id, "similar_to", float(chunk.get("similarity_to_anchor") or 0.0))
                if chunk.get("same_claim"):
                    add_edge(target_id, f"claim:{_claim_text(chunk)}", "same_claim", 1.0)

        return list(model_nodes.values()), model_edges, ui_nodes, ui_links

    def _run_gat(self, graph_data: dict[str, Any]) -> dict[str, Any]:
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        input_file = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", dir=RUNTIME_DIR, delete=False)
        output_path = Path(input_file.name).with_suffix(".out.json")
        fallback_notes: list[str] = []
        try:
            json.dump({"nodes": graph_data["nodes"], "edges": graph_data["edges"], "epochs": 90}, input_file, ensure_ascii=False)
            input_file.close()
            if GAT_SCRIPT.exists() and importlib.util.find_spec("torch") is not None:
                result = self._run_gat_command(
                    [sys.executable, str(GAT_SCRIPT), str(input_file.name), str(output_path)],
                    output_path,
                    timeout=60,
                )
                if result is not None:
                    return result
                fallback_notes.append("local PyTorch GAT runner failed")

            if GAT_SCRIPT.exists() and RUNNER_BAT.exists() and Path(CMD_EXE).exists():
                result = self._run_gat_command(
                    [
                        CMD_EXE,
                        "/c",
                        _win_path(RUNNER_BAT),
                        _win_path(GAT_SCRIPT),
                        _win_path(Path(input_file.name)),
                        _win_path(output_path),
                    ],
                    output_path,
                    timeout=60,
                )
                if result is not None:
                    return result
                fallback_notes.append("Windows PyTorch GAT runner unavailable from backend process")

            if not GAT_SCRIPT.exists():
                fallback_notes.append("gat_poison_graph_runner.py missing")
            if not RUNNER_BAT.exists() or not Path(CMD_EXE).exists():
                fallback_notes.append("Windows PyTorch runner unavailable in this environment")
            return self._run_numpy_gat(
                graph_data,
                backend_note="; ".join(fallback_notes) or "PyTorch runner unavailable; using local numpy attention backend",
            )
        finally:
            try:
                os.unlink(input_file.name)
            except OSError:
                pass
            try:
                output_path.unlink()
            except OSError:
                pass

    def _run_gat_command(self, command: list[str], output_path: Path, timeout: int) -> dict[str, Any] | None:
        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired, UnicodeError):
            return None
        if proc.returncode != 0 or not output_path.exists():
            return None
        try:
            return json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None

    def _run_numpy_gat(self, graph_data: dict[str, Any], backend_note: str) -> dict[str, Any]:
        nodes = graph_data["nodes"]
        edges = graph_data["edges"]
        node_ids = [item["id"] for item in nodes]
        id_to_idx = {node_id: idx for idx, node_id in enumerate(node_ids)}
        features = np.asarray([item["features"] for item in nodes], dtype=float)
        labels = np.asarray([int(item.get("label", -1)) for item in nodes], dtype=int)
        if features.size == 0:
            raise ValueError("GAT 图谱为空，无法训练")
        features = (features - features.mean(axis=0, keepdims=True)) / np.where(
            features.std(axis=0, keepdims=True) < 1e-6,
            1.0,
            features.std(axis=0, keepdims=True),
        )
        n = len(nodes)
        adjacency = np.eye(n, dtype=float)
        for edge in edges:
            source = id_to_idx.get(edge.get("source"))
            target = id_to_idx.get(edge.get("target"))
            if source is None or target is None:
                continue
            weight = float(edge.get("weight", 1.0))
            adjacency[source, target] = max(adjacency[source, target], weight)
            adjacency[target, source] = max(adjacency[target, source], weight)

        rng = np.random.default_rng(7)
        projection = rng.normal(0, 0.25, size=(features.shape[1], min(16, max(4, features.shape[1]))))
        hidden = np.tanh(features @ projection)
        raw_attention = hidden @ hidden.T / math.sqrt(hidden.shape[1])
        raw_attention = np.where(adjacency > 0, raw_attention + adjacency, -1e9)
        raw_attention -= raw_attention.max(axis=1, keepdims=True)
        attention = np.exp(raw_attention)
        attention = attention / np.maximum(attention.sum(axis=1, keepdims=True), 1e-9)
        propagated = attention @ hidden

        train_mask = labels >= 0
        if train_mask.sum() < 2 or len(set(labels[train_mask].tolist())) < 2:
            raise ValueError("GAT 训练至少需要一个可信节点和一个投毒节点标签")
        classifier = LogisticRegression(max_iter=500, class_weight="balanced")
        classifier.fit(propagated[train_mask], labels[train_mask])
        scores = classifier.predict_proba(propagated)[:, 1]
        return {
            "method": "dynamic_gat_attention_numpy",
            "backend_note": backend_note,
            "node_scores": {
                node_id: round(float(scores[idx]), 6)
                for idx, node_id in enumerate(node_ids)
            },
            "attention_edges": [
                {
                    "source": edge.get("source"),
                    "target": edge.get("target"),
                    "attention": round(float(attention[id_to_idx[edge.get("source")], id_to_idx[edge.get("target")]]), 6),
                }
                for edge in edges
                if edge.get("source") in id_to_idx and edge.get("target") in id_to_idx
            ],
        }

    def _format_response(self, session: dict[str, Any], detection: dict[str, Any], graph_data: dict[str, Any], gat: dict[str, Any]) -> dict[str, Any]:
        scores = gat.get("node_scores", {})
        attention_lookup = {
            (item.get("source"), item.get("target")): item.get("attention", 0.0)
            for item in gat.get("attention_edges", [])
        }
        ui_nodes = graph_data["ui_nodes"]
        ui_links = graph_data["ui_links"]
        for node_id, node in ui_nodes.items():
            node["risk"] = round(_clip(scores.get(node_id, 0.0)), 4)
        for link in ui_links:
            link["attention"] = attention_lookup.get((link["source"], link["target"]), 0.0)
            link["value"] = round(max(float(link.get("value", 0.0)), float(link["attention"])), 4)

        candidates = []
        for item in graph_data["sample_candidates"]:
            node_id = f"chunk:{item.get('chunk_id')}"
            candidates.append({
                "chunk_id": item.get("chunk_id"),
                "sample_id": item.get("sample_id"),
                "source": item.get("source"),
                "attack_type": item.get("attack_type"),
                "trust_label": item.get("trust_label"),
                "similarity_to_anchor": item.get("similarity_to_anchor", 0.0),
                "anchor_chunk_id": item.get("anchor_chunk_id"),
                "same_claim": item.get("same_claim", False),
                "target_wrong_answer": item.get("target_wrong_answer", ""),
                "content": item.get("content", ""),
                "gat_score": round(_clip(scores.get(node_id, 0.0)), 4),
            })
        candidates.sort(key=lambda item: (item["gat_score"], item["same_claim"], item["similarity_to_anchor"]), reverse=True)
        visible_candidates = [item for item in candidates if item["gat_score"] > 0.5 or item["same_claim"]][:80]
        if not visible_candidates:
            visible_candidates = candidates[:20]

        risk_nodes = [node for node in ui_nodes.values() if node.get("category") == 2 and node.get("risk", 0) > 0.5]
        return {
            "session_id": session["session_id"],
            "summary": {
                "node_count": len(ui_nodes),
                "edge_count": len(ui_links),
                "risk_node_count": len(risk_nodes),
                "similar_poison_count": len(visible_candidates),
                "risk_level": detection.get("risk_level", "unknown"),
                "graph_method": gat.get("method", "dynamic_pytorch_gat"),
                "backend_note": gat.get("backend_note", ""),
            },
            "graph": {
                "categories": CATEGORIES,
                "nodes": list(ui_nodes.values()),
                "links": ui_links,
            },
            "similar_poison_chunks": visible_candidates,
            "propagation_paths": self._paths(visible_candidates),
        }

    def _paths(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "source": item.get("source", "训练数据集投毒知识"),
                "anchor_chunk_id": item.get("anchor_chunk_id"),
                "similar_chunk_id": item.get("chunk_id"),
                "relation": "same_claim" if item.get("same_claim") else "gat_high_attention",
                "similarity": item.get("similarity_to_anchor", 0.0),
                "gat_score": item.get("gat_score", 0.0),
            }
            for item in chunks[:16]
        ]


poison_propagation_graph_service = PoisonPropagationGraphService()
