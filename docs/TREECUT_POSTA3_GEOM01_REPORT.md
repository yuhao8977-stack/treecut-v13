# POST-A3 GEOM01 Report（bbox 绝对面积 ≠ EXTEND/RETRACT）

- 日期：2026-09-06 · 阶段：CALIBRATION INFRA（合成证明 + 新方法实现；真实媒体待人工 ROI）· A3 永为 HISTORICAL_BLIND_V1

## 1. A3 暴露（不可变历史）
- 冻结 ca34678 `build_geometry_direction_evidence()` 的 robust 判定核心 = 目标 bbox **绝对面积 abs_seq**：
  bbox 变大→EXTEND、变小→RETRACT。
- A3 原始几何通道（相机闸解除假设下）：H002/H006（真 EXTEND）判 RETRACT-down；H001/H003（真 NO_EXTEND）判
  EXTEND-up；仅 H004（EXTEND 方向对）、H005（STATIC 对）。
- 结论：非阈值可修，是**特征定义错误**：镜头角度/跟拍/透视/框变化都会让 bbox 面积失真。

## 2. 新法：RELATIVE_ANCHOR_V1（scripts/posta3_geometry_lab.py）
- 用 `ISLAND_BODY` 归一化：left_off/right_off/top/bottom_off（(目标边−岛台边)/岛台宽高）、span_w/span_h。
- 机器推导 `dominant_extension_axis`（LEFT/RIGHT/UP/DOWN/UNKNOWN）：远侧边缘净位移最大 + 对侧锚边稳定。
- 判定（EXTEND 优先证据）：ANCHOR_EDGE_STABLE + FAR_EDGE_OUTWARD_PROGRESS + SPAN_INCREASE；
  RETRACT：FAR_EDGE_INWARD_PROGRESS + SPAN_DECREASE；STATIC：锚边/远侧振荡无净进展。
- 禁止 area↑→EXTEND / area↓→RETRACT（面积仅辅助）。

## 3. 合成场景验证（6/6 tests pass；tests/test_posta3_geometry_lab.py）
| 场景 | OLD_ABS_AREA | NEW_RELATIVE_ANCHOR | 说明 |
|---|---|---|---|
| extend_right | EXTEND | EXTEND (RIGHT) | 真拉出 |
| retract_right | RETRACT | RETRACT (RIGHT) | 真收回 |
| perspective_grow_static | **EXTEND（错）** | STATIC | 纯推近：相对锚点不变 |
| perspective_shrink_static | **RETRACT（错）** | STATIC | 纯拉远 |
| static | STATIC | STATIC | 静止 |
- 结果**精确复现并修复 GEOM01**：旧法被透视缩放骗，新法免疫。

## 4. Gate 状态
- 合成 infra：READY（6/6）。
- 真实 gate（≥4 EXTEND 中方向正确 ≥3/4；NO_EXTEND False EXTEND=0；且优于 OLD）→ **待 calibration 人工
  ACTION GT + 第二轮人工 ROI 后执行**。现状态：GEOM01_INFRA_READY_NEEDS_REAL_DATA。

## 5. 配套
- ROI 语义契约：docs/TREECUT_EXTEND_ROI_SEMANTIC_CONTRACT_V1.md（TABLETOP/EXTENSION_TABLETOP/ISLAND_BODY 定义；
  动件/固定件分离，防混叠污染锚点；H001 部分不可见教训已写入）。

## 证据路径
scripts/posta3_geometry_lab.py · tests/test_posta3_geometry_lab.py ·
reports/storage/TREECUT_POSTA3_GEOMETRY_CALIBRATION_V1.json
