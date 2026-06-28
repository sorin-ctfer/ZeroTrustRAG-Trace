"""JSON persistence for RAG evaluation runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[4]
RESULT_ROOT = PROJECT_ROOT / "data" / "results" / "rag_evaluation"
RUN_ROOT = RESULT_ROOT / "runs"


class EvaluationStorage:
    def __init__(self, result_root: Path = RESULT_ROOT) -> None:
        self.result_root = result_root
        self.run_root = result_root / "runs"

    def ensure_dirs(self) -> None:
        self.run_root.mkdir(parents=True, exist_ok=True)

    def save_run(self, run_id: str, result: dict[str, Any]) -> dict[str, Any]:
        self.ensure_dirs()
        run_dir = self.run_root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(run_dir / "summary.json", result["summary"])
        self._write_json(run_dir / "metrics_by_method.json", result["metrics_by_method"])
        self._write_json(run_dir / "metrics_by_scenario.json", result["metrics_by_scenario"])
        self._write_json(run_dir / "progress.json", result["progress"])
        self._write_json(run_dir / "selected_thresholds.json", result["selected_thresholds"])
        self._write_json(run_dir / "label_distribution.json", result["label_distribution"])
        (run_dir / "detailed_records.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in result["detailed_records"]),
            encoding="utf-8",
        )
        (run_dir / "false_positives.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in result.get("false_positives", [])),
            encoding="utf-8",
        )
        (run_dir / "false_negatives.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in result.get("false_negatives", [])),
            encoding="utf-8",
        )
        self._write_json(self.result_root / "latest.json", result["summary"])
        self._write_json(self.result_root / "metrics_by_method.json", result["metrics_by_method"])
        self._write_json(self.result_root / "metrics_by_scenario.json", result["metrics_by_scenario"])
        self._write_json(self.result_root / "selected_thresholds.json", result["selected_thresholds"])
        self._write_json(self.result_root / "label_distribution.json", result["label_distribution"])
        (self.result_root / "detailed_records.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in result["detailed_records"]),
            encoding="utf-8",
        )
        (self.result_root / "false_positives.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in result.get("false_positives", [])),
            encoding="utf-8",
        )
        (self.result_root / "false_negatives.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in result.get("false_negatives", [])),
            encoding="utf-8",
        )
        return {"run_dir": str(run_dir.relative_to(PROJECT_ROOT)), "latest": str((self.result_root / "latest.json").relative_to(PROJECT_ROOT))}

    def load_latest(self) -> dict[str, Any]:
        path = self.result_root / "latest.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def load_details_for_sample(self, sample_id: str) -> list[dict[str, Any]]:
        path = self.result_root / "detailed_records.jsonl"
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("sample_id") == sample_id:
                rows.append(row)
        return rows

    def _write_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


evaluation_storage = EvaluationStorage()
