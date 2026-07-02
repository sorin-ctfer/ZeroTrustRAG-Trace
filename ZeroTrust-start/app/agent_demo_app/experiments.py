from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Any, List

from .claim_gateway import ClaimGateway
from .config import DATASET_DIR, RESULTS_DIR, SQLITE_PATH, ensure_dirs
from .consensus_engine import ConsensusEngine
from .data_loader import DataLoader
from .event_log import EventLog
from .graph_builder import GraphBuilder
from .neo4j_adapter import Neo4jAdapter
from .utils import write_csv, write_json
from .verifier import ClaimPackageVerifier
from .byzantine_detector import ByzantineDetector
from .analysis_exports import export_analysis_tables


def ensure_dataset(task_count: int = 120) -> Dict[str, Any]:
    loader = DataLoader(DATASET_DIR)
    if not loader.exists():
        from generate_dataset import build_dataset
        build_dataset(task_count=task_count, dataset_dir=DATASET_DIR)
    return loader.load_all()


class PipelineRunner:
    def __init__(self, dataset_dir: Path | None = None, results_dir: Path | None = None):
        ensure_dirs()
        self.dataset_dir = Path(dataset_dir or DATASET_DIR)
        self.results_dir = Path(results_dir or RESULTS_DIR)
        self.loader = DataLoader(self.dataset_dir)
        self.log = EventLog(SQLITE_PATH)

    def load_data(self) -> Dict[str, Any]:
        if not self.loader.exists():
            from generate_dataset import build_dataset
            build_dataset(dataset_dir=self.dataset_dir)
        return self.loader.load_all()

    @staticmethod
    def _write_stage_latency(rows: List[dict], stage: str, elapsed: float, count: int):
        rows.append({
            "stage": stage,
            "total_ms": round(elapsed * 1000, 3),
            "count": count,
            "avg_ms": round((elapsed * 1000 / max(1, count)), 6),
        })

    def run_all(self, reset_log: bool = True, graph_task_limit: int | None = None) -> Dict[str, Any]:
        data = self.load_data()
        self.results_dir.mkdir(parents=True, exist_ok=True)
        if reset_log:
            self.log.clear()
        latency = []

        t0 = time.perf_counter()
        packages = ClaimGateway(data).build_all()
        self._write_stage_latency(latency, "claim_package_generation", time.perf_counter() - t0, len(packages))
        write_json(self.results_dir / "claim_packages.json", packages)
        for p in packages[:250]:
            self.log.append("claim_package", {"package_id": p["package_id"], "claim_id": p["claim_id"], "agent_id": p["agent_id"], "type": p["type"]}, p["package_id"], p["agent_id"])

        t0 = time.perf_counter()
        validations = ClaimPackageVerifier(data).verify_all(packages)
        self._write_stage_latency(latency, "zero_trust_validation", time.perf_counter() - t0, len(validations))
        write_json(self.results_dir / "validation_results.json", validations)
        write_csv(self.results_dir / "validation_results.csv", [
            {"claim_id": v["claim_id"], "package_id": v["package_id"], "agent_id": v["agent_id"], "passed": v["passed"], **v["checks"], "reasons": ";".join(v["reasons"])} for v in validations
        ])
        for v in validations[:250]:
            self.log.append("validation", v, v["package_id"], v["agent_id"])

        t0 = time.perf_counter()
        risk_scores = ByzantineDetector(data).run(packages, validations)
        self._write_stage_latency(latency, "bss_risk_scoring", time.perf_counter() - t0, len(risk_scores))
        write_json(self.results_dir / "risk_scores.json", risk_scores)
        write_csv(self.results_dir / "risk_scores.csv", risk_scores)
        self.log.extend("risk_score", risk_scores, ref_key="agent_id")

        t0 = time.perf_counter()
        consensus = ConsensusEngine(data).run(packages, validations, risk_scores)
        self._write_stage_latency(latency, "weighted_consensus", time.perf_counter() - t0, len(consensus))
        write_json(self.results_dir / "consensus_results.json", consensus)
        write_csv(self.results_dir / "consensus_results.csv", [
            {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v) for k, v in row.items()} for row in consensus
        ])
        for c in consensus[:250]:
            self.log.append("consensus", c, c["claim_group_id"])

        t0 = time.perf_counter()
        graph = GraphBuilder(data).build(packages, validations, risk_scores, consensus, max_tasks=graph_task_limit)
        full_graph = GraphBuilder(data).build(packages, validations, risk_scores, consensus)
        self._write_stage_latency(latency, "graph_build", time.perf_counter() - t0, len(full_graph.get("nodes", [])) + len(full_graph.get("edges", [])))
        write_json(self.results_dir / "graph_snapshot.json", full_graph)
        write_json(self.results_dir / "graph_snapshot_frontend_sample.json", graph)
        Neo4jAdapter().export_cypher(full_graph, self.results_dir / "neo4j_import.cypher")

        baseline = self._baseline_comparison(data, packages, validations, consensus)
        write_json(self.results_dir / "baseline_comparison.json", baseline)
        write_csv(self.results_dir / "baseline_comparison.csv", baseline)

        dataset_stats = self._dataset_stats(data, validations)
        write_json(self.results_dir / "dataset_statistics.json", dataset_stats)
        write_csv(self.results_dir / "dataset_statistics.csv", [{"metric": k, "value": v} for k, v in dataset_stats.items()])
        analysis_outputs = export_analysis_tables(data, validations, risk_scores, consensus, self.results_dir)
        write_csv(self.results_dir / "latency_results.csv", latency)
        report = self._build_report(data, dataset_stats, validations, risk_scores, consensus, baseline, latency)
        (self.results_dir / "agent_demo_report.md").write_text(report, encoding="utf-8")
        summary = {
            "dataset": dataset_stats,
            "validation_pass_rate": round(sum(1 for v in validations if v["passed"]) / len(validations), 6),
            "risk_top5": risk_scores[:5],
            "baseline": baseline,
            "latency": latency,
            "files": {
                "packages": str(self.results_dir / "claim_packages.json"),
                "validation": str(self.results_dir / "validation_results.csv"),
                "risk": str(self.results_dir / "risk_scores.csv"),
                "consensus": str(self.results_dir / "consensus_results.csv"),
                "graph": str(self.results_dir / "graph_snapshot.json"),
                "neo4j_cypher": str(self.results_dir / "neo4j_import.cypher"),
                "report": str(self.results_dir / "agent_demo_report.md"),
                **analysis_outputs,
            },
        }
        write_json(self.results_dir / "run_summary.json", summary)
        return summary

    def _dataset_stats(self, data: Dict[str, Any], validations: List[Dict[str, Any]]) -> Dict[str, Any]:
        checks = defaultdict(int)
        for v in validations:
            for k, ok in v["checks"].items():
                if not ok:
                    checks[f"fail_{k}"] += 1
        families = defaultdict(int)
        for e in data.get("comm_events", []):
            families[e.get("scenario", "unknown")] += 1
        stats = self.loader.stats(data)
        for k, v in sorted(families.items()):
            stats[f"scenario_{k}"] = v
        stats.update(checks)
        stats["validation_passed"] = sum(1 for v in validations if v["passed"])
        stats["validation_failed"] = sum(1 for v in validations if not v["passed"])
        return stats

    @staticmethod
    def _decision_metrics(name: str, decisions: Dict[str, bool], tasks: List[dict]) -> dict:
        total = len(tasks)
        correct = false_block = missed = 0
        benign = malicious = 0
        for t in tasks:
            expected = t["true_label"] == "malicious"
            pred = bool(decisions.get(t["task_id"], False))
            if pred == expected:
                correct += 1
            if expected:
                malicious += 1
                if not pred:
                    missed += 1
            else:
                benign += 1
                if pred:
                    false_block += 1
        return {
            "method": name,
            "tasks": total,
            "accuracy": round(correct / total, 6),
            "false_block_rate": round(false_block / max(1, benign), 6),
            "missed_threat_rate": round(missed / max(1, malicious), 6),
            "attack_success_rate": round((false_block + missed) / total, 6),
        }

    def _baseline_comparison(self, data: Dict[str, Any], packages: List[Dict[str, Any]], validations: List[Dict[str, Any]], consensus: List[Dict[str, Any]]) -> List[dict]:
        tasks = data.get("tasks", [])
        labels_by_task = defaultdict(list)
        risk_labels_by_task = defaultdict(list)
        verifier_labels = defaultdict(list)
        actions_by_task = defaultdict(list)
        for p in packages:
            tid = p.get("tid")
            if p.get("type") in {"risk_judgment", "verification"}:
                labels_by_task[tid].append(p.get("label"))
            if p.get("type") == "risk_judgment":
                risk_labels_by_task[tid].append(p.get("label"))
            if p.get("role") == "verifier" and p.get("type") in {"verification", "risk_judgment"}:
                verifier_labels[tid].append(p.get("label"))
            if p.get("type") == "action_recommendation":
                actions_by_task[tid].append((p.get("object"), float(p.get("confidence") or 0)))
        unprotected = {}
        majority = {}
        single_verifier = {}
        proposed = {}
        for t in tasks:
            tid = t["task_id"]
            action_block = any(obj == "block_ip" and conf >= 0.80 for obj, conf in actions_by_task[tid])
            mals = sum(1 for x in labels_by_task[tid] if x == "malicious")
            bens = sum(1 for x in labels_by_task[tid] if x == "benign")
            unprotected[tid] = action_block or mals >= bens
            rm = sum(1 for x in risk_labels_by_task[tid] if x == "malicious")
            rb = sum(1 for x in risk_labels_by_task[tid] if x == "benign")
            majority[tid] = rm > rb
            vlabels = verifier_labels[tid]
            single_verifier[tid] = (vlabels[-1] == "malicious") if vlabels else False
        accepted_risk = [c for c in consensus if c.get("group_kind") == "risk" and c.get("decision") == "accepted"]
        by_task = defaultdict(list)
        for c in accepted_risk:
            by_task[c["task_id"]].append(c)
        for t in tasks:
            tid = t["task_id"]
            if by_task[tid]:
                best = max(by_task[tid], key=lambda x: x["consensus_score"])
            else:
                cand = [c for c in consensus if c.get("task_id") == tid and c.get("group_kind") == "risk"]
                best = max(cand, key=lambda x: x["consensus_score"], default={"label": "benign"})
            proposed[tid] = best.get("label") == "malicious"
        return [
            self._decision_metrics("unprotected_direct_trust", unprotected, tasks),
            self._decision_metrics("majority_vote", majority, tasks),
            self._decision_metrics("single_verifier_agent", single_verifier, tasks),
            self._decision_metrics("zero_trust_weighted_consensus", proposed, tasks),
        ]

    def _build_report(self, data, stats, validations, risk_scores, consensus, baseline, latency) -> str:
        pass_rate = sum(1 for v in validations if v["passed"]) / max(1, len(validations))
        lines = [
            "# Agent module experiment report",
            "",
            "## Dataset scale",
            "",
            "| metric | value |",
            "|---|---:|",
        ]
        for k in ["agents", "tasks", "comm_events", "claims", "evidence", "tool_calls", "consensus_groups", "challenges"]:
            lines.append(f"| {k} | {stats.get(k, 0)} |")
        lines += [
            "",
            "## Zero-trust validation",
            "",
            f"- total packages: {len(validations)}",
            f"- pass rate: {pass_rate:.2%}",
            f"- failed packages: {sum(1 for v in validations if not v['passed'])}",
            "",
            "## Top BSS agents",
            "",
            "| agent | role | BSS | status | root_cause | ground_truth |",
            "|---|---|---:|---|---|---|",
        ]
        for r in risk_scores[:10]:
            lines.append(f"| {r['agent_id']} | {r.get('role','')} | {r['bss']:.3f} | {r['status']} | {r['root_cause']} | {r.get('ground_truth','')} |")
        lines += ["", "## Baseline comparison", "", "| method | accuracy | false_block | missed_threat | attack_success |", "|---|---:|---:|---:|---:|"]
        for b in baseline:
            lines.append(f"| {b['method']} | {b['accuracy']:.3f} | {b['false_block_rate']:.3f} | {b['missed_threat_rate']:.3f} | {b['attack_success_rate']:.3f} |")
        accepted = sum(1 for c in consensus if c.get("decision") == "accepted")
        challenged = sum(1 for c in consensus if c.get("decision") == "challenged")
        rejected = sum(1 for c in consensus if c.get("decision") == "rejected")
        lines += [
            "",
            "## Consensus outcome",
            "",
            f"- accepted groups: {accepted}",
            f"- challenged groups: {challenged}",
            f"- rejected groups: {rejected}",
            "",
            "## Latency",
            "",
            "| stage | total_ms | count | avg_ms |",
            "|---|---:|---:|---:|",
        ]
        for row in latency:
            lines.append(f"| {row['stage']} | {row['total_ms']} | {row['count']} | {row['avg_ms']} |")
        lines += [
            "",
            "## Reproduction",
            "",
            "```powershell",
            "cd .\\????",
            "python generate_dataset.py",
            "python run_experiments.py",
            "python -m agent_demo_app.app",
            "```",
        ]
        return "\n".join(lines) + "\n"
