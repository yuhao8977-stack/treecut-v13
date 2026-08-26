# TreeCut Phase 1 — Canonical Data Spine 审计总报告

> 阶段: Phase 1（统一素材身份与生产数据主干）| 日期: 2026-08-26
> 前置: Phase 0 验收 PASS | 基线: v13.5.15-baseline
> 状态: 完成，等待架构监工验收 | 未进入 Phase 2

---

## 目录

1. [执行摘要](#一执行摘要)
2. [0. Phase 前置保护](#二0-phase-前置保护)
3. [1-2. Canonical Identity 规则](#三1-2-canonical-identity-规则)
4. [3. AssetService / SegmentService](#四3-assetservice--segmentservice)
5. [4. 三链路 ID 迁移审计](#五4-三链路-id-迁移审计)
6. [5. 全项目 ID Dependency Matrix](#六5-全项目-id-dependency-matrix)
7. [6. Segment 完整性检查](#七6-segment-完整性检查)
8. [7. Shot Usage Ledger（Migration 0002）](#八7-shot-usage-ledgermigration-0002)
9. [8. Visual Cluster 占位模型](#九8-visual-cluster-占位模型)
10. [9. 旧表与 Legacy 策略](#十9-旧表与-legacy-策略)
11. [10. 测试与覆盖率](#十一10-测试与覆盖率)
12. [11. 数据一致性验收](#十二11-数据一致性验收)
13. [12. Rollback](#十三12-rollback)
14. [13. 验收硬门槛核对](#十四13-验收硬门槛核对)
15. [14. 遗留问题与风险](#十五14-遗留问题与风险)

---

## 一、执行摘要

Phase 1 目标：解决 `asset_id / media_id / segment_id` 三套 ID 并存的核心技术债，
统一素材身份与生产数据主干。**本 Phase 未碰 AI 识别/知识库/脚本理解/自动剪辑算法**。

| 验收项 | 结果 |
|---|---|
| git commit | `fc70299`（已 push origin/main） |
| migration version | **0002**（shot_usage + visual_clusters） |
| pytest | **62 passed / 0 failed / 0 skipped** |
| 新增测试 | 11 个（Phase 1） |
| coverage（新增模块） | **90%**（identity 92% / shot_usage 100% / migrations 80%） |
| DB integrity | **ok**（49 表） |
| Canonical 追溯 | **100%**（抽样 2000 segment + 全量 22465 assets） |
| 旧链路 | 未破坏（industry/value 冒烟通过） |

**关键成果**：
- 正式固定三级身份：`media_files.id → assets.asset_id → segments.segment_id`
- 建立 AssetRepository / SegmentRepository（业务模块不再自行写 SQL）
- 建立 shot_usage 镜头使用 Ledger（宪法 8 落地）
- 产出全项目 ID Dependency Matrix（24 模块 4 分类）
- Segment 完整性 7/8 项 0 异常

---

## 二、0. Phase 前置保护

| 项 | 值 |
|---|---|
| git 工作树 | 干净（Phase1 开始前） |
| 当前 commit | a21446d（Phase0 末态） |
| baseline tag | `v13.5.15-baseline` ✅ 存在 |
| remote push | ✅ `main`（34b7945..a21446d）✅ `v13.5.15-baseline`（new tag） |
| Phase1 备份 | `backups/materials_phase1_20260826_162946.db`（329.02 MB） |
| 备份完整性 | ✅ ok（原库 + 备份库） |
| 备份 manifest | `PHASE1_BACKUP_MANIFEST.json` |

### PHASE1_BACKUP_MANIFEST.json 摘要

```json
{
  "phase": "1-pre", "git_commit": "a21446d", "baseline_tag": "v13.5.15-baseline",
  "backup_file": ".../backups/materials_phase1_20260826_162946.db",
  "backup_size_mb": 329.02,
  "source_sha256": "<sha256>", "backup_sha256": "<sha256>",
  "source_integrity_ok": true, "backup_integrity_ok": true,
  "wal_before_bytes": 0, "wal_after_bytes": 0,
  "tables": { "assets": 22465, "segments": 41814, "...": "46 表" },
  "restore_command": "python -c \"import sqlite3; s=sqlite3.connect(r'<backup>'); d=sqlite3.connect(r'<db>'); s.backup(d); d.close(); s.close()\""
}
```

---

## 三、1-2. Canonical Identity 规则

### 正式固定

```
media_files.id     = 文件发现层 File Identity
                     仅允许：文件定位 / 文件元数据 / 物理路径解析
assets.asset_id    = 视频资产唯一 Canonical Asset Identity（唯一 Source of Truth）
segments.segment_id = 自动生产最小单位 / Shot Identity 基础
```

关系：`media_file → asset → segment`（上层引用下层）

### 禁止

- ❌ media_id 作为业务主键
- ❌ 新造第四套镜头身份（shot_id / clip_id / video_item_id / material_id）
- 未来"镜头 / shot / clip / candidate shot"统一引用 `segment_id`
- 仅真正产生新逻辑对象才允许新 ID：`script_beat_id` / `production_id` / `visual_cluster_id`

### 落地位置

- `src/treecut/services/identity.py` 模块 docstring
- 本报告第三节（Canonical 规则成为文档级约束）

---

## 四、3. AssetService / SegmentService

### 代码位置

**文件**: `src/treecut/services/identity.py`
**统一入口**: `services/__init__.py` → `services.assets` / `services.segments` / `services.shot_usage`

### AssetRepository（AssetService）

| 方法 | 功能 | 测试覆盖 |
|---|---|---|
| get_asset(asset_id) | 资产 + media + source 联查 | ✅ |
| resolve_media(asset_id) | asset → media_id（仅文件定位） | ✅ |
| resolve_path(asset_id) | asset → 物理绝对路径 | ✅ |
| list_segments(asset_id) | 资产下所有 segment | ✅ |
| validate_asset(asset_id) | 存在性 + 文件可达性 | ✅ |

### SegmentRepository（SegmentService）

| 方法 | 功能 | 测试覆盖 |
|---|---|---|
| get_segment(segment_id) | 取镜头 | ✅ |
| get_asset_id(segment_id) | segment → asset（回溯第一跳） | ✅ |
| resolve_source(segment_id) | segment → {asset, media, path} 完整链 | ✅ |
| resolve_time_range(segment_id) | start/end/duration | ✅ |
| list_by_asset(asset_id) | 按资产列镜头 | ✅ |
| validate_segment(segment_id) | 存在 + 时间合法 + 回源可达 | ✅ |

### 边界原则

- 业务模块**不自行重复写 SQL**（Repository 封装）
- CLI/UI 统一经 Service Layer（宪法 7）
- 本 Phase 未重写任何旧代码的 ID 逻辑（宪法：不一次性大重构）

---

## 五、4. 三链路 ID 迁移审计

| 链路 | 当前 ID | 判定 | 证据 | 计划 |
|---|---|---|---|---|
| **A. workflow/matching.py**（P4 检索） | media_id 中心（15 处） | **MIGRATE_LATER** | L17/33 候选物 ID；L145-192 打分键/重排键 | Phase 4 检索重构 |
| **B. roughcut/engine.py**（粗剪） | segment→asset→media | **KEEP ✅ 符合设计** | L46-65 `_resolve_segment` 完整追溯 | - |
| **C. cognitive/production.py**（Phase5 生产） | asset_id 直接选素材 | **LEGACY_ASSET_LEVEL_PRODUCTION** | L122-143 `_asset_pool` 整素材截取 | Phase 6 替换 |

**Phase 1 行动**：
- A 链路：仅记录（Matrix），不迁移
- B 链路：确认符合 Canonical 设计，无需改动
- C 链路：加 `LEGACY_ASSET_LEVEL_PRODUCTION` 代码注释标记，等待 Phase 6

---

## 六、5. 全项目 ID Dependency Matrix

**基于全项目扫描**：33 个文件含 media_id，36 个文件含 asset_id。

### 分类汇总

| 分类 | 模块数 | 代表 |
|---|---|---|
| **KEEP**（符合设计） | 12 | roughcut 链路 / brain / industry / vision / value / task_store / quality_validation / 新服务 |
| **ADAPT**（小改） | 6 | library/assets(42处) / catalog(43处) / ui/library_dialog(17处) / api(14处) / learning/feedback(14处) |
| **MIGRATE_LATER**（核心迁移） | 3 | matching.py(media_id中心) / semantic_matching / 粗剪渲染段 |
| **LEGACY**（标记保留） | 3 | production.py / P4 旧检索 / production_plans |
| **合计** | **24** | |

### 关键分类明细

**KEEP（12）**：roughcut/engine、roughcut/sort_advisor、cognitive/brain、cognitive/industry、cognitive/vision、cognitive/value、library/task_store、quality_validation/*、services/identity（新）、services/shot_usage（新）

**ADAPT（6）**：library/assets.py、library/catalog.py、ui/library_dialog.py、api.py、learning/feedback.py、ui/result_dialog.py
（media_id 作业务主键 → 需逐步改 asset_id 为主，media_id 仅路径；非本 Phase）

**MIGRATE_LATER（3）**：workflow/matching.py（高）、models/semantic_matching.py（中）、roughcut/engine.py 渲染段（低）

**LEGACY（3）**：cognitive/production.py（`LEGACY_ASSET_LEVEL_PRODUCTION`）、P4 旧检索（`LEGACY_MEDIA_CENTERED_RETRIEVAL`）、production_plans

---

## 七、6. Segment 完整性检查

### 8 项检查结果（生产库 41814 行）

| # | 检查项 | 结果 | 状态 |
|---|---|---|---|
| 6.1 | segment_id 唯一性 | 0 重复 | ✅ PASS |
| 6.2 | asset_id 外键有效性 | 0 orphan | ✅ PASS |
| 6.3 | start_ms < end_ms | 0 非法 | ✅ PASS |
| 6.4 | duration_ms > 0 | 0 非法 | ✅ PASS |
| 6.5 | 时间 ≤ asset 真实时长（+2s 容差） | 0 超界 | ✅ PASS |
| 6.6 | 同 asset 重复 [start,end] | 0 组 / 0 行 | ✅ PASS |
| 6.7 | orphan segment | 0 | ✅ PASS |
| 6.8 | quality_score 未评分 | **41814 (100%)** | ⚠️ 历史遗留 |

### 基础统计

| 项 | 值 |
|---|---|
| segments 总数 | 41814 |
| 覆盖 asset 数 | 22390 |
| 时长分布 | 平均 4.19s / 中位 5.0s / P10 2.0s / P90 5.0s |
| 生成方式 | ContentDetector(threshold=27) + 固定 5s 兜底（P9 降级） |

### 处理原则

- ⚠️ 6.8 quality_score 全 0：**仅标记，不删除、不修改**（宪法：异常只报告）
- ⚠️ 生成方式混杂：Phase 2 认知语义化时按 segment 重新标注，不回溯修改

---

## 八、7. Shot Usage Ledger（Migration 0002）

### Migration 记录

| 项 | 值 |
|---|---|
| 文件 | `migrations/0002_shot_usage_visual_clusters.sql` |
| schema_migrations | v0002（commit a21446d，checksum 69f8425a） |
| 应用方式 | MigrationManager.apply_pending() |

### shot_usage 表（宪法 8：素材使用必须有记忆）

```sql
usage_id / segment_id / production_id / account_id / beat_id / template_id
usage_type(candidate|preview|rendered|published)
used_at / usage_count / cooldown_until / status(active|cancelled) / created_at
索引: segment_id, production_id
```

### ShotUsageService

| 方法 | 功能 | 测试 |
|---|---|---|
| record_usage() | 记录（拒绝无效 segment_id） | ✅ |
| query_by_segment() | 查询镜头历史 | ✅ |
| cancel() | 置 cancelled | ✅ |
| usage_count() | 活跃使用计数 | ✅ |
| stats() | 统计 | ✅ |

**本 Phase 仅建 Schema + Service，未启用 reuse cooldown 算法**（Phase 6 实现，宪法 8 完整落地）。

---

## 九、8. Visual Cluster 占位模型

**决策：建立占位表（migration 0002 内），不运行聚类。**

| 表 | 字段 |
|---|---|
| visual_clusters | cluster_id / method / created_at / status(empty) |
| visual_cluster_members | cluster_id / segment_id / distance / added_at |

**明确未做**：
- ❌ 未自动聚类 2.2 万素材
- ❌ 未调用 CLIP 重跑
- ❌ 未修改 duplicate 逻辑

目标仅为 Phase 6 近重复防重预留规范数据模型（宪法 8 visual_cluster_id）。

---

## 十、9. 旧表与 Legacy 策略

**原则：禁止删除旧表。**

| 表 | 分类 | 说明 |
|---|---|---|
| assets | ACTIVE | Canonical |
| media_files | ACTIVE | 文件发现层，保留 |
| segments | ACTIVE | 生产单位 |
| analysis_jobs | COMPATIBILITY | P4 检索依赖 |
| media_tags | COMPATIBILITY | |
| production_plans | LEGACY_READ_ONLY | Phase 6 替换为 production_runs |
| 旧 P4/P6 概念表 | LEGACY | 未落库/代码引用 |
| 其余 42 表 | ACTIVE / COMPATIBILITY | 不影响 |

**无表被删除；全部保留。** 迁移后总表数 46 → 49（+shot_usage/visual_clusters/visual_cluster_members）。

---

## 十一、10. 测试与覆盖率

### 新增测试（`tests/test_phase1_identity.py`，11 用例）

| 组 | 用例 |
|---|---|
| AssetService | resolve_media / resolve_path / invalid handling |
| SegmentService | resolve_asset / resolve_path+time / invalid_orphan |
| Canonical 链路 | segment→asset→media→path 完整追溯 |
| Migration | 0001→0002 / 幂等重放 |
| ShotUsage | 插入/查询/cancel / 拒绝无效 segment |

### pytest 结果

| 指标 | 值 |
|---|---|
| 总测试 | **62** |
| 通过 | **62** |
| 失败 | **0** |
| 跳过 | **0** |
| 用时 | 45.33s |

### coverage（Phase 1 新增模块）

| 模块 | Stmts | Miss | Cover |
|---|---|---|---|
| services/identity.py | 79 | 6 | **92%** |
| services/shot_usage.py | 49 | 0 | **100%** |
| platform/migrations.py | 69 | 14 | **80%** |
| **合计** | 197 | 20 | **90%** |

（Phase 0 三模块不变：industry 49% / value 24% / accuracy 11%）

---

## 十二、11. 数据一致性验收

### 真实数字（生产库）

| 指标 | 值 |
|---|---|
| assets | **22465** |
| media_files | **28096** |
| segments | **41814** |
| orphan assets（无 media） | **0** |
| orphan segments（无 asset） | **0** |
| invalid time ranges | **0** |
| duplicate exact segments | **0** |
| Canonical 追溯（抽样 2000） | **100%**（2000/2000 成功） |
| assets→path 全量 | **100%**（22465/22465） |

### Canonical 追溯验证（生产库）

```
segment_id → asset_id → media_id → physical path
抽样 2000 segment：100% 成功
全量 22465 asset → path：100% 成功
```

### 模块分类统计

| 分类 | 模块数 |
|---|---|
| KEEP | 12 |
| ADAPT | 6 |
| MIGRATE_LATER | 3 |
| LEGACY | 3 |

---

## 十三、12. Rollback

### 从 migration 0002 恢复到 Phase 0 状态

**数据库回滚**（0002 新增 3 表，无破坏性）：

```
# 方式 A：恢复 Phase 1 前备份（推荐，已验证可打开 + integrity ok）
python -c "import sqlite3; s=sqlite3.connect(r'...\backups\materials_phase1_20260826_162946.db'); d=sqlite3.connect(r'...\materials.db'); s.backup(d); d.close(); s.close()"

# 方式 B：仅删 0002 新增表（不推荐，需手工）
DROP TABLE shot_usage; DROP TABLE visual_cluster_members; DROP TABLE visual_clusters;
DELETE FROM schema_migrations WHERE version='0002';
```

**代码回滚**：`git revert fc70299` 或 `git checkout v13.5.15-baseline`

**备份可恢复性验证**：

| 项 | 值 |
|---|---|
| 备份文件 | materials_phase1_20260826_162946.db |
| 可打开 | ✅ |
| integrity_check | **ok** |
| 恢复命令 | 见 PHASE1_BACKUP_MANIFEST.json |

---

## 十四、13. 验收硬门槛核对

| [ ] 门槛 | 状态 |
|---|---|
| assets 正式确认唯一视频 Canonical | ✅ |
| segment 正式确认自动生产最小单位 | ✅ |
| 不存在新造第四套镜头身份 | ✅ |
| segment→asset→media→path 追溯 100% | ✅ 100% |
| orphan segment = 0 | ✅ 0 |
| 所有新 Schema 来自 migration | ✅ 0002 |
| AssetService 可用 | ✅ |
| SegmentService 可用 | ✅ |
| shot_usage 基础 Schema 可用 | ✅ |
| 新测试全部通过 | ✅ 62/62 |
| 旧链路未破坏 | ✅（industry/value 冒烟通过） |
| 数据库 integrity = ok | ✅ |
| rollback 方案经过验证 | ✅ |
| 未修改认知/模板/自动生产算法 | ✅（仅加 LEGACY 注释） |

---

## 十五、14. 遗留问题与风险

| 项 | 说明 | 处理 Phase |
|---|---|---|
| media_id 仍被 6 模块作业务主键（ADAPT） | library/assets、catalog、api 等 | Phase 2+ 渐进迁移 |
| P4 检索 media_id 中心（MIGRATE_LATER） | matching.py 候选/打分键 | Phase 4 检索重构 |
| Phase5 生产 asset 级选材（LEGACY） | `LEGACY_ASSET_LEVEL_PRODUCTION` 已标记 | Phase 6 替换 |
| segment quality_score 全 0 | 历史未评分 | Phase 2 补充 |
| segment 生成方式混杂（scene+固定5s） | 语义粒度不均 | Phase 2 重标注 |
| coverage 全库未测 | 当前只测指定模块 | 逐 Phase 提高 |
| backup manifest 未入 git | 数据根下（含敏感哈希） | 保持 .gitignore |

---

**Phase 1 完成。按宪法 14 条，未进入 Phase 2，等待架构监工验收。**
