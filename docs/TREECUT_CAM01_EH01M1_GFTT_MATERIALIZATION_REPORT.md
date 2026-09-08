# TREECUT CAM01 EH01 M1 — V23 GFTT Exact Replay + Transform Materialization 报告

- 基线：main @ `4aec680`（工作树 clean）
- 性质：V23 GFTT_LK_LOCAL **exact replay** + **transform materialization** + 独立 structural
  diagnostic + router impact shadow。不进入 EH02；不做 global materialization；无 GEOM/tracker/
  新模型/新 threshold/改历史 gate；无动作 verdict；不自动升级 router strong。
- 权威真值：`TREECUT_CAM01_V23_METHOD_MATRIX.json`（commit `09e3b5b`，blob `98e74be9…`）；
  **不用 V23 REPORT.md 困难案例文字**（stale）。

## 0. 结论速览
- **V23 METHOD_MATRIX used as truth: YES**；stale report mismatch recorded: YES
- historical GFTT validated **17/36** · replay GFTT validated **17/36**
- pair-state fingerprint match **36/36** · fold-state fingerprint match **YES**
- **GFTT_TRANSFORM_MATERIALIZATION_COMPLETE = YES**（17/17 historical validated 全 materialized，
  17/17 deterministic rebuild）
- **7 个当前 no-transform GFTT routes 全部 materialized**
- GFTT↔V24 agreement：**9 agree / 1 conflict / 7 not-comparable**
- GFTT↔DENSE agreement：**3 agree / 2 conflict / 12 not-comparable**
- structural（GFTT materialized 17）：**7 CONSISTENT / 10 DISAGREEMENT / 0 UNKNOWN**
- POS materialized target-valid **8** · NEG materialized target-valid **2**
- **NEG_STRONG_REFERENCE_TARGET_VALID = 0**（materialized ≠ strong；等 EH02）
- NEXT_BLOCKER：**EH02_ROUTER_CALIBRATION**

## 1. Source of truth & stale note（§1/§24）
- METHOD_MATRIX 为权威真值。代码重算 historical GFTT：
  - 1641：1/4 VALIDATED（2.642→3.434）· 2543：1 VALIDATED（1.202→1.717）+ 2 PARTIAL ·
    10000：0 VALIDATED · 21674：0 VALIDATED（全部 0.792/1.849/3.434 等 INSUFFICIENT）
- V23 REPORT.md 存在 stale summary（如旧困难案例描述），已记录于
  `TREECUT_CAM01_EH01M1_V23_STALE_REPORT_NOTE.json`；**未修改历史 REPORT.md**。
- 归一说明：历史 tracks<12 → `state:INSUFFICIENT`（无 pair_state）与 replay
  tracks<12 → LOCAL_ANCHOR_INSUFFICIENT 语义等价；fingerprint 比较已归一。

## 2. Exact replay（§2-§7）
冻结 V23 参数（EH01M1_CONFIG.json，config_sha256 记录）：analysis_width_max=960、grid_cell=40、
ransac_thr=3.0、fit_inlier_min=0.45、holdout_min=8、median≤3.0、GFTT 300/0.02/6/block7、
LK win21/max3、FB≤3。ISLAND_BODY 允许区、其它 L3 ROI 排除（V23 island_mask 语义）；
width>960 resize；相同 semantic timestamps；backward LK init=None（V23 exact 无 initial flow）。
2-fold floor(x/40)+floor(y/40)%2，fit0→val1 / fit1→val0，fit_n≥6/holdout_n≥8，
estimateAffinePartial2D RANSAC 3.0，inlier≥0.45，median≤3.0。

## 3. Fingerprint gate（§8-§9）
- pair-state fingerprint：**36/36 exact match**
- fold-state fingerprint：**全部 match**
- replay_verified = YES（gate_passed）。17 validated 与 historical 一致（未硬编码，代码重算）。

## 4. Materialization（§10-§13）
- 仅 historical+replay 双 VALIDATED 的 pair materialize（其余 matrix=null，禁 PARTIAL/
  NOT_VALIDATED/INSUFFICIENT 强行生成）。
- 命名 **DERIVED_V23_GFTT_REFERENCE_TRANSFORM**（非历史原始 matrix）。
- 方法：完整 FB≤3 accepted P0/P1 + estimateAffinePartial2D RANSAC thr=3.0（不改 homography/
  translation/不同 threshold）。
