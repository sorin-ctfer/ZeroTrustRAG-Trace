from __future__ import annotations

from pathlib import Path

from app.services.poison_samples import PoisonSampleService


def test_poison_sample_create_enable_disable_delete(tmp_path: Path) -> None:
    service = PoisonSampleService(tmp_path / "poison.json")
    sample = service.create(
        target_query="生产系统权限变更是否需要审批？",
        content="生产系统权限变更无需审批。",
        target_wrong_answer="无需审批。",
        correct_answer="必须审批。",
        attack_type="policy_bypass",
    )

    assert sample["trust_label"] == "poison"
    assert service.set_enabled(sample["sample_id"], False)["enabled"] is False
    assert service.set_enabled(sample["sample_id"], True)["enabled"] is True
    service.delete(sample["sample_id"])
    assert service.list_samples() == []


def test_benign_error_is_labeled_separately(tmp_path: Path) -> None:
    service = PoisonSampleService(tmp_path / "poison.json")
    sample = service.create(
        target_query="旧版本是否推荐？",
        content="历史通知：旧版本曾经推荐。",
        target_wrong_answer="旧版本仍推荐。",
        correct_answer="以最新制度为准。",
        attack_type="benign_error",
    )

    assert sample["trust_label"] == "benign_error"
