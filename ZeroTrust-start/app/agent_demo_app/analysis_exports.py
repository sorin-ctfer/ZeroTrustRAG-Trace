from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, Any, List

from .utils import write_csv, write_json


def export_analysis_tables(data: Dict[str, Any], validations: List[dict], risk_scores: List[dict], consensus: List[dict], results_dir: Path) -> Dict[str, str]:
    outputs: Dict[str, str] = {}
    total = max(1, len(validations))
    validation_rows = []
    check_names = ["I_schema", "I_sig", "I_time", "I_nonce", "I_perm", "I_ev", "I_tool"]
    for check in check_names:
        fail = sum(1 for v in validations if not v.get("checks", {}).get(check, False))
        validation_rows.append({"check": check, "failed": fail, "total": total, "failure_rate": round(fail / total, 6)})
    failed_all = sum(1 for v in validations if not v.get("passed"))
    validation_rows.append({"check": "V_all", "failed": failed_all, "total": total, "failure_rate": round(failed_all / total, 6)})
    p = results_dir / "validation_summary.csv"; write_csv(p, validation_rows); outputs["validation_summary"] = str(p)

    confusion = defaultdict(int)
    for r in risk_scores:
        confusion[(r.get("ground_truth", "unknown"), r.get("root_cause", "unknown"))] += 1
    confusion_rows = [{"ground_truth": k[0], "predicted_root_cause": k[1], "count": v} for k, v in sorted(confusion.items())]
    p = results_dir / "root_cause_confusion.csv"; write_csv(p, confusion_rows); outputs["root_cause_confusion"] = str(p)

    risk_group = defaultdict(list)
    for r in risk_scores:
        risk_group[r.get("ground_truth", "unknown")].append(r)
    risk_rows = []
    for gt, rows in sorted(risk_group.items()):
        risk_rows.append({
            "ground_truth": gt,
            "agent_count": len(rows),
            "avg_bss": round(sum(float(x.get("bss", 0)) for x in rows) / max(1, len(rows)), 6),
            "restricted_or_isolated": sum(1 for x in rows if x.get("status") in {"restricted", "isolated"}),
            "normal_or_watch": sum(1 for x in rows if x.get("status") in {"normal", "watch"}),
        })
    p = results_dir / "risk_detection_summary.csv"; write_csv(p, risk_rows); outputs["risk_detection_summary"] = str(p)

    cons_group = defaultdict(list)
    for c in consensus:
        cons_group[(c.get("group_kind", "risk"), c.get("label", "unknown"), c.get("decision", "unknown"))].append(c)
    cons_rows = []
    for (kind, label, decision), rows in sorted(cons_group.items()):
        cons_rows.append({
            "group_kind": kind,
            "label": label,
            "decision": decision,
            "count": len(rows),
            "avg_score": round(sum(float(x.get("consensus_score", 0)) for x in rows) / max(1, len(rows)), 6),
            "avg_ess": round(sum(float(x.get("ess", 0)) for x in rows) / max(1, len(rows)), 6),
            "avg_q_bar": round(sum(float(x.get("q_bar", 0)) for x in rows) / max(1, len(rows)), 6),
        })
    p = results_dir / "consensus_decision_summary.csv"; write_csv(p, cons_rows); outputs["consensus_decision_summary"] = str(p)

    write_json(results_dir / "analysis_exports_manifest.json", outputs)
    return outputs
