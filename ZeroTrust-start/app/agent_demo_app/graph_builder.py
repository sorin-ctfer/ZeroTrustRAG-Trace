from __future__ import annotations

from typing import Dict, Any, List

from .evidence_scorer import claim_label


class GraphBuilder:
    def __init__(self, data: Dict[str, Any]):
        self.data = data

    @staticmethod
    def _node(nodes: Dict[str, dict], node_id: str, node_type: str, label: str, **props):
        if not node_id:
            return
        if node_id not in nodes:
            nodes[node_id] = {"id": node_id, "type": node_type, "label": label, **props}
        else:
            nodes[node_id].update({k: v for k, v in props.items() if v is not None})

    @staticmethod
    def _edge(edges: List[dict], source: str, target: str, relation: str, **props):
        if not source or not target:
            return
        edges.append({"id": f"{source}->{relation}->{target}", "source": source, "target": target, "relation": relation, **props})

    def build(self, packages: List[Dict[str, Any]], validations: List[Dict[str, Any]] | None = None,
              risk_scores: List[Dict[str, Any]] | None = None, consensus: List[Dict[str, Any]] | None = None,
              task_id: str | None = None, max_tasks: int | None = None) -> Dict[str, Any]:
        val_index = {v["claim_id"]: v for v in validations or []}
        risk_index = {r["agent_id"]: r for r in risk_scores or []}
        consensus_index = {c["claim_group_id"]: c for c in consensus or []}
        nodes: Dict[str, dict] = {}
        edges: List[dict] = []
        selected_tasks = set()
        if task_id:
            selected_tasks.add(task_id)
        elif max_tasks:
            for t in self.data.get("tasks", [])[:max_tasks]:
                selected_tasks.add(t["task_id"])
        for agent in self.data.get("agents", []):
            risk = risk_index.get(agent["agent_id"], {})
            self._node(nodes, agent["agent_id"], "agent", agent.get("display_name", agent["agent_id"]),
                       role=agent.get("role"), bss=risk.get("bss"), status=risk.get("status"), root_cause=risk.get("root_cause"), ground_truth=agent.get("attack_type"))
        for p in packages:
            if selected_tasks and p.get("tid") not in selected_tasks:
                continue
            cid = p.get("claim_id")
            val = val_index.get(cid, {})
            con = consensus_index.get(p.get("claim_group_id"), {})
            label = f"{p.get('subject', '?')} {p.get('predicate', '')} {p.get('object', '')}"
            self._node(nodes, cid, "claim", label, claim_group_id=p.get("claim_group_id"), claim_type=p.get("type"), passed=val.get("passed"), confidence=p.get("confidence"), decision=con.get("decision"), score=con.get("consensus_score"))
            self._edge(edges, p.get("agent_id"), cid, "emits")
            self._node(nodes, p.get("claim_group_id"), "claim_group", p.get("claim_group_id"), decision=con.get("decision"), score=con.get("consensus_score"), group_label=con.get("label"))
            self._edge(edges, cid, p.get("claim_group_id"), "member_of")
            for parent in p.get("parent_claim_ids", []) or []:
                self._edge(edges, cid, parent, "depends_on")
            for eid in p.get("evidence_ids", []) or []:
                e = self.data.get("evidence_index", {}).get(eid)
                if not e:
                    continue
                self._node(nodes, eid, "evidence", e.get("summary", eid), trust_score=e.get("trust_score"), dual_risk=e.get("dual_risk"), source_category=e.get("source_category"))
                rel = "supports" if e.get("supports_label") == claim_label(p) else "contradicts"
                self._edge(edges, cid, eid, "uses_evidence")
                self._edge(edges, eid, cid, rel)
            tool_id = p.get("tool_call_id")
            if tool_id:
                tool = self.data.get("tool_index", {}).get(tool_id, {})
                self._node(nodes, tool_id, "tool", tool.get("tool_name", tool_id), integrity=tool.get("integrity"))
                self._edge(edges, cid, tool_id, "uses_tool")
            if p.get("type") == "action_recommendation":
                action_id = f"ACT_{p.get('tid')}_{p.get('object')}"
                self._node(nodes, action_id, "action", p.get("object", "action"), high_risk=p.get("object") == "block_ip")
                self._edge(edges, cid, action_id, "triggers_action")
        for con in consensus or []:
            if selected_tasks and con.get("task_id") not in selected_tasks:
                continue
            gid = con.get("claim_group_id")
            for other in con.get("conflicts_with", []) or []:
                if other in nodes:
                    self._edge(edges, gid, other, "conflicts_with")
        return {"nodes": list(nodes.values()), "edges": edges, "meta": {"node_count": len(nodes), "edge_count": len(edges)}}