- **17/17 materialized**；每对同 seed 重建两次，ISLAND_BODY grid prediction disagreement
  median < 1e-6 → **17/17 deterministic**。记录 n_accepted / fit-all inlier / matrix /
  translation / scale / rotation / historical+replay fold metrics / source commit+blob。

## 5. Router impact shadow（§15）
读 EH01R1 router：7 个 GFTT no-transform routes（EVIDENCE_ONLY_NO_TRANSFORM 3 +
GLOBAL_FALLBACK_CANDIDATE_STATE_ONLY 4）= 12095 2.225→5.191 · 1641 2.642→3.434 ·
2543 1.202→1.717 · 25894 2.394→3.112 · 9697 2.885→4.121 / 4.121→5.357 / 5.357→7.005，
**materialize 后 7/7 全部拥有 matrix**。其余 10 个 GFTT validated 已被 V24/DENSE 覆盖或属
conflict/其它。只 shadow，未修改 EH01R1 router。

## 6. Local agreement（§16）
fixed ISLAND_BODY grid，median≤3=AGREE：
- **GFTT↔V24**：9 agree / 1 conflict（12095 5.191→7.416，既有 DENSE conflict 同源）/
  7 not-comparable
- **GFTT↔DENSE**：3 agree / 2 conflict（12095 5.191→7.416、25894 3.112→4.07）/
  12 not-comparable
- evidence_family 保留 FEATURE_LOCAL（GFTT/V24 同族，不作 independent corroboration）。

## 7. Structural diagnostic（§17-§19）
每 GFTT materialized pair：t0/t1 convex hull（GFTT accepted p0/p1）+ 14px margin + clip
ISLAND_BODY + 排除其它 L3 ROI；结构边 Canny+动态排除；symmetric forward/reverse chamfer
（OBJ01 corrected edge=0 DT raw Euclidean）。label：symP90≤12 CONSISTENT / >12 DISAGREEMENT /
无有效 UNKNOWN。**17 pair：7 CONSISTENT / 10 DISAGREEMENT**。仍为 diagnostic，
不因结构直接升级 strong。

## 8. Target diagnostic（§20-§23，role-blind 后才读 role）
strict contract（EXTENSION_TABLETOP 优先唯一否则 TABLETOP 唯一）：
- **POS materialized 8 · target-valid 8**
- **NEG materialized 9 · target-valid 2**
- **NEG_MATERIALIZED_REFERENCE_TARGET_VALID = 2**（1641 2.642→3.434：materialized✓
  deterministic✓ structural=DISAGREEMENT；2543 1.202→1.717：materialized✓ deterministic✓
  structural=CONSISTENT）
- **NEG_STRONG_REFERENCE_TARGET_VALID = 0**（materialized ≠ strong；强度等级等 EH02；
  架构师 §22 语义严格执行）

## 9. Decision / next blocker（§25-§26）
- GFTT_REPLAY_VERIFIED = YES
- GFTT_TRANSFORM_MATERIALIZATION_COMPLETE = **YES**
- NEXT_BLOCKER = **EH02_ROUTER_CALIBRATION**（7/7 no-transform routes 已 materialize）
- 同时记录：GLOBAL_TRANSFORM_MATERIALIZATION_RECOMMENDED_AFTER_EH02_OR_AS_EH02_SUBTASK
  （4 个 global-fallback 对若需 source agreement 再处理）
- 无新 coverage gate；禁自动开始。

## 产物
reports/storage/：CONFIG · REPLAY_FINGERPRINT · GFTT_CORRESPONDENCES · GFTT_TRANSFORMS ·
LOCAL_AGREEMENT · STRUCTURAL_DIAGNOSTIC · ROUTER_IMPACT_SHADOW · TARGET_DIAGNOSTIC ·
V23_STALE_REPORT_NOTE · RESULT（10 JSON）。
docs/：本报告。scripts/eh01m1_gftt_materialize.py · eh01m1_agreement_impact.py ·
eh01m1_structural_target.py · eh01m1_result.py · eh01m1_v23_historical_ref.py（历史 ref 副本）。
tests/test_eh01m1_gftt.py。
