#!/usr/bin/env python3
"""Prepare raw RAG evaluation dataset files.

Sample mode creates bounded raw files for all supported public benchmark
adapters.  Full dataset downloads are intentionally left for the next stage so
large external corpora are not pulled before the pipeline is validated.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.rag_evaluation.real_data import real_subset_service
from app.services.rag_evaluation_datasets import SAMPLE_LIMIT, positive_int, rag_evaluation_dataset_service


def main() -> int:
    parser = argparse.ArgumentParser(description="Download or create raw public RAG evaluation datasets.")
    parser.add_argument("--sample", action="store_true", help="Create bounded sample raw files for all adapters.")
    parser.add_argument("--full", action="store_true", help="Reserved for full public dataset downloads.")
    parser.add_argument("--mode", choices=["sample", "subset"], default=None, help="Dataset mode to prepare.")
    parser.add_argument("--per-dataset", type=positive_int, default=100, help="Real unique records per dataset in subset mode.")
    parser.add_argument("--limit", type=positive_int, default=SAMPLE_LIMIT, help="Maximum rows per dataset in sample mode.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing raw sample files.")
    args = parser.parse_args()

    mode = args.mode or ("sample" if args.sample else "subset" if args.full else "sample")
    if mode == "subset":
        results = real_subset_service.download_subset(args.per_dataset)
        print(json.dumps({"mode": "subset", **results}, ensure_ascii=False, indent=2))
        return 0
    if args.full and not args.sample:
        raise SystemExit("full mode will be implemented after sample-mode validation; run with --sample for now")
    results = rag_evaluation_dataset_service.download_sample(limit=min(args.limit, SAMPLE_LIMIT), force=args.force)
    print(json.dumps({"mode": "sample", "datasets": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
