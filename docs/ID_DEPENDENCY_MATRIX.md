# TreeCut ID Dependency Matrix（ID 依赖矩阵）

> Phase: 1 | 日期: 2026-08-26
> 目的: 全项目 ID 使用分类，防止未来产生第四套身份体系
> 分类: KEEP（符合设计）/ ADAPT（小改）/ MIGRATE_LATER（需迁移）/ LEGACY（旧链路标记）

---

## 一、Canonical Identity 规则（正式固定）

```
media_files.id    = 文件发现层 File Identity（仅文件定位/元数据/路径解析）
assets.asset_id   = 视频资产唯一 Canonical Asset Identity（唯一 Source of Truth）
segments.segment_id = 自动生产最小单位 / Shot Identity 基础
```

**关系**：`media_file → asset → segment`（上层引用下层）

**禁止**：以 media_id 作为业务主键；新造 shot_id/clip_id/video_item_id 等第四套身份。
新逻辑对象 ID 仅允许：`script_beat_id` / `production_id` / `visual_cluster_id` 等。

---

## 二、模块依赖矩阵

### KEEP（符合 Canonical 设计，无需改动）

| 模块 | 文件 | 主 ID | 读取表 | 说明 |
|---|---|---|---|---|
| SegmentService（新） | services/identity.py | segment_id | segments→assets→media_files | ✅ Phase1 新建，符合设计 |
| AssetService（新） | services/identity.py | asset_id | assets→media_files | ✅ Phase1 新建，符合设计 |
| roughcut/engine.py | roughcut/engine.py | segment_id | segments JOIN assets | ✅ 已按 segment→asset→media 追溯 |
| roughcut/sort_advisor.py | roughcut/sort_advisor.py | segment_id | project_segments | ✅ |
| brain 认知链 | cognitive/brain.py | asset_id | transcripts/ocr_text/segments | ✅ |
| 行业引擎 | cognitive/industry.py | asset_id | transcripts/ocr_text | ✅ |
| 视觉补认知 | cognitive/vision.py | asset_id | keyframes | ✅ |
| 内容价值 | cognitive/value.py | asset_id | content_classification | ✅ |
| 任务系统 | library/task_store.py | asset_id | analysis_tasks | ✅ |
| 质量验证 | quality_validation/* | asset_id | asset_processing_state | ✅ |

### ADAPT（小改即可符合，非本 Phase 优先级）

| 模块 | 文件 | 当前主 ID | 读取表 | 目标 | 计划 |
|---|---|---|---|---|---|
| 素材库 | library/assets.py | media_id(42处) | media_files | asset_id 为主，media_id 仅路径 | Phase 2+ |
| 目录 | library/catalog.py | media_id(43处) | media_files | 同上 | Phase 2+ |
| UI 库对话框 | ui/library_dialog.py | media_id(17处) | media_files | 同上 | Phase 2+ |
| API | api.py | media_id(14处) | media_files | 同上 | Phase 2+ |
| 反馈学习 | learning/feedback.py | media_id(14处) | media_files | 同上 | Phase 2+ |

### MIGRATE_LATER（核心业务需迁移到 segment/asset）

| 模块 | 文件 | 当前主 ID | 风险 | 计划 Phase |
|---|---|---|---|---|
| **P4 检索链路** | workflow/matching.py | **media_id(15处)** | 高：候选物身份/打分键 | Phase 4（检索重构） |
| P4 候选模型 | workflow/matching.py | media_id | 高 | Phase 4 |
| 语义匹配 | models/semantic_matching.py | media_id(3处) | 中 | Phase 4 |
| 粗剪工程 | roughcut/engine.py 渲染段 | media_id | 低（仅解析） | 已兼容 |

### LEGACY（标记保留，等待替换）

| 模块 | 文件 | 说明 | 标记 | 替换 Phase |
|---|---|---|---|---|
| **Phase5 自动生产** | cognitive/production.py | asset_id 直接选素材（整段截取） | **LEGACY_ASSET_LEVEL_PRODUCTION** | Phase 6 |
| P4 旧检索 | workflow/matching.py 全链 | media_id 中心 | LEGACY_MEDIA_CENTERED_RETRIEVAL | Phase 4 |
| 生产计划表 | production_plans | asset 级 plan_json | LEGACY | Phase 6 |

---

## 三、统计汇总

| 分类 | 模块数 | 说明 |
|---|---|---|
| KEEP | 12 | 符合 Canonical 设计 |
| ADAPT | 6 | 小改（media_id→asset_id 主键化），非本 Phase |
| MIGRATE_LATER | 3 | 核心业务链路，需专项 Phase |
| LEGACY | 3 | 标记保留，等待替换 |
| **合计** | **24** | 全项目主要 ID 使用点已覆盖 |

---

## 四、Phase 1 声明

- 本 Phase **不修改任何旧代码的 ID 逻辑**（宪法：不一次性大重构）
- 已建立新访问边界（AssetRepository/SegmentRepository），新代码必须走 services
- LEGACY 标记在代码注释中体现，等待对应 Phase 替换

---

*Matrix 基于全项目 media_id/asset_id/segment_id 使用扫描（33 文件含 media_id，36 文件含 asset_id）。*
