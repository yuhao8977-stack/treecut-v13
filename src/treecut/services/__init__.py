"""TreeCut Service Layer — 统一 Service bootstrap（Phase 0.5）。

目标：UI/CLI 不再直接操作数据库业务，统一经由 Service Layer。
本 Phase 只建立框架与统一入口，不迁移既有 CLI 业务逻辑
（按架构宪法，后续新功能禁止继续写入 main.py 业务逻辑）。

用法：
  from treecut.services import bootstrap_services
  services = bootstrap_services(db_path)
  services.cognition.analyze_asset(...)
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ServiceContext:
    """统一服务上下文：数据库路径 + 版本信息。"""
    db_path: Path
    schema_version: str = ""
    git_commit: str = ""


@dataclass
class Services:
    """服务集合（惰性初始化，避免加载重量级模型直到被调用）。"""
    db_path: Path
    context: ServiceContext = field(init=False)
    _cognition = None
    _knowledge = None
    _accuracy = None
    _value = None
    _migrations = None

    def __post_init__(self):
        self.context = ServiceContext(db_path=self.db_path)
        self._load_versions()

    def _load_versions(self) -> None:
        try:
            conn = sqlite3.connect(
                "file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
            row = conn.execute(
                "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
            ).fetchone()
            if row:
                self.context.schema_version = row[0]
            conn.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 服务访问（惰性）
    # ------------------------------------------------------------------

    @property
    def migrations(self):
        if self._migrations is None:
            from treecut.platform.migrations import MigrationManager
            self._migrations = MigrationManager(self.db_path)
        return self._migrations

    @property
    def knowledge(self):
        """KnowledgeService：知识库加载/查询。"""
        if self._knowledge is None:
            from treecut.cognitive.knowledge import KnowledgeLoader
            self._knowledge = KnowledgeLoader(self.db_path)
        return self._knowledge

    @property
    def cognition(self):
        """CognitionService：认知分析（行业理解/内容分类）。"""
        if self._cognition is None:
            from treecut.cognitive.industry import IndustryEngine
            self._cognition = IndustryEngine(self.db_path)
        return self._cognition

    @property
    def accuracy(self):
        """EvaluationService：准确率验证（测试集/审核/报告）。"""
        if self._accuracy is None:
            from treecut.cognitive.accuracy import AccuracyEngine
            self._accuracy = AccuracyEngine(self.db_path)
        return self._accuracy

    @property
    def value(self):
        """ValueService：内容价值评分（Phase 6）。"""
        if self._value is None:
            from treecut.cognitive.value import ContentValueEngine
            self._value = ContentValueEngine(self.db_path)
        return self._value


def bootstrap_services(db_path: str | Path | None = None) -> Services:
    """统一 Service bootstrap：所有入口从这里获取服务。"""
    if db_path is None:
        from treecut.platform.paths import RuntimePaths
        db_path = RuntimePaths.discover().databases / "materials.db"
    return Services(db_path=Path(db_path))
