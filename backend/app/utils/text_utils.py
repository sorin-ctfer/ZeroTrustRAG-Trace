"""
文本工具函数：TF-IDF 检索、相似度计算、声明拆分、关键词提取。

MVP 使用字符 n-gram + sklearn TfidfVectorizer，无需 jieba。
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ---------------------------------------------------------------------------
# 哈希
# ---------------------------------------------------------------------------

def sha256_hash(text: str) -> str:
    """计算文本的 SHA-256 哈希。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# TF-IDF 检索器
# ---------------------------------------------------------------------------

class TfidfRetriever:
    """
    基于 TF-IDF 的简单检索器。

    使用字符级 n-gram (2,4) 适配中文，无需分词。
    """

    def __init__(self, ngram_range: tuple[int, int] = (2, 4), max_features: int = 5000):
        self.vectorizer = TfidfVectorizer(
            analyzer="char",
            ngram_range=ngram_range,
            max_features=max_features,
        )
        self._doc_matrix: Optional[np.ndarray] = None
        self._doc_ids: list[str] = []

    def index(self, doc_ids: list[str], doc_texts: list[str]) -> None:
        """构建索引。"""
        self._doc_ids = doc_ids
        self._doc_matrix = self.vectorizer.fit_transform(doc_texts)

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[tuple[str, float]]:
        """
        检索 Top-K。

        返回: [(doc_id, score), ...] 按分数降序。
        """
        if self._doc_matrix is None or len(self._doc_ids) == 0:
            return []
        q_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(q_vec, self._doc_matrix)[0]
        top_indices = np.argsort(scores)[::-1][:top_k]
        return [(self._doc_ids[i], float(scores[i])) for i in top_indices]

    def similarity(self, text_a: str, text_b: str) -> float:
        """计算两段文本的余弦相似度。"""
        vecs = self.vectorizer.transform([text_a, text_b])
        return float(cosine_similarity(vecs[0:1], vecs[1:2])[0, 0])


# ---------------------------------------------------------------------------
# 文本处理
# ---------------------------------------------------------------------------

def split_claims(text: str) -> list[str]:
    """
    将答案拆分为原子声明。

    策略：按句号、分号切分；过滤空句和过短句。
    """
    parts = re.split(r"[。；!！?？\n]", text)
    claims = []
    for p in parts:
        p = p.strip()
        if len(p) >= 4:
            claims.append(p)
    return claims


def extract_key_terms(text: str) -> set[str]:
    """
    提取关键词/关键短语（MVP：基于字符 bigram + 高频词）。

    对于短文本，直接按标点切分后取连续 2-4 字的子串作为候选。
    """
    # 去除标点和空白
    cleaned = re.sub(r"[^一-鿿\w]", "", text)
    terms: set[str] = set()
    # 提取 2-4 字的滑动窗口
    for n in range(2, min(5, len(cleaned) + 1)):
        for i in range(len(cleaned) - n + 1):
            terms.add(cleaned[i : i + n])
    # 也添加整词（按标点切分）
    for word in re.split(r"[，。、；：！？\s]", text):
        w = word.strip()
        if 2 <= len(w) <= 8:
            terms.add(w)
    return terms


def query_term_coverage(query: str, doc: str) -> float:
    """
    查询词覆盖率：查询中的关键字符 bigram 出现在文档中的比例。
    """
    q_terms = extract_key_terms(query)
    if not q_terms:
        return 0.0
    hits = sum(1 for t in q_terms if t in doc)
    return hits / len(q_terms)


# ---------------------------------------------------------------------------
# 否定词 / 权威词 / 排他词 词典
# ---------------------------------------------------------------------------

NEGATION_WORDS = {
    "不", "未", "没有", "无", "非", "勿", "禁止", "不得", "不可",
    "不允许", "不能", "不会", "并非", "并非如此",
}

AUTHORITY_WORDS = {
    "权威", "官方", "认证", "确认", "验证", "规定", "规范", "标准",
    "要求", "必须", "强制", "已获", "获准", "公告",
}

EXCLUSIVE_WORDS = {
    "唯一", "仅需", "只需", "无需", "不必", "不再", "彻底",
    "完全", "全部", "一定", "必然", "绝对", "已经",
}

INSTRUCTION_WORDS = {
    "应当", "应该", "必须", "务必", "请", "需要", "要求",
    "建议", "可以", "允许", "许可",
}


def count_word_matches(text: str, word_set: set[str]) -> int:
    """统计文本中命中词典的词数。"""
    return sum(1 for w in word_set if w in text)


def has_negation(text: str) -> bool:
    """文本是否包含否定词。"""
    return any(w in text for w in NEGATION_WORDS)


def extract_target_phrases(target_answer: str) -> list[str]:
    """
    从攻击目标答案中提取关键短语，用于匹配。
    """
    phrases = []
    for seg in re.split(r"[，。、；：！？\s]", target_answer):
        seg = seg.strip()
        if 2 <= len(seg) <= 12:
            phrases.append(seg)
    return phrases


def target_claim_presence(answer: str, target_phrases: list[str]) -> float:
    """
    检查目标错误声明在答案中的出现程度。

    返回: 0.0 ~ 1.0，命中短语比例。
    """
    if not target_phrases:
        return 0.0
    hits = sum(1 for p in target_phrases if p in answer)
    return hits / len(target_phrases)
