from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .claim_gateway import ClaimGateway
from .config import RESULTS_DIR, SQLITE_PATH, ensure_dirs, BSS_WEIGHTS
from .data_loader import DataLoader
from .evidence_scorer import EvidenceScorer
from .experiments import ensure_dataset
from .utils import parse_time, utc8_now_iso, write_json, write_csv
from .verifier import ClaimPackageVerifier

DYNAMIC_DB = RESULTS_DIR / "dynamic_runtime.db"
VIRTUAL_NODES = [
    {
        "agent_id": "ZT_GATEWAY",
        "display_name": "Zero-Trust Gateway",
        "role": "gateway",
        "attack_type": "system",
        "trust_prior": 100,
    },
    {
        "agent_id": "CLAIM_RELAY",
        "display_name": "Claim Relay / Builder",
        "role": "relay",
        "attack_type": "system",
        "trust_prior": 100,
    },
]

STATUS_COLOR = {
    "normal": "#9E9E9E",
    "watch": "#FBC02D",
    "restricted": "#FB8C00",
    "isolated": "#D32F2F",
    "system": "#212121",
}


def _j(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _loads(s: str | None, default=None):
    if not s:
        return default
    try:
        return json.loads(s)
    except Exception:
        return default


class DynamicSimulator:
    """动态发包仿真器。

    与上一版静态导入不同：这里只在加载数据集时创建节点和待处理事件队列；声明包、校验、冲突、BSS、
    图谱边和统计图表全部在“开始发包/step”过程中逐条写入 SQLite。
    """

    def __init__(self, db_path: Path | None = None):
        ensure_dirs()
        self.db_path = Path(db_path or DYNAMIC_DB)
        ensure_dataset()
        self.data = DataLoader().load_all()
        self.gateway = ClaimGateway(self.data)
        self.scorer = EvidenceScorer(self.data)
        self.max_time = self._dataset_max_time()
        self.init_db()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sim_state(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS nodes(
                    node_id TEXT PRIMARY KEY,
                    label TEXT,
                    role TEXT,
                    node_type TEXT,
                    ground_truth TEXT,
                    status TEXT,
                    root_cause TEXT,
                    bss REAL DEFAULT 0,
                    H REAL DEFAULT 0, R REAL DEFAULT 0, P REAL DEFAULT 0, S REAL DEFAULT 0,
                    D REAL DEFAULT 0, F REAL DEFAULT 0, O REAL DEFAULT 0, M REAL DEFAULT 0,
                    H_count INTEGER DEFAULT 0, R_count INTEGER DEFAULT 0, P_count INTEGER DEFAULT 0, S_count INTEGER DEFAULT 0,
                    D_count INTEGER DEFAULT 0, F_count INTEGER DEFAULT 0, O_count INTEGER DEFAULT 0, M_count INTEGER DEFAULT 0,
                    sample_count INTEGER DEFAULT 0,
                    x REAL, y REAL,
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS event_queue(
                    idx INTEGER PRIMARY KEY,
                    event_id TEXT UNIQUE,
                    payload_json TEXT NOT NULL,
                    processed INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS seen_nonces(
                    agent_id TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    first_step INTEGER NOT NULL,
                    PRIMARY KEY(agent_id, nonce)
                );
                CREATE TABLE IF NOT EXISTS claims(
                    claim_id TEXT PRIMARY KEY,
                    package_id TEXT,
                    step INTEGER,
                    event_id TEXT,
                    task_id TEXT,
                    group_kind TEXT,
                    claim_group_id TEXT,
                    agent_id TEXT,
                    receiver TEXT,
                    claim_type TEXT,
                    subject TEXT,
                    predicate TEXT,
                    object TEXT,
                    label TEXT,
                    confidence REAL,
                    validation_passed INTEGER,
                    conflict INTEGER DEFAULT 0,
                    package_json TEXT,
                    validation_json TEXT,
                    created_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_claim_task_kind ON claims(task_id, group_kind, label);
                CREATE INDEX IF NOT EXISTS idx_claim_agent ON claims(agent_id);
                CREATE TABLE IF NOT EXISTS transmissions(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    step INTEGER,
                    event_id TEXT,
                    source TEXT,
                    target TEXT,
                    relation TEXT,
                    payload_json TEXT,
                    created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS conflicts(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    step INTEGER,
                    task_id TEXT,
                    subject TEXT,
                    group_kind TEXT,
                    claim_group_id TEXT,
                    opposing_group_id TEXT,
                    labels TEXT,
                    payload_json TEXT,
                    created_at TEXT
                );
                """
            )

    def _dataset_max_time(self):
        times = []
        for e in self.data.get("comm_events", []):
            try:
                times.append(parse_time(e["timestamp"]))
            except Exception:
                pass
        return max(times) if times else None

    def _set_state(self, conn, key: str, value: Any):
        conn.execute(
            "INSERT INTO sim_state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, _j(value)),
        )

    def _get_state(self, conn, key: str, default=None):
        row = conn.execute("SELECT value FROM sim_state WHERE key=?", (key,)).fetchone()
        if not row:
            return default
        return _loads(row["value"], default)

    def is_loaded(self) -> bool:
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM sim_state WHERE key='loaded' AND value='true'").fetchone()
            return bool(row)

    def reset_and_load(self) -> Dict[str, Any]:
        with self.connect() as conn:
            conn.executescript(
                """
                DELETE FROM sim_state;
                DELETE FROM nodes;
                DELETE FROM event_queue;
                DELETE FROM seen_nonces;
                DELETE FROM claims;
                DELETE FROM transmissions;
                DELETE FROM conflicts;
                """
            )
            agents = list(self.data.get("agents", [])) + VIRTUAL_NODES
            coords = self._layout_nodes(agents)
            for a in agents:
                node_id = a["agent_id"]
                is_virtual = node_id in {"ZT_GATEWAY", "CLAIM_RELAY"}
                conn.execute(
                    """
                    INSERT INTO nodes(node_id,label,role,node_type,ground_truth,status,root_cause,bss,x,y,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        node_id,
                        a.get("display_name", node_id),
                        a.get("role", "agent"),
                        "system" if is_virtual else "agent",
                        a.get("attack_type", "system" if is_virtual else "none"),
                        "system" if is_virtual else "normal",
                        "system" if is_virtual else "none",
                        0.0,
                        coords[node_id][0],
                        coords[node_id][1],
                        utc8_now_iso(),
                    ),
                )
            for idx, event in enumerate(self.data.get("comm_events", []), start=1):
                conn.execute(
                    "INSERT INTO event_queue(idx,event_id,payload_json,processed) VALUES(?,?,?,0)",
                    (idx, event["event_id"], _j(event)),
                )
            self._set_state(conn, "loaded", True)
            self._set_state(conn, "running", False)
            self._set_state(conn, "current_index", 0)
            self._set_state(conn, "total_events", len(self.data.get("comm_events", [])))
            self._set_state(conn, "finished", False)
            self._set_state(conn, "last_active", [])
        return self.state()

    def ensure_loaded(self):
        if not self.is_loaded():
            return self.reset_and_load()
        return self.state()

    def _layout_nodes(self, agents: List[dict]) -> Dict[str, Tuple[float, float]]:
        coords: Dict[str, Tuple[float, float]] = {}
        width, height = 1000.0, 660.0
        cx, cy = width / 2, height / 2
        normal_agents = [a for a in agents if a["agent_id"] not in {"ZT_GATEWAY", "CLAIM_RELAY"}]
        rings = defaultdict(list)
        for a in normal_agents:
            rings[a.get("attack_type", "none")].append(a)
        ring_specs = [
            ("none", 285.0, -0.2),
            ("evidence_poisoning", 210.0, 0.4),
            ("byzantine_agent", 155.0, 1.1),
            ("communication_tampering", 345.0, 2.4),
            ("noisy_watch", 250.0, 2.8),
        ]
        for family, radius, offset in ring_specs:
            arr = rings.get(family, [])
            if not arr:
                continue
            for i, a in enumerate(arr):
                angle = offset + 2 * math.pi * i / max(1, len(arr))
                coords[a["agent_id"]] = (cx + radius * math.cos(angle), cy + radius * math.sin(angle))
        coords["ZT_GATEWAY"] = (cx - 70, cy)
        coords["CLAIM_RELAY"] = (cx + 70, cy)
        return coords

    def start(self) -> Dict[str, Any]:
        self.ensure_loaded()
        with self.connect() as conn:
            self._set_state(conn, "running", True)
            self._set_state(conn, "finished", False)
            self._set_state(conn, "started_at", utc8_now_iso())
        return self.state()

    def pause(self) -> Dict[str, Any]:
        with self.connect() as conn:
            self._set_state(conn, "running", False)
        return self.state()

    def state(self) -> Dict[str, Any]:
        with self.connect() as conn:
            total = int(self._get_state(conn, "total_events", 0) or 0)
            cur = int(self._get_state(conn, "current_index", 0) or 0)
            running = bool(self._get_state(conn, "running", False))
            finished = bool(self._get_state(conn, "finished", False))
            nodes = [self._row_to_node(r) for r in conn.execute("SELECT * FROM nodes ORDER BY node_type DESC, node_id").fetchall()]
            last_active = self._get_state(conn, "last_active", []) or []
            recent_claims = [self._row_to_claim(r) for r in conn.execute("SELECT * FROM claims ORDER BY step DESC LIMIT 20").fetchall()]
            recent_conflicts = [dict(r) for r in conn.execute("SELECT * FROM conflicts ORDER BY id DESC LIMIT 10").fetchall()]
            return {
                "loaded": self.is_loaded(),
                "running": running,
                "finished": finished,
                "current_index": cur,
                "total_events": total,
                "progress": round(cur / total, 6) if total else 0,
                "nodes": nodes,
                "active_links": last_active,
                "recent_claims": recent_claims,
                "recent_conflicts": recent_conflicts,
                "counts": self._counts(conn),
            }

    def _counts(self, conn) -> Dict[str, int]:
        return {
            "nodes": conn.execute("SELECT count(*) FROM nodes").fetchone()[0],
            "claims": conn.execute("SELECT count(*) FROM claims").fetchone()[0],
            "conflicts": conn.execute("SELECT count(*) FROM conflicts").fetchone()[0],
            "processed": conn.execute("SELECT count(*) FROM event_queue WHERE processed=1").fetchone()[0],
        }

    def _row_to_node(self, r) -> Dict[str, Any]:
        d = dict(r)
        d["color"] = STATUS_COLOR.get(d.get("status"), "#9E9E9E")
        d["symbolSize"] = 24 if d.get("node_type") == "system" else max(16, min(42, 18 + float(d.get("bss") or 0) * 28))
        return d

    def _row_to_claim(self, r) -> Dict[str, Any]:
        d = dict(r)
        d["package"] = _loads(d.pop("package_json", None), {})
        d["validation"] = _loads(d.pop("validation_json", None), {})
        return d

    def step(self, batch_size: int = 1) -> Dict[str, Any]:
        self.ensure_loaded()
        batch_size = max(1, min(30, int(batch_size or 1)))
        processed: List[Dict[str, Any]] = []
        active_links: List[Dict[str, Any]] = []
        conflicts: List[Dict[str, Any]] = []
        with self.connect() as conn:
            running = bool(self._get_state(conn, "running", False))
            if not running:
                return self.state()
            rows = conn.execute(
                "SELECT idx,event_id,payload_json FROM event_queue WHERE processed=0 ORDER BY idx LIMIT ?",
                (batch_size,),
            ).fetchall()
            if not rows:
                self._set_state(conn, "running", False)
                self._set_state(conn, "finished", True)
                self._export_final(conn)
                return self.state()
            for row in rows:
                event = _loads(row["payload_json"], {})
                item = self._process_event(conn, int(row["idx"]), event)
                processed.append(item)
                active_links.extend(item["active_links"])
                conflicts.extend(item["conflicts"])
                conn.execute("UPDATE event_queue SET processed=1 WHERE idx=?", (row["idx"],))
                self._set_state(conn, "current_index", int(row["idx"]))
            self._set_state(conn, "last_active", active_links[-18:])
            total = int(self._get_state(conn, "total_events", 0) or 0)
            cur = int(self._get_state(conn, "current_index", 0) or 0)
            if cur >= total:
                self._set_state(conn, "running", False)
                self._set_state(conn, "finished", True)
                self._export_final(conn)
        st = self.state()
        st.update({"processed_batch": processed, "batch_conflicts": conflicts, "active_links": active_links[-18:]})
        return st

    def _verify_dynamic(self, conn, package: Dict[str, Any], step: int) -> Dict[str, Any]:
        verifier = ClaimPackageVerifier(self.data)
        verifier.reference_time = self.max_time
        vr = verifier.verify(package).to_dict()
        key = (package.get("agent_id"), package.get("nonce"))
        exists = conn.execute("SELECT 1 FROM seen_nonces WHERE agent_id=? AND nonce=?", key).fetchone()
        if exists:
            vr["checks"]["I_nonce"] = False
            if "replayed_nonce" not in vr["reasons"]:
                vr["reasons"].append("replayed_nonce")
        else:
            conn.execute("INSERT INTO seen_nonces(agent_id,nonce,first_step) VALUES(?,?,?)", (key[0], key[1], step))
        vr["passed"] = all(vr["checks"].values())
        return vr

    def _process_event(self, conn, step: int, event: Dict[str, Any]) -> Dict[str, Any]:
        package = self.gateway.build_package(event)
        validation = self._verify_dynamic(conn, package, step)
        conflict_rows = self._detect_conflict(conn, step, package)
        group_kind = "action" if package.get("type") == "action_recommendation" else "risk"
        now = utc8_now_iso()
        conn.execute(
            """
            INSERT INTO claims(claim_id,package_id,step,event_id,task_id,group_kind,claim_group_id,agent_id,receiver,
                               claim_type,subject,predicate,object,label,confidence,validation_passed,conflict,
                               package_json,validation_json,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                package["claim_id"], package["package_id"], step, package["mid"], package["tid"], group_kind,
                package["claim_group_id"], package["agent_id"], package.get("receiver"), package.get("type"),
                package.get("subject"), package.get("predicate"), package.get("object"), package.get("label"),
                float(package.get("confidence") or 0), int(validation["passed"]), int(bool(conflict_rows)),
                _j(package), _j(validation), now,
            ),
        )
        if conflict_rows:
            conn.execute("UPDATE claims SET conflict=1 WHERE task_id=? AND group_kind=?", (package["tid"], group_kind))
        metrics = self._event_metrics(package, validation, has_conflict=bool(conflict_rows))
        self._update_node_risk(conn, package["agent_id"], metrics)
        links = self._record_transmissions(conn, step, event, package, validation)
        claim = {
            "claim_id": package["claim_id"],
            "package_id": package["package_id"],
            "agent_id": package["agent_id"],
            "receiver": package.get("receiver"),
            "subject": package.get("subject"),
            "object": package.get("object"),
            "label": package.get("label"),
            "confidence": package.get("confidence"),
            "validation_passed": validation["passed"],
            "checks": validation["checks"],
            "conflict": bool(conflict_rows),
            "package": package,
            "validation": validation,
        }
        return {"step": step, "event_id": event["event_id"], "claim": claim, "active_links": links, "conflicts": conflict_rows}

    def _record_transmissions(self, conn, step: int, event: Dict[str, Any], package: Dict[str, Any], validation: Dict[str, Any]) -> List[Dict[str, Any]]:
        links = [
            {"source": package["agent_id"], "target": "ZT_GATEWAY", "relation": "message_to_gateway", "event_id": event["event_id"], "claim_id": package["claim_id"], "passed": validation["passed"]},
            {"source": "ZT_GATEWAY", "target": "CLAIM_RELAY", "relation": "claim_package", "event_id": event["event_id"], "claim_id": package["claim_id"], "passed": validation["passed"]},
            {"source": "CLAIM_RELAY", "target": package.get("receiver"), "relation": "verified_delivery", "event_id": event["event_id"], "claim_id": package["claim_id"], "passed": validation["passed"]},
        ]
        for l in links:
            conn.execute(
                "INSERT INTO transmissions(step,event_id,source,target,relation,payload_json,created_at) VALUES(?,?,?,?,?,?,?)",
                (step, event["event_id"], l["source"], l["target"], l["relation"], _j(l), utc8_now_iso()),
            )
        return links

    def _detect_conflict(self, conn, step: int, package: Dict[str, Any]) -> List[Dict[str, Any]]:
        label = package.get("label")
        group_kind = "action" if package.get("type") == "action_recommendation" else "risk"
        rows = conn.execute(
            """
            SELECT claim_group_id,label,agent_id,claim_id FROM claims
            WHERE task_id=? AND group_kind=? AND label<>?
            ORDER BY step DESC LIMIT 8
            """,
            (package["tid"], group_kind, label),
        ).fetchall()
        conflicts: List[Dict[str, Any]] = []
        seen_groups = set()
        for r in rows:
            if r["claim_group_id"] in seen_groups:
                continue
            seen_groups.add(r["claim_group_id"])
            payload = {
                "new_claim_id": package["claim_id"],
                "new_group": package["claim_group_id"],
                "new_label": label,
                "opposing_group": r["claim_group_id"],
                "opposing_label": r["label"],
                "opposing_agent": r["agent_id"],
                "opposing_claim_id": r["claim_id"],
            }
            conn.execute(
                """
                INSERT INTO conflicts(step,task_id,subject,group_kind,claim_group_id,opposing_group_id,labels,payload_json,created_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    step, package["tid"], package.get("subject"), group_kind, package["claim_group_id"],
                    r["claim_group_id"], f"{label} vs {r['label']}", _j(payload), utc8_now_iso(),
                ),
            )
            conflicts.append({"step": step, "task_id": package["tid"], "subject": package.get("subject"), **payload})
        return conflicts

    def _event_metrics(self, package: Dict[str, Any], validation: Dict[str, Any], has_conflict: bool) -> Dict[str, int]:
        checks = validation.get("checks", {})
        ev_ids = package.get("evidence_ids", []) or []
        q_vals = []
        poison_hit = False
        for eid in ev_ids:
            e = self.data.get("evidence_index", {}).get(eid)
            if not e:
                continue
            q_vals.append(self.scorer.evidence_quality(e))
            if e.get("source_category") == "poisoned_rag" or float(e.get("dual_risk", 0)) >= 0.65:
                poison_hit = True
        avg_q = sum(q_vals) / len(q_vals) if q_vals else 0.0
        ess = self.scorer.claim_ess(package)
        conf = float(package.get("confidence") or 0)
        out = {k: 0 for k in BSS_WEIGHTS}
        if (not package.get("transport_integrity", True)) or package.get("message_hash_sent") != package.get("message_hash_received"):
            out["H"] = 1
        if not checks.get("I_nonce", True):
            out["R"] = 1
        if poison_hit and conf >= 0.70:
            out["P"] = 1
        if (not checks.get("I_schema", True)) or (not checks.get("I_sig", True)) or (not checks.get("I_tool", True)):
            out["S"] = 1
        if (conf >= 0.75 and ess < 0.42) or (conf >= 0.75 and avg_q and avg_q < 0.45):
            out["D"] = 1
        if package.get("type") == "action_recommendation" and package.get("object") == "block_ip":
            if ess < 0.55 or avg_q < 0.60 or not validation.get("passed", True):
                out["F"] = 1
        if (conf >= 0.85 and (ess < 0.45 or avg_q < 0.45)) or not checks.get("I_time", True):
            out["O"] = 1
        if has_conflict and (conf >= 0.80 or ess < 0.50):
            out["M"] = 1
        return out

    def _update_node_risk(self, conn, agent_id: str, metrics: Dict[str, int]):
        row = conn.execute("SELECT * FROM nodes WHERE node_id=?", (agent_id,)).fetchone()
        if not row:
            return
        sample = int(row["sample_count"] or 0) + 1
        counts = {k: int(row[f"{k}_count"] or 0) + int(metrics.get(k, 0)) for k in BSS_WEIGHTS}
        rates = {k: counts[k] / sample for k in BSS_WEIGHTS}
        bss = min(1.0, sum(rates[k] * BSS_WEIGHTS[k] for k in BSS_WEIGHTS) * (1.0 + 0.25 * max(rates["P"], rates["M"], rates["S"])))
        if bss < 0.25:
            status = "normal"
        elif bss < 0.50:
            status = "watch"
        elif bss < 0.75:
            status = "restricted"
        else:
            status = "isolated"
        if rates["H"] >= 0.35:
            root = "communication_tampering"
        elif rates["S"] >= 0.25 or rates["F"] >= 0.35 or (rates["M"] >= 0.70 and rates["P"] < 0.80):
            root = "byzantine_agent"
        elif rates["P"] >= 0.35:
            root = "evidence_poisoning"
        elif bss >= 0.50 or max(rates["D"], rates["O"]) >= 0.55:
            root = "byzantine_agent"
        else:
            root = "none"
        conn.execute(
            """
            UPDATE nodes SET sample_count=?, H_count=?,R_count=?,P_count=?,S_count=?,D_count=?,F_count=?,O_count=?,M_count=?,
                H=?,R=?,P=?,S=?,D=?,F=?,O=?,M=?,bss=?,status=?,root_cause=?,updated_at=?
            WHERE node_id=?
            """,
            (
                sample,
                counts["H"], counts["R"], counts["P"], counts["S"], counts["D"], counts["F"], counts["O"], counts["M"],
                rates["H"], rates["R"], rates["P"], rates["S"], rates["D"], rates["F"], rates["O"], rates["M"],
                bss, status, root, utc8_now_iso(), agent_id,
            ),
        )

    def claim_graph(self, limit: int = 120) -> Dict[str, Any]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM claims ORDER BY step DESC LIMIT ?", (max(1, min(500, limit)),)).fetchall()
            nodes: Dict[str, dict] = {}
            links: List[dict] = []
            for r in reversed(rows):
                claim = self._row_to_claim(r)
                cid = claim["claim_id"]
                aid = claim["agent_id"]
                gid = claim["claim_group_id"]
                nodes.setdefault(aid, {"id": aid, "name": aid, "type": "agent", "category": 0, "symbolSize": 22})
                nodes[cid] = {
                    "id": cid,
                    "name": f"{claim['subject']} {claim['object']}",
                    "type": "claim",
                    "category": 1,
                    "symbolSize": 18 + float(claim.get("confidence") or 0) * 10,
                    "claim_id": cid,
                    "package_id": claim.get("package_id"),
                    "passed": bool(claim.get("validation_passed")),
                    "conflict": bool(claim.get("conflict")),
                    "itemStyle": {"color": "#D32F2F" if claim.get("conflict") else ("#212121" if claim.get("validation_passed") else "#9E9E9E")},
                }
                nodes.setdefault(gid, {"id": gid, "name": gid, "type": "group", "category": 2, "symbolSize": 20})
                links.append({"source": aid, "target": cid, "name": "emits"})
                links.append({"source": cid, "target": gid, "name": "member_of"})
                pkg = claim.get("package", {})
                for evid in pkg.get("evidence_ids", []) or []:
                    ev = self.data.get("evidence_index", {}).get(evid, {})
                    nodes.setdefault(evid, {"id": evid, "name": evid.replace("E_", ""), "type": "evidence", "category": 3, "symbolSize": 16, "trust_score": ev.get("trust_score")})
                    links.append({"source": cid, "target": evid, "name": "uses_evidence"})
                if pkg.get("tool_call_id"):
                    tid = pkg["tool_call_id"]
                    nodes.setdefault(tid, {"id": tid, "name": tid.replace("TOOL_", "tool_"), "type": "tool", "category": 4, "symbolSize": 14})
                    links.append({"source": cid, "target": tid, "name": "uses_tool"})
            for cf in conn.execute("SELECT * FROM conflicts ORDER BY id DESC LIMIT 80").fetchall():
                a, b = cf["claim_group_id"], cf["opposing_group_id"]
                if a in nodes and b in nodes:
                    links.append({"source": a, "target": b, "name": "conflicts_with", "lineStyle": {"color": "#D32F2F", "width": 2, "type": "dashed"}})
            return {"nodes": list(nodes.values()), "links": links, "categories": [
                {"name": "Agent"}, {"name": "Claim"}, {"name": "ClaimGroup"}, {"name": "Evidence"}, {"name": "Tool"}
            ]}

    def claim_detail(self, claim_id: str) -> Dict[str, Any]:
        with self.connect() as conn:
            r = conn.execute("SELECT * FROM claims WHERE claim_id=?", (claim_id,)).fetchone()
            if not r:
                return {"error": "claim not found"}
            return self._row_to_claim(r)

    def _charts_from_conn(self, conn) -> Dict[str, Any]:
        status = Counter(r["status"] for r in conn.execute("SELECT status FROM nodes WHERE node_type='agent'").fetchall())
        roots = Counter(r["root_cause"] for r in conn.execute("SELECT root_cause FROM nodes WHERE node_type='agent'").fetchall())
        failures = Counter()
        for r in conn.execute("SELECT validation_json FROM claims").fetchall():
            v = _loads(r["validation_json"], {})
            for k, ok in (v.get("checks") or {}).items():
                if not ok:
                    failures[k] += 1
        progress_rows = conn.execute("SELECT step, count(*) AS c FROM claims GROUP BY step ORDER BY step").fetchall()
        conflict_rows = conn.execute("SELECT step, count(*) AS c FROM conflicts GROUP BY step ORDER BY step").fetchall()
        top_risk = [dict(r) for r in conn.execute("SELECT node_id,bss,status,root_cause FROM nodes WHERE node_type='agent' ORDER BY bss DESC LIMIT 12").fetchall()]
        return {
            "status": [{"name": k, "value": v} for k, v in status.items()],
            "roots": [{"name": k, "value": v} for k, v in roots.items()],
            "validation_failures": [{"name": k, "value": v} for k, v in failures.items()],
            "progress": [[r["step"], r["c"]] for r in progress_rows],
            "conflicts": [[r["step"], r["c"]] for r in conflict_rows],
            "top_risk": top_risk,
        }

    def charts(self) -> Dict[str, Any]:
        with self.connect() as conn:
            return self._charts_from_conn(conn)

    def _export_final(self, conn):
        charts = self._charts_from_conn(conn)
        out_json = RESULTS_DIR / "dynamic_final_charts.json"
        write_json(out_json, charts)
        write_csv(RESULTS_DIR / "dynamic_nodes.csv", [dict(r) for r in conn.execute("SELECT * FROM nodes ORDER BY bss DESC").fetchall()])
        write_csv(RESULTS_DIR / "dynamic_claims.csv", [dict(r) for r in conn.execute("SELECT claim_id,step,event_id,task_id,group_kind,claim_group_id,agent_id,receiver,claim_type,subject,object,label,confidence,validation_passed,conflict,created_at FROM claims ORDER BY step").fetchall()])
        write_csv(RESULTS_DIR / "dynamic_conflicts.csv", [dict(r) for r in conn.execute("SELECT * FROM conflicts ORDER BY step").fetchall()])


_dynamic: DynamicSimulator | None = None


def get_dynamic() -> DynamicSimulator:
    global _dynamic
    if _dynamic is None:
        _dynamic = DynamicSimulator()
    return _dynamic
