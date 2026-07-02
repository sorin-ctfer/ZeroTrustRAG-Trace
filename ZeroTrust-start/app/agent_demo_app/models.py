from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any, List


@dataclass
class ValidationResult:
    claim_id: str
    package_id: str
    agent_id: str
    checks: Dict[str, bool]
    passed: bool
    reasons: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RiskScore:
    agent_id: str
    H: float
    R: float
    P: float
    S: float
    D: float
    F: float
    O: float
    M: float
    bss: float
    status: str
    root_cause: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
