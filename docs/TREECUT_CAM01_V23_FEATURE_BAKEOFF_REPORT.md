# POST-A3 CAM01 V2.3 — Local Anchor Feature Bakeoff 报告

- 日期：2026-09-07 · main @ 942d459 → 本次提交
- 未改 ROI/GT/GEOM/gate；不读 A3；不造叶板；参数预冻结（TREECUT_CAM01_V23_METHOD_CONFIG.json）

## 1. R1 诊断修正（已修，未影响 13/40 主结果）
- 象限：`("L"/"R")+("T"/"B")` 生成 LT/LB/RT/RB 曾对不上 TL/TR/BL/BR → 修正映射（代码直接产出 TL/TR/BL/BR）。
- target-neighborhood residual：改为**只用 2-fold holdout 点**（两 fold 独立验证残差合并），禁止 all-match fit residual。
  （诊断性修正；验证 gate 未动。）

## 2. 方法对比（36 island-present pairs，统一 gate）
| 方法 | VALIDATED/36 | case coverage/9 | med holdout px | P90 px | heavy-tail | hull ratio |
|---|---|---|---|---|---|---|
| AKAZE_BASELINE | 13（复现 R1 ✓） | 5 | 1.60 | 12.5 | 13 | 0.44 |
| AKAZE_CLAHE | 15 | 5 | 1.76 | 7.0 | 14 | 0.49 |
| SIFT_BASELINE | 11 | 6 | 1.05 | 25.4 | 9 | 0.49 |
| SIFT_GRID_BALANCED | 11 | 6 | 0.91 | 27.7 | 9 | 0.49 |
| **GFTT_LK_LOCAL** | **17** | **7** | **0.92** | **3.5** | **6** | 0.50 |

## 3. 困难案例（不特判，仅报告）
- 1641：仅 GFTT_LK 在 pair3 VALIDATED（其余全 INSUFFICIENT）——描述子匹配不足，LK 岛台内追踪可救 1/4。
- 10000：AKAZE 3/4、CLAHE 4/4、SIFT 2/4、GFTT 3/4 → CLAHE 改善明显。
- 2543：AKAZE 仅 1/4；**GFTT_LK 3/4 VALIDATED**（1.202/1.717->2.232/2.232->2.918）——LK 显著修复该 case。
- 21674：SIFT pair1、AKAZE pair4 各 1 VALIDATED；GFTT 全 insufficient（视角/纹理变化大）→ 仍最难。

## 4. 判定（预置规则，未临时改）
- 最佳 = GFTT_LK_LOCAL：17/36（47%）、case coverage 7/9、heavy-tail 6（最低）、P90 3.5（最低）。
- **improvement class = NO_MEANINGFUL_IMPROVEMENT**（17 < 18 的 MODERATE 门槛；按 §11 预置规则执行）。
- 状态 = **LOCAL_ANCHOR_FEATURE_BAKEOFF_FAILED**（未到 MODERATE/STRONG → 不冻结 CAM01_LOCAL_ANCHOR_CANDIDATE_V1）。
- 诚实补充：GFTT 相对 AKAZE baseline 是**方向性最优**（+4 validated、+2 case、heavy 13→6、P90 12.5→3.5），仅差 1 对到 MODERATE；但不按"差一点"破例。

## 5. NEG target control（最佳方法 GFTT 下统计）
- 具备 validated anchor + 两端真实 target ROI 的 NEG case：**2 个（1641×1 对、2543×1 对）** → NEG_TARGET_CONTROL = PARTIAL（较 R1 的 0 有改善；仍不足以做 separation）。不设 EXTEND threshold。

## 6. 结论与下一步建议（不自动开始）
- 特征源不是唯一瓶颈：5 种方法 11–17/36，均未过半 → 换 detector 无法单点解决。
- 组合信号：GFTT_LK 在难例（2543/1641）有效、CLAHE 在 10000 有效、SIFT 在 21674 有效 →
  提示瓶颈在**anchor region 纹理与跨帧变化**，非单一特征。
- 建议下一阶段候选（等指令）：Anchor Region 界定（岛台局部子区域/自动鲁棒区域）或物体级表征；不得在本轮结果上自行开始。

## 产物
reports/storage/TREECUT_CAM01_V23_METHOD_CONFIG.json · _METHOD_MATRIX.json · _SPATIAL_VALIDATION.json ·
_CASE_DIAGNOSTIC.json · _WINNER.json · scripts/posta3_cam01_v23.py
