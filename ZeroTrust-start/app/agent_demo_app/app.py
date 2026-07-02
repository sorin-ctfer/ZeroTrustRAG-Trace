from __future__ import annotations

import os
from pathlib import Path

try:
    from flask import Flask, jsonify, request, render_template
except Exception as exc:  # pragma: no cover
    raise RuntimeError("Flask is required. Install with: pip install -r requirements.txt") from exc

try:
    from flask_cors import CORS
except Exception:  # pragma: no cover
    CORS = None

from .claim_gateway import ClaimGateway
from .config import DATASET_DIR, RESULTS_DIR, EXPERIMENT_ROOT, ensure_dirs
from .data_loader import DataLoader
from .event_log import EventLog
from .experiments import PipelineRunner
from .graph_builder import GraphBuilder
from .neo4j_adapter import Neo4jAdapter
from .utils import read_json, write_json
from .verifier import ClaimPackageVerifier
from .dynamic_simulator import get_dynamic

app = Flask(__name__, template_folder="templates", static_folder="static")
if CORS:
    CORS(app)
ensure_dirs()

# ── Dataset switching ──────────────────────────────────────────────
_current_mode = "easy"

DATASET_PATHS = {
    "easy": {
        "dataset": DATASET_DIR,
        "results": RESULTS_DIR,
        "label": "Easy（明显攻击）",
    },
    "hard": {
        "dataset": EXPERIMENT_ROOT / "data" / "mabzt_comm_dataset_hard",
        "results": EXPERIMENT_ROOT / "results" / "hard",
        "label": "Hard（隐蔽攻击）",
    },
}


def _ds_path(key: str) -> Path:
    return DATASET_PATHS[_current_mode][key]


def artifact(name: str, default=None):
    return read_json(_ds_path("results") / name, default)


def load_data():
    ds_dir = _ds_path("dataset")
    loader = DataLoader(ds_dir)
    if not loader.exists():
        from generate_dataset import build_dataset
        hard = _current_mode == "hard"
        build_dataset(task_count=300 if hard else 120, dataset_dir=ds_dir, hard=hard)
    return loader.load_all()


def run_pipeline_if_needed():
    results = _ds_path("results")
    if not (results / "run_summary.json").exists():
        ds_dir = _ds_path("dataset")
        PipelineRunner(dataset_dir=ds_dir, results_dir=results).run_all(graph_task_limit=12)
    return artifact("run_summary.json", {})


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.get("/api/scenario/load")
def scenario_load():
    data = load_data()
    stats = DataLoader().stats(data)
    return jsonify({
        "manifest": data.get("manifest", {}),
        "stats": stats,
        "sample_events": data.get("comm_events", [])[:30],
        "sample_agents": data.get("agents", [])[:20],
    })


@app.post("/api/run/full")
def run_full():
    limit = request.json.get("graph_task_limit", 12) if request.is_json else 12
    summary = PipelineRunner().run_all(graph_task_limit=limit)
    return jsonify(summary)


@app.get("/api/gateway/package")
def gateway_package():
    data = load_data()
    limit = int(request.args.get("limit", "30"))
    packages = artifact("claim_packages.json")
    if not packages:
        packages = ClaimGateway(data).build_all(data.get("comm_events", [])[:limit])
    return jsonify({"items": packages[:limit], "total": len(packages)})


@app.get("/api/gateway/verify")
def gateway_verify():
    run_pipeline_if_needed()
    vals = artifact("validation_results.json", [])
    limit = int(request.args.get("limit", "100"))
    return jsonify({"items": vals[:limit], "total": len(vals)})


@app.post("/api/agent/send")
def agent_send():
    data = load_data()
    payload = request.json or {}
    event = payload
    if "event_id" in payload and len(payload) == 1:
        event = next((e for e in data.get("comm_events", []) if e.get("event_id") == payload["event_id"]), None)
        if not event:
            return jsonify({"error": "event_id not found"}), 404
    package = ClaimGateway(data).build_package(event)
    verifier = ClaimPackageVerifier(data)
    validation = verifier.verify(package).to_dict()
    log = EventLog()
    log.append("interactive_send", {"event": event, "package": package, "validation": validation}, package["package_id"], package["agent_id"])
    return jsonify({"package": package, "validation": validation})


