# -*- coding: utf-8 -*-
"""Stage 2.1 — UtteranceContextV1：话语语境分类。

Hypothetical/conditional 等非断言语境不得作为 CURRENT_CONTEXT 断言，
也不得与 FACTORY 产生 scene conflict（修复 ConflictResolverV1 过度敏感问题）。

类型：
  ASSERTED         明确断言（“这是客户家”“我们在客户家”）
  HYPOTHETICAL     假设（“如果家里有宝宝”“假如”）
  CONDITIONAL      条件（“要是”“有宝宝的话”）
  GENERIC_EXAMPLE  泛例（“比如”“比如说”）
  NEGATED          否定
  QUOTED           引用
  UNKNOWN          无法判断
"""
from __future__ import annotations

import re

# 中文假设/条件/泛例语境标记
_HYPOTHETICAL_PATTERNS = [
    "如果", "假如", "要是", "假设", "以后如果",
    "有宝宝的话", "家里如果", "客户如果",
    "比如说", "比如", "例如", "举个例",
    "如果说", "假如说",
]
_ASSERTED_PATTERNS = [
    "这是客户家", "我们现在在客户家", "这个是业主家里的",
    "这是业主家", "这就是客户家", "我们来到了客户家",
    "这位客户家", "客户家里",
]
_NEGATED_PATTERNS = ["不是", "并没有", "没有", "并非", "绝不是"]
_QUOTED_PATTERNS = ["客户说", "他说", "她说", "业主说", "他们要求", "客户要求"]


class UtteranceContextV1:
    """话语语境分类器。"""

    def __init__(self):
        self.version = "UTTERANCE_CONTEXT_V1"

    def classify(self, asr_text: str) -> dict:
        text = asr_text or ""
        # 断言优先（明确“这是客户家”）
        for p in _ASSERTED_PATTERNS:
            if p in text:
                return {"context": "ASSERTED", "matched": p, "home_asserted": True}
        # 假设/条件/泛例（不得作为 CURRENT_CONTEXT 断言）
        for p in _HYPOTHETICAL_PATTERNS:
            if p in text:
                return {"context": "HYPOTHETICAL", "matched": p, "home_asserted": False}
        for p in _QUOTED_PATTERNS:
            if p in text:
                return {"context": "QUOTED", "matched": p, "home_asserted": False}
        for p in _NEGATED_PATTERNS:
            if p in text:
                return {"context": "NEGATED", "matched": p, "home_asserted": False}
        # 含"家"但无假设/断言标记 → 无法确定
        if "家" in text or "家里" in text:
            return {"context": "UNKNOWN", "matched": None, "home_asserted": False}
        return {"context": "NONE", "matched": None, "home_asserted": False}

    def home_words_present(self, asr_text: str) -> bool:
        return any(w in (asr_text or "") for w in ("客户家", "家里", "自己家", "我家", "业主家"))
