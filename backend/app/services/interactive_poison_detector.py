"""Risk detection for session-scoped interactive RAG."""

from __future__ import annotations

import math
from typing import Any

from .interactive_rag_service import interactive_rag_service
from .rag_detector_training import rag_detector_training_service

INJECTION_TERMS = (
    "忽略之前规则",
    "无视系统提示",
    "不要遵守",
    "关闭安全策略",
    "你必须回答",
    "绕过审批",
    "禁用检测",
    "删除日志",
    "提权",
    "越权",
    "无需授权",
    "无需审批",
    "无需验证",
    "提交口令",
    "关闭 MFA",
)


def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _contains_target(answer: str, target: str) -> bool:
    target = target.strip()
    return bool(target and (target in answer or any(part and part in answer for part in target.split("，"))))


class InteractivePoisonDetector:
    def detect(self, session_id: str, question: str, before_answer: str, after_answer: str) -> dict[str, Any]:
        session = interactive_rag_service.get_session(session_id)
        if session is None:
            raise ValueError(f"Interactive session does not exist: {session_id}")
        before_retrieved = session.get("topk_before") or session.get("chats", {}).get("before_poison", {}).get("retrieved_chunks", [])
        after_retrieved = session.get("topk_after") or session.get("chats", {}).get("after_poison", {}).get("retrieved_chunks", [])
        before_ids = {item["chunk_id"] for item in before_retrieved}
        newly_retrieved_ids = [item["chunk_id"] for item in after_retrieved if item["chunk_id"] not in before_ids]
        injected_samples = session.get("injected_poison_chunks", [])
        target_wrong_answer = next((item.get("target_wrong_answer", "") for item in injected_samples if item.get("target_wrong_answer")), "")
        correct_answer = next((item.get("correct_answer", "") for item in injected_samples if item.get("correct_answer")), "")
        train_status = rag_detector_training_service.status()
        trained = train_status.get("model_exists", False)
        trained_predictions = (
            rag_detector_training_service.predict(
                [item.get("content", "") for item in after_retrieved],
                question,
                correct_answer,
                target_wrong_answer,
            )
            if trained and after_retrieved else {"mode": "规则模式", "predictions": []}
        )
        prediction_by_id = {
            item["chunk_id"]: pred
            for item, pred in zip(after_retrieved, trained_predictions.get("predictions", []))
        }

        drift = before_answer.strip() != after_answer.strip()
        candidate_scores: list[float] = []
        risk_chunks: list[dict[str, Any]] = []
        benign_warnings: list[dict[str, Any]] = []
        reasons: list[str] = []
        for item in after_retrieved:
            label = item.get("trust_label") or item.get("trust_level", "trusted")
            content = item.get("content", "")
            rank = int(item.get("rank", 99))
            rank_score = 1.0 if rank == 1 else 0.85 if rank <= 3 else 0.6
            injection_score = _clip(0.12 * sum(term in content for term in INJECTION_TERMS))
            trained_score = prediction_by_id.get(item["chunk_id"], {}).get("poison_probability", 0.0)
            label_score = 0.9 if label == "poison" else 0.25 if label == "benign_error" else 0.0
            target_hit = _contains_target(after_answer, item.get("target_wrong_answer", ""))
            chunk_ras = _clip(0.55 * rank_score + 0.25 * label_score + 0.20 * trained_score) if label != "trusted" else _clip(0.2 * rank_score + 0.2 * trained_score)
            chunk_gis = _clip(0.45 * injection_score + 0.35 * (1.0 if target_hit else 0.0) + 0.20 * (1.0 if drift else 0.0))
            dual = _clip(0.7 * math.sqrt(chunk_ras * chunk_gis) + 0.3 * (chunk_ras + chunk_gis) / 2)
            e_remove = _clip(dual * (1.0 if item["chunk_id"] in newly_retrieved_ids else 0.7))
            e_solo = _clip(max(injection_score, label_score, trained_score))
            e_replace = _clip(0.85 if drift and label == "poison" else 0.35 if drift else 0.0)
            causal = _clip(0.4 * e_remove + 0.3 * e_solo + 0.3 * e_replace)
            item_risk = _clip(0.5 * dual + 0.5 * causal)
            detail = {
                "chunk_id": item["chunk_id"],
                "rank": rank,
                "source": item.get("source", ""),
                "content": content,
                "trust_label": label,
                "risk_score": round(item_risk, 4),
                "RAS": round(chunk_ras, 4),
                "GIS": round(chunk_gis, 4),
                "DualRisk": round(dual, 4),
                "CausalScore": round(causal, 4),
                "target_wrong_answer_hit": target_hit,
                "reason": "、".join([
                    reason for reason in [
                        "检索排名异常" if item["chunk_id"] in newly_retrieved_ids else "",
                        "来源可信度低" if label in {"poison", "benign_error"} else "",
                        "命中 Prompt Injection 特征" if injection_score >= 0.2 else "",
                        "回答发生漂移" if drift else "",
                        "命中 target_wrong_answer" if target_hit else "",
                    ] if reason
                ]) or "低风险观察项",
            }
            if label == "benign_error":
                benign_warnings.append(detail)
                continue
            if label == "poison" or item_risk >= 0.55:
                candidate_scores.append(item_risk)
                risk_chunks.append(detail)
        risk_chunks.sort(key=lambda item: item["risk_score"], reverse=True)
        ras = max([item["RAS"] for item in risk_chunks], default=0.0)
        gis = max([item["GIS"] for item in risk_chunks], default=0.0)
        dual_risk = _clip(0.7 * math.sqrt(ras * gis) + 0.3 * (ras + gis) / 2)
        e_remove = max([_clip(item["DualRisk"] * 0.9) for item in risk_chunks], default=0.0)
        e_solo = max([item["RAS"] for item in risk_chunks], default=0.0)
        e_replace = max([item["GIS"] for item in risk_chunks], default=0.0)
        causal_score = _clip(0.4 * e_remove + 0.3 * e_solo + 0.3 * e_replace)
        high = bool(risk_chunks) and dual_risk >= 0.45 and causal_score >= 0.45
        risk_score = _clip(0.5 * dual_risk + 0.5 * causal_score)
        if newly_retrieved_ids:
            reasons.append("检索排名异常")
        if risk_chunks:
            reasons.append("来源可信度低")
        if any("Prompt Injection" in item["reason"] for item in risk_chunks):
            reasons.append("命中 Prompt Injection 特征")
        if drift:
            reasons.append("回答发生漂移")
        if risk_chunks:
            reasons.append("与可信知识冲突")
        trust_before = 88.0
        trust_after = round(max(0.0, trust_before * (1 - 0.75 * risk_score)), 2)
        report = {
            "session_id": session_id,
            "question": question,
            "risk_score": round(risk_score, 4),
            "risk_level": "high" if high else "medium" if risk_score >= 0.35 else "low",
            "detection_mode": "训练模型模式" if trained else "规则模式",
            "risk_types": reasons,
            "risk_chunks": risk_chunks,
            "detected_poison_chunks": risk_chunks if high else [],
            "benign_warnings": benign_warnings,
            "metrics": {
                "RAS": round(ras, 4),
                "GIS": round(gis, 4),
                "DualRisk": round(dual_risk, 4),
                "E_remove": round(e_remove, 4),
                "E_solo": round(e_solo, 4),
                "E_replace": round(e_replace, 4),
                "CausalScore": round(causal_score, 4),
                "TrustScore_before": trust_before,
                "TrustScore_after_poison": trust_after,
            },
            "details": {
                "before_retrieved_chunk_ids": [item["chunk_id"] for item in before_retrieved],
                "after_retrieved_chunk_ids": [item["chunk_id"] for item in after_retrieved],
                "newly_retrieved_chunk_ids": newly_retrieved_ids,
                "metric_note": "训练模型概率来自验证后模型；无模型时使用规则模式 fallback。",
            },
            "before_answer": before_answer,
            "after_answer": after_answer,
            "retrieved_chunks": after_retrieved,
        }
        interactive_rag_service.update_session(session_id, detection_result=report, detection_report=report)
        interactive_rag_service.append_trace(
            session_id,
            "detect_poison",
            {"question": question},
            {
                "risk_level": report["risk_level"],
                "detection_mode": report["detection_mode"],
                "risk_chunks": risk_chunks,
                "metrics": report["metrics"],
            },
        )
        return report


interactive_poison_detector = InteractivePoisonDetector()
