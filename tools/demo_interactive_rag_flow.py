"""Run a local interactive RAG poisoning demo through HTTP APIs."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request


BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/api"
DEFAULT_QUESTION = "生产系统权限变更是否需要主管审批？"


def request(method: str, path: str, payload: dict | None = None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise SystemExit(exc.read().decode("utf-8")) from exc
    if body.get("success") is False:
        raise SystemExit(body.get("error") or "API request failed")
    return body.get("data")


def main() -> None:
    health = request("GET", "/health")
    request("POST", "/external-knowledge/load-demo")
    samples = request("POST", "/poison-samples/load-demo")
    enabled_samples = [item for item in request("GET", "/poison-samples/list") if item.get("enabled", True)]
    sample = next(
        (
            item for item in enabled_samples
            if item.get("attack_type") == "policy_bypass" and "权限变更" in item.get("target_query", "")
        ),
        enabled_samples[0] if enabled_samples else samples[0],
    )
    question = sample.get("target_query") or DEFAULT_QUESTION
    if sample.get("attack_type") == "policy_bypass":
        question = "生产系统权限变更是否无需主管审批，可以直接执行？"
    session = request("POST", "/interactive/session/create")
    before = request("POST", "/interactive/rag/chat", {
        "session_id": session["session_id"],
        "question": question,
        "stage": "before_poison",
    })
    request("POST", f"/interactive/session/{session['session_id']}/inject-poison", {"sample_id": sample["sample_id"]})
    after = request("POST", "/interactive/rag/chat", {
        "session_id": session["session_id"],
        "question": question,
        "stage": "after_poison",
    })
    detection = request("POST", "/interactive/rag/chat-detect", {
        "session_id": session["session_id"],
        "question": question,
        "before_answer": before["answer"],
        "after_answer": after["answer"],
    })
    detail = request("GET", f"/interactive/correction/{session['session_id']}/detail")
    print(json.dumps({
        "health": health,
        "session_id": session["session_id"],
        "sample_id": sample["sample_id"],
        "before_topk": [item["chunk_id"] for item in before["retrieved_chunks"]],
        "after_topk": [item["chunk_id"] for item in after["retrieved_chunks"]],
        "risk_level": detection["risk_level"],
        "detection_mode": detection["detection_mode"],
        "metrics": detection["metrics"],
        "correction_ready": detail["ready"],
        "correction_url": f"http://127.0.0.1:5173/interactive-correction/{session['session_id']}",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
