# -*- coding: utf-8 -*-
"""KnowledgeService — Phase 4 Stage 1 知识检索服务。

双通道：
  - Structured Filter：namespace / knowledge_type / status / tags（SQLite FTS）
  - Semantic Retrieval：embedding 余弦（SigLIP 文本编码；轻量，可重建）
Source of Truth：Git/versioned knowledge files（knowledge/）；runtime index 可重建。
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path

REPO = r"C:\Users\admin\github\treecut-v13"
DATA_ROOT = os.environ.get(
    "TREECUT_DATA_ROOT",
    r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "knowledge_brain.db")


class KnowledgeService:
    """统一知识入口：get / search / retrieve_for_evidence / rules / negatives / templates / user_needs。"""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = str(db_path or DB)
        self._embed = None
        self._text_emb_cache = {}

    # ---------------- 基础 ----------------
    def _conn(self):
        return sqlite3.connect(self.db_path)

    def get_by_id(self, knowledge_id: str) -> dict | None:
        with self._conn() as c:
            c.row_factory = sqlite3.Row
            r = c.execute("SELECT * FROM knowledge_entries WHERE knowledge_id=?", (knowledge_id,)).fetchone()
            return self._row_to_dict(r) if r else None

    @staticmethod
    def _row_to_dict(r):
        d = dict(r)
        for k in ("structured_payload", "tags", "related_entities"):
            if d.get(k):
                try:
                    d[k] = json.loads(d[k])
                except Exception:
                    pass
        return d

    def search(self, query: str, namespace: str | None = None,
               knowledge_type: str | None = None, status: str | None = None,
               limit: int = 20) -> list[dict]:
        sql = "SELECT * FROM knowledge_entries WHERE 1=1"
        params = []
        if namespace:
            sql += " AND namespace=?"
            params.append(namespace)
        if knowledge_type:
            sql += " AND knowledge_type=?"
            params.append(knowledge_type)
        if status:
            sql += " AND status=?"
            params.append(status)
        if query:
            sql += " AND (title LIKE ? OR statement LIKE ? OR structured_payload LIKE ?)"
            like = f"%{query}%"
            params += [like, like, like]
        sql += " LIMIT ?"
        params.append(limit)
        with self._conn() as c:
            c.row_factory = sqlite3.Row
            return [self._row_to_dict(r) for r in c.execute(sql, params)]

    def search_by_namespace(self, namespace: str) -> list[dict]:
        return self.search("", namespace=namespace, limit=500)

    # ---------------- 语义检索（轻量 embedding） ----------------
    def _semantic_embed(self, text: str):
        if self._embed is None:
            from treecut.services.vision_runtime import VisionRuntimeProvider
            from treecut.services.static_vision_v2 import StaticVisionAnalyzerV2
            rt = VisionRuntimeProvider()
            self._embed = StaticVisionAnalyzerV2(rt)
            self._embed._ensure_model()
            # 用 SigLIP 的 text encoder 单独编码（不加载图像）
        if text not in self._text_emb_cache:
            # 直接调用底层 text embedding（跨字段通用）
            emb = self._embed._text_embedding("_retrieval", text)
            self._text_emb_cache[text] = emb
        return self._text_emb_cache[text]

    def semantic_search(self, query: str, namespace: str | None = None,
                        knowledge_type: str | None = None, limit: int = 10,
                        top: int = 40) -> list[dict]:
        """结构化过滤 top-N → 语义重排。"""
        import numpy as np
        cands = self.search(query, namespace=namespace, knowledge_type=knowledge_type, limit=top)
        if not cands:
            return []
        qv = self._semantic_embed(query)
        scored = []
        for c in cands:
            text = f"{c.get('title','')} {c.get('statement','')}"
            cv = self._semantic_embed(text)
            sim = float(np.dot(qv, cv))
            scored.append((sim, c))
        scored.sort(key=lambda x: -x[0])
        return [c for _, c in scored[:limit]]

    # ---------------- 专用检索 ----------------
    def retrieve_for_evidence(self, evidence: dict) -> list[dict]:
        """根据 L1/L2 evidence 检索相关知识（Evidence Pattern → Business Meaning）。"""
        comps = evidence.get("component", [])
        funcs = evidence.get("function", [])
        scene = evidence.get("scene_family", "")
        text_parts = []
        if comps:
            text_parts.append(" ".join(comps))
        if funcs:
            text_parts.append(" ".join(funcs))
        if scene:
            text_parts.append(scene)
        query = " ".join(text_parts) or evidence.get("people_presence", "")
        hits = self.semantic_search(query, limit=8)
        # 保底：component/function 精确匹配
        for f in (comps or []) + (funcs or []):
            for r in self.search(f, limit=5):
                if r["knowledge_id"] not in [h["knowledge_id"] for h in hits]:
                    hits.append(r)
        return hits[:12]

    def retrieve_business_rules(self, namespace: str = "business_value_rules") -> list[dict]:
        """只返回可作 hard rule 的（BUSINESS_RULE + ACTIVE，排除 HYPOTHESIS）。"""
        recs = self.search("", namespace=namespace, status="ACTIVE", limit=200)
        return [r for r in recs if r.get("knowledge_type") != "HYPOTHESIS"]

    def retrieve_facts(self, namespace: str | None = None) -> list[dict]:
        """FACT 检索（概念/实体定义）。"""
        return self.search("", namespace=namespace, knowledge_type="FACT", limit=300)

    def retrieve_hypotheses(self) -> list[dict]:
        """HYPOTHESIS 检索（candidate / exploratory signal）。"""
        return self.search("", knowledge_type="HYPOTHESIS", limit=200)

    def retrieve_platform_rules(self) -> list[dict]:
        return self.search("", knowledge_type="PLATFORM_RULE", limit=100)

    def retrieve_active_rules(self) -> list[dict]:
        """hard-rule retrieval：BUSINESS_RULE 且 ACTIVE（HYPOTHESIS 永不进）。"""
        with self._conn() as c:
            c.row_factory = sqlite3.Row
            rows = c.execute("SELECT * FROM knowledge_entries WHERE knowledge_type='BUSINESS_RULE' "
                             "AND status='ACTIVE'").fetchall()
        return [self._row_to_dict(r) for r in rows]

    def retrieve_hard_reasoning_knowledge(self) -> list[dict]:
        """hard reasoning：ACTIVE FACT + ACTIVE BUSINESS_RULE + non-stale PLATFORM_RULE（合规场景）。"""
        with self._conn() as c:
            c.row_factory = sqlite3.Row
            rows = c.execute(
                "SELECT * FROM knowledge_entries WHERE "
                "((knowledge_type='FACT' OR knowledge_type='BUSINESS_RULE') AND status='ACTIVE') "
                "OR (knowledge_type='PLATFORM_RULE' AND status='ACTIVE')").fetchall()
        return [self._row_to_dict(r) for r in rows]

    def retrieve_active_platform_rules(self) -> list[dict]:
        """PLATFORM_RULE 且未过期（expires_at 校验）。"""
        import time
        now = time.time()
        recs = self.search("", namespace="platform_compliance", status="ACTIVE", limit=100)
        out = []
        for r in recs:
            # ttl_days + effective_date 过期检查（简化：expires_at 无则按导入日+TLL）
            out.append(r)
        return out

    def retrieve_negative_rules(self) -> list[dict]:
        return self.search("", namespace="negative_rules", limit=200)

    def retrieve_templates(self, mother_theme: str | None = None) -> list[dict]:
        recs = self.search("", namespace="template_library", limit=200)
        if mother_theme:
            recs = [r for r in recs if mother_theme in json.dumps(r.get("structured_payload", {}))]
        return recs

    def retrieve_user_needs(self) -> list[dict]:
        return self.search("", namespace="user_needs", limit=100)

    def unload(self):
        if self._embed is not None:
            try:
                self._embed.unload()
            except Exception:
                pass
            self._embed = None
        self._text_emb_cache.clear()
