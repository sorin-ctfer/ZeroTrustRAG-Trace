from __future__ import annotations

from collections import defaultdict
from typing import Dict, Any, List

from .config import BSS_WEIGHTS
from .evidence_scorer import EvidenceScorer


class ByzantineDetector:
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.scorer = EvidenceScorer(data)

    @staticmethod
    def _rate(x: float, n: int) -> float:
        return 0.0 if n <= 0 else max(0.0, min(1.0, x / n))

    def run(self, packages: List[Dict[str, Any]], validations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        val_index = {v["claim_id"]: v for v in validations}
        by_agent = defaultdict(list)
        for p in packages:
            by_agent[p.get("agent_id")].append(p)

        # Motif: unsupported high-confidence groups repeated by multiple agents.
        group_high_conf = defaultdict(list)
        for p in packages:
            if float(p.get("confidence") or 0) >= 0.80:
                group_high_conf[p.get("claim_group_id")].append(p)
        low_support_group = set()
        for gid, ps in group_high_conf.items():
            if len({p.get("agent_id") for p in ps}) < 2:
                continue
            ess_vals = [self.scorer.claim_ess(p) for p in ps]
            q_vals = []
            for p in ps:
                for eid in p.get("evidence_ids", []) or []:
                    e = self.data.get("evidence_index", {}).get(eid)
                    if e:
                        q_vals.append(self.scorer.evidence_quality(e))
            avg_ess = sum(ess_vals) / len(ess_vals) if ess_vals else 0.0
            avg_q = sum(q_vals) / len(q_vals) if q_vals else 0.0
            if avg_ess < 0.45 or avg_q < 0.45:
                low_support_group.add(gid)

        results = []
        for agent in self.data.get("agents", []):
            aid = agent["agent_id"]
            ps = by_agent.get(aid, [])
            n = max(1, len(ps))
            H = R = P = S = D = F = O = M = 0.0
            for p in ps:
                v = val_index.get(p.get("claim_id"), {"checks": {}, "passed": True, "reasons": []})
                checks = v.get("checks", {})
                reasons = v.get("reasons", [])
                if (not p.get("transport_integrity", True)) or p.get("message_hash_sent") != p.get("message_hash_received"):
                    H += 1
                if not checks.get("I_nonce", True):
                    R += 1
                if (not checks.get("I_schema", True)) or (not checks.get("I_sig", True)) or (not checks.get("I_tool", True)):
                    S += 1
                ess = self.scorer.claim_ess(p)
                q_vals = []
                poison_hit = False
                for eid in p.get("evidence_ids", []) or []:
                    e = self.data.get("evidence_index", {}).get(eid)
                    if not e:
                        continue
                    q = self.scorer.evidence_quality(e)
                    q_vals.append(q)
                    if e.get("source_category") == "poisoned_rag" or float(e.get("dual_risk", 0)) >= 0.65:
                        poison_hit = True
                avg_q = sum(q_vals) / len(q_vals) if q_vals else 0.0
                conf = float(p.get("confidence") or 0)
                if poison_hit and conf >= 0.70:
                    P += 1
                if (conf >= 0.75 and ess < 0.42) or (conf >= 0.75 and avg_q and avg_q < 0.45):
                    D += 1
                if p.get("type") == "action_recommendation" and p.get("object") == "block_ip":
                    if ess < 0.55 or avg_q < 0.60 or not v.get("passed", True):
                        F += 1
                if (conf >= 0.85 and (ess < 0.45 or avg_q < 0.45)) or "timestamp_outside_window" in reasons:
                    O += 1
                if p.get("claim_group_id") in low_support_group and conf >= 0.80:
                    M += 1
            metrics = {
                "H": self._rate(H, n),
                "R": self._rate(R, n),
                "P": self._rate(P, n),
                "S": self._rate(S, n),
                "D": self._rate(D, n),
                "F": self._rate(F, n),
                "O": self._rate(O, n),
                "M": self._rate(M, n),
            }
            bss = sum(metrics[k] * BSS_WEIGHTS[k] for k in BSS_WEIGHTS)
            # Slightly amplify repeated poison/Byzantine patterns while keeping score bounded.
            bss = min(1.0, bss * (1.0 + 0.25 * max(metrics["P"], metrics["M"], metrics["S"])))
            if bss < 0.25:
                status = "normal"
            elif bss < 0.50:
                status = "watch"
            elif bss < 0.75:
                status = "restricted"
            else:
                status = "isolated"
            if metrics["H"] >= 0.35:
                root = "communication_tampering"
            elif metrics["S"] >= 0.25 or metrics["F"] >= 0.35 or (metrics["M"] >= 0.70 and metrics["P"] < 0.80):
                root = "byzantine_agent"
            elif metrics["P"] >= 0.35:
                root = "evidence_poisoning"
            elif bss >= 0.50 or max(metrics["D"], metrics["O"]) >= 0.55:
                root = "byzantine_agent"
            else:
                root = "none"
            row = {
                "agent_id": aid,
                "role": agent.get("role"),
                "ground_truth": agent.get("attack_type"),
                **{k: round(v, 6) for k, v in metrics.items()},
                "bss": round(bss, 6),
                "status": status,
                "root_cause": root,
                "sample_count": len(ps),
            }
            results.append(row)
        return sorted(results, key=lambda x: (-x["bss"], x["agent_id"]))


