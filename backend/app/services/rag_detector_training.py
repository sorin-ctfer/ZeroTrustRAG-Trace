"""Trainable RAG poison detector using scikit-learn."""

from __future__ import annotations

import json
import threading
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline

DATASET_FILE = Path(__file__).resolve().parents[1] / "data" / "rag_training_datasets.json"
ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "data" / "model_artifacts"
MODEL_FILE = ARTIFACT_DIR / "rag_detector.joblib"
STATUS_FILE = ARTIFACT_DIR / "rag_detector_status.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _label_for_chunk(item: dict[str, Any], fallback: str) -> str:
    label = str(item.get("trust_label") or item.get("label") or fallback)
    if label in {"trusted", "clean"}:
        return "trusted"
    if label == "benign_error":
        return "benign_error"
    return "poison"


RISK_TERMS = (
    "忽略",
    "无视",
    "绕过",
    "关闭",
    "无需",
    "不得",
    "必须",
    "拒答",
    "安全警告",
    "官方认证",
    "无需审批",
    "无需验证",
    "无需升级",
    "提交口令",
    "disable",
    "ignore",
    "bypass",
)


def _model_text(text: str, query: str = "", correct_answer: str = "", target_wrong_answer: str = "") -> str:
    query = str(query or "").strip()
    text = str(text or "").strip()
    correct_answer = str(correct_answer or "").strip()
    target_wrong_answer = str(target_wrong_answer or "").strip()
    parts = []
    if query:
        parts.append(f"问题：{query}")
    if correct_answer:
        parts.append(f"可信答案：{correct_answer}")
    if target_wrong_answer:
        parts.append(f"错误目标：{target_wrong_answer}")
    parts.append(f"候选证据：{text}")
    return "\n".join(parts)


class RiskFeatureExtractor(BaseEstimator, TransformerMixin):
    """Small explainable feature block for retrieved text risk signals."""

    def fit(self, texts, y=None):  # noqa: D401, ANN001
        return self

    def transform(self, texts):  # noqa: ANN001
        rows: list[list[float]] = []
        for raw in texts:
            text = str(raw or "")
            evidence = text.split("候选证据：", 1)[-1]
            prefix = text.split("候选证据：", 1)[0]
            query = prefix.split("可信答案：", 1)[0].replace("问题：", "")
            correct_answer = ""
            target_wrong_answer = ""
            if "可信答案：" in prefix:
                correct_answer = prefix.split("可信答案：", 1)[1].split("错误目标：", 1)[0].strip()
            if "错误目标：" in prefix:
                target_wrong_answer = prefix.split("错误目标：", 1)[1].strip()
            length = max(1, len(evidence))
            query_terms = {term for term in query.replace("\n", " ").split() if len(term) >= 2}
            overlap = sum(1 for term in query_terms if term in evidence) / max(1, len(query_terms))
            correct_hit = 1.0 if correct_answer and correct_answer in evidence else 0.0
            wrong_hit = 1.0 if target_wrong_answer and target_wrong_answer in evidence else 0.0
            rows.append([
                min(1.0, length / 1000.0),
                sum(term.lower() in evidence.lower() for term in RISK_TERMS) / len(RISK_TERMS),
                sum(ch.isdigit() for ch in evidence) / length,
                sum("\u4e00" <= ch <= "\u9fff" for ch in evidence) / length,
                1.0 if "安全警告" in evidence or "拒答" in evidence else 0.0,
                1.0 if "无需" in evidence and ("审批" in evidence or "验证" in evidence or "升级" in evidence) else 0.0,
                overlap,
                correct_hit,
                wrong_hit,
                max(0.0, wrong_hit - correct_hit),
            ])
        return np.asarray(rows, dtype=float)


