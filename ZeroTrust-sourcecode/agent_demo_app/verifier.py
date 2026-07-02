from __future__ import annotations

from datetime import timedelta
from typing import Dict, Any, List, Tuple

from .config import DEFAULT_TIME_WINDOW_SECONDS, ROLE_PERMISSIONS
from .models import ValidationResult
from .signer import ClaimPackageSignerVerifier
from .utils import parse_time

REQUIRED_FIELDS = [
    "package_id", "schema_version", "mid", "tid", "agent_id", "role", "type",
    "claim_id", "claim_group_id", "subject", "predicate", "object", "confidence",
    "timestamp", "nonce", "signature",
]


class ClaimPackageVerifier:
    def __init__(self, data: Dict[str, Any], time_window_seconds: int = DEFAULT_TIME_WINDOW_SECONDS):
        self.data = data
        self.time_window = timedelta(seconds=time_window_seconds)
        self.signer = ClaimPackageSignerVerifier()
        self.seen_nonce: set[Tuple[str, str]] = set()
        self.reference_time = None

    def reset(self) -> None:
        self.seen_nonce.clear()

    def _schema_ok(self, package: Dict[str, Any], reasons: List[str]) -> bool:
        missing = [k for k in REQUIRED_FIELDS if k not in package or package.get(k) in (None, "")]
        if missing:
            reasons.append("missing_fields:" + ",".join(missing))
            return False
        conf = package.get("confidence")
        if not isinstance(conf, (int, float)) or conf < 0 or conf > 1:
            reasons.append("confidence_out_of_range")
            return False
        if not isinstance(package.get("evidence_ids", []), list):
            reasons.append("evidence_ids_not_list")
            return False
        return True

    def _signature_ok(self, package: Dict[str, Any], reasons: List[str]) -> bool:
        agent = self.data["agent_index"].get(package.get("agent_id"))
        if not agent:
            reasons.append("unknown_agent")
            return False
        ok = self.signer.verify(package, agent["hmac_secret"])
        if not ok:
            reasons.append("invalid_signature")
        return ok

    def _time_ok(self, package: Dict[str, Any], reasons: List[str]) -> bool:
        try:
            t = parse_time(package["timestamp"])
        except Exception:
            reasons.append("invalid_timestamp")
            return False
        ref = self.reference_time or t
        ok = abs(ref - t) <= self.time_window
        if not ok:
            reasons.append("timestamp_outside_window")
        return ok

    def _nonce_ok(self, package: Dict[str, Any], reasons: List[str]) -> bool:
        key = (package.get("agent_id"), package.get("nonce"))
        if key in self.seen_nonce:
            reasons.append("replayed_nonce")
            return False
        self.seen_nonce.add(key)
        return True

    def _permission_ok(self, package: Dict[str, Any], reasons: List[str]) -> bool:
        agent = self.data["agent_index"].get(package.get("agent_id"), {})
        allowed = agent.get("permissions") or ROLE_PERMISSIONS.get(package.get("role"), [])
        ok = package.get("type") in allowed
        if not ok:
            reasons.append("role_permission_denied")
        return ok

    def _evidence_ok(self, package: Dict[str, Any], reasons: List[str]) -> bool:
        ev_ids = package.get("evidence_ids", []) or []
        ev_index = self.data.get("evidence_index", {})
        missing = [e for e in ev_ids if e not in ev_index]
        if missing:
            reasons.append("unknown_evidence:" + ",".join(missing))
            return False
        high_conf = float(package.get("confidence") or 0) >= 0.75
        high_risk_action = package.get("type") == "action_recommendation" and package.get("object") == "block_ip"
        if (high_conf or high_risk_action) and not ev_ids:
            reasons.append("high_confidence_or_risk_action_without_evidence")
            return False
        return True

    def _tool_ok(self, package: Dict[str, Any], reasons: List[str]) -> bool:
        tool_id = package.get("tool_call_id")
        if not tool_id:
            return True
        tool = self.data.get("tool_index", {}).get(tool_id)
        if not tool:
            reasons.append("unknown_tool_call")
            return False
        ok = tool.get("actual_tool_hash") == package.get("tool_hash")
        if not ok:
            reasons.append("tool_hash_mismatch")
        return ok

    def verify(self, package: Dict[str, Any]) -> ValidationResult:
        reasons: List[str] = []
        checks = {
            "I_schema": self._schema_ok(package, reasons),
            "I_sig": self._signature_ok(package, reasons),
            "I_time": self._time_ok(package, reasons),
            "I_nonce": self._nonce_ok(package, reasons),
            "I_perm": self._permission_ok(package, reasons),
            "I_ev": self._evidence_ok(package, reasons),
            "I_tool": self._tool_ok(package, reasons),
        }
        passed = all(checks.values())
        return ValidationResult(
            claim_id=package.get("claim_id", ""),
            package_id=package.get("package_id", ""),
            agent_id=package.get("agent_id", ""),
            checks=checks,
            passed=passed,
            reasons=reasons,
        )

    def verify_all(self, packages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        self.reset()
        times = []
        for p in packages:
            try:
                times.append(parse_time(p["timestamp"]))
            except Exception:
                pass
        self.reference_time = max(times) if times else None
        return [self.verify(p).to_dict() for p in packages]
