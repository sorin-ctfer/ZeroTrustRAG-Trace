"""
案例加载器：从 JSON 文件加载 DemoCase。

⚠️ 安全声明：以下数据仅为本地防御检测演示，不得用于真实攻击。
所有投毒样本仅在本地模拟环境中使用，不连接任何真实服务。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Protocol

from ..models.schema import DemoCase, Evidence
from ..utils.text_utils import sha256_hash

# demo_cases 目录
_DEMO_DIR = Path(__file__).resolve().parent.parent / "data" / "demo_cases"

# 已加载的案例缓存
_cases: dict[str, DemoCase] = {}


class CaseLoaderProtocol(Protocol):
    """案例存储后端的可替换接口。"""

    def load_case(self, case_id: str) -> Optional[DemoCase]:
        """按 ID 加载案例。"""
        ...

    def load_all_cases(self) -> list[DemoCase]:
        """加载全部案例。"""
        ...


def _compute_hashes(case: DemoCase) -> DemoCase:
    """为所有 Evidence 计算 content_hash。"""
    for ev in case.evidences:
        if not ev.content_hash:
            ev.content_hash = sha256_hash(ev.content)
    return case


def load_case(case_id: str) -> Optional[DemoCase]:
    """按 case_id 加载单个案例，返回 None 如果不存在。"""
    if case_id in _cases:
        return _cases[case_id]

    # 尝试精确匹配文件名
    json_path = _DEMO_DIR / f"{case_id}.json"
    if not json_path.exists():
        return None

    with open(json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    case = DemoCase(**raw)
    case = _compute_hashes(case)
    _cases[case_id] = case
    return case


def load_all_cases() -> list[DemoCase]:
    """加载所有案例。"""
    cases: list[DemoCase] = []
    if not _DEMO_DIR.exists():
        return cases

    for json_path in sorted(_DEMO_DIR.glob("*.json")):
        case_id = json_path.stem
        case = load_case(case_id)
        if case is not None:
            cases.append(case)
    return cases


def list_case_ids() -> list[str]:
    """列出所有可用案例 ID。"""
    if not _DEMO_DIR.exists():
        return []
    return sorted(p.stem for p in _DEMO_DIR.glob("*.json"))
