# FRESH_HOLDOUT_V1 — Blind Review UI Blocking Fix Report

- **日期**：2026-08-28 17:51 ｜ git `10ccfdb` ｜ 性质：仅修 Blind Review UI 数据装载/布局；未动 AI 预测/Bundle/题目/manifest
- **AI 锁定状态保持**：prediction_sha256=`f5c7c5e70c0fa299`（未变）、PREDICTION_LOCKED=True、DO_NOT_REPREDICT=True

## 1-3. 为什么之前表单/Segment 信息没显示（根因）

**代码级根因**：`ReviewTaskWindow._build_review()` 中
`paned.add(right, weight=6, minsize=520)` —— **`ttk.Panedwindow` 不支持 `minsize` 选项**，
执行到该行抛 `TclError: unknown option "-minsize"`，`_build_review` **中途崩溃**：
- 崩溃点之前的 top 工具栏 + 左栏（播放按钮/说明）已构建并显示
- 崩溃点之后的 **right 栏 + `_V21Form` 从未创建**
- `_load()`（在 `_build_review` 末尾）从未执行 → **Segment metadata 未填充**

→ 用户看到"顶部置信度/状态 + 播放按钮 + 盲审说明，中部大片空白"。

**盲审路径数据装载**：修复后实测——manifest(strata) 读取 30 条、queue=30、current 非空、
info 填充（片段编号/素材/时间范围/stratum=GAP）、`1/30`、`已完成 0/30`。

## 4. 是否 blind=True 分支逻辑错误？

**否**。blind=True 只影响：manifest 结构兼容（strata）、持久化表（fresh_holdout_human_review_v1）、
提示文案。**表单构建路径与普通审核完全一致**（复用同一 `_V21Form`）；BLIND 语义正确 = 隐藏 AI、不隐藏人工表单。

## 5-6. 修复后验证（运行时审计 + 11 项回归）

| 项 | 结果 |
|---|---|
| `_V21Form` 实例数 | **1** |
| 30 条全部能加载 | **是**（items=30、queue=30） |
| AI 信息泄漏检查 | **0**（UI 文本 dump 不含任何 AI prediction 值/provider/score/evidence/routing/bundle） |
| 字段完整性 | 场景/产品/材质/组件/功能/动作/景别/镜头角色/人物/质量 全部在表单 |
| 打开/关闭不保存 | human count 保持 0、HUMAN_REVIEW_STARTED 保持 FALSE |
| prediction hash | **未变** `f5c7c5e70c0fa299` |

## 7-9. 状态与测试

- Human Review count：**0**（未开始）；HUMAN_REVIEW_STARTED：**FALSE**（打开页面不算开始）
- pytest：**11 项盲审回归全过**（含 leak dump 对照 30 条预测文件、hash 恒等、widget 稳定 load30）
- 全量回归：见提交说明

## 10. 交付与下一步

- 修复：`review_center.py` 移除非法 `minsize` 选项（Panedwindow）
- 报告：本文件
- **下一步（待视觉验收）**：Main → 人工审核中心 → FRESH_HOLDOUT_V1 应显示：第 1/30、已完成 0/30、左栏 Segment 信息+播放、右栏完整 V2.1 表单；验收通过后开始 30 条盲审

> 完成后 STOP：未自动开始审核、未保存任何人工答案、未触碰 AI 预测。
