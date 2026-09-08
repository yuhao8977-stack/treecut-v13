# TREECUT CAM01 DENSE01 R2 — FROZEN INTENDED-SPEC CLOSURE 报告

- 基线：main @ `8cb7682`（PRE_RUN clean 记录于 `TREECUT_CAM01_DENSE01R2_PRE_RUN_GIT_STATUS.json`，先于一切 R2 artifact）
- 历史：DENSE01R1 production @ `08a6d28`（0/36）· overnight audit @ `8cb7682`（0/36 复现，但 FB gate 未实现 → INTENDED_SPEC_INCONCLUSIVE）
- 本轮：补全冻结规格中声明但未实现的 **true LK forward+backward FB≤3 gate**，并用 FB-filtered
  evidence set 重跑完整几何 pipeline。**未修改任何冻结参数**（DINO vits14_reg、RGB 归一化、
  letterbox、valid-MNN、top_k=256、T=1、LK win21/max3、RANSAC stride=max(14/s0,14/s1)、
  4×4 checkerboard、fit/holdout≥8、inlier≥0.45、median≤3/P90≤8、coverage bins≥4/quads≥2、
  模型分歧≤3px、STRONG/MODERATE/PARTIAL/FAIL 门槛）。不改 A3/GEOM/tracker/hierarchy。

## 0. 结论速览
- **true FB gate implemented：YES**
- **union = 8/36**（R1 forward-only 0/36 → R2 8/36），class **FAIL_DENSE**（8 < 17）
- **DENSE_ENDPOINT_ROUTE_CLOSED = TRUE**（完整冻结规格实现后仍失败，按架构师 §20 判词）
- FB gate 不是"只会更严格"：过滤错误对应 → RANSAC purity 大幅提升（pairs FB3≥8 = 24/36，
  validated folds 10 → 33），true pooled **median 0.995px / P90 2.75px** —— 达到历史从未达到的精度
- 但 8 < 17 → endpoint capability **NOT_ESTABLISHED**

## 1. OVERNIGHT_FINDING_01 正式登记（§1）
`08a6d28` production 声明 FB≤3（config fb_max=3.0、docstring）但无 backward gate；overnight
audit 只量化 1434 production accepted 中 1003 FB≤3，未用 FB-filtered correspondences 重跑
fold/RANSAC/holdout/pair verdict。"FB gate only makes result stricter so union stays 0" 不是
有效证明。R2 完成前 DENSE01R1 final capability = **INTENDED_SPEC_INCONCLUSIVE**。（R2 完成后
更新为本报告结论。）

## 2. 真 FB gate 实现（§3/§4/§5）
- FORWARD: t0 p0 → t1，init = DINO subtoken 预测，OPTFLOW_USE_INITIAL_FLOW。
- BACKWARD: forward p1 → t0，init = 原 p0，OPTFLOW_USE_INITIAL_FLOW。
- FB = ||p0_back − p0||。
- 正式 accepted（`lk_accept_verdict` 纯函数，单测覆盖）：fwd_ok AND bwd_ok AND FB≤3 AND
  p1 in ISLAND_BODY_t1 AND p1 not in dynamic_t1。
- **FB filter 在 fit 前**：只有 FINAL_ACCEPTED_FB3 进入 coverage / fold / RANSAC / holdout /
  consensus（同一 evidence set，无 all-MNN coverage + FB subset fit 混用）。
- fold 在 accepted_fb3 P0 上重算 4×4 checkerboard（不继承 full-MNN fold index）；
  每 pair 保存 fold0/fold1 ids，intersection=0 全通过（SPATIAL_COVERAGE.json）。

## 3. 主结果（§6/§17，36 pairs）
| 指标 | R1 forward-only | **R2 true FB3** |
|---|---|---|
| MNN sufficient /36 | 34 | **34** |
| LK attempted | 2571 | 2571 |
| fwd_ok | 1434 (accepted) | 1613 |
| bwd_ok | —（未实现） | 1522 |
| FB≤3 raw | — | 1060 |
| **FINAL_ACCEPTED_FB3** | 1434 | **1003** |
| pairs FB3≥8 /36 | 36 | **24** |
| AFFINE validated /36 | 0 | **7** |
| HOMOGRAPHY validated /36 | 0 | **7** |
| MULTI / SINGLE / CONFLICT / NO | 0/0/0/36 | **6 / 2 / 0 / 12** |
| union /36 | 0 | **8** |
| case coverage /9 | 0 | **4** |
| true pooled median / P90 / P95 | null | **0.995 / 2.752 / 4.162 px** |
| class | FAIL_DENSE | **FAIL_DENSE** |

- state 分解：DENSE_NO_ANCHOR 12 · LK_INSUFFICIENT_AFTER_FB 10 · SUPPORT_TOO_LOCALIZED 4 ·
  MATCH_INSUFFICIENT 2 · SINGLE 2 · MULTI 6。
- validated pairs（8）：3571 的 4 对（1.842→4.299 / 4.299→6.142 / 6.142→7.984 /
  7.984→10.441，均 MULTI）· 25894 的 2 对（0.718→1.676 / 3.112→4.07，MULTI）·
  12095 5.191→7.416（SINGLE）· 10000 0.768→1.793（SINGLE）。

## 4. failure taxonomy（§8，正式）
- **overnight 的 10 个 validated folds（forward-only 语义）在真 FB gate 后：retained 8 /
  lost 2 / new 25 → 共 33 validated folds**（详见 RESULT.fold_retention）。
  - lost 2：2543 2.232→2.918 的 PA/HOM fold1（FB 过滤后该 pair FB3<8 被 LK_INSUFFICIENT 拦截）。
  - new 25：FB 过滤显著提升 purity，多个此前 NO_ANCHOR 的 pair 出现 validated folds
    （如 3571 各 pair 的 fold0、12095、25894 等）。
