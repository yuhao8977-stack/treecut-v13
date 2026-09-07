# TREECUT CAM01 — LOCAL / GLOBAL / UNSURE Evidence Hierarchy V1（架构草案）

- 状态：**架构提案，未实现**（overnight audit §28 输出；不开发代码）
- 依据：CAM01 锚点路线全链数据（feature 12/36 · GFTT 17/36 · V25/26 patch 0/7/7 ·
  STRUCT01 0 · OBJ01 0 · DENSE01 0 · DENSE01R1 0；本 overnight audit 独立 replay 确认）
- 原则：**fail closed**；允许 UNSURE；绝不为 coverage 把 UNKNOWN 变 PASS。

## 1. 为什么需要层级（本 audit 证据）

DENSE01R1 独立 replay 显示：1434/2571 LK accepted（56%），但 0/36 通过 3/8px holdout。
分层证据：
- DINO semantic MNN：34/36 pair 有 ≥12 对应（召回好）——**语义级证据可靠**；
- LK pixel refine：median 4.0px（接近 3px 门）但 P90 37px、FB P90 45px——**像素级尾部不可靠**；
- 结构 chamfer diagnostic：median 2.9px 但 P90 64px——**几何残差与结构错位同源**；
- 单条证据链在"真值层级"上不足，但不同层（语义/像素/结构/时间）各有强项。

结论：**单一端点锚点不可判定运动；须按证据层级融合并显式声明不确定性。**

## 2. 层级定义

### L2_STRONG_LOCAL（强局部证据）
条件（全部满足）：
- DINO valid-MNN ≥ 12 且空间覆盖 bins≥4 / quads≥2（用 **accepted refined** 子集，非全量 MNN——§17 修正点）；
- LK accepted ≥ 8 且 accepted 子集 FB median ≤ 3px、FB P90 ≤ 8px（**补上正式代码缺失的 FB 门**）；
- AFFINE 或 HOM 2-fold holdout：两 fold 均 inlier≥0.45、median≤3px、P90≤8px；
- representative 模型分歧（若双模型）≤3px。
→ 可输出局部刚性运动估计（affine/homography），置信高。

### L1_GLOBAL_CAMERA（全局相机 fallback）
条件：ISLAND_BODY bbox/尺寸在 t0→t1 变化小（中心位移 < 阈值、面积比 ≈1）且
局部证据不足 → 用全局相机估计（背景 warp）作为运动代理。
局限：只覆盖 camera translation/zoom；不能解释岛台自身部件相对运动。
（G1 生产管线已有 camera channel；此处仅作为 fallback 而非主判据。）

### L0_UNSURE（明确不确定）
条件：以上都不满足，或不同层证据冲突（语义说 move、全局说 static 等）。
→ 输出 UNSURE（沿用 A3 的 CAMERA_UNRELIABLE_* / UNSURE 语义），**不算 PASS/FAIL**。

## 3. 判定表（v1 草案）

| 局部证据 | 全局相机 | 冲突 | 输出 |
|---|---|---|---|
| STRONG（3/8 gate 过） | 任意 | 无 | 用局部运动（+相机参考校正） |
| STRONG | 任意 | 有（分歧>阈值） | UNSURE（不能消歧则 fail closed） |
| 部分（MNN ok 但 pixel/结构不足） | 一致支持 | 无 | 尝试 L1，标注 LOW_CONF |
| 部分 | — | — | UNSURE |
| 无 | 一致 | 无 | L1 结果（camera-only），标注代理 |
| 无 | 无/冲突 | — | UNSURE |

- **fail-closed 规则**：UNSURE 是合法终态；下游不得把 UNSURE 解释为 PASS/NEG。
- **不做**：不 tune 阈值以增加 coverage；不因某 case 表现好而放松别 case。

## 4. 证据输入（均为现有真实能力）
- DINO semantic evidence：DENSE01R1 已验证（MNN 34/36 覆盖，召回好）；
- GFTT whole-island：历史 17/36（能追踪纹理点）；
- V24 feature consensus：历史 12/36；
- global camera：production mmv_camera_diag（estimate_camera_background）；
- structural chamfer（audit-only 已建）：结构残差作为**校验/否决通道**（若 transform
  后结构边 chamfer P90 大 → 即便几何 gate 过也降级，因几何与结构错位同源）。

## 5. 预期价值与风险
- 价值：不再要求"单个 3/8px 锚点全对"，而是分层表决 + 显式 UNSURE；
  语义 MNN 召回（34/36）可支撑 LOCAL/GLOBAL 分层，覆盖显著高于 0/36 锚点。
- 风险：层级权重/冲突阈值仍需标定（新 calibration 数据，非 A3）；UNSURE 率可能高，
  但符合 fail-closed 契约（宁 UNSURE 不误报）。
- 后续校准建议（仅提案）：以 CALIBRATION10 的 POS/NEG 之外的扩展集做层级门标定，
  冻结后再 shadow 评估；不读 A3。

## 6. 与 Temporal Learned Tracker 的关系
若走 TEMPORAL_LEARNED_TRACKER（TAPIR/SEA-RAFT 等 Apache/MIT/BSD 候选，§27 调研），
其输出是 **temporal dense correspondence**，可充当 L2 的更强局部证据源（中间帧约束），
但许可与算力成本更高；Evidence Hierarchy 是**无需新模型**的先行方案。
推荐先按 §30 决策。
