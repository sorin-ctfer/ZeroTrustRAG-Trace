from __future__ import annotations

from pathlib import Path
from typing import Dict, Any

from .config import DATASET_DIR
from .utils import read_json, write_json

DATA_FILES = {
    "manifest": "manifest.json",
    "agents": "agents.json",
    "evidence": "evidence.json",
    "comm_events": "comm_events.json",
    "tool_calls": "tool_calls.json",
    "claims": "claims.json",
    "challenges": "challenges.json",
    "consensus_groups": "consensus_groups.json",
    "tasks": "tasks.json",
}


class DataLoader:
    def __init__(self, dataset_dir: Path | None = None):
        self.dataset_dir = Path(dataset_dir or DATASET_DIR)

    def path(self, key: str) -> Path:
        return self.dataset_dir / DATA_FILES[key]

    def exists(self) -> bool:
        return self.path("manifest").exists() and self.path("comm_events").exists()

    def load_all(self) -> Dict[str, Any]:
        data = {}
        for key, filename in DATA_FILES.items():
            data[key] = read_json(self.dataset_dir / filename, [] if key != "manifest" else {})
        data["agent_index"] = {a["agent_id"]: a for a in data.get("agents", [])}
        data["evidence_index"] = {e["evidence_id"]: e for e in data.get("evidence", [])}
        data["tool_index"] = {t["tool_call_id"]: t for t in data.get("tool_calls", [])}
        data["task_index"] = {t["task_id"]: t for t in data.get("tasks", [])}
        data["claim_index"] = {c["claim_id"]: c for c in data.get("claims", [])}
        return data

    def save_all(self, data: Dict[str, Any]) -> None:
        self.dataset_dir.mkdir(parents=True, exist_ok=True)
        for key, filename in DATA_FILES.items():
            if key in data:
                write_json(self.dataset_dir / filename, data[key])

    def stats(self, data: Dict[str, Any] | None = None) -> Dict[str, int]:
        data = data or self.load_all()
        return {
            "agents": len(data.get("agents", [])),
            "tasks": len(data.get("tasks", [])),
            "evidence": len(data.get("evidence", [])),
            "comm_events": len(data.get("comm_events", [])),
            "claims": len(data.get("claims", [])),
            "tool_calls": len(data.get("tool_calls", [])),
            "challenges": len(data.get("challenges", [])),
            "consensus_groups": len(data.get("consensus_groups", [])),
        }
