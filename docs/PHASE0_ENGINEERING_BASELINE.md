# TreeCut Phase 0 工程基线与治理验收报告（PHASE0_ENGINEERING_BASELINE）

> 日期: 2026-08-26 | Phase: 0（稳定基线与工程治理）
> 状态: **完成** | 已按宪法 13 条流程：备份 → migration → tests → regression → 文档 → Git → rollback 说明

---

## 一、0.1 版本冻结

| 项 | 值 |
|---|---|
| git tag | **v13.5.15-baseline**（annotated，未覆盖任何已有 tag） |
| git commit | **7a66fa4**（冻结时刻 HEAD） |
| 分支 | main |
| 工作树 | 干净（Office 锁文件已 .gitignore 忽略） |

## 二、0.2 数据库完整备份

**manifest**: `runtime_data/temp/batch1/BACKUP_MANIFEST.json`

| 项 | 值 |
|---|---|
| 备份文件 | `backups/materials_20260826_161519.db` |
| 大小 | 329.02 MB |
| 原库完整性 | **ok**（integrity_check 全行通过） |
| 备份库完整性 | **ok** |
| 原库 SHA256 | 记录于 manifest |
| 备份库 SHA256 | 记录于 manifest |
| WAL checkpoint | `PRAGMA wal_checkpoint(FULL)` 已执行（WAL 0 → 0 字节） |
| 表清单 | 45 表（含行数，记录于 manifest） |
| 恢复命令 | 见 manifest.restore_command（停止进程后执行） |

## 三、0.3 确定性 Bug 修复

| Bug | 修复 |
|---|---|
| learning.py 查询 `error_type='content_type_mismatch'` 与实际写入 `'content_type'` 不一致 → 反馈采集 0 条 | 改为 `'content_type'`，**仅改字段匹配，未改任何学习逻辑** |
| 验证 | 采集从 0 条 → **32 条**（learning_rules 来源） |

## 四、0.4 Migration 框架

**代码**: `src/treecut/platform/migrations.py`（MigrationManager）
**目录**: `migrations/`（版本化 SQL）
**表**: `schema_migrations`（version/name/git_commit/checksum/applied_at/status）

| version | name | git_commit | checksum | status |
|---|---|---|---|---|
| 0001 | baseline_v13_schema | 7a66fa4 | 89df54995dc1c24b | applied |

- 已生成基线记录（45 表存量 Schema 登记，不重建、不删除）
- 支持 `init()` / `status()` / `apply_pending()` / `create_migration()`

## 五、0.5 Service Layer 框架

**代码**: `src/treecut/services/__init__.py` → `bootstrap_services()`

| 服务 | 对应引擎 |
|---|---|
| knowledge | KnowledgeLoader |
| cognition | IndustryEngine |
| accuracy | AccuracyEngine |
| value | ContentValueEngine |
| migrations | MigrationManager |

- 统一 bootstrap 已验证可用（schema_version=0001）
- 本 Phase 未重写 62 个 CLI；后续新功能禁止继续写入 main.py 业务逻辑

## 六、0.6 自动测试

### 修复的既有测试问题

| 问题 | 修复 |
|---|---|
| test_task_store.py 用 `tmp` fixture（不存在）→ 4 ERROR | 改为 pytest 内置 `tmp_path` |
| CognitiveStore.ensure_schema 新库缺 schema_version 表 → 8 FAIL | ensure_schema 先建 schema_version（既有 bug，新库才触发） |

### pytest 结果（全量 51 个）

| 指标 | 值 |
|---|---|
| 总测试数 | **51** |
| 通过 | **51** |
| 失败 | **0** |
| 跳过 | **0** |
| 错误 | **0** |
| 用时 | 32.55s |

### 覆盖率（pytest-cov，新增回归测试后）

| 模块 | Stmts | Miss | Cover |
|---|---|---|---|
| cognitive/industry.py | 275 | 141 | **49%** |
| cognitive/value.py | 151 | 115 | 24% |
| cognitive/accuracy.py | 414 | 370 | 11% |
| **TOTAL** | 840 | 626 | **25%** |

新增回归测试文件：
- `tests/test_cognitive_regression.py`（6 用例：表结构/双层分类/证据机制/场景修正/产品组合/繁简）
- `tests/test_accuracy_value_regression.py`（4 用例：表字段/评分表/ABCD 阈值/五维权重）

## 七、0.7 CI

**文件**: `.github/workflows/ci.yml`

| 步骤 | 内容 |
|---|---|
| Python 3.12 | actions/setup-python |
| 核心依赖 | pytest / pytest-cov / scenedetect / rapidocr（**不下载数 GB 模型**） |
| unit + integration | `pytest tests` |
| migration smoke | 临时库跑 MigrationManager.init → 验证 0001 |
| coverage | industry/value/accuracy 覆盖率报告 |

模型相关测试使用 mock/临时库，CI 无模型下载依赖。

## 八、验收汇总

| 验收项 | 结果 |
|---|---|
| git tag | ✅ v13.5.15-baseline |
| git commit | ✅ 7a66fa4（基线）+ 本 Phase 提交 |
| pytest 结果 | ✅ 51 passed / 0 failed |
| coverage | ✅ 25%（industry 49%） |
| database integrity | ✅ ok（原库+备份库） |
| migration version | ✅ 0001（baseline_v13_schema） |
| BACKUP_MANIFEST.json | ✅ 已生成 |
| DATABASE_MIGRATION_POLICY.md | ✅ 已生成 |
| CI 配置 | ✅ ci.yml |

## 九、本 Phase 交付物清单

| 文件 | 说明 |
|---|---|
| `docs/PHASE0_ENGINEERING_BASELINE.md` | 本报告 |
| `docs/DATABASE_MIGRATION_POLICY.md` | 迁移政策 |
| `BACKUP_MANIFEST.json` | 备份清单（数据根下） |
| `src/treecut/platform/migrations.py` | Migration 框架 |
| `src/treecut/services/__init__.py` | Service bootstrap |
| `tests/test_cognitive_regression.py` | 认知回归测试 |
| `tests/test_accuracy_value_regression.py` | 验证回归测试 |
| `.github/workflows/ci.yml` | CI |

## 十、rollback 说明

- 本 Phase 数据库变更 = 仅新增 `schema_migrations` 表 + baseline 行（无破坏性变更）
- 代码回滚：`git revert <Phase0 commit>` 或 `git checkout v13.5.15-baseline`
- 数据库回滚：如异常，用 `backups/materials_20260826_161519.db` 恢复（命令见 manifest）

---

*Phase 0 完成。按宪法 14 条，未进入 Phase 1，等待验收。*
