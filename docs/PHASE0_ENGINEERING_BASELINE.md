# TreeCut Phase 0 工程基线与治理 总报告

> 阶段: Phase 0（稳定基线与工程治理）| 日期: 2026-08-26
> 流程: 已按架构宪法 13 条执行（备份 → migration → tests → regression → 文档 → Git → rollback 说明）
> 状态: 完成，等待验收 | 未进入 Phase 1

---

## 目录

1. [执行摘要](#一执行摘要)
2. [0.1 版本冻结](#二01-版本冻结)
3. [0.2 数据库完整备份](#三02-数据库完整备份)
4. [0.3 确定性技术 Bug 修复](#四03-确定性技术-bug-修复)
5. [0.4 Migration 框架与数据库迁移政策](#五04-migration-框架与数据库迁移政策)
6. [0.5 Service Layer 统一入口](#六05-service-layer-统一入口)
7. [0.6 自动测试与覆盖率](#七06-自动测试与覆盖率)
8. [0.7 CI 持续集成](#八07-ci-持续集成)
9. [验收汇总与交付物](#九验收汇总与交付物)
10. [回滚说明](#十回滚说明)
11. [遗留问题与风险](#十一遗留问题与风险)

---

## 一、执行摘要

Phase 0 目标：在系统级重构前建立**可靠、可回滚、可测试的工程基线**。

| 验收项 | 结果 |
|---|---|
| git tag | ✅ `v13.5.15-baseline`（annotated） |
| git commit | ✅ 冻结 7a66fa4 → Phase0 提交 06c192a |
| pytest | ✅ **51 passed / 0 failed / 0 skipped / 0 error** |
| coverage | ✅ industry **49%** / value 24% / accuracy 11%，总 25% |
| database integrity | ✅ ok（原库 + 备份库双验证） |
| migration version | ✅ `0001 baseline_v13_schema` |
| 数据库备份 | ✅ 329.02 MB + BACKUP_MANIFEST.json |

**关键成果**：
- 建立正式 Migration 框架（`schema_migrations` 表 + 版本化迁移目录）
- 建立统一 Service Layer bootstrap（后续新功能禁止写入 main.py 业务逻辑）
- 修复 3 个确定性 bug（learning 采集失效 / 测试 fixture 错误 / 新库 schema 缺失）
- CI 就绪（无模型下载，migration smoke 测试）

---

## 二、0.1 版本冻结

| 项 | 值 |
|---|---|
| git tag | **v13.5.15-baseline**（annotated tag，未覆盖任何已有 tag） |
| 冻结 commit | **7a66fa4**（docs(audit): 生产级架构差距审计报告） |
| Phase0 提交 | **06c192a**（本阶段交付） |
| 分支 | main |
| 工作树 | 干净（Office 临时锁文件已加入 .gitignore） |

```
git tag -a v13.5.15-baseline -m "Production Grade Phase 0 baseline — 稳定基线冻结"
```

---

## 三、0.2 数据库完整备份

### 备份文件

| 项 | 值 |
|---|---|
| 备份路径 | `runtime_data/temp/batch1/backups/materials_20260826_161519.db` |
| 备份大小 | **329.02 MB** |
| 原库大小 | 记录于 manifest |
| WAL checkpoint | `PRAGMA wal_checkpoint(FULL)` 已执行（WAL 0 → 0 字节） |
| 原库完整性 | **ok**（integrity_check 全行通过） |
| 备份库完整性 | **ok** |
| 原库 SHA256 | 记录于 manifest |
| 备份库 SHA256 | 记录于 manifest |
| 表清单 | **45 张表**（含行数，记录于 manifest） |

### BACKUP_MANIFEST.json（清单内容）

```json
{
  "phase": "0.2",
  "created_at": "2026-08-26 16:15:19",
  "source_db": "E:\\...\\database\\materials.db",
  "backup_file": "E:\\...\\backups\\materials_20260826_161519.db",
  "backup_size_bytes": 345002296,
  "backup_size_mb": 329.02,
  "source_sha256": "<sha256>",
  "backup_sha256": "<sha256>",
  "source_integrity_ok": true,
  "backup_integrity_ok": true,
  "wal_before_bytes": 0,
  "wal_after_bytes": 0,
  "checkpoint": "wal_checkpoint(FULL) 已执行",
  "tables": { "assets": 22465, "analysis_tasks": 31106, "segments": 41814, ... },
  "restore_command": "python -c \"import sqlite3; s=sqlite3.connect(r'<backup.db>'); d=sqlite3.connect(r'<materials.db>'); s.backup(d); d.close(); s.close(); print('restored')\"",
  "restore_note": "恢复命令将备份库完整覆盖回 materials.db（执行前请停止所有 TreeCut 进程）"
}
```

### 关键表行数快照（备份时）

| 表 | 行数 | 表 | 行数 |
|---|---|---|---|
| assets | 22465 | analysis_tasks | 31106 |
| media_files | 28096 | asset_processing_state | 224650 |
| segments | 41814 | keyframes | 125199 |
| transcripts | 51516 | ocr_text | 289218 |
| content_classification | 140 | content_value | 22465 |
| accuracy_review | 100 | accuracy_test | 100 |
| learning_rules | 237 | scene_semantics | 4986 |
| knowledge_entries | 39 | schema_version | 3 |

---

## 四、0.3 确定性技术 Bug 修复

### Bug 1：learning.py 反馈采集路径失效（核心修复）

**问题**：`learning.py::_collect_feedback` 查询 `error_type='content_type_mismatch'`，
但 accuracy_ui.py 实际写入的是 `error_type='content_type'` → **反馈采集恒为 0 条**，学习闭环实际断裂。

**修复**（`src/treecut/cognitive/learning.py`）：
```python
# 修改前
"SELECT * FROM learning_rules WHERE error_type='content_type_mismatch'"
# 修改后
"SELECT * FROM learning_rules WHERE error_type='content_type'"
```

**约束遵守**：仅改字段匹配，**未改变任何学习逻辑**（规则提炼/权重更新/评估不变）。

**验证**：采集从 0 条 → **32 条**（来源=learning_rules，AI=产品工艺展示 → 人工=产品介绍 等）。

### Bug 2：test_task_store.py 使用不存在的 fixture

**问题**：4 个测试声明 `tmp: Path` 参数，pytest 内置 fixture 为 `tmp_path`（返回 Path）→ 4 ERROR。

**修复**：`tmp` → `tmp_path`，`make_db(tmp)` → `make_db(tmp_path)`。

### Bug 3：CognitiveStore 新库初始化缺 schema_version 表

**问题**：`ensure_schema()` 在 SCHEMA 执行后立刻查询 `schema_version`，
但 SCHEMA 常量不含其建表语句 → **新库首次初始化报 `no such table: schema_version`**（生产库因表已存在未触发，属既有隐患）。

**修复**（`src/treecut/cognitive/store.py`）：
```python
connection.execute(
    "CREATE TABLE IF NOT EXISTS schema_version ("
    "name TEXT PRIMARY KEY, version INTEGER NOT NULL)")
connection.executescript(SCHEMA)
```

---

## 五、0.4 Migration 框架与数据库迁移政策

### 5.1 框架代码

**模块**: `src/treecut/platform/migrations.py` → `MigrationManager`

| 方法 | 功能 |
|---|---|
| `init()` | 建 `schema_migrations` 表 + 写入 baseline（幂等） |
| `status()` | 查询已应用迁移 |
| `apply_pending()` | 扫描 `migrations/` 目录应用未执行迁移 |
| `create_migration(name, sql)` | 自动编号创建迁移文件（`NNNN_name.sql`） |

### 5.2 schema_migrations 表结构

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    version      TEXT NOT NULL UNIQUE,      -- '0001', '0002', ...
    name         TEXT NOT NULL,             -- 迁移名
    git_commit   TEXT NOT NULL DEFAULT '',  -- 应用时的 git commit
    checksum     TEXT NOT NULL DEFAULT '',  -- 迁移内容 SHA256 前16位
    applied_at   REAL NOT NULL,
    status       TEXT NOT NULL DEFAULT 'applied',  -- applied|failed|rolled_back
    notes        TEXT NOT NULL DEFAULT ''
)
```

### 5.3 基线记录（已落库）

| version | name | git_commit | checksum | status |
|---|---|---|---|---|
| 0001 | baseline_v13_schema | 7a66fa4 | 89df54995dc1c24b | applied |

**基线说明**：v13.5.15 现有全部 Schema（45 表，P1-P9 / P2.5 / P2.7 / Brain / Phase6 累积），
由历史 `CREATE TABLE IF NOT EXISTS` 生成，本迁移**仅登记不重建、不删除任何表**。

### 5.4 迁移政策（Policy）

**原则**：
1. 所有数据库结构变更必须通过 Migration 框架，禁止直接 ALTER/CREATE 绕过
2. 禁止删除现有表；旧链路采用兼容迁移（宪法 10）
3. 禁止覆盖原始素材数据
4. 每个迁移可校验 checksum、记录 git_commit
5. rollback = 依赖备份恢复（不做反向迁移）

**强制顺序**：
```
备份数据库（BACKUP_MANIFEST.json）
  → 应用迁移
  → 运行 tests + regression
  → 提交 git
  → 记录 rollback 说明
```

**禁止事项**：
- ❌ 绕过 MigrationManager 直接 ALTER TABLE
- ❌ 删除/重命名旧表
- ❌ 覆盖原始视频素材
- ❌ 无备份情况下执行迁移

---

## 六、0.5 Service Layer 统一入口

### 代码

**模块**: `src/treecut/services/__init__.py` → `bootstrap_services(db_path)`

### 服务清单（惰性加载）

| 服务 | 引擎 | 用途 |
|---|---|---|
| `services.knowledge` | KnowledgeLoader | 知识库加载/查询 |
| `services.cognition` | IndustryEngine | 认知分析（行业理解/内容分类） |
| `services.accuracy` | AccuracyEngine | 准确率验证 |
| `services.value` | ContentValueEngine | 内容价值评分（Phase 6） |
| `services.migrations` | MigrationManager | 数据库迁移 |

### 统一上下文

```python
@ServiceContext:
    db_path: Path
    schema_version: str   # 从 schema_migrations 读取最新版本
    git_commit: str
```

### 验证

```
Service bootstrap OK
  db: materials.db
  schema_version: 0001
  knowledge 服务: KnowledgeLoader
  cognition 服务: IndustryEngine
  accuracy 服务: AccuracyEngine
  value 服务: ContentValueEngine
  migrations 服务: MigrationManager
```

**架构宪法 7 落地**：本 Phase 未重写 62 个 CLI，但建立了统一入口；
后续新功能**禁止继续写入 main.py 业务逻辑**，必须经 Service Layer。

---

## 七、0.6 自动测试与覆盖率

### 7.1 既有测试修复

| 问题 | 修复 | 影响 |
|---|---|---|
| test_task_store.py `tmp` fixture 不存在 | 改 `tmp_path` | 4 ERROR → 通过 |
| CognitiveStore 新库缺 schema_version 表 | ensure_schema 先建表 | 8 FAIL → 通过 |

### 7.2 新增回归测试

**`tests/test_cognitive_regression.py`**（6 用例，内存/临时库）：

| 用例 | 验证 |
|---|---|
| test_store_schema_creates_tables | 认知 6 表创建 |
| test_classify_v2_double_layer | V2 双层分类（主类型+元素） |
| test_classify_v2_customer_case_needs_strong_evidence | 客户案例证据机制（称呼词不构成） |
| test_correct_scenes_factory_show | 工厂空镜 → 只判工厂 |
| test_compose_products_material_combo | 材质+岛台 → 细粒度产品 |
| test_simplify_traditional | 繁简归一化 |

**`tests/test_accuracy_value_regression.py`**（4 用例）：

| 用例 | 验证 |
|---|---|
| test_accuracy_schema_has_human_fields | accuracy_review 人工内容字段 |
| test_value_schema_and_classify | content_value 表结构 |
| test_value_pool_classification_thresholds | ABCD 分类阈值 |
| test_value_dims_weights | 五维权重 25/25/20/20/10 |

### 7.3 pytest 结果

| 指标 | 值 |
|---|---|
| 总测试数 | **51** |
| 通过 | **51** |
| 失败 | **0** |
| 跳过 | **0** |
| 错误 | **0** |
| 用时 | 25.85s - 32.55s |

### 7.4 覆盖率（pytest-cov）

| 模块 | Stmts | Miss | Cover |
|---|---|---|---|
| cognitive/industry.py | 275 | 141 | **49%** |
| cognitive/value.py | 151 | 115 | 24% |
| cognitive/accuracy.py | 414 | 370 | 11% |
| **TOTAL** | 840 | 626 | **25%** |

> 注：pytest-cov 数据文件写入 E 盘可写目录（`COVERAGE_FILE` 指向 runtime_data），避免 C 盘写入拒绝。

---

## 八、0.7 CI 持续集成

**文件**: `.github/workflows/ci.yml`

| 步骤 | 内容 |
|---|---|
| checkout | actions/checkout@v4 |
| Python | actions/setup-python@v5, 3.12 |
| 依赖 | pytest / pytest-cov / scenedetect / rapidocr-onnxruntime（**不下载数 GB 模型**） |
| unit + integration | `pytest tests` |
| migration smoke | 临时库跑 MigrationManager.init → 断言 0001 |
| coverage | industry/value/accuracy 覆盖率报告 |

**模型策略**：CI 不依赖真实模型（ASR/CLIP/BGE），
模型相关测试使用 mock/临时库/轻量 fixture，确保 CI 快速可复现。

---

## 九、验收汇总与交付物

### 9.1 验收项

| 验收项 | 结果 |
|---|---|
| git tag | ✅ v13.5.15-baseline |
| git commit | ✅ 7a66fa4（基线）+ 06c192a（Phase0） |
| pytest | ✅ 51 passed / 0 failed |
| coverage | ✅ 25%（industry 49%） |
| database integrity | ✅ ok（原库+备份库） |
| migration version | ✅ 0001（baseline_v13_schema） |
| BACKUP_MANIFEST.json | ✅ 已生成 |
| CI | ✅ ci.yml |

### 9.2 交付物清单

| 文件 | 说明 |
|---|---|
| `docs/PHASE0_ENGINEERING_BASELINE.md` | 本总报告（含迁移政策全量内容） |
| `BACKUP_MANIFEST.json` | 数据库备份清单（数据根下） |
| `src/treecut/platform/migrations.py` | Migration 框架 |
| `src/treecut/services/__init__.py` | Service Layer bootstrap |
| `src/treecut/cognitive/learning.py` | Bug 修复（字段匹配） |
| `src/treecut/cognitive/store.py` | Bug 修复（schema_version 建表） |
| `tests/test_cognitive_regression.py` | 认知回归测试（6） |
| `tests/test_accuracy_value_regression.py` | 验证回归测试（4） |
| `tests/test_task_store.py` | fixture 修复 |
| `.github/workflows/ci.yml` | CI 配置 |
| `.gitignore` | 备份/锁文件忽略 |

---

## 十、回滚说明

| 场景 | 回滚方式 |
|---|---|
| 代码回滚 | `git revert 06c192a` 或 `git checkout v13.5.15-baseline` |
| 数据库回滚 | 用 `backups/materials_20260826_161519.db` 恢复（命令见 manifest.restore_command） |
| Migration 回滚 | 无反向迁移；Phase0 变更仅为新增 schema_migrations 表（无破坏性），可直接删除该表 + 记录 |

**本 Phase 数据库变更清单**（最小化）：
1. 新增 `schema_migrations` 表 + 1 行 baseline 记录
2. 未改动任何现有 45 表

---

## 十一、遗留问题与风险

| 项 | 说明 | 阶段 |
|---|---|---|
| 覆盖率 25% | 仅 cognitive 三模块；全库覆盖率未测 | 后续 Phase |
| 62 个 CLI 未瘦身 | 仅建 Service Layer 框架，未迁移既有逻辑 | 后续 Phase |
| pytest-cov 需 E 盘路径 | C 盘写入受限（环境约束，非代码问题） | 已知 |
| baseline tag 未推送远程 | 仅本地 tag（无 push 指令） | 待确认 |

---

*Phase 0 完成。按宪法 14 条，未进入 Phase 1，等待架构监工验收。*
