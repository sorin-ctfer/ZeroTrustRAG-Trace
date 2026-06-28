#!/usr/bin/env python3
"""Convert raw benchmark files to the unified RAG evaluation JSONL schema."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.rag_evaluation_datasets import DEFAULT_SEED, SAMPLE_LIMIT, positive_int, rag_evaluation_dataset_service


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare unified RAG evaluation splits.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Fixed random seed for leakage-safe splitting.")
    parser.add_argument("--limit", type=positive_int, default=SAMPLE_LIMIT, help="Maximum raw rows per dataset.")
    args = parser.parse_args()

    manifest = rag_evaluation_dataset_service.prepare(seed=args.seed, limit_per_dataset=min(args.limit, SAMPLE_LIMIT))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
