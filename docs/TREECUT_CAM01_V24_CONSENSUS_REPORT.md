# POST-A3 CAM01 V2.4 — Multi-method Consensus + V2.3 报告修正

- 日期：2026-09-07 · main @ 09e3b5b → 本次提交
- 未调参/未碰 A3/未造叶板/方法选择与共识不用动作 GT

## 1. V2.3 报告修正（依真实 METHOD_MATRIX）
- state 汇总不再把 INSUFFICIENT 归 UNKNOWN（每 method 用 pair_state 优先、state 兜底）。
- CASE 统计按本 case 4 pairs 真实状态。
- 困难案例真实状态（修正后）：
  - **10000：0/4 VALIDATED**（全部 NO_VALID_ANCHOR；NOT_VALIDATED×3 + INSUFFICIENT×1）——V2.3 报告"CLAHE 4/4"错误，作废。
  - **2543：GFTT = 1 VALIDATED + 2 PARTIAL + 1 INSUFFICIENT**（非 3/4 VALIDATED）。
  - **21674：SIFT+SIFT_GRID 在 pair1 双 VALIDATED（→共识）；AKAZE 无 VALIDATED**。
  - **1641：GFTT 1/4 VALIDATED**（此条原报告正确）。
- P90 命名修正：不再用 median(per-fold P90)；改 pooled holdout（真残差数组）→ 见 consensus pooled 指标。
- NEG target control 严格化：要求 anchor VALIDATED 且 target_t0/target_t1 均合法（EXTENSION_TABLETOP→TABLETOP contract）。

## 2. Union / Consensus（36 island-present pairs，5 方法冻结参数）
| 项 | 值 |
|---|---|
| ORACLE_UNION validated | **22/36**（61.1%，架构师预估 ✓） |
| union case coverage | **8/9** |
| MULTI_METHOD_CONSENSUS | **12/36**（6/9 cases） |
| SINGLE_METHOD_VALIDATED | 6 |
| METHOD_CONFLICT | 4 |
| NO_VALID_ANCHOR | 14 |
| consensus pooled holdout median / P90 | **0.92 / 3.46 px**（representative 法） |
| transform disagreement median / P90 | **0.94 / 1.16 px**（共识对内方法高度一致） |
| representative 分布 | GFTT_LK 11 · SIFT 2 · AKAZE_CLAHE 2 · AKAZE_BASELINE 2 · SIFT_GRID 1 |

## 3. NEG target control（严格 contract）
- CONSENSUS_NEG_TARGET_CONTROL：**0 case**
- SINGLE_SOURCE_NEG_TARGET_CONTROL：**2 case**（1641 1 对 · 2543 1 对，均为 GFTT single-source）

## 4. 判定
- 状态：**CONSENSUS_PARTIAL**（union 22 明显 > 单法 17，但 consensus 仅 12，未高于 AKAZE baseline 13；冲突 4 不致命但存在；case 覆盖 6/9 未到 7/9）。
- Candidate：**未冻结**（仅 PROMISING 才冻结 ensemble candidate；PARTIAL 不冻结）。
- 按 §15 解释：**union≫单法 但 consensus 不足 → 下一 blocker = ANCHOR_REGION / OBJECT REPRESENTATION**
  （下一轮转 anchor 子区域/区域级配准/更稳定固定结构参照，不再无限换 detector）。
- 保留正式解释：V2.3 单特征失败成立（GFTT 17/36 NO_MEANINGFUL_IMPROVEMENT 不变）。

## 产物
reports/storage/TREECUT_CAM01_V24_V23_CORRECTIONS.json(见下注) · _METHOD_UNION.json · _TRANSFORM_CONSENSUS.json ·
_CASE_MATRIX.json · _NEG_TARGET_CONTROL.json · _CANDIDATE.json · scripts/posta3_cam01_v24.py
注：V2.3 修正记录并入本报告 §1（未单独 json；METHOD_MATRIX 为真实源）。
