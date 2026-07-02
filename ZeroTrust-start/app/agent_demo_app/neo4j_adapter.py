from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Any


def _label(t: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", (t or "Node").title())


def _rel(r: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", (r or "RELATED").upper())


def _cypher_value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    if isinstance(v, (int, float)):
        return str(v)
    if not isinstance(v, str):
        v = json.dumps(v, ensure_ascii=False)
    return json.dumps(v, ensure_ascii=False)


def _props(props: Dict[str, Any]) -> str:
    parts = []
    for k, v in props.items():
        key = str(k).replace("`", "``")
        parts.append(f"`{key}`: {_cypher_value(v)}")
    return "{" + ", ".join(parts) + "}"


class Neo4jAdapter:
    def __init__(self, uri: str | None = None, user: str | None = None, password: str | None = None):
        self.uri = uri
        self.user = user
        self.password = password

    def export_cypher(self, graph: Dict[str, Any], path: Path) -> Path:
        lines = ["// Generated Cypher import for MABZT claim provenance graph", "CREATE CONSTRAINT node_id IF NOT EXISTS FOR (n:ZTNode) REQUIRE n.id IS UNIQUE;"]
        for n in graph.get("nodes", []):
            props = dict(n)
            node_label = _label(props.pop("type", "Node"))
            node_id = props.get("id")
            lines.append(f"MERGE (n:ZTNode:{node_label} {{id: {json.dumps(node_id, ensure_ascii=False)}}}) SET n += {_props(props)};")
        for e in graph.get("edges", []):
            rel = _rel(e.get("relation"))
            props = {k: v for k, v in e.items() if k not in {"source", "target"}}
            lines.append(
                f"MATCH (a:ZTNode {{id: {json.dumps(e.get('source'), ensure_ascii=False)}}}), (b:ZTNode {{id: {json.dumps(e.get('target'), ensure_ascii=False)}}}) "
                f"MERGE (a)-[r:{rel} {{id: {json.dumps(e.get('id'), ensure_ascii=False)}}}]->(b) SET r += {_props(props)};"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def sync(self, graph: Dict[str, Any]) -> Dict[str, Any]:
        if not self.uri:
            return {"synced": False, "reason": "NEO4J_URI not configured; Cypher export is available."}
        try:
            from neo4j import GraphDatabase  # type: ignore
        except Exception as exc:
            return {"synced": False, "reason": f"neo4j driver unavailable: {exc}"}
        driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        with driver.session() as session:
            session.run("CREATE CONSTRAINT node_id IF NOT EXISTS FOR (n:ZTNode) REQUIRE n.id IS UNIQUE")
            for n in graph.get("nodes", []):
                label = _label(n.get("type"))
                props = dict(n)
                session.run(f"MERGE (n:ZTNode:{label} {{id: $id}}) SET n += $props", id=n.get("id"), props=props)
            for e in graph.get("edges", []):
                rel = _rel(e.get("relation"))
                props = dict(e)
                session.run(
                    f"MATCH (a:ZTNode {{id: $source}}), (b:ZTNode {{id: $target}}) MERGE (a)-[r:{rel} {{id: $id}}]->(b) SET r += $props",
                    source=e.get("source"), target=e.get("target"), id=e.get("id"), props=props,
                )
        driver.close()
        return {"synced": True, "nodes": len(graph.get("nodes", [])), "edges": len(graph.get("edges", []))}

