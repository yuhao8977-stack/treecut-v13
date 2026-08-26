"""AI Business Cognitive System — Phase 0 数据库存储层。

新增 6 张表（全部新增，不修改既有表）：
  - scene_semantics        Layer2 场景语义
  - knowledge_entries      Layer3 行业知识库（版本化）
  - content_classification Layer4 内容类型
  - account_dna            Layer5 账号 DNA
  - content_templates      Layer6 内容模板
  - learning_rules         Layer7 反馈学习规则
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path

SCHEMA_VERSION = 1
SCHEMA_NAME = "cognitive"

SCHEMA = """
CREATE TABLE IF NOT EXISTS scene_semantics (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id      TEXT NOT NULL,
    segment_id    TEXT,
    semantic      TEXT NOT NULL,
    action        TEXT NOT NULL DEFAULT '',
    lens_value    INTEGER NOT NULL DEFAULT 0,
    confidence    REAL NOT NULL DEFAULT 0,
    model_version TEXT NOT NULL DEFAULT '',
    created_time  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sem_asset ON scene_semantics(asset_id);

CREATE TABLE IF NOT EXISTS knowledge_entries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    domain       TEXT NOT NULL,
    category     TEXT NOT NULL,
    name         TEXT NOT NULL,
    aliases      TEXT NOT NULL DEFAULT '',
    description  TEXT NOT NULL DEFAULT '',
    keywords     TEXT NOT NULL DEFAULT '',
    weight       REAL NOT NULL DEFAULT 1.0,
    version      TEXT NOT NULL DEFAULT '1.0',
    active       INTEGER NOT NULL DEFAULT 1,
    updated_time REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_knowledge_domain ON knowledge_entries(domain, category);

CREATE TABLE IF NOT EXISTS content_classification (
    asset_id         TEXT PRIMARY KEY,
    content_type     TEXT NOT NULL,
    sub_type         TEXT NOT NULL DEFAULT '',
    confidence       REAL NOT NULL DEFAULT 0,
    reasons          TEXT NOT NULL DEFAULT '',
    model_version    TEXT NOT NULL DEFAULT '',
    content_elements TEXT NOT NULL DEFAULT '',
    reviewed         INTEGER NOT NULL DEFAULT 0,
    created_time     REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS account_dna (
    account_id    TEXT PRIMARY KEY,
    account_name  TEXT NOT NULL,
    goal          TEXT NOT NULL DEFAULT '',
    content_prefs TEXT NOT NULL DEFAULT '',
    high_value    TEXT NOT NULL DEFAULT '',
    mid_value     TEXT NOT NULL DEFAULT '',
    low_value     TEXT NOT NULL DEFAULT '',
    created_time  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS content_templates (
    template_id   TEXT PRIMARY KEY,
    template_name TEXT NOT NULL,
    content_type  TEXT NOT NULL,
    structure     TEXT NOT NULL DEFAULT '',
    slot_rules    TEXT NOT NULL DEFAULT '',
    cta           TEXT NOT NULL DEFAULT '',
    version       TEXT NOT NULL DEFAULT '1.0',
    active        INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS learning_rules (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT NOT NULL,
    ai_output     TEXT NOT NULL,
    human_output  TEXT NOT NULL,
    error_type    TEXT NOT NULL DEFAULT '',
    rule          TEXT NOT NULL DEFAULT '',
    weight        REAL NOT NULL DEFAULT 1.0,
    applied_count INTEGER NOT NULL DEFAULT 0,
    created_time  REAL NOT NULL,
    updated_time  REAL NOT NULL
);
"""


class CognitiveStore:
    """认知体系存储：建表 + 各层数据读写。"""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            from treecut.platform.paths import RuntimePaths
            db_path = RuntimePaths.discover().databases / "materials.db"
        self.db_path = Path(db_path)

    def _connect(self):
        connection = sqlite3.connect(str(self.db_path), timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def ensure_schema(self) -> int:
        with closing(self._connect()) as connection:
            # schema_version 表需先存在（SCHEMA 不含其建表语句；新库首次初始化必需）
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_version ("
                "name TEXT PRIMARY KEY, version INTEGER NOT NULL)")
            connection.executescript(SCHEMA)
            # 幂等迁移：content_classification 增加 content_elements 列
            cols = [r[1] for r in connection.execute(
                "PRAGMA table_info(content_classification)")]
            if "content_elements" not in cols:
                connection.execute(
                    "ALTER TABLE content_classification ADD COLUMN content_elements "
                    "TEXT NOT NULL DEFAULT ''")
            row = connection.execute(
                "SELECT version FROM schema_version WHERE name=?", (SCHEMA_NAME,)
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT OR REPLACE INTO schema_version(name,version) VALUES(?,?)",
                    (SCHEMA_NAME, SCHEMA_VERSION),
                )
            connection.commit()
        return SCHEMA_VERSION

    # ------------------------------------------------------------------
    # Layer 2: 场景语义
    # ------------------------------------------------------------------

    def save_scene_semantics(self, asset_id: str, items: list[dict]) -> int:
        now = time.time()
        with closing(self._connect()) as connection:
            for item in items:
                connection.execute(
                    "INSERT INTO scene_semantics(asset_id,segment_id,semantic,action,"
                    "lens_value,confidence,model_version,created_time) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (asset_id, item.get("segment_id"), item.get("semantic", ""),
                     item.get("action", ""), int(item.get("lens_value", 0)),
                     float(item.get("confidence", 0)),
                     item.get("model_version", ""), now),
                )
            connection.commit()
        return len(items)

    def list_scene_semantics(self, asset_id: str) -> list[dict]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM scene_semantics WHERE asset_id=? ORDER BY id",
                (asset_id,)).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Layer 3: 知识库
    # ------------------------------------------------------------------

    def upsert_knowledge(self, entries: list[dict]) -> int:
        """批量写入知识条目（JSON 同步入口）。按 (domain, category, name) 幂等更新。"""
        now = time.time()
        with closing(self._connect()) as connection:
            for e in entries:
                connection.execute(
                    "INSERT INTO knowledge_entries(domain,category,name,aliases,"
                    "description,keywords,weight,version,active,updated_time) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(id) DO UPDATE SET "
                    "aliases=excluded.aliases, description=excluded.description, "
                    "keywords=excluded.keywords, weight=excluded.weight, "
                    "version=excluded.version, active=excluded.active, "
                    "updated_time=excluded.updated_time",
                    (e["domain"], e.get("category", ""), e["name"],
                     e.get("aliases", ""), e.get("description", ""),
                     e.get("keywords", ""), float(e.get("weight", 1.0)),
                     e.get("version", "1.0"), int(e.get("active", 1)), now),
                )
            connection.commit()
        return len(entries)

    def query_knowledge(self, domain: str | None = None,
                        category: str | None = None,
                        keyword: str = "") -> list[dict]:
        """知识库查询：按 domain/category 过滤 + 关键词模糊匹配。"""
        where = ["active=1"]
        params: list = []
        if domain:
            where.append("domain=?")
            params.append(domain)
        if category:
            where.append("category=?")
            params.append(category)
        if keyword:
            where.append("(name LIKE ? OR aliases LIKE ? OR keywords LIKE ?)")
            kw = f"%{keyword}%"
            params.extend([kw, kw, kw])
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"SELECT * FROM knowledge_entries WHERE {' AND '.join(where)} "
                f"ORDER BY weight DESC LIMIT 200", params).fetchall()
        return [dict(r) for r in rows]

    def knowledge_stats(self) -> dict:
        with closing(self._connect()) as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM knowledge_entries WHERE active=1").fetchone()[0]
            by_domain = {r[0]: r[1] for r in connection.execute(
                "SELECT domain, COUNT(*) FROM knowledge_entries WHERE active=1 "
                "GROUP BY domain")}
        return {"total": total, "by_domain": by_domain}

    # ------------------------------------------------------------------
    # Layer 4: 内容分类
    # ------------------------------------------------------------------

    def save_classification(self, asset_id: str, content_type: str,
                            sub_type: str = "", confidence: float = 0.0,
                            reasons: str = "", model_version: str = "",
                            content_elements: list[str] | None = None) -> None:
        now = time.time()
        elements_json = json.dumps(content_elements or [],
                                   ensure_ascii=False) if content_elements else ""
        with closing(self._connect()) as connection:
            # 幂等迁移：content_classification 增加 content_elements 列
            cols = [r[1] for r in connection.execute(
                "PRAGMA table_info(content_classification)")]
            if "content_elements" not in cols:
                connection.execute(
                    "ALTER TABLE content_classification ADD COLUMN content_elements "
                    "TEXT NOT NULL DEFAULT ''")
            connection.execute(
                "INSERT OR REPLACE INTO content_classification(asset_id,content_type,"
                "sub_type,confidence,reasons,model_version,content_elements,"
                "reviewed,created_time) VALUES(?,?,?,?,?,?,?,0,?)",
                (asset_id, content_type, sub_type, confidence, reasons,
                 model_version, elements_json, now),
            )
            connection.commit()

    def classification_stats(self) -> dict:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT content_type, COUNT(*) FROM content_classification "
                "GROUP BY content_type").fetchall()
            total = connection.execute(
                "SELECT COUNT(*) FROM content_classification").fetchone()[0]
        return {"total": total, "by_type": {r[0]: r[1] for r in rows}}

    # ------------------------------------------------------------------
    # Layer 5: 账号 DNA
    # ------------------------------------------------------------------

    def upsert_account(self, account: dict) -> None:
        now = time.time()
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT OR REPLACE INTO account_dna(account_id,account_name,goal,"
                "content_prefs,high_value,mid_value,low_value,created_time) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (account["account_id"], account.get("account_name", ""),
                 account.get("goal", ""), account.get("content_prefs", ""),
                 account.get("high_value", ""), account.get("mid_value", ""),
                 account.get("low_value", ""), now),
            )
            connection.commit()

    def list_accounts(self) -> list[dict]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM account_dna ORDER BY account_id").fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Layer 6: 模板
    # ------------------------------------------------------------------

    def upsert_template(self, template: dict) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT OR REPLACE INTO content_templates(template_id,template_name,"
                "content_type,structure,slot_rules,cta,version,active) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (template["template_id"], template.get("template_name", ""),
                 template.get("content_type", ""), template.get("structure", ""),
                 template.get("slot_rules", ""), template.get("cta", ""),
                 template.get("version", "1.0"), int(template.get("active", 1))),
            )
            connection.commit()

    def list_templates(self, content_type: str | None = None) -> list[dict]:
        with closing(self._connect()) as connection:
            if content_type:
                rows = connection.execute(
                    "SELECT * FROM content_templates WHERE active=1 AND content_type=?",
                    (content_type,)).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM content_templates WHERE active=1").fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Layer 7: 学习规则
    # ------------------------------------------------------------------

    def add_learning_rule(self, source: str, ai_output: str, human_output: str,
                          error_type: str = "", rule: str = "") -> int:
        now = time.time()
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "INSERT INTO learning_rules(source,ai_output,human_output,error_type,"
                "rule,weight,applied_count,created_time,updated_time) "
                "VALUES(?,?,?,?,?,1.0,0,?,?)",
                (source, ai_output, human_output, error_type, rule, now, now),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def learning_stats(self) -> dict:
        with closing(self._connect()) as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM learning_rules").fetchone()[0]
            by_error = {r[0]: r[1] for r in connection.execute(
                "SELECT error_type, COUNT(*) FROM learning_rules GROUP BY error_type")}
        return {"total": total, "by_error_type": by_error}

    # ------------------------------------------------------------------
    # 整体状态
    # ------------------------------------------------------------------

    def status(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "scene_semantics": self._count("scene_semantics"),
            "knowledge_entries": self._count("knowledge_entries"),
            "content_classification": self._count("content_classification"),
            "account_dna": self._count("account_dna"),
            "content_templates": self._count("content_templates"),
            "learning_rules": self._count("learning_rules"),
        }

    def _count(self, table: str) -> int:
        with closing(self._connect()) as connection:
            return int(connection.execute(
                f"SELECT COUNT(*) FROM {table}").fetchone()[0])
