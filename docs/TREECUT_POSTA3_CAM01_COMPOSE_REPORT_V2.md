# POST-A3 CAM01 — ROI-Aware Bridge Camera Composition Report V2

- 日期：2026-09-07 · main @ f49d899 → 本次提交
- 数据：POSTA3_CALIBRATION10（10 案例 = 4 EXTEND + 6 NO_ACTION）· Human ROI 前景排除（统一规则：排除除 ISLAND_BODY 外全部人工框）
- 评价完全独立于动作 GT；未使用 A3 数据；未放宽阈值

## 第一屏（§16）
| 方法 | reliable % | pairs | median residual px | P90 residual | 说明 |
|---|---|---|---|---|---|
| SPARSE_DIRECT | **32.5** | 40 | 1.47 | 3.12 | 直接关键帧→关键帧 |
| FULL_FRAME_DIRECT | 25.0 | 40 | 1.15 | 3.19 | 诊断基线 |
| BRIDGE_500 | 25.0 | 24 | 3.32 | 12.6 | 真 compose |
| BRIDGE_250 | 17.5 | 40 | 3.53 | 10.4 | 真 compose |
| BRIDGE_125 | 20.0 | 40 | 6.23 | 50.1 | 真 compose（误差累积最重） |
- best method：SPARSE_DIRECT（32.5%）
- residual median/P90（sparse）：1.47 / 3.12 px
- drift：round-trip 位移按构造≈0（一致性自检通过，无独立误差信息）；真实累计质量用 补偿后背景对齐残差（上表 residual）衡量
- scene discontinuity：0
- top failure reasons：
  - SPARSE：NO_RELIABLE_CAMERA_MODEL ×17、FORWARD_BACKWARD_TRACKS_UNSTABLE ×6
  - BRIDGE_250：seg_fail=1 ×21、seg_fail=0(全段 ok 但组合后残差超标) ×12
  - BRIDGE_125：seg_fail=0 ×23（段全 ok 但组合残差中位 6.2 → **小段误差累积**）
- CAM01_STATUS：**CAM01_PARTIAL_NEEDS_REDESIGN**
  （最佳 32.5% < 80% 门；且 **bridge 并未优于 sparse** —— 真 compose 后小步长误差累积，桥接假设在本数据上被削弱）
- LEAF_ROI_DECISION：**LEAF_ROI_DEFERRED_CAMERA_BLOCKED**（相机本身不稳，先不让用户画叶板）

## 分析
1. 即便带 Human ROI 前景排除，40 语义对中仅约 20–33% 能形成可靠相机证据；主因仍是背景 track 不足/不稳
   （NO_RELIABLE_CAMERA_MODEL / FORWARD_BACKWARD_TRACKS_UNSTABLE）——近景手持+大量前景排除后可靠背景点太少。
2. Bridge 真组合未带来收益：BRIDGE_125 残差中位 6.2px、P90 50px，远差于 sparse 1.47px →
   **每小段误差在组合中累积**（与"小步更稳"假设相反，至少在当前估计器/排除规则下）。
3. 因此：Camera 通道在此校准集仍是上游 blocker；几何正例召回（GEOM01）依赖的"补偿后像素运动"暂不可用。
4. 不据此调任何阈值；不改 A3；不建叶板页；不融合。

## 产物
reports/storage/TREECUT_POSTA3_CAMERA_COMPOSE_V2.json · TREECUT_POSTA3_CAMERA_PAIR_MATRIX_V2.json ·
TREECUT_POSTA3_TARGET_MOTION_DIAGNOSTIC_V2.json（目标运动诊断仅记录 POS 可靠对 before 项，after 需可靠矩阵——因可靠对稀少，值有限，如实标注）
scripts/posta3_camera_compose_v2.py
