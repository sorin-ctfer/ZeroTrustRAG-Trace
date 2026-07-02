from __future__ import annotations

from typing import Dict, Any, List, Tuple


def claim_label(package_or_claim: Dict[str, Any]) -> str:
    if package_or_claim.get("label") in {"malicious", "benign"}:
        return package_or_claim["label"]
    obj = str(package_or_claim.get("object", "")).lower()
    if obj in {"c2", "malicious", "block_ip"}:
        return "malicious"
    return "benign"


class EvidenceScorer:
    def __init__(self, data: Dict[str, Any]):
        self.data = data

    @staticmethod
    def evidence_quality(e: Dict[str, Any]) -> float:
        q = 0.40 * (float(e.get("trust_score", 0)) / 100.0)
        q += 0.30 * (1.0 - float(e.get("dual_risk", 1)))
        q += 0.30 * (1.0 - float(e.get("causal_score", 1)))
        return max(0.0, min(1.0, q))

    def evidence_relation_probs(self, e: Dict[str, Any], claim: Dict[str, Any]) -> Tuple[float, float]:
        aligned = e.get("supports_label") == claim_label(claim)
        entail = float(e.get("p_entail_if_aligned", 0.5)) if aligned else 1.0 - float(e.get("p_contra_if_opposed", 0.6))
        contra = 1.0 - float(e.get("p_entail_if_aligned", 0.5)) if aligned else float(e.get("p_contra_if_opposed", 0.6))
        return max(0.0, min(1.0, entail)), max(0.0, min(1.0, contra))

    def claim_ess(self, claim: Dict[str, Any]) -> float:
        ev_ids = claim.get("evidence_ids", []) or []
        if not ev_ids:
            return 0.08
        numerator = 0.0
        denominator = 0.0
        for eid in ev_ids:
            e = self.data.get("evidence_index", {}).get(eid)
            if not e:
                continue
            q = self.evidence_quality(e)
            entail, contra = self.evidence_relation_probs(e, claim)
            numerator += q * entail
            denominator += q * (entail + contra)
        return numerator / (denominator + 1e-9) if denominator else 0.08

    def group_stats(self, claims: List[Dict[str, Any]]) -> Dict[str, float]:
        if not claims:
            return {"ess": 0.0, "q_bar": 0.0, "independence": 0.0, "core_trust": 0.0}
        ess_vals = [self.claim_ess(c) for c in claims]
        evs = []
        seen = set()
        for c in claims:
            for eid in c.get("evidence_ids", []) or []:
                if eid in seen:
                    continue
                seen.add(eid)
                e = self.data.get("evidence_index", {}).get(eid)
                if e:
                    evs.append(e)
        q_vals = [self.evidence_quality(e) for e in evs]
        ind_vals = [float(e.get("source_independence", 0.5)) for e in evs]
        trust_vals = [float(e.get("trust_score", 0)) for e in evs]
        return {
            "ess": sum(ess_vals) / len(ess_vals),
            "q_bar": sum(q_vals) / len(q_vals) if q_vals else 0.08,
            "independence": sum(ind_vals) / len(ind_vals) if ind_vals else 0.35,
            "core_trust": max(trust_vals) if trust_vals else 0.0,
        }
