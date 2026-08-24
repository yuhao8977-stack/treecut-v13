# 人工反馈系统设计（P2.7）

- **日期**：2026-08-24
- **目标**：人工审核反馈进入数据库，为 Segment/模板/反馈学习系统提供数据

---

## 1. 数据库设计（新增表，不修改既有表）

### 1.1 `human_feedback` — 人工反馈（核心）

```sql
CREATE TABLE IF NOT EXISTS human_feedback (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id     TEXT NOT NULL,               -- 素材 ID
    ai_type      TEXT NOT NULL,               -- scene|asr|ocr|keyframe|label
    ai_label     TEXT NOT NULL DEFAULT '',    -- AI 原始结果
    human_label  TEXT NOT NULL DEFAULT '',    -- 人工修正
    verdict      TEXT NOT NULL DEFAULT 'correct',  -- correct|partial|wrong
    comment      TEXT NOT NULL DEFAULT '',
    operator     TEXT NOT NULL DEFAULT '',    -- 操作员
    created_time REAL NOT NULL
);
```

**评价体系**：
| verdict | 含义 | 图标 |
|---|---|---|
| correct | 正确 | ✅ |
| partial | 部分正确 | ⚠️ |
| wrong | 错误 | ❌ |

**字段对照需求**：
| 需求字段 | 表字段 |
|---|---|
| id | id |
| asset_id | asset_id |
| ai_label | ai_label |
| human_label | human_label |
| score | → 见 asset_quality |
| comment | comment |
| operator | operator |
| created_time | created_time |

### 1.2 `asset_quality` — 100 分制评分

```sql
CREATE TABLE IF NOT EXISTS asset_quality (
    asset_id     TEXT PRIMARY KEY,
    scene_score    INTEGER NOT NULL DEFAULT 0,   -- 0/10/20
    product_score  INTEGER NOT NULL DEFAULT 0,
    function_score INTEGER NOT NULL DEFAULT 0,
    value_score    INTEGER NOT NULL DEFAULT 0,
    business_score INTEGER NOT NULL DEFAULT 0,
    total_score    INTEGER NOT NULL DEFAULT 0,
    reviewer       TEXT NOT NULL DEFAULT '',
    reviewed_time  REAL,
    comment        TEXT NOT NULL DEFAULT ''
);
```

### 1.3 `asset_status` — 素材业务状态

```sql
CREATE TABLE IF NOT EXISTS asset_status (
    asset_id     TEXT PRIMARY KEY,
    status       TEXT NOT NULL DEFAULT 'REVIEW',
    source       TEXT NOT NULL DEFAULT 'system',
    updated_time REAL NOT NULL
);
```

状态：`READY`（可用）/ `REVIEW`（待审）/ `HIGH_VALUE`（高价值）/ `LOW_VALUE`（低价值）/ `REJECTED`（废弃）/ `BROKEN`（损坏）

### 1.4 `broken_assets` — 损坏素材隔离

```sql
CREATE TABLE IF NOT EXISTS broken_assets (
    asset_id     TEXT PRIMARY KEY,
    file_path    TEXT NOT NULL DEFAULT '',
    error_reason TEXT NOT NULL DEFAULT '',
    failed_time  REAL NOT NULL,
    stage        TEXT NOT NULL DEFAULT '',
    resolved     INTEGER NOT NULL DEFAULT 0   -- 0=损坏 1=已恢复
);
```

## 2. 100 分评分标准（家具行业/小红书岛台）

| 维度 | 分值 | 评分 | 判断标准 |
|---|---|---|---|
| 场景识别 Scene | 20 | 20/10/0 | 是否识别正确（客户家/工厂/展厅/生产/安装/运输/厨房/客厅） |
| 产品识别 Product | 20 | 20/10/0 | 是否识别正确（岛台/岩板岛台/奢石岛台/实木岛台/餐桌/餐边柜/吧台/厨房柜体） |
| 功能识别 Function | 20 | 20/10/0 | 是否理解功能（伸缩/展开/收缩/抽屉/薄抽/深抽/收纳/轨道插座/隐藏电器/烤箱位/水吧） |
| 镜头价值 Value | 20 | 20/10/0 | 高价值（客户入户/空间展示/产品细节/功能展示/使用场景）；低价值（空镜/重复/模糊/人物挡产品/无关画面） |
| 商业价值 Business | 20 | 20/10/0 | 高价值（客户案例/尺寸展示/价格咨询/装修需求/痛点解决）；低价值（单纯展示/无信息） |

**总分分级**：
- ≥80 → HIGH_VALUE（高价值素材）
- 60-79 → READY（可使用）
- 40-59 → REVIEW（待确认）
- <40 → LOW_VALUE（低价值）

## 3. 反馈学习接口（`feedback_learning/`）

```
feedback_learning/__init__.py
├── correction_stats()       # AI vs 人工标签差异统计（学习信号）
├── label_confusion(type)    # 标签混淆矩阵（发现系统性误判）
└── high_value_candidates()  # 高评分素材推荐（供模板/推荐系统）
```

**未来用途**：
1. **优化标签排序**：AI 标签 vs 人工标签差异 → 调整模型标签权重
2. **优化素材推荐**：HIGH_VALUE 素材加权，LOW_VALUE 降权
3. **优化模板匹配**：人工确认的场景/产品标签反哺模板槽位匹配

## 4. 数据流

```
AI 分析结果（只读）
      ↓ 加载到 UI
人工审核 UI（quality_validation/ui.py）
      ↓ 操作员点击 ✅/⚠️/❌ + 修改 + 评分
human_feedback / asset_quality / asset_status（新增表）
      ↓
feedback_learning 接口
      ↓（未来）
Segment 系统 / 模板系统 / 推荐系统
```
