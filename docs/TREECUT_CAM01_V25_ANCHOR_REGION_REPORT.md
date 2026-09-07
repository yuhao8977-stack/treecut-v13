# POST-A3 CAM01 V2.5 — Automatic Stable Anchor Patch 报告（NO_REGION_IMPROVEMENT）

- 日期：2026-09-07 · main @ e2bb0ae → 本次提交
- 未调阈值/未碰 A3/无新人工/不用动作 GT；4×4 normalized grid、25% overlap(任一帧)、MIN 阈值均为跑前冻结

## 0. Baseline 真 pooled 修正（从 V24R1 存盘残差合并）
- V24R1 12 个 consensus pair、representative holdout 残差全合并（n=822）：
  **GLOBAL_POOLED median 0.574 · P90 3.682 · P95 7.491 px**（替代原"per-pair P90 取中位"口径；12/36 不变）。

## 1. 结果（36 island-present pairs）
- PATCH_MULTI_CONSENSUS = **0/36** · PATCH_SINGLE = 0 · PATCH_CONFLICT = 0 · PATCH_NO_ANCHOR = 36
- patch union = 0 · case coverage = 0/9 · selected patches = 0（全部 case PATCH_BANK_INSUFFICIENT）
- improvement class = **NO_REGION_IMPROVEMENT**（预置规则，不改门槛）

## 2. 根因（系统性，非单例）
- 全局审计：8 个有岛台 case 中 **7 个 free_cells=0**（全部 cell 在至少 1 帧 overlap>25%），1641 仅 1 free cell 且纹理不足。
- 机制：人工框的 **EXTENSION_TABLETOP 大框横贯岛台**（例 27433：x76–914）＋手/腿/插座/抽屉 +
  **逐帧岛台框本身随画面变化** → 固定 normalized 4×4 cell 在"全部 5 帧"保持 clean 的约束下无一幸存；
  剩余条带（如 27433 r3）跨帧会被动件/手覆盖，或为暗色低纹理（std≈7 < 阈值）。
- 结论（保留为发现，不调参）：**"整岛一锅端"不是唯一问题；在"逐帧人工岛台框 + 大面积动件标注"下，
  固定网格 any-frame>25% 规则过严**。这不是 detector 问题，是 region 定义/约束问题。

## 3. 比较基线（不变）
V24R1 strict consensus 12/36 · GFTT whole-island 17/36 · V25 patch = 0（未能比）→ 本方案当前不成立。

## 4. 困难案例
1641/10000/2543/21674 全部 bank insufficient（与上文同因）；无 media-id 特判。

## 5. NEG target control
- 无 validated anchor → consensus=0、single=0（沿用严格 t0/t1 contract 空集）；不进入 GEOM threshold。

## 6. 产物与边界
- 产物：PATCH_SCORE_CONFIG / PATCH_BANK / PATCH_METHOD_MATRIX / PATCH_CONSENSUS / TARGET_SUPPORT / NEG_TARGET_CONTROL / RESULT json + PATCH_GALLERY.html（绿=0，展示 16 cell 与拒绝原因）。
- 边界：即使成功也只说明"已知 body ROI 下 region representation 有进展"；AUTO ROI/PRODUCTION 仍不作数。

## 7. 下一步候选（等你定，不自动开始）
A) region 约束放宽/合理化：按 **pair 级**而非全 5 帧建 bank（语义帧对只需两端 clean）；
B) 网格加密 + 从"多帧岛台并集−前景并集"推导干净子域（避开逐帧框抖动）；
C) 结构先验子区（台面边缘/侧板/正面柜体 top rail）做锚；
D) 放弃 ISLAND_BODY 内部 patch，转向"非目标静态背景带"。
（V2.5 历史结果保留；不改任何阈值。）