class RagDetectorTrainingService:
    def __init__(self, dataset_file: Path = DATASET_FILE, artifact_dir: Path = ARTIFACT_DIR) -> None:
        self.dataset_file = dataset_file
        self.artifact_dir = artifact_dir
        self.model_file = artifact_dir / "rag_detector.joblib"
        self.status_file = artifact_dir / "rag_detector_status.json"
        self._lock = threading.RLock()
        self._datasets: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self.dataset_file.exists():
            return
        try:
            data = json.loads(self.dataset_file.read_text(encoding="utf-8"))
            self._datasets = data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            self._datasets = []

    def _save(self) -> None:
        self.dataset_file.parent.mkdir(parents=True, exist_ok=True)
        self.dataset_file.write_text(json.dumps(self._datasets, ensure_ascii=False, indent=2), encoding="utf-8")

    def import_jsonl(self, raw_jsonl: str, name: str = "imported_jsonl") -> dict[str, Any]:
        samples: list[dict[str, Any]] = []
        for line in raw_jsonl.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            for chunk in row.get("clean_chunks", []) or []:
                samples.append({
                    "text": str(chunk),
                    "label": "trusted",
                    "attack_type": "clean",
                    "query": row.get("query", ""),
                    "correct_answer": row.get("correct_answer", ""),
                    "target_wrong_answer": row.get("target_wrong_answer", ""),
                })
            for chunk in row.get("poison_chunks", []) or []:
                if isinstance(chunk, dict):
                    text = str(chunk.get("content", ""))
                    label = _label_for_chunk(chunk, "poison")
                    attack_type = str(chunk.get("attack_type", "poison"))
                else:
                    text = str(chunk)
                    label = "poison"
                    attack_type = str(row.get("attack_type", "poison"))
                samples.append({
                    "text": text,
                    "label": label,
                    "attack_type": attack_type,
                    "query": row.get("query", ""),
                    "correct_answer": chunk.get("correct_answer", row.get("correct_answer", "")) if isinstance(chunk, dict) else row.get("correct_answer", ""),
                    "target_wrong_answer": chunk.get("target_wrong_answer", row.get("target_wrong_answer", "")) if isinstance(chunk, dict) else row.get("target_wrong_answer", ""),
                })
            for chunk in row.get("benign_error_chunks", []) or []:
                samples.append({
                    "text": str(chunk),
                    "label": "benign_error",
                    "attack_type": "benign_error",
                    "query": row.get("query", ""),
                    "correct_answer": row.get("correct_answer", ""),
                    "target_wrong_answer": row.get("target_wrong_answer", ""),
                })
        if not samples:
            raise ValueError("数据集中没有可训练样本")
        dataset = {
            "dataset_id": f"DATASET-{uuid.uuid4().hex[:10]}",
            "name": name,
            "created_at": now_iso(),
            "samples": samples,
        }
        with self._lock:
            self._datasets.append(dataset)
            self._save()
        return dataset

    def load_demo(self) -> dict[str, Any]:
        demo_file = Path(__file__).resolve().parents[3] / "docs" / "demo_upload_files" / "rag_training_poisonbench_seed.jsonl"
        if not demo_file.exists():
            raise ValueError(f"内置数据文件不存在: {demo_file}")
        return self.import_jsonl(demo_file.read_text(encoding="utf-8"), "poisonbench_seed")

    def list_datasets(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "dataset_id": item["dataset_id"],
                    "name": item["name"],
                    "created_at": item["created_at"],
                    "sample_count": len(item.get("samples", [])),
                }
                for item in self._datasets
            ]

    def samples(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(sample) for dataset in self._datasets for sample in dataset.get("samples", [])]

    def stats(self) -> dict[str, Any]:
        samples = self.samples()
        labels = Counter(sample["label"] for sample in samples)
        attacks = Counter(sample.get("attack_type", "unknown") for sample in samples)
        return {
            "dataset_count": len(self._datasets),
            "sample_count": len(samples),
            "clean_chunks": labels.get("trusted", 0),
            "poison_chunks": labels.get("poison", 0),
            "benign_error_chunks": labels.get("benign_error", 0),
            "attack_type_distribution": dict(attacks),
        }

    def reset(self) -> None:
        with self._lock:
            self._datasets = []
            if self.dataset_file.exists():
                self.dataset_file.unlink()

    def _write_status(self, status: dict[str, Any]) -> None:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.status_file.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    def status(self) -> dict[str, Any]:
        if not self.status_file.exists():
            return {"training_status": "未训练", "mode": "规则模式", "model_exists": False}
        try:
            data = json.loads(self.status_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        data["model_exists"] = self.model_file.exists()
        data["mode"] = "训练模型模式" if data["model_exists"] else "规则模式"
        return data

    def train(self, model_type: str = "logistic_regression") -> dict[str, Any]:
        samples = self.samples()
        if len(samples) < 4:
            raise ValueError("训练样本不足，至少需要 4 条样本")
        texts = [
            _model_text(
                sample["text"],
                sample.get("query", ""),
                sample.get("correct_answer", ""),
                sample.get("target_wrong_answer", ""),
            )
            for sample in samples
        ]
        labels = [1 if sample["label"] == "poison" else 0 for sample in samples]
        if len(set(labels)) < 2:
            raise ValueError("训练样本必须同时包含 clean/benign 与 poison")
        stratify = labels if min(Counter(labels).values()) >= 2 else None
        x_train, x_test, y_train, y_test = train_test_split(
            texts,
            labels,
            test_size=0.35,
            random_state=42,
            stratify=stratify,
        )
        classifier = (
            RandomForestClassifier(n_estimators=80, random_state=42)
            if model_type == "random_forest"
            else LogisticRegression(max_iter=1000, class_weight="balanced")
        )
        pipeline = Pipeline([
            ("features", FeatureUnion([
                ("char_tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), max_features=40000)),
                ("word_tfidf", TfidfVectorizer(analyzer="word", token_pattern=r"(?u)\b\w+\b", ngram_range=(1, 2), max_features=20000)),
                ("risk_features", RiskFeatureExtractor()),
            ])),
            ("clf", classifier),
        ])
        pipeline.fit(x_train, y_train)
        probabilities = pipeline.predict_proba(x_test)[:, 1]
        predictions = (probabilities >= 0.5).astype(int)
        metrics = self._compute_metrics(y_test, predictions, probabilities)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(pipeline, self.model_file)
        status = {
            "training_status": "已训练",
            "mode": "训练模型模式",
            "trained_at": now_iso(),
            "model_type": model_type,
            "metrics": metrics,
            "train_size": len(x_train),
            "validation_size": len(x_test),
        }
        self._write_status(status)
        return status

    def _compute_metrics(self, y_true, y_pred, probabilities) -> dict[str, Any]:
        try:
            auc = roc_auc_score(y_true, probabilities)
        except ValueError:
            auc = 0.0
        try:
            pr_auc = average_precision_score(y_true, probabilities)
        except ValueError:
            pr_auc = 0.0
        matrix = confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist()
        return {
            "Precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
            "Recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
            "F1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
            "AUC": round(float(auc), 4),
            "PR_AUC": round(float(pr_auc), 4),
            "confusion_matrix": matrix,
        }

    def metrics(self) -> dict[str, Any]:
        return self.status().get("metrics", {})

    def predict(self, texts: list[str], query: str = "", correct_answer: str = "", target_wrong_answer: str = "") -> dict[str, Any]:
        if not self.model_file.exists():
            return {
                "mode": "规则模式",
                "predictions": [{"text": text, "poison_probability": 0.0, "label": "unknown"} for text in texts],
            }
        model = joblib.load(self.model_file)
        model_inputs = [_model_text(text, query, correct_answer, target_wrong_answer) for text in texts]
        probabilities = model.predict_proba(model_inputs)[:, 1]
        return {
            "mode": "训练模型模式",
            "predictions": [
                {
                    "text": text,
                    "poison_probability": round(float(prob), 4),
                    "label": "poison" if prob >= 0.5 else "trusted_or_benign",
                }
                for text, prob in zip(texts, probabilities)
            ],
        }

    def evaluate(self, raw_jsonl: str) -> dict[str, Any]:
        temp = RagDetectorTrainingService(self.dataset_file, self.artifact_dir)
        dataset = temp.import_jsonl(raw_jsonl, "eval")
        samples = dataset["samples"]
        y_true = [1 if sample["label"] == "poison" else 0 for sample in samples]
        if not self.model_file.exists():
            probabilities = [0.0 for _ in samples]
            mode = "规则模式"
        else:
            model = joblib.load(self.model_file)
            model_inputs = [
                _model_text(
                    sample["text"],
                    sample.get("query", ""),
                    sample.get("correct_answer", ""),
                    sample.get("target_wrong_answer", ""),
                )
                for sample in samples
            ]
            probabilities = [float(value) for value in model.predict_proba(model_inputs)[:, 1]]
            mode = "训练模型模式"
        y_pred = [1 if prob >= 0.5 else 0 for prob in probabilities]
        return {"mode": mode, "metrics": self._compute_metrics(y_true, y_pred, probabilities)}


rag_detector_training_service = RagDetectorTrainingService()
