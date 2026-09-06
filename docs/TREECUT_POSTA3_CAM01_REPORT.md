# POST-A3 CAM01 Report（Camera 稀疏关键帧泛化失败）

- 日期：2026-09-06 · 阶段：CALIBRATION INFRA（PRELIMINARY，无 L3 ROI）· A3 永为 HISTORICAL_BLIND_V1

## 1. A3 暴露（不可变历史）
- 24 相邻帧对中 20 对 `CAMERA_MODEL_UNRELIABLE`（多为 `FORWARD_BACKWARD_TRACKS_UNSTABLE` /
  `NO_RELIABLE_CAMERA_MODEL`）→ 冻结 validator 相机闸 fail-safe → 6/6 UNSURE、0 FP。
- 推断根因：A3 每窗口仅 5 冻结帧，相邻帧间隔约 1–1.6s，LK 直接追踪稀疏帧在人物移动/手持/近景下不稳定。
  （这不等于连续视频 Camera 无解——见 bridge 假设。）

## 2. 假设（架构师 2026-09-06）
> 语义判定仍看冻结关键帧；Camera 可在关键帧之间用连续"桥接帧"估计，把多个小位移组合。

## 3. 本轮 infra + preliminary 结果（TREECUT_POSTA3_CAMERA_CALIBRATION_V1.json）
- 方法：SPARSE_DIRECT（关键帧→关键帧）/ FULL_FRAME_DIRECT（全帧 RANSAC）/
  BRIDGE_500 / BRIDGE_250 / BRIDGE_125（分段估计、逐段 ok 统计）。
- 样本：6 个非 A3 候选（EXTEND×3 / RETRACT×1 / STATIC×1 / LEG 干扰×1），中段语义对 (0.35d,0.65d)；
  **无 L3 ROI 阶段 boxes=[] 全背景采样**（诚实标注）。
- Reliability rates（分段全部可建模 / 对总数）：
  | 方法 | 率 |
  |---|---|
  | SPARSE_DIRECT | 0.0 |
  | FULL_FRAME_DIRECT | 0.0 |
  | BRIDGE_500 | 0.20 |
  | BRIDGE_250 | 0.167 |
  | BRIDGE_125 | 0.333 |
- 观察：bridge 在个别样本（3571，gap≈3.7s）500/250ms 全段可建模而直接法失败 → **bridge 方向有初步支持**；
  但整体率远低于 80% 门 → **CAM01_NEEDS_REDESIGN（确认）**。

## 4. 局限（勿过度解读）
- 无 ROI 排除 → 背景掩码=全背景；人物/手近景污染仍可能影响。
- BRIDGE 本版仅统计"逐段可建模"，尚未实现矩阵 compose + 累计漂移（composition_supported=False）。
- 只取中段单语义对；未覆盖多点/不同运动类型。

## 5. 下一步（gate 前不融合）
1. calibration 人工 ACTION GT（26 候选 → 12 入选）→ 第二轮人工 ROI（按 ROI 语义契约）。
2. 带 ROI 排除后重跑 CAM lab；实现 3×3 compose + 漂移记录；增加多语义对。
3. 门：≥80% semantic-frame pairs 可靠且 bridge 明显优于 SPARSE_DIRECT，否则 CAM01_NEEDS_REDESIGN 持续。
4. 不得用动作正确性评价 camera（§8）。

## 证据路径
scripts/posta3_camera_bridge_lab.py · reports/storage/TREECUT_POSTA3_CAMERA_CALIBRATION_V1.json
