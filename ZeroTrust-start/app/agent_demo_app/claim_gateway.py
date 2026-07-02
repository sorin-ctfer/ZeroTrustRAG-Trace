from __future__ import annotations

from typing import Dict, Any, List

from .config import SCHEMA_VERSION
from .signer import ClaimPackageSignerVerifier, canonical_payload


class ClaimGateway:
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.signer = ClaimPackageSignerVerifier()

    def build_package(self, event: Dict[str, Any]) -> Dict[str, Any]:
        agent = self.data["agent_index"][event["sender"]]
        tool = self.data["tool_index"].get(event.get("tool_call_id"), {})
        package = {
            "package_id": f"PKG_{event['event_id']}",
            "schema_version": SCHEMA_VERSION,
            "mid": event["event_id"],
            "tid": event["task_id"],
            "round": event["round"],
            "agent_id": event["sender"],
            "receiver": event["receiver"],
            "role": agent["role"],
            "type": event["claim_type"],
            "claim_id": event["claim_id"],
            "claim_group_id": event["claim_group_id"],
            "subject": event.get("subject"),
            "predicate": event.get("predicate"),
            "object": event.get("object"),
            "label": event.get("label"),
            "confidence": event.get("confidence"),
            "evidence_ids": list(event.get("evidence_ids", [])),
            "parent_claim_ids": list(event.get("parent_claim_ids", [])),
            "tool_call_id": event.get("tool_call_id"),
            "tool_hash": event.get("tool_hash_declared") or tool.get("declared_tool_hash"),
            "timestamp": event.get("timestamp"),
            "nonce": event.get("nonce"),
            "message_hash_sent": event.get("message_hash_sent"),
            "message_hash_received": event.get("message_hash_received"),
            "transport_integrity": bool(event.get("transport_integrity", True)),
            "gateway_received": bool(event.get("gateway_received", True)),
            "risk": 0.0,
            "scenario": event.get("scenario", "unknown"),
            "attack_vector": event.get("attack_vector", "none"),
            "raw_message": event.get("received_message"),
        }
        if event.get("schema_status") == "missing_subject":
            package.pop("subject", None)
        secret = agent["hmac_secret"]
        if event.get("signature_status") == "invalid":
            secret = "wrong-demo-secret::" + agent["agent_id"]
        package["signature"] = self.signer.sign(package, secret)
        package["canonical_json_before_signature"] = canonical_payload(package)
        return package

    def build_all(self, events: List[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
        events = events if events is not None else self.data.get("comm_events", [])
        return [self.build_package(e) for e in events]
