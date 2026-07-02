from __future__ import annotations

from collections import defaultdict
from typing import Dict, Any, List

from .config import ROLE_WEIGHT
from .evidence_scorer import EvidenceScorer


class ConsensusEngine:
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.scorer = EvidenceScorer(data)

    def _challenge_approve(self, task_id: str, label: str) -> int:
        for ch in self.data.get("challenges", []):
            if ch.get("task_id") == task_id and ch.get("approved_label") == label and ch.get("verifier_approve"):
                return 1
        return 0

    def run(self, packages: List[Dict[str, Any]], validations: List[Dict[str, Any]], risk_scores: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        val_index = {v["claim_id"]: v for v in validations}
        risk_index = {r["agent_id"]: r for r in risk_scores}
        valid_packages = [p for p in packages if val_index.get(p.get("claim_id"), {}).get("passed", False)]
        groups = defaultdict(list)
        for p in valid_packages:
            groups[p.get("claim_group_id")].append(p)
        meta = {g["claim_group_id"]: g for g in self.data.get("consensus_groups", [])}
        rows = []
        for gid, claims in groups.items():
            gmeta = meta.get(gid, {})
            stats = self.scorer.group_stats(claims)
            numerator = 0.0
            denominator = 0.0
            agent_weights = []
            for c in claims:
                agent = self.data["agent_index"].get(c.get("agent_id"), {})
                risk = risk_index.get(c.get("agent_id"), {"bss": 0.0})
                base = (float(agent.get("trust_prior", 70)) / 100.0) * ROLE_WEIGHT.get(agent.get("role"), 0.9)
                ch = 1.0
                weighted = base * stats["ess"] * stats["independence"] * stats["q_bar"] * ch * (1.0 - float(risk.get("bss", 0.0)))
                numerator += weighted
                denominator += base
                agent_weights.append({
                    "agent_id": c.get("agent_id"),
                    "base": round(base, 4),
                    "bss": risk.get("bss", 0.0),
                    "weight": round(weighted, 4),
                })
            score = numerator / denominator if denominator else 0.0
            # Normalize by the feasible high-quality evidence product so thresholds remain interpretable.
            normalized = min(1.0, score / 0.72)
            high_risk = bool(gmeta.get("high_risk_action"))
            label = gmeta.get("label") or (claims[0].get("label") if claims else "unknown")
            task_id = gmeta.get("task_id") or (claims[0].get("tid") if claims else "")
            challenge = self._challenge_approve(task_id, label)
            high_risk_constraint = (not high_risk) or (normalized >= 0.80 and stats["core_trust"] >= 70 and challenge == 1)
            if normalized >= 0.75 and high_risk_constraint:
                decision = "accepted"
            elif normalized >= 0.50:
                decision = "challenged"
            else:
                decision = "rejected"
            if high_risk and not high_risk_constraint:
                decision = "rejected"
            rows.append({
                "claim_group_id": gid,
                "task_id": task_id,
                "subject": gmeta.get("subject") or (claims[0].get("subject") if claims else ""),
                "group_kind": gmeta.get("group_kind", "risk"),
                "label": label,
                "claim_count": len(claims),
                "agent_count": len({c.get("agent_id") for c in claims}),
                "ess": round(stats["ess"], 6),
                "q_bar": round(stats["q_bar"], 6),
                "independence": round(stats["independence"], 6),
                "core_trust": round(stats["core_trust"], 2),
                "consensus_score": round(normalized, 6),
                "raw_score": round(score, 6),
                "challenge_approve": challenge,
                "high_risk_action": high_risk,
                "high_risk_constraint_pass": bool(high_risk_constraint),
                "decision": decision,
                "agent_weights": agent_weights,
                "conflicts_with": gmeta.get("conflicts_with", []),
            })
        # Suppress losing non-action groups when a conflict winner is clearly accepted.
        by_task_kind = defaultdict(list)
        for r in rows:
            by_task_kind[(r["task_id"], r["group_kind"])].append(r)
        for rs in by_task_kind.values():
            if len(rs) <= 1:
                continue
            winner = max(rs, key=lambda x: x["consensus_score"])
            for r in rs:
                if r is not winner and r["decision"] == "accepted":
                    r["decision"] = "challenged" if r["consensus_score"] >= 0.50 else "rejected"
        return sorted(rows, key=lambda x: (x["task_id"], x["group_kind"], -x["consensus_score"]))
