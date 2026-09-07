# POST-A3 CAM01 V2.1 — Validity Closure + Local Island Anchor 报告

- 日期：2026-09-07 · main @ f85b363 → 本次提交
- 未改任何既有 threshold；未碰 A3；未造叶板 ROI；不输出动作判定

## 第一屏（§18）
1. **旧 V2 bridge endpoint 未走到 t1**：40 语义对 × 3 步长 = **120 处** endpoint_gap≠0（如 3.106→7.246 在 500ms 步长下旧表末点 7.106，漏约 140ms）→ 登记 `BRIDGE_ENDPOINT_NOT_CLOSED`。
2. **旧 V2 中间段无 Human ROI**：bridge 中间时间点不在人工 5 语义帧上；按步长累计中间段 = 500ms:144 段 / 250ms:260 段 / 125ms:502 段，**带人工框掩码的中间段 = 0**。旧报告"ROI-aware"表述不实 → 修正版用 `MASK_B`(端点非岛台框并集+8px margin) / `MASK_C`(同对象两端唯一→外包络走廊，否则回退 union) 并**如实声明**。
3. **旧 round-trip drift 非独立指标**：T∘T⁻¹ 代数自反 ≈0 无诊断意义 → `ROUNDTRIP_DRIFT_NOT_INDEPENDENT_METRIC`；修正版独立验证改用 AKAZE 背景区匹配（不参与拟合）+RANSAC inlier 支撑 + 逆变换残差 + 背景边缘差第二通道。
4. **修正后全局相机可靠率（40 对，AKAZE 独立验证）**：
   | 方法 | reliable % |
   |---|---|
   | SPARSE_MASK_A(不排除) | 27.5 |
   | SPARSE_MASK_B | 40.0 |
   | SPARSE_MASK_C | 40.0 |
   | BRIDGE_500_MASK_B | 37.5 |
   | BRIDGE_250_MASK_B | 40.0 |
   | BRIDGE_125_MASK_B | 40.0 |
   | BRIDGE_250_MASK_C | 40.0 |
5. **bridge 结论是否改变**：**是**。修正时间链+掩码+独立验证后，bridge 与 sparse 基本持平（37.5–40% vs 40%），
   旧 V2"bridge 更差/假设被削弱"**部分为方法伪影**；但仍全部 <80%，全局相机在本素材上**仅 PARTIAL**，bridge 亦无优势。
6. **LOCAL_ISLAND_ANCHOR（36 对有岛台记录；岛台两端存在者 29/36 可估计）**：
   - 可用对 eligible：29/40（72.5% coverage；2212 无岛台 → 4 对不适用）
   - descriptor 模型全部 OK；**residual median 0.78px · P90 1.31px**（亚像素级，远优于全局 40%）
   - LK 对照：35 对有 track
7. **global vs local**：本素材上 **Local Island Anchor 明显更适合**（岛台可见时估计残差亚像素 vs 全局 40% 可靠）；
   支持未来证据层级 LOCAL_ANCHOR → GLOBAL_CAMERA → UNSURE（本轮不融合）。
8. **leaf ROI decision**：**LEAF_ROI_DEFERRED** —— Local Anchor 可靠，但"粗 target ROI 经锚点归一后是否可辨 POS3 动作"
   尚需"锚点补偿的目标像素/边缘运动"微步（target 相对几何增量不具区分度：POS3 max|right_off|=0.10 而 socket NEG 达 0.52，
   因 NEG 相机/注释使粗框相对岛台大幅漂移）→ 先跑该微步，暂不让你画叶板。

## 状态（§19）
**CAM01_V21_LOCAL_ANCHOR_PROMISING**（全局 partial 40%；局部锚点估计 promising 且高可靠；锚点补偿判别为下一步）

## 证据
reports/storage/TREECUT_CAM01_V21_METHOD_AUDIT.json · _CORRECTED_GLOBAL.json · _LOCAL_ISLAND_ANCHOR.json · _TARGET_RELATIVE_MOTION.json
scripts/posta3_cam01_v21.py
