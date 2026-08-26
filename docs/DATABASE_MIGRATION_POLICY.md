# TreeCut 数据库迁移政策（DATABASE_MIGRATION_POLICY）

> 版本: 1.0 | Phase: 0.4 | 生效日期: 2026-08-26

---

## 一、原则

1. **所有数据库结构变更必须通过 Migration 框架**，禁止直接执行 ALTER/CREATE 绕过。
2. **禁止删除现有表**；旧链路必须采用兼容迁移（宪法 10）。
3. **禁止覆盖原始素材数据**；迁移只做前向变更。
4. 每个迁移必须可**校验 checksum**、记录 **git_commit**。
5. **rollback 策略**：依赖数据库备份（备份优先于迁移执行），不做反向迁移。

## 二、迁移框架

**代码**: `src/treecut/platform/migrations.py` → `MigrationManager`
**迁移目录**: `migrations/`（版本化 `NNNN_name.sql`）
**记录表**: `schema_migrations`

### schema_migrations 表结构

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

## 三、迁移流程

### 创建新迁移

```python
from treecut.platform.migrations import MigrationManager
mgr = MigrationManager(db_path)
mgr.create_migration("add_shot_usage", "CREATE TABLE shot_usage (...);")
# 生成 migrations/0002_add_shot_usage.sql
```

### 应用迁移

```python
mgr.apply_pending()   # 自动扫描 migrations/ 应用未执行迁移
mgr.status()          # 查看状态
```

### 强制顺序（Phase 0 定）

```
备份数据库（BACKUP_MANIFEST.json）
  → 应用迁移
  → 运行 tests + regression
  → 提交 git
  → 记录 rollback 说明（恢复备份命令）
```

## 四、基线记录

Phase 0 已登记基线：

| version | name | git_commit | checksum | status |
|---|---|---|---|---|
| 0001 | baseline_v13_schema | 7a66fa4 | 89df54995dc1c24b | applied |

**基线说明**: v13.5.15 现有全部 Schema（45 表，含 P1-P9/P2.5/P2.7/Brain/Phase6），
由历史 `CREATE TABLE IF NOT EXISTS` 累积生成，本迁移仅登记不重建。

## 五、回滚政策（Rollback）

- **无反向迁移**。rollback = 用备份库恢复：

```
python -c "import sqlite3; s=sqlite3.connect(r'<backup.db>'); d=sqlite3.connect(r'<materials.db>'); s.backup(d); d.close(); s.close()"
```

- 恢复前必须停止所有 TreeCut 进程（含 Worker/UI）。
- 备份文件保留在 `runtime_data/temp/batch1/backups/materials_<时间戳>.db`。

## 六、禁止事项

- ❌ 绕过 MigrationManager 直接 ALTER TABLE
- ❌ 删除/重命名旧表（兼容迁移替代）
- ❌ 覆盖原始视频素材
- ❌ 在无备份情况下执行迁移
