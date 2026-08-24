# AI 认知体系 Phase 5 报告 — 自动生产链路

- **日期**：2026-08-24
- **范围**：模板 → 槽位选材 → 生产计划 → 成片草稿（认知驱动自动生产）
- **状态**：核心链路已验证（首个成片计划已生成）

---

## 1. 实施内容

### 1.1 认知生产引擎（`cognitive/production.py`）

**流程**：
```
content_classification（内容类型）
  + template（槽位结构：T001-T004）
  → 素材池（按内容类型 + 关键帧/场景段/置信度评分排序）
  → 槽位选材（每槽位挑最优未用素材，按槽位时长切分）
  → 生产计划（production_plans 表 + production_plan.json）
  → 口播脚本建议（narration_script.txt）
```

**槽位选材逻辑**：
- 素材池排序：`score = 关键帧数×2 + 场景段数 + 置信度×10`
- 每槽位取最高分未用素材，槽位时长按模板时间轴（如"0-3s"→3s）

### 1.2 生产计划存储

`production_plans` 表：project_id / template_id / content_type / plan_json / status / output_dir

### 1.3 CLI

- `--brain-produce T001 项目名`：按模板生成成片
- `--brain-produce-status`：生产计划状态

## 2. 验收结果（首个成片）

**命令**：`--brain-produce T001 客户案例001`

| 项 | 结果 |
|---|---|
| 模板 | T001 客户案例模板 |
| 槽位 | 4 个全部选到素材 ✅ |
| 素材来源 | 客户案例类素材池（按价值评分排序） |
| 最高分素材 | 89.2（结果展示槽位，完工实景） |
| 生产计划 | `output/brain_production/客户案例001/production_plan.json` |
| 口播脚本 | `narration_script.txt` |
| 状态 | draft_ready（素材齐全） |
| 落库 | production_plans 表 ✅ |

**槽位素材（示例）**：
| 槽位 | 时间 | 素材 | 评分 | 口播建议 |
|---|---|---|---|---|
| 结果展示 | 0-3s | 完工实景 MP4 | 89.2 | 高镜头价值画面 |
| 客户背景 | 3-13s | 杭州客户岛台案例 | 26.2 | — |
| 功能卖点 | 13-33s | 佛山客户产品介绍 | 26.2 | 功能演示素材 |
| CTA | 33-40s | 客户案例片段 | 26.2 | — |

## 3. 链路完整性

```
认知链（Phase1-2）→ 内容类型/模板推荐（已入库）
  → 生产引擎选材 → production_plans（已入库）
  → production_plan.json + narration_script.txt（已落盘）
  → 【后续】接 jianying.py/mp4.py 渲染成片
```

**当前达到**：认知驱动的**自动选材 + 生产计划**。成片渲染（剪映草稿/MP4）已预留接口（output 模块可复用）。

## 4. 局限与后续

| 项 | 说明 |
|---|---|
| 成片渲染未自动执行 | 生成 plan.json + 脚本，渲染可接 P2.6 的 jianying.py/mp4.py（需真实素材路径可达） |
| 素材评分基于数据量 | 关键帧/场景段/置信度近似价值，人工审核后可校准 |
| 槽位时长固定 | 按模板时间轴；可扩展智能匹配素材实际时长 |
| 需人工审核 | 生产计划建议人工确认后渲染（质量门禁） |

## 5. 验收结论

| 验收项 | 结果 |
|---|---|
| 认知生产引擎（槽位选材 + 计划） | ✅ |
| production_plans 表 + 落盘 | ✅ |
| CLI --brain-produce / --brain-produce-status | ✅ |
| 首个成片计划生成（T001 客户案例） | ✅ 4/4 槽位有素材 |
| 只读分析数据、产物写 output 目录 | ✅ |

**Phase 5 验收通过。** 认知体系全链路（分析→理解→判断→生产计划）已打通。

## 6. 复现命令

```bash
python -m treecut.main --brain-produce T001 客户案例001   # 生成成片计划
python -m treecut.main --brain-produce-status             # 查看计划
# 产物: output/brain_production/<项目>/production_plan.json + narration_script.txt
```
