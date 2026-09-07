# POST-A3 CAM01 V2.4 R1 — 共识真 clique 确定性修正报告

- 日期：2026-09-07 · main @ 3b8b27d → 本次提交
- 只修 V2.4 共识实现/口径；不重跑 detector；不调阈值；不碰 A3/ROI/GT

## 1. 修正
- 登记 `CAM01_V24_DEFECT_STAR_CLUSTER_01`：旧 cluster = "以某方法为中心收拢 ≤3px 方法"（星形，非 pairwise clique）。
- 改为**真 pairwise clique**：agreement edge = 固定 island grid 上 median transform disagreement ≤3.0px；
  穷举最大 clique（≤5 方法）；多同 size 按预置规则（成员 pooled median 最大→P90 最大→成员名 lexicographic）。
- 代表：clique 内 pooled median 最低 → P90 → 固定 TIE_ORDER（GFTT 优先）。全程不用动作 GT。

## 2. 受影响 pairs（代码重算，非硬编码）
| case | pair | old cluster | true clique | removed | rep before/after |
|---|---|---|---|---|---|
| 12095 | 5.191->7.416 | AKAZE, AKAZE_CLAHE, GFTT | AKAZE, GFTT | AKAZE_CLAHE | GFTT / GFTT（不变） |
| 25894 | 3.112->4.07 | AKAZE, AKAZE_CLAHE, GFTT | AKAZE, AKAZE_CLAHE | GFTT | AKAZE_CLAHE / AKAZE_CLAHE（不变） |
- 两例均存在真 2-method clique → **consensus 数量不变**（CONSENSUS_COUNT_UNCHANGED），代表亦不变。

## 3. 修后计数（36 island-present）
TRUE_MULTI_METHOD_CONSENSUS = **12** · SINGLE = 6 · CONFLICT = 4 · NO_VALID_ANCHOR = 14
oracle union = 22（8/9 cases）· consensus case coverage = 6/9

## 4. 指标分口径（不再混合）
| 集合 | pooled median px | pooled P90 px | representative 分布 |
|---|---|---|---|
| **MULTI_CONSENSUS_ONLY** | **0.538** | **2.819** | GFTT 8 · SIFT 2 · SIFT_GRID 1 · AKAZE_CLAHE 1 |
| SINGLE_SOURCE_ONLY | 1.895 | 13.417 | GFTT 3 · AKAZE 2 · AKAZE_CLAHE 1 |
- 说明：V2.4 报告 "0.92/3.46" 为混合口径（含 6 个 single-source，其噪声抬高了值）；纯 consensus 实际更稳（0.54/2.82）。

## 5. NEG target control（严格 t0/t1 contract，按新状态）
- TRUE_MULTI_METHOD_CONSENSUS：**0 case**
- SINGLE_SOURCE：**2 case**（1641 2.642->3.434 · 2543 1.202->1.717）

## 6. 判定
- **CAM01 V2.4 R1 status = CONSENSUS_PARTIAL**（沿用 V2.4 预置规则；12 < 18，不因"只差"破例）。
- candidate = **null · candidate_frozen = false**（仅保留 diagnostic_recipe 字段）。
- **NEXT_BLOCKER = ANCHOR_REGION_OR_OBJECT_REPRESENTATION**（正式确认；union 22 ≫ 单法但严格共识 12 → 不再换 detector）。

## 产物
reports/storage/TREECUT_CAM01_V24R1_METHOD_CORRECTION.json · _TRUE_CLIQUE_CONSENSUS.json ·
_METRICS_SEPARATED.json · _NEG_TARGET_CONTROL.json · _CANDIDATE.json · scripts/posta3_cam01_v24r1.py
