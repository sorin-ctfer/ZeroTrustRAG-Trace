"""Download, convert and import public RAG safety datasets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.public_dataset_ingestion import public_dataset_ingestion_service  # noqa: E402
from app.services.rag_detector_training import rag_detector_training_service  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare public RAG safety datasets for zyjd_system.")
    parser.add_argument("--sources", nargs="*", default=None, help="Dataset source keys. Defaults to all sources.")
    parser.add_argument("--limit", type=int, default=120, help="Rows converted per source.")
    parser.add_argument("--force", action="store_true", help="Re-download existing raw files.")
    parser.add_argument("--reset-training", action="store_true", help="Clear existing training datasets before import.")
    parser.add_argument("--train", action="store_true", help="Train the detector after importing.")
    parser.add_argument("--model-type", default="logistic_regression", choices=["logistic_regression", "random_forest"])
    args = parser.parse_args()

    if args.reset_training:
        rag_detector_training_service.reset()

    downloaded = public_dataset_ingestion_service.download(args.sources, force=args.force)
    imported = []
    for source in args.sources or [item["key"] for item in public_dataset_ingestion_service.sources()]:
        imported.append(public_dataset_ingestion_service.import_training(source, args.limit))

    result = {
        "downloaded": downloaded,
        "imported_dataset_count": len(imported),
        "stats": rag_detector_training_service.stats(),
    }
    if args.train:
        result["training"] = rag_detector_training_service.train(args.model_type)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
