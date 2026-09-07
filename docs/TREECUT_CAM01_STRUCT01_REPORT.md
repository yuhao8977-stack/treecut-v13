# POST-A3 CAM01 STRUCT01 — Structural Object Anchor V1 报告（FAIL / EXHAUSTED）

- 日期：2026-09-07 · main @ 0f26e69 → 本次提交
- 不调参/不读 A3/无新人工/不用动作 GT；ECC 多尺度金字塔为固定算法；门槛跑前冻结

## 1. 合成 ECC 方向测试
- 4/4 通过：translation ±（err<3px, known-point）；rotation/affine-scale 语义方向/量级正确
  （ECC 局部极小已知，不claim亚像素；平移严格）。
- 修正过程记录：OpenCV ECC 返回 M = template→input forward（原取逆为方向 bug）；金字塔按输入原生尺寸逐级。

## 2. 主结果（36 island-present pairs）
| 指标 | 值 |
|---|---|
| EUCLIDEAN validated /36 | **0** |
| AFFINE validated /36 | **0** |
| STRUCT_MULTI_MODEL_CONSENSUS /36 | 0 |
| STRUCT_SINGLE /36 | 0 |
| STRUCT_CONFLICT /36 | 0 |
| STRUCT_NO_ANCHOR /36 | **36** |
| STRUCT union /36 | **0** |
| case coverage /9 | 0 |
| pooled sym median/P90/P95 | null（无 validated） |

- fold 细节：绝大多数 ECC_NOT_CONVERGED（masked fit 在真实梯度图上不收敛）；个别 fold 到验证步但 sym 距离缺失。

## 3. 困难案例
1641 / 10000 / 2543 / 21674：4/4 pairs 全 NO_ANCHOR（EUCLIDEAN/AFFINE 均未 validated）。无特判。

## 4. NEG target control（真实 contract）
MULTI 0 · SINGLE 0（无 validated anchor 可对照；不设 EXTEND threshold）。

## 5. 判定（预置门槛）
- improvement class = **FAIL**（union 0 < 17）。
- **LOW_LEVEL_LOCAL_ANCHOR_EXHAUSTED = TRUE**（按 §28：union<17 → 不再调 Canny/ECC/Hough/grid）。
- NEXT_BLOCKER（下一阶段候选，不自动开发）：**higher-level object correspondence 或 global/background fallback hierarchy**。

## 6. 诚实说明
- 结构性失败的直接原因是 **ECC（masked）在真实柜体梯度图上不收敛**，而非"画面无结构"（LINE_DIAGNOSTIC 中柜体确有边缘线）；
  但按 §28 明确禁止继续迭代 ECC/Canny → 本结论即校准数据下该低层结构路线的正式判定，保留历史。

## 7. 全链低层 Anchor 汇总（对照）
V24R1 strict feature consensus 12/36 · GFTT whole-island 17/36 · V26R1 pair-region union 7/36 ·
STRUCT01 ECC structural 0/36 → **低层局部 Anchor（点/块/边）在现有 L3 ROI+冻结5帧条件下均已测到极限**。

## 产物
reports/storage/TREECUT_CAM01_STRUCT01_CONFIG.json · _METHOD_MATRIX.json · _EDGE_VALIDATION.json ·
_LINE_DIAGNOSTIC.json · _CONSENSUS.json · _NEG_TARGET_CONTROL.json · _RESULT.json · _GALLERY.html ·
scripts/posta3_cam01_struct01.py · tests/test_cam01_struct01_ecc.py
