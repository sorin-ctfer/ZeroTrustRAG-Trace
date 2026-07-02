import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
CODE_DIR = APP_DIR.parent
EXPERIMENT_ROOT = CODE_DIR.parent
DATASET_DIR = Path(os.getenv("MABZT_DATASET_DIR", str(EXPERIMENT_ROOT / "data" / "mabzt_comm_dataset")))
RESULTS_DIR = Path(os.getenv("MABZT_RESULTS_DIR", str(EXPERIMENT_ROOT / "results")))
OTHER_DIR = Path(os.getenv("MABZT_OTHER_DIR", str(EXPERIMENT_ROOT / "docs")))
SQLITE_PATH = Path(os.getenv("MABZT_SQLITE_PATH", str(RESULTS_DIR / "runtime.db")))
SCHEMA_VERSION = "mabzt-claim-v1"
DEFAULT_TIME_WINDOW_SECONDS = 7 * 24 * 3600

ROLE_PERMISSIONS = {
    "rag_reader": ["risk_judgment", "evidence_summary"],
    "planner": ["risk_judgment", "action_recommendation"],
    "verifier": ["risk_judgment", "verification", "challenge_response"],
    "executor": ["action_execution", "action_recommendation"],
    "forensic": ["risk_judgment", "root_cause", "evidence_summary"],
    "comm_monitor": ["transport_audit", "risk_judgment"],
    "watcher": ["risk_judgment"],
}

ROLE_WEIGHT = {
    "verifier": 1.08,
    "forensic": 1.03,
    "rag_reader": 1.00,
    "planner": 0.96,
    "comm_monitor": 0.92,
    "watcher": 0.84,
    "executor": 0.82,
}

BSS_WEIGHTS = {
    "H": 0.18,
    "R": 0.08,
    "P": 0.18,
    "S": 0.14,
    "D": 0.15,
    "F": 0.11,
    "O": 0.08,
    "M": 0.08,
}


def ensure_dirs():
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    OTHER_DIR.mkdir(parents=True, exist_ok=True)
