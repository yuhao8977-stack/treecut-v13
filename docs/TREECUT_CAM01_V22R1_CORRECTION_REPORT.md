# POST-A3 CAM01 V2.2 R1 — Deterministic 修正 + Local Anchor 失败地图报告

- 日期：2026-09-07 · main @ 69b88ed → 本次提交
- 仅修 holdout 计数 bug；未调阈值/未换算法/未造叶板/未碰 A3

## 1. 修正（CAM01_V22_DEFECT_HOLDOUT_COUNT_01）
- `two_fold_validate()` 用 `len(vi)>=8`（vi 为布尔数组 → len=全部 match 数）→ 改为 `int(vi.sum())>=CRIT_HOLDOUT_N`。
- 污染例确认：2543 pair `1.202->1.717` fit1val0 holdout_n=6 曾被标 VALIDATED；修正后该对 → **LOCAL_ANCHOR_PARTIAL**（FOLD_HOLDOUT_TOO_FEW）。
- 回归测试 2 项通过：sum=6 绝不 VALIDATED；sum=8 且满足其它条件才 VALIDATED（tests/test_cam01_v22_holdout_count.py）。

## 2. V2.2 → V2.2R1 状态变化（40 pairs）
| 状态 | V2.2 | V2.2R1 |
|---|---|---|
| LOCAL_ANCHOR_VALIDATED | 14 | **13** |
| LOCAL_ANCHOR_PARTIAL | 2 | **3**（12095 2.225->5.191 · 3571 7.984->10.441 · 2543 1.202->1.717） |
| NOT_VALIDATED | 8 | 8 |
| INSUFFICIENT | 12 | 12 |
| NO_ISLAND/N/A | 4 | 4 |
- 2543 最终：`1.202->1.717 = LOCAL_ANCHOR_PARTIAL`（其余三对 INSUFFICIENT）。

## 3. VALIDATED 分布与 target-motion 后果
- VALIDATED 13 对分布：27433 POS ×3 · 12095 POS ×3 · 3571 POS ×3 · 9697 NEG ×2 · 25894 NEG ×2。
- **POS3（MOTION_VISIBLE）锚点全部 VALIDATED（9/9 对）** → 9 条 target-motion 行（几何+像素，锚点补偿）。
- **NEG validated-with-target 行 = 0**（9697/25894 的 VALIDATED 对无桌板目标框；2543 原唯一对照对降为 PARTIAL；1641/10000 无 VALIDATED 对）→
  **TARGET_MOTION_NEG_CONTROL = NOT_ESTABLISHED**。不做 POS vs NEG separation，不以 POS 幅度设阈值。

## 4. 失败分类（40 对可多原因）
- HIGH_HOLDOUT_MEDIAN 15 · TARGET_NEIGHBORHOOD_UNSUPPORTED 9 · SPATIALLY_CLUSTERED 7 ·
  MATCHES_TOO_FEW 6 · LOW_FIT_INLIER 5 · FOLD_HOLDOUT_TOO_FEW 5 · FEATURES_TOO_FEW 5 · VALIDATED_CLEAN 2。
- 个案：1641 全 4 对 feature 不足；2212 无 ISLAND_BODY(4 对 NO_ISLAND)；10000 匹配稀少/不稳；
  9697/25894 各 2 对 VALIDATED（但无目标框可对照）；2543 验证点少(1 对 PARTIAL)。
- tail：VALIDATED 对中亦有 P90/尾部重者（见 JSON validated_tail；P90 不设 gate，仅诊断）。

## 5. 空间支撑（诊断，不改状态）
- 空间信息对 40 对：mean convex_hull/island ≈ **0.376**；SPATIALLY_CLUSTERED 7。
- 目标邻域：17 对有邻域诊断；**VALIDATED 中 9 对 NEAR-TARGET 支撑不足（<3 个近目标点）** →
  即使整岛 median≤3px，目标附近锚点支撑仍可能弱（重要发现，指向空间分布而非纯匹配数）。

## 6. 下一问题类建议（§13，不自动开始）
**D. MIXED** —— 非单一原因：
- 主因 1（robustness/B）：HIGH_HOLDOUT_MEDIAN 15 → 匹配/模型稳健性；
- 主因 2（spatial/C）：近目标锚点支撑不足 9 + SPATIALLY_CLUSTERED 7 → 空间分布；
- 次因（A）：特定案例纹理稀缺（1641/10000/2543 子集）。
- 非 E：POS3 全部 VALIDATED + 亚像素级中位 → 岛台局部参照路线值得继续。

## 产物
reports/storage/TREECUT_CAM01_V22R1_METHOD_CORRECTION.json · _LOCAL_ANCHOR_VALIDATION.json ·
_ANCHOR_FAILURE_MAP.json · _TARGET_RELATIVE_GEOMETRY.json · _TARGET_PIXEL_EDGE_MOTION.json ·
scripts/posta3_cam01_v22r1.py · tests/test_cam01_v22_holdout_count.py
