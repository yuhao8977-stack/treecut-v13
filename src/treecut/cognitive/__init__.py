"""AI Business Cognitive System — 认知体系模块。

模块组成：
  store.py     — 6 张新表（scene_semantics/knowledge_entries/content_classification/
                 account_dna/content_templates/learning_rules）
  knowledge.py — 知识库加载/校验/热更新（JSON → SQLite）
  brain.py     — 认知引擎（7 层调用链）
  industry.py  — Layer3/4 行业知识引擎（特征抽取 + 内容分类）
"""
from __future__ import annotations

from treecut.cognitive.store import CognitiveStore
from treecut.cognitive.knowledge import KnowledgeLoader, KNOWLEDGE_ROOT
from treecut.cognitive.brain import Brain
from treecut.cognitive.industry import IndustryEngine

__all__ = ["CognitiveStore", "KnowledgeLoader", "Brain", "KnowledgeLoader",
           "IndustryEngine", "KNOWLEDGE_ROOT"]

