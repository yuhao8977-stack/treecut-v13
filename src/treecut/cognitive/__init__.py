"""AI Business Cognitive System — 认知体系模块。

模块组成：
  store.py     — 6 张新表（scene_semantics/knowledge_entries/content_classification/
                 account_dna/content_templates/learning_rules）
  knowledge.py — 知识库加载/校验/热更新（JSON → SQLite）
  brain.py     — 认知引擎（7 层调用链）
  industry.py  — Layer3/4 行业知识引擎（特征抽取 + 内容分类）
  account.py   — Layer5 账号适配度引擎
  template.py  — Layer6 模板匹配 + 商业价值引擎
  learning.py  — Layer7 反馈学习引擎
  production.py — Phase5 认知生产引擎（模板→选材→成片）
"""
from __future__ import annotations

from treecut.cognitive.store import CognitiveStore
from treecut.cognitive.knowledge import KnowledgeLoader, KNOWLEDGE_ROOT
from treecut.cognitive.brain import Brain
from treecut.cognitive.industry import IndustryEngine
from treecut.cognitive.account import AccountEngine
from treecut.cognitive.template import TemplateEngine
from treecut.cognitive.learning import LearningEngine
from treecut.cognitive.production import ProductionEngine

__all__ = ["CognitiveStore", "KnowledgeLoader", "Brain", "IndustryEngine",
           "AccountEngine", "TemplateEngine", "LearningEngine",
           "ProductionEngine", "KNOWLEDGE_ROOT"]


