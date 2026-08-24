"""AI Business Cognitive System — 知识库加载/校验/热更新。

JSON（TreeCut_AI_Brain/）→ SQLite（knowledge_entries）同步。
支持：
  - load_all()        全量加载并同步到库
  - reload_domain()   单域热更新
  - validate()        校验 JSON 结构
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from treecut.cognitive.store import CognitiveStore

# 知识库根目录（相对本模块）
KNOWLEDGE_ROOT = Path(__file__).resolve().parent.parent / "knowledge" / "TreeCut_AI_Brain"

# domain → 文件名模式
DOMAIN_FILES = {
    "industry": "industry_v1.json",
    "product": "product_v1.json",
    "material": "material_v1.json",
    "scene": "scene_v1.json",
    "content_type": "content_type_v1.json",
    "account": "account_v1.json",
    "template": "template_v1.json",
    "evaluation": "evaluation_v1.json",
}


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate(data: dict, domain: str) -> list[str]:
    """校验单个知识域 JSON，返回错误列表（空=通过）。"""
    errors = []
    if domain in ("account", "template"):
        key = "accounts" if domain == "account" else "templates"
        items = data.get(key, [])
        if not isinstance(items, list) or not items:
            errors.append(f"{domain}: 缺少 {key} 数组")
        id_key = "account_id" if domain == "account" else "template_id"
        for item in items:
            if id_key not in item:
                errors.append(f"{domain}: 条目缺少 {id_key}")
    else:
        entries = data.get("entries", [])
        if not isinstance(entries, list):
            errors.append(f"{domain}: entries 必须是数组")
        for e in entries:
            if "name" not in e:
                errors.append(f"{domain}: 条目缺少 name")
    return errors


class KnowledgeLoader:
    """知识库加载器：JSON → SQLite。"""

    def __init__(self, db_path: str | Path | None = None,
                 root: Path | None = None):
        self.store = CognitiveStore(db_path)
        self.root = Path(root) if root else KNOWLEDGE_ROOT

    # ------------------------------------------------------------------
    # 加载
    # ------------------------------------------------------------------

    def load_domain(self, domain: str) -> dict:
        """加载单个知识域 JSON 并同步到 SQLite。"""
        self.store.ensure_schema()
        fname = DOMAIN_FILES.get(domain)
        if not fname:
            return {"domain": domain, "loaded": 0, "errors": [f"未知 domain: {domain}"]}
        path = self.root / domain / fname
        if not path.exists():
            return {"domain": domain, "loaded": 0, "errors": [f"文件缺失: {path}"]}
        data = _load_json(path)
        errors = validate(data, domain)
        if errors:
            return {"domain": domain, "loaded": 0, "errors": errors}

        loaded = 0
        if domain in ("account", "template"):
            key = "accounts" if domain == "account" else "templates"
            items = data.get(key, [])
            for item in items:
                if domain == "account":
                    self.store.upsert_account({
                        "account_id": item.get("account_id", ""),
                        "account_name": item.get("account_name", ""),
                        "goal": item.get("goal", ""),
                        "content_prefs": json.dumps(item.get("content_prefs", []), ensure_ascii=False),
                        "high_value": json.dumps(item.get("high_value", []), ensure_ascii=False),
                        "mid_value": json.dumps(item.get("mid_value", []), ensure_ascii=False),
                        "low_value": json.dumps(item.get("low_value", []), ensure_ascii=False),
                    })
                else:
                    self.store.upsert_template({
                        "template_id": item.get("template_id", ""),
                        "template_name": item.get("template_name", ""),
                        "content_type": item.get("content_type", ""),
                        "structure": json.dumps(item.get("structure", []), ensure_ascii=False),
                        "slot_rules": json.dumps(item.get("slot_rules", {}), ensure_ascii=False),
                        "cta": item.get("cta", ""),
                        "version": data.get("version", "1.0"),
                    })
                loaded += 1
        else:
            entries = data.get("entries", [])
            rows = []
            for e in entries:
                rows.append({
                    "domain": domain,
                    "category": e.get("category", ""),
                    "name": e.get("name", ""),
                    "aliases": json.dumps(e.get("aliases", []), ensure_ascii=False),
                    "description": e.get("description", ""),
                    "keywords": json.dumps(e.get("keywords", []), ensure_ascii=False),
                    "weight": float(e.get("weight", 1.0)),
                    "version": data.get("version", "1.0"),
                })
            self.store.upsert_knowledge(rows)
            loaded = len(rows)
        return {"domain": domain, "loaded": loaded, "errors": []}

    def load_all(self) -> dict:
        """全量加载所有知识域。"""
        results = {}
        for domain in DOMAIN_FILES:
            results[domain] = self.load_domain(domain)
        return results

    # ------------------------------------------------------------------
    # 热更新
    # ------------------------------------------------------------------

    def reload_domain(self, domain: str) -> dict:
        """热更新单域：重新读取 JSON 并覆盖 SQLite 对应域。"""
        result = self.load_domain(domain)
        if not result["errors"]:
            # 标记该域其他旧条目为非活跃（保留历史，停用）
            self._deactivate_other(domain, result["loaded"])
        return result

    def _deactivate_other(self, domain: str, keep_count: int) -> None:
        """简单策略：本次加载的条目已 upsert 更新，旧条目保留（active 不变）。
        如需完全替换，可在此实现按 version 批量停用。
        """
        pass

    # ------------------------------------------------------------------
    # 查询入口
    # ------------------------------------------------------------------

    def query(self, domain: str | None = None, category: str | None = None,
              keyword: str = "") -> list[dict]:
        return self.store.query_knowledge(domain, category, keyword)

    def status(self) -> dict:
        store_status = self.store.status()
        knowledge = self.store.knowledge_stats()
        accounts = len(self.store.list_accounts())
        templates = len(self.store.list_templates())
        return {
            "store": store_status,
            "knowledge": knowledge,
            "accounts": accounts,
            "templates": templates,
            "knowledge_root": str(self.root),
        }