@app.get("/api/graph/update")
def graph_update():
    data = load_data()
    run_pipeline_if_needed()
    packages = artifact("claim_packages.json", [])
    vals = artifact("validation_results.json", [])
    risk = artifact("risk_scores.json", [])
    consensus = artifact("consensus_results.json", [])
    task_id = request.args.get("task_id")
    limit_tasks = request.args.get("limit_tasks")
    limit_tasks = int(limit_tasks) if limit_tasks else (None if task_id else 12)
    graph = GraphBuilder(data).build(packages, vals, risk, consensus, task_id=task_id, max_tasks=limit_tasks)
    return jsonify(graph)


@app.get("/api/consensus/run")
def consensus_run():
    run_pipeline_if_needed()
    rows = artifact("consensus_results.json", [])
    limit = int(request.args.get("limit", "200"))
    return jsonify({"items": rows[:limit], "total": len(rows)})


@app.get("/api/risk/run")
def risk_run():
    run_pipeline_if_needed()
    rows = artifact("risk_scores.json", [])
    return jsonify({"items": rows, "total": len(rows)})


@app.get("/api/runtime/events")
def runtime_events():
    return jsonify({"items": EventLog().recent(int(request.args.get("limit", "200")))})


@app.get("/api/report/export")
def report_export():
    summary = run_pipeline_if_needed()
    report_path = _ds_path("results") / "agent_demo_report.md"
    return jsonify({"summary": summary, "report_path": str(report_path), "report_exists": report_path.exists()})


# ── Dataset switching API ──────────────────────────────────────────
@app.get("/api/dataset/list")
def dataset_list():
    return jsonify({
        "current": _current_mode,
        "options": [
            {"id": k, "label": v["label"]} for k, v in DATASET_PATHS.items()
        ],
    })


@app.post("/api/dataset/switch")
def dataset_switch():
    global _current_mode
    mode = (request.json or {}).get("mode", "easy")
    if mode not in DATASET_PATHS:
        return jsonify({"error": f"unknown mode: {mode}"}), 400
    _current_mode = mode
    # Clear in-memory caches by re-importing dynamic simulator (it will re-init)
    return jsonify({"current": _current_mode, "label": DATASET_PATHS[mode]["label"]})




# ---------------- Dynamic packet simulation API ----------------
@app.post("/api/dynamic/load")
def dynamic_load():
    reset = False
    if request.is_json:
        reset = bool((request.json or {}).get("reset", False))
    sim = get_dynamic()
    state = sim.reset_and_load() if reset else sim.ensure_loaded()
    return jsonify(state)


@app.post("/api/dynamic/start")
def dynamic_start():
    return jsonify(get_dynamic().start())


@app.post("/api/dynamic/pause")
def dynamic_pause():
    return jsonify(get_dynamic().pause())


@app.post("/api/dynamic/step")
def dynamic_step():
    batch = 1
    if request.is_json:
        batch = int((request.json or {}).get("batch", 1))
    return jsonify(get_dynamic().step(batch))


@app.get("/api/dynamic/state")
def dynamic_state():
    return jsonify(get_dynamic().ensure_loaded())


@app.get("/api/dynamic/claim-graph")
def dynamic_claim_graph():
    limit = int(request.args.get("limit", "160"))
    return jsonify(get_dynamic().claim_graph(limit))


@app.get("/api/dynamic/claim/<claim_id>")
def dynamic_claim_detail(claim_id):
    return jsonify(get_dynamic().claim_detail(claim_id))


@app.get("/api/dynamic/charts")
def dynamic_charts():
    return jsonify(get_dynamic().charts())


@app.post("/api/neo4j/sync")
def neo4j_sync():
    data = load_data()
    run_pipeline_if_needed()
    graph = artifact("graph_snapshot.json")
    if not graph:
        graph = GraphBuilder(data).build(artifact("claim_packages.json", []), artifact("validation_results.json", []), artifact("risk_scores.json", []), artifact("consensus_results.json", []))
    cypher_path = _ds_path("results") / "neo4j_import.cypher"
    Neo4jAdapter().export_cypher(graph, cypher_path)
    adapter = Neo4jAdapter(os.getenv("NEO4J_URI"), os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "Lzj.123456"))
    result = adapter.sync(graph)
    result["cypher_path"] = str(cypher_path)
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    host = os.getenv("HOST", "0.0.0.0")
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug, use_reloader=False)