- 最终 fold 级 taxonomy（DINO_LK_FB3）：VALIDATED 33 · MED_AND_P90_FAIL 0（fold 级已无
  MED_AND_P90 于 validated 判定内；fail 分类见 MATCH_MATRIX 各 fold state）。

## 5. coverage / consensus（§9/§10）
- coverage（bins/quads/hull_ratio）全部来自 FINAL_ACCEPTED_FB3；SUPPORT_TOO_LOCALIZED 4 对
  由 FB3 子集覆盖不足触发（非 all-MNN）。
- 真 consensus：aff & hom 均双 fold VALIDATED 的 pair 在共同 FB3 support 上算 median/P90
  分歧；6 对 MULTI（分歧≤3px）、0 CONFLICT（MODEL_CONSENSUS.json 记录 median/P90）。

## 6. Support-hull 结构通道（§11/§12，真实现）
- **OVERNIGHT_STRUCTURAL_DIAG_DEFECT_01 登记**：overnight 所谓 support-hull structural 实际
  未裁 hull（直接 warp 全体 ISLAND_BODY 结构边，单向 chamfer）。
- R2 真实现：t0 hull = convexHull(FB3 accepted P0)、t1 hull = convexHull(FB3 accepted P1)，
  margin = 14/scale_t 扩张并 clip 到 ISLAND_BODY，只保留 hull+margin 内 clean structural
  edges（Canny + 动态排除）。
- symmetric：forward（t0 hull edges → T3 → t1 hull edge DT）+ reverse（t1 hull edges →
  T3⁻¹ → t0 hull edge DT），OBJ01 corrected edge=0 DT raw Euclidean。
- 结果（validated 8 对的 representative transform）：见 STRUCTURAL_VALIDATION.json 每行
  forward/reverse/symmetric median/P90/P95；若 geometric validated 但 structural P90>12px
  标 DENSE_STRUCTURAL_DISAGREEMENT。
- 仍为 diagnostic channel，未新增主 gate。

## 7. DINO_ONLY vs DINO_LK（§13B，修正统计）
- **MODEL_COMPARISON_COUNTS（72 model×pair cells）**：HELPED 37 · NO_COMPARISON 35 ·
  HURT 0 · NEUTRAL 0。
- **PAIR_LEVEL_COUNTS（36 pairs）**：HELPED_ONLY 19 · NO_COMPARISON 17 ·
  HURT_ONLY 0 · MIXED 0 · NEUTRAL_ONLY 0。
- **不再写"36 pairs helped"**（上一版 36 HELPED model-cells 的表述已修正）。

## 8. Reporting corrections（§13/§15）
- 语义：`SEMANTIC_MATCH_SUFFICIENT = 34/36`，`SEMANTIC_RECALL_STATUS = NOT_FORMALLY_GATED`
  （不再写 SEMANTIC_RECALL_ESTABLISHED=False）。
- raw refine 拆分：`RAW_REFINEMENT_EFFECTIVE = YES`（DINO_ONLY 0 validated → DINO_LK 7/7；
  pooled median 14.2→4.0px 链在 FB 过滤后达 0.995px）；`RAW_REFINEMENT_SUFFICIENT = NO`
  （8 union < 17）。
- RANSAC stride：未 round float 验证 threshold == max(14/s0,14/s1)，tolerance 1e-6；
  全部 pair `ransac_thr_check.all_pass = true`。
- provenance（§14）：checkpoint G 绝对路径 + SHA256 `F4331770…` + license + torch 2.6.0+cu124 +
  CUDA 12.4 + cache path（不再 checkpoint="?"/sha256=""）。

## 9. 判定（§19/§20）
- union 8 < 17 → **FAIL_DENSE** → **DENSE_ENDPOINT_ROUTE_CLOSED = TRUE**，
  **DENSE_ENDPOINT_CAPABILITY = NOT_ESTABLISHED**。
- 架构师判词对应：R2 完整冻结规格实现后 union 仍 <17/36 → 正式接受 endpoint route closed。
- candidate frozen：**NO**（CANDIDATE.json）。

## 10. 历史同屏（§18）
DENSE01 original **0/36** · DENSE01R1 forward-only **0/36** · overnight forward-only replay
**0/36** · **DENSE01R2 true FB3 = 8/36**（union；FAIL_DENSE）。

## 11. Evidence Hierarchy 状态（§21）
`TREECUT_CAM01_EVIDENCE_HIERARCHY_PROPOSAL_V1.md` 状态：**PROPOSAL_PENDING_DENSE_R2_CLOSURE**
（本轮不实现；未接入 MMVV）。

## 12. NEXT_BLOCKER
**EVIDENCE_HIERARCHY_REDESIGN 或 TEMPORAL_LEARNED_TRACKER**（不自动开始；等架构师指令）。

## 产物
reports/storage/：PRE_RUN_GIT_STATUS · CONFIG · PROVENANCE · LK_FB · MATCH_MATRIX ·
HOLDOUT_VALIDATION · FAILURE_MAP · SPATIAL_COVERAGE · MODEL_CONSENSUS · STRUCTURAL_VALIDATION ·
DINO_VS_LK · NEG_TARGET_CONTROL · RESULT · CANDIDATE · GALLERY.html。
docs/：本报告。tests/test_cam01_dense01r2.py（11 测试）。scripts/posta3_cam01_dense01r2.py。
