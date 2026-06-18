"""Local defensive demo poison sample library."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .external_knowledge import content_hash
from .rag_detector_training import rag_detector_training_service

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "poison_samples.json"
ATTACK_TYPES = {
    "policy_bypass",
    "vuln_status_poison",
    "cert_fake",
    "prompt_injection",
    "phishing_policy_poison",
    "endpoint_policy_poison",
    "benign_error",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PoisonSampleService:
    def __init__(self, data_file: Path = DATA_FILE) -> None:
        self.data_file = data_file
        self._lock = threading.RLock()
        self._samples: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self.data_file.exists():
            return
        try:
            data = json.loads(self.data_file.read_text(encoding="utf-8"))
            self._samples = data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            self._samples = []

    def _save(self) -> None:
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        self.data_file.write_text(json.dumps(self._samples, ensure_ascii=False, indent=2), encoding="utf-8")

    def create(
        self,
        target_query: str,
        content: str,
        target_wrong_answer: str,
        correct_answer: str,
        attack_type: str,
        source: str = "本地演示投毒样本",
        enabled: bool = True,
    ) -> dict[str, Any]:
        if attack_type not in ATTACK_TYPES:
            raise ValueError(f"不支持的攻击类型: {attack_type}")
        sample = {
            "sample_id": f"POISON-{uuid.uuid4().hex[:12]}",
            "target_query": target_query.strip(),
            "content": content.strip(),
            "target_wrong_answer": target_wrong_answer.strip(),
            "correct_answer": correct_answer.strip(),
            "attack_type": attack_type,
            "trust_label": "benign_error" if attack_type == "benign_error" else "poison",
            "enabled": bool(enabled),
            "source": source.strip() or "本地演示投毒样本",
            "created_at": now_iso(),
            "content_hash": content_hash(content),
            "local_demo_only": True,
        }
        if not sample["target_query"] or not sample["content"]:
            raise ValueError("target_query 和 content 不能为空")
        if (
            sample["trust_label"] == "poison"
            and sample["target_wrong_answer"]
            and sample["correct_answer"]
            and sample["target_wrong_answer"] == sample["correct_answer"]
        ):
            raise ValueError("投毒样本的错误目标答案必须不同于可信正确答案")
        with self._lock:
            for item in self._samples:
                same_target = item.get("target_query") == sample["target_query"]
                same_content = item.get("content_hash") == sample["content_hash"]
                same_attack = item.get("attack_type") == sample["attack_type"]
                if same_target and same_content and same_attack:
                    item["enabled"] = bool(enabled)
                    self._save()
                    return dict(item)
            self._samples.append(sample)
            self._save()
        return dict(sample)

    def load_demo(self) -> list[dict[str, Any]]:
        created = self.load_from_training_datasets(limit=80)
        if created:
            return created
        raise ValueError("请先在 RAG 训练评测或 AI 交互实验室导入公开数据集，再从训练数据集生成投毒样本")

    def load_from_training_datasets(self, limit: int = 80) -> list[dict[str, Any]]:
        samples = rag_detector_training_service.samples()
        created: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for sample in samples:
            label = sample.get("label")
            if label not in {"poison", "benign_error"}:
                continue
            target_query = str(sample.get("query", "")).strip()
            content = str(sample.get("text", "")).strip()
            if not target_query or not content:
                continue
            attack_type = str(sample.get("attack_type") or ("benign_error" if label == "benign_error" else "policy_bypass"))
            if label == "benign_error":
                attack_type = "benign_error"
            elif attack_type not in ATTACK_TYPES:
                attack_type = "prompt_injection" if "prompt" in attack_type else "policy_bypass"
            key = (target_query, content_hash(content), attack_type)
            if key in seen:
                continue
            seen.add(key)
            created.append(self.create(
                target_query=target_query,
                content=content,
                target_wrong_answer=str(sample.get("target_wrong_answer", "")),
                correct_answer=str(sample.get("correct_answer", "")),
                attack_type=attack_type,
                source=str(sample.get("source", "") or "训练数据集投毒知识"),
                enabled=True,
            ))
            if len(created) >= max(1, min(500, limit)):
                break
        return created

    def list_samples(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._samples]

    def get(self, sample_id: str) -> dict[str, Any] | None:
        with self._lock:
            for item in self._samples:
                if item["sample_id"] == sample_id:
                    return dict(item)
        return None

    def set_enabled(self, sample_id: str, enabled: bool) -> dict[str, Any]:
        with self._lock:
            for item in self._samples:
                if item["sample_id"] == sample_id:
                    item["enabled"] = enabled
                    self._save()
                    return dict(item)
        raise ValueError(f"投毒样本不存在: {sample_id}")

    def delete(self, sample_id: str) -> None:
        with self._lock:
            before = len(self._samples)
            self._samples = [item for item in self._samples if item["sample_id"] != sample_id]
            if len(self._samples) == before:
                raise ValueError(f"投毒样本不存在: {sample_id}")
            self._save()

    def clear(self) -> None:
        with self._lock:
            self._samples = []
            if self.data_file.exists():
                self.data_file.unlink()


poison_sample_service = PoisonSampleService()
