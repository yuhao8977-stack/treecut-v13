# POST-A3 CAM01 DENSE01 R1 — DINOv2 密集语义锚点·缺陷修正审计版报告（FAIL_DENSE）

- 日期：2026-09-07 · main @ 71999fd → 本次提交
- 模型：dinov2_vits14_reg（facebookresearch/dinov2 hub，**Apache-2.0**；G 盘缓存）
- CUDA 运行；不读 A3；不用动作 GT；无特判；无阈值后调
- 契约同 DENSE01：CALIBRATION10 36 对 island-present（含岛对）· 5-frame 均匀采样不变

## 0. 本轮性质
R1 = 按架构师 DENSE01_IMPLEMENTATION_FAIL 审计逐项修正后的**干净重跑**。8 项缺陷全部
登记 fixed（TREECUT_CAM01_DENSE01R1_DEFECT_AUDIT.json，DENSE01_IMPLEMENTATION_FAIL=True），
实现语义经单测与实证核对。随后发现并修正一处**测试自身断言错误**（非实现缺陷，见 §3），
5/5 单测通过；下述 R1 数据为干净版本最终结果。

## 1. 缺陷修正清单（8/8 → fixed）
| # | DENSE01 缺陷 | R1 实现 |
|---|---|---|
| 1 | 灰度复制输入 | crop→BGR→**COLOR_BGR2RGB**（值保持重排）→RGB 张量 |
| 2 | 无 ImageNet 归一化 | MEAN [0.485,0.456,0.406] / STD [0.229,0.224,0.225]，逐真通道（实证：R=192→ch0 用 R 统计量） |
| 3 | padding token 未排除 | letterbox 518²（37×37 patch）+ content-valid mask（token 全含在内容内才有效） |
| 4 | MNN 在域外计算 | valid-domain MNN：仅 valid token 参与 NN/reciprocity |
| 5 | 温度在加权均值中抵消 | softmax subtoken refine（T=1.0，相对峰值指数，3×3 邻域）保留 |
| 6 | RANSAC stride 方向错 | raw RANSAC thr = max(PATCH/scale0, PATCH/scale1)（单测覆盖） |
| 7 | 无真分歧判定 | aff&hom 双 validated → hull 分歧 ≤3px = CONSENSUS，>3px = CONFLICT |
| 8 | 结构通道占位 | support-hull 结构通道随 final anchor 后补（**非本轮 gate，仍占位**，见 STRUCTURAL_VALIDATION.json） |

单测：RGB 通道保持/归一化数学 · padding 排除 · 无效 token 不能赢得 MNN · raw stride ·
true pooled 指标 = 5/5 PASS。

## 2. 主结果（36 pairs）
| 指标 | DENSE01 v1 | **DENSE01 R1（干净）** |
|---|---|---|
| old MNN sufficient /36 | 36 | 36 |
| corrected（valid-domain）MNN /36 | —（未实现） | **34** |
| LK attempted | — | 2571 |
| LK accepted | — | **1434**（56%） |
| DINO_ONLY AFFINE/HOM validated | 0/0 | 0 / 0 |
| DINO_LK AFFINE / HOMOGRAPHY validated | 0 / 0 | **0 / 0** |
| MULTI / SINGLE / CONFLICT | 0/0/0 | **0 / 0 / 0** |
| NO | 36 | **36** |
| dense union /36 | 0 | **0** |
| case coverage /9 | 0 | 0 |
| pooled holdout median/P90/P95 | null | null（无 validated） |

state 分解：DENSE_NO_ANCHOR=31 · DENSE_SUPPORT_TOO_LOCALIZED=3（bins<4 或 quads<2）·
DENSE_MATCH_INSUFFICIENT=2（valid MNN<12）。**无一对经 LK 像素细化后通过确定性
spatial 2-fold holdout（inlier≥0.45，median≤3px，P90≤8px）。**

对照：本轮早期"RGB 通道错位归一化"版本曾报 AFFINE=1/HOM=1/CONFLICT=1——该伪成功
正是缺陷 #1/#2 的产物；干净版本 0 validated，判据更严格，**union 结论不变（=0）**。

## 3. 测试断言修正记录（实现无改动）
test_rgb_channels_preserved_and_normalized 初版按 "COLOR_BGR2RGB ⇒ R←B(64)" 误解断言，
与 cv2 实际"值保持通道重排（BGR(64,128,192)→RGB 数组 [192,128,64]，R 值 192 仍在 R 槽
用 R 统计量）"相反，导致 1/5 失败。已修正测试预期（通道索引与统计量对齐真语义），
代码实现自始正确——**R1 干净重跑数据不受该测试缺陷影响**（运行路径 prep_rgb 与实证一致）。

## 4. 困难案例（MNN 全足够，模型验证未过）
1641 / 10000 / 2543 / 21674：valid MNN ≥12 无问题，瓶颈在端点像素精度与支撑分布，
非召回。（2543 = extend-bucket 无动作 NEG 亦在 NO_ANCHOR 列，未见伪 positive 锚点。）

## 5. NEG target control
MULTI 0 · SINGLE 0（真实 contract；无 validated anchor ⇒ 无泄漏）。

## 6. 判定（架构师预置门槛，未后调）
- union 0 < 17 → **FAIL_DENSE** → **DENSE_ENDPOINT_ROUTE_CLOSED = TRUE**。
- SEMANTIC_RECALL_ESTABLISHED = False（34/36 ≠ 36）；RAW_REFINEMENT_REQUIRED = False。
- 按预置规则：**不做 DINO-B/L、不调 similarity/threshold/更多 RANSAC；不开 GEOM；STOP**。
- NEXT_BLOCKER（不自动开始）：**TEMPORAL_LEARNED_TRACKER**（利用中间帧；注意 CoTracker3
  CC-BY-NC 不合规，需 Apache-2.0 实现如 DINOv2-flow/RAFT 系）或
  **EVIDENCE_HIERARCHY_REDESIGN（LOCAL/GLOBAL/UNSURE 三层）**。

## 7. 全链 Anchor 汇总（对照，同数据 36 对）
feature 12/36 · GFTT 17/36 · patch(V25/V26/V26R1) 0/7/7 · STRUCT01 0/36 · OBJ01 0/36 ·
DENSE01 v1 0/36 · **DENSE01 R1 0/36**（34/36 valid-MNN 全覆盖但 holdout 0 —— 语义
端点召回足够、像素级对应精度与支撑结构不足，低层几何/语义锚点路线合流收敛于 0）。

## 产物
reports/storage/TREECUT_CAM01_DENSE01R1_{CONFIG,DEFECT_AUDIT,PREPROCESS_AUDIT,
VALID_TOKEN_AUDIT,MATCH_MATRIX,LK_REFINEMENT,HOLDOUT_VALIDATION,STRUCTURAL_VALIDATION,
CONSENSUS,NEG_TARGET_CONTROL,RESULT,CANDIDATE}.json · _GALLERY.html ·
scripts/posta3_cam01_dense01r1.py · tests/test_cam01_dense01r1.py
