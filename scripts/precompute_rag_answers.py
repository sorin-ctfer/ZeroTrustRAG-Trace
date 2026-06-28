#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.rag_evaluation.evaluator import rag_evaluation_service
from app.services.rag_evaluation.schemas import EvaluationConfig


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="subset")
    parser.add_argument("--splits", default="validation,test")
    parser.add_argument("--methods", default="original,remove,only,replace")
    parser.add_argument("--per-dataset", type=int, default=100)
    args = parser.parse_args()
    cfg = EvaluationConfig.from_mapping({"mode": args.mode, "subset_per_dataset": args.per_dataset, "top_k": [3], "poison_ratios": [0.01]})
    rag_evaluation_service.prepare(cfg)
    result = rag_evaluation_service.run_sync(cfg)
    print(json.dumps({"status": result["status"], "generation_cache": result.get("generation_cache", {})}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
