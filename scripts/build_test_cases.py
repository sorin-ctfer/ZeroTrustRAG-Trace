#!/usr/bin/env python3
"""Build clean, single-poison and cluster-poison evaluation cases."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.rag_evaluation_datasets import rag_evaluation_dataset_service


def _ratios(value: str) -> tuple[float, ...]:
    ratios = tuple(float(item.strip()) for item in value.split(",") if item.strip())
    if not ratios or any(ratio <= 0 or ratio > 1 for ratio in ratios):
        raise argparse.ArgumentTypeError("ratios must be comma-separated values in (0, 1]")
    return ratios


def _top_ks(value: str) -> tuple[int, ...]:
    top_ks = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not top_ks or any(top_k <= 0 for top_k in top_ks):
        raise argparse.ArgumentTypeError("top-k values must be positive integers")
    return top_ks


def main() -> int:
    parser = argparse.ArgumentParser(description="Build RAG poisoning evaluation test cases.")
    parser.add_argument("--poison-ratios", type=_ratios, default=(0.01, 0.03, 0.05, 0.10))
    parser.add_argument("--top-ks", type=_top_ks, default=(3, 5, 10))
    args = parser.parse_args()

    manifest = rag_evaluation_dataset_service.build_test_cases(args.poison_ratios, args.top_ks)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
