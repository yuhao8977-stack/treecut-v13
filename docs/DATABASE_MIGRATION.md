# P2.5 数据库迁移文档

- **版本**：v1.0
- **日期**：2026-08-22
- **约束**：不修改任何既有表；只新增表；运行中 PID 19152 不重启

---

## 1. 迁移原则

1. **只增不改**：全部新增（`analysis_tasks`、`schema_version`），既有表（assets / asset_processing_state / media_files / segments / keyframes / transcripts / ocr_text / analysis_jobs …）**零修改**
2. **幂等可重入**：`CREATE TABLE IF NOT EXISTS`，重复执行无副作用
3. **迁移前备份**：复用 `database.backup_before_migration`（官方 sqlite backup API + 拒绝符号链接库）
4. **版本独立**：新 `schema_version(name, version)` 表，**不再依赖**被 6 个模块互相覆盖的 `PRAGMA user_version`

---

## 2. 新增表结构

### 2.1 `analysis_tasks`（任务调度表）

```sql
CREATE TABLE IF NOT EXISTS analysis_tasks (
    task_id       TEXT PRIMARY KEY,              -- 'p25_' + uuid4().hex
    asset_id      TEXT NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
    task_type     TEXT NOT NULL,                 -- vision|asr|ocr|full|segment|embedding
    stages        TEXT NOT NULL DEFAULT '',      -- 'scene,keyframe' 等自由组合
    status        TEXT NOT NULL DEFAULT 'pending',
        -- pending | processing | completed | failed | skipped
    worker_id     TEXT NOT NULL DEFAULT '',      -- 领取者（worker_001）
    priority      INTEGER NOT NULL DEFAULT 0,    -- 未来高优插队
    retry_count   INTEGER NOT NULL DEFAULT 0,    -- 失败重试计数（≤3）
    attempt       INTEGER NOT NULL DEFAULT 0,    -- 领取次数（含失联回收）
    error         TEXT NOT NULL DEFAULT '',      -- 最近错误信息
    created_time  REAL NOT NULL,                 -- unix 秒
    started_time  REAL,
    finished_time REAL,
    UNIQUE(asset_id, task_type)                  -- 幂等：同资产同类型任务唯一
);
CREATE INDEX IF NOT EXISTS idx_analysis_tasks_status
    ON analysis_tasks(status, priority DESC, created_time);
CREATE INDEX IF NOT EXISTS idx_analysis_tasks_asset
    ON analysis_tasks(asset_id);
```

**字段与需求对照**（对应任务指令）：
| 需求 | 字段 |
|---|---|
| task_id | `task_id` |
| asset_id | `asset_id` |
| task_type | `task_type` |
| status | `status`（pending/processing/completed/failed/skipped） |
| worker_id | `worker_id` |
| priority | `priority` |
| retry_count | `retry_count` |
| created_time | `created_time` |
| started_time | `started_time` |
| finished_time | `finished_time` |

### 2.2 `schema_version`（版本表）

```sql
CREATE TABLE IF NOT EXISTS schema_version (
    name    TEXT PRIMARY KEY,     -- 如 'analysis_tasks'
    version INTEGER NOT NULL      -- 如 1
);
```

每个模块用独立行记录自己的版本（`TaskStore.schema_status()` 可读全部），彻底解决"多模块共写 user_version 互相覆盖"的审计问题（A 类问题 H3）。

---

## 3. 迁移执行方式

代码路径：`TaskStore.ensure_schema()` / `TaskStore.migrate_if_needed()`

```
migrate_if_needed():
  backup = backup_before_migration(db, 0, 1)   # 仅当库存在用户表时备份
  ensure_schema()                               # executescript(SCHEMA) + 版本记录
```

**何时执行**：`scheduler.run()` 启动时自动调用；`--p2.5-status` 也触发 ensure（幂等）。运行中旧进程**不执行**任何迁移代码（其代码路径未改动）。

---

## 4. 迁移验证

| 检查项 | SQL | 期望 |
|---|---|---|
| 表存在 | `SELECT name FROM sqlite_master WHERE name='analysis_tasks'` | 1 行 |
| 版本记录 | `SELECT version FROM schema_version WHERE name='analysis_tasks'` | 1 |
| 旧表未动 | `PRAGMA table_info(asset_processing_state)` | 列与迁移前一致 |
| 数据完整 | `PRAGMA integrity_check` | ok |
| 备份文件 | `database/backups/` | 迁移前自动生成 1 份 |

---

## 5. 回滚方案

由于是**纯增量**迁移（无 ALTER、无数据重写），回滚即 `DROP TABLE analysis_tasks; DROP TABLE schema_version;`（不影响任何既有数据）。备份文件保留在 `database/backups/` 供必要时恢复。
