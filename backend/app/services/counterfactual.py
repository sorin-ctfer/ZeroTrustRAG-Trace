"""
四路反事实验证 + CausalScore 因果分。

对应报告公式 (2-6) ~ (2-9)。
MVP 使用模板生成 + 目标声明匹配模拟 pO/pR/pS/pT。
"""

from __future__ import annotations

from typing import Protocol

from ..models.schema import Evidence, CounterfactualResult
from ..utils.text_utils import (
    split_claims,
    extract_target_phrases,
    target_claim_presence,
    TfidfRetriever,
)
from ..utils.score_utils import compute_causal_score


class CounterfactualProtocol(Protocol):
    """反事实生成与因果评分实现的可替换接口。"""

    def run(
        self,
        query: str,
        suspicious_evidence: Evidence,
        top_k_evidences: list[Evidence],
        all_evidences: list[Evidence],
        target_wrong_answer: str,
    ) -> CounterfactualResult:
        """执行 O/R/S/T 四路验证。"""
        ...


# ---------------------------------------------------------------------------
# 模板答案生成
# ---------------------------------------------------------------------------

def _template_generate(query: str, evidences: list[Evidence]) -> str:
    """
    模板化答案生成（MVP 不使用 LLM）。

    策略：从证据中提取与查询最相关的句子拼接为答案。
    """
    if not evidences:
        return f'关于“{query}”，现有证据不足以确认。'

    retriever = TfidfRetriever()
    doc_ids = [ev.evidence_id for ev in evidences]
    doc_texts = [ev.content for ev in evidences]
    retriever.index(doc_ids, doc_texts)

    # 收集各证据中与 query 最相关的句子
    relevant_sentences: list[tuple[float, str, str]] = []  # (score, sentence, evidence_id)

    for ev in evidences:
        sentences = split_claims(ev.content)
        for sent in sentences:
            sim = retriever.similarity(query, sent)
            if sim > 0.05:  # 最低相关性阈值
                relevant_sentences.append((sim, sent, ev.evidence_id))

    # 按相似度排序，取 top 句子
    relevant_sentences.sort(key=lambda x: x[0], reverse=True)
    top_sents = relevant_sentences[:5]

    if not top_sents:
        return f'关于“{query}”，现有证据不足以确认。'

    # 拼接答案
    parts = [f"{s}[{eid}]" for _, s, eid in top_sents]
    answer = f'关于“{query}”，根据证据：' + "；".join(parts)
    return answer


def _target_probability(
    answer: str,
    evidences: list[Evidence],
    target_wrong_answer: str,
) -> float:
    """估计目标错误声明在一路生成中的出现概率。"""
    target_phrases = extract_target_phrases(target_wrong_answer)
    phrase_score = target_claim_presence(answer, target_phrases)
    if not evidences:
        return phrase_score

    retriever = TfidfRetriever()
    retriever.index(
        [ev.evidence_id for ev in evidences],
        [ev.content for ev in evidences],
    )
    alignment = max(
        retriever.similarity(target_wrong_answer, ev.content)
        for ev in evidences
    )
    poisoned_ratio = sum(ev.is_poisoned for ev in evidences) / len(evidences)
    return min(1.0, 0.40 * phrase_score + 0.45 * alignment + 0.15 * poisoned_ratio)


# ---------------------------------------------------------------------------
# 四路反事实验证
# ---------------------------------------------------------------------------

def run_counterfactual(
    query: str,
    suspicious_evidence: Evidence,
    top_k_evidences: list[Evidence],
    all_evidences: list[Evidence],
    target_wrong_answer: str,
    trusted_evidence_ids: list[str] | None = None,
) -> CounterfactualResult:
    """
    执行四路反事实验证。

    O (原始): 使用原始 Top-K 证据
    R (删除): 从 Top-K 删除可疑 Chunk
    S (单片段): 仅使用可疑 Chunk
    T (替代): 使用可信证据替代可疑 Chunk

    pO/pR/pS/pT: 目标错误声明在各路答案中的出现程度 (0~1)。
    """
    trusted_ids = set(trusted_evidence_ids or [])

    # O: 原始 Top-K
    answer_O = _template_generate(query, top_k_evidences)

    # R: 删除可疑 Chunk
    remaining = [ev for ev in top_k_evidences if ev.evidence_id != suspicious_evidence.evidence_id]
    answer_R = _template_generate(query, remaining)

    # S: 仅使用可疑 Chunk
    answer_S = _template_generate(query, [suspicious_evidence])

    # T: 可信证据替代
    trusted_ev = [ev for ev in all_evidences if ev.evidence_id in trusted_ids]
    if not trusted_ev:
        # 如果没有指定可信证据，使用非可疑的 top-k
        trusted_ev = remaining
    answer_T = _template_generate(query, trusted_ev)

    # 计算 pO/pR/pS/pT: 目标错误声明出现程度
    pO = _target_probability(answer_O, top_k_evidences, target_wrong_answer)
    pR = _target_probability(answer_R, remaining, target_wrong_answer)
    pS = _target_probability(answer_S, [suspicious_evidence], target_wrong_answer)
    pT = _target_probability(answer_T, trusted_ev, target_wrong_answer)

    # 计算因果分 (公式 2-6 ~ 2-9)
    e_remove, e_solo, e_replace, causal = compute_causal_score(pO, pR, pS, pT)

    return CounterfactualResult(
        suspicious_evidence_id=suspicious_evidence.evidence_id,
        original_answer=answer_O,
        remove_answer=answer_R,
        solo_answer=answer_S,
        replace_answer=answer_T,
        pO=round(pO, 4),
        pR=round(pR, 4),
        pS=round(pS, 4),
        pT=round(pT, 4),
        E_remove=round(e_remove, 4),
        E_solo=round(e_solo, 4),
        E_replace=round(e_replace, 4),
        causal_score=round(causal, 4),
    )


def run_all_counterfactuals(
    query: str,
    suspicious_evidences: list[Evidence],
    top_k_evidences: list[Evidence],
    all_evidences: list[Evidence],
    target_wrong_answer: str,
    trusted_evidence_ids: list[str] | None = None,
) -> list[CounterfactualResult]:
    """对所有可疑证据执行反事实验证。"""
    results = []
    for ev in suspicious_evidences:
        result = run_counterfactual(
            query=query,
            suspicious_evidence=ev,
            top_k_evidences=top_k_evidences,
            all_evidences=all_evidences,
            target_wrong_answer=target_wrong_answer,
            trusted_evidence_ids=trusted_evidence_ids,
        )
        results.append(result)
    return results
