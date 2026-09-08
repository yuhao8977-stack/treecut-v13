# TREECUT CAM01 EH01 R1 — Reference Materialization + Router Semantics Correction 报告

- 基线：main @ `f46701a`（工作树 clean）
- 性质：**evidence semantics / transform materialization / local agreement / global capability
  semantics / router metrics / classification protocol 修正**。EH01 历史结果保留
  （LOCAL_STRONG 9 · PARTIAL 10 · CONFLICT 2 · NONE 15 · ROUTER_USABLE 19 · RAW_UNION 22 ·
  HIERARCHY_FEASIBLE），正式标记 `EH01_RESULT_PENDING_REFERENCE_SEMANTICS_CORRECTION`。
- 不进入 EH02；无 GEOM/tracker/新模型/新 threshold/改历史 gate；无动作 verdict。

## 0. 结论速览
- **4 EH01 defects fixed：YES**
- 精确 R2 transform materialization：**8/8 validated**（representative model + pair thr_raw，
  重建两次确定性验证，无固定 4px/无强制 affine）
- corrected local agreement：**3 agree / 2 conflict**（同旧数但本次为 exact transforms 结果）
- GLOBAL_STATE_MATERIALIZED=YES · **GLOBAL_TRANSFORM_MATERIALIZED=NO**
- **REFERENCE_EMITTABLE_STRONG 9/36** · PARTIAL_WITH_TRANSFORM 4 · EVIDENCE_ONLY_NO_TRANSFORM 3 ·
  GLOBAL_FALLBACK_CANDIDATE_STATE_ONLY 4 · LOCAL_CONFLICT 2 · UNSURE_NO_EVIDENCE 14
- **NEG_STRONG_REFERENCE_TARGET_VALID = 0 → NEG_REFERENCE_CONTROL_NOT_READY = YES**
- reference router output capability：**PARTIAL**（非 ESTABLISHED——4 个 partial-with-transform +
  7 个 evidence-only/global-state-only 不可 emit）

## 1. Defect 01 — Evidence != Emittable Reference（§1/§2）
旧 ROUTER_USABLE=STRONG+PARTIAL+GLOBAL 把无 transform 的 GFTT evidence 计入。R1 拆：
- **REFERENCE_EMITTABLE_STRONG 9**：strong historical + **transform materialized** + 无 conflict +
  无 STRUCTURAL_DISAGREEMENT（V24 UNKNOWN 视为 NO_STRUCTURAL_VETO_AVAILABLE 非 confirmed）
- **REFERENCE_PARTIAL_WITH_TRANSFORM 4**：DENSE 被结构 veto 降级但 matrix 存在（3571 1.842→4.299、
  3571 7.984→10.441、10000 0.768→1.793、25894 0.718→1.676）——**不计 SAFE_EMITTABLE**
- **EVIDENCE_ONLY_NO_TRANSFORM 3**：GFTT validated 但无 matrix 且 global 不可靠
  （12095 2.225→5.191、1641 2.642→3.434、25894 2.394→3.112）
- GFTT_V23 全部标 EVIDENCE_ONLY_NO_TRANSFORM 或 GLOBAL_FALLBACK（transform=null 不升级 emittable；
  未借用别轮 transform）

## 2. Defect 02 — R2 transform reconstruction（§3-§5）
旧 EH01 `r2_transform()` 固定 PARTIAL_AFFINE + 4px。R1 从 R2 MATCH_MATRIX 精确读取每 validated pair：
- representative：6×PARTIAL_AFFINE + 1×**HOMOGRAPHY**（10000 0.768→1.793）+ 1×PARTIAL_AFFINE（12095 5.191）
- thr_raw：11.68 / 13.38–13.78 / 15.51 / 26.76 / 31.22px（无一为 4px）
- FB3 accepted corr (p0 → p1_fb)，estimateAffinePartial2D 或 findHomography + pair thr
- **重建两次**：8/8 deterministic（fixed body grid prediction disagreement < 1e-6）
- 输出 EXACT_R2_REFERENCE_TRANSFORM（matrix/model/thr/corr count 见 R2_TRANSFORMS.json）

## 3. Local agreement 重算（§6-§7）
只比有 materialized transform 的源：DENSE_R2 exact rep + V24R1 exact rep（final_M_2x3 不 refit）。
- **old EH01: 3 agree / 2 conflict**
- **R1 corrected: 3 agree / 2 conflict**（verdict changed pairs: 无——但冲突值基于正确 thr 重算：
  12095 5.191→7.416 med 5.48px、25894 3.112→4.07 med 5.35px 保持 CONFLICT）
- GFTT 无 transform 未参与 transform agreement。

## 4. Defect 03 — Global state != Global transform（§8-§10）
- GLOBAL_STATE_MATERIALIZED = **YES**（V2 SPARSE_DIRECT RELIABLE/UNRELIABLE 逐 pair）
- GLOBAL_TRANSFORM_MATERIALIZED = **NO**（artifact 无最终 transform matrix）
- GLOBAL_TRANSFORM_MATERIALIZATION_REQUIRED = **YES**（下一阶段前需单独 materialize，不自动执行）
- fallback 语义重执行（§9）：LOCAL_STRONG 不看 global；**LOCAL_PARTIAL/GFTT + global reliable →
  GLOBAL_FALLBACK_CANDIDATE_STATE_ONLY（4 pair：2543 1.202→1.717、9697 2.885/4.121/5.357）**；
  LOCAL_CONFLICT → UNSURE（global 不得覆盖）；LOCAL_PARTIAL 有 global state 的计数见 metrics
  （GLOBAL_STATE_ONLY_CANDIDATE 4 = 全部为 GFTT-evidence + global-state fallback candidates，均不可 emit）。

## 5. Structural semantics（§11）
沿用 symmetric P90 规则（≤12 CONSISTENT / >12 DISAGREEMENT / 无 symmetric UNKNOWN）。
文字区分：V24 UNKNOWN = **NO_STRUCTURAL_VETO_AVAILABLE**（非 STRUCTURAL_CONFIRMED），
已避免把 UNKNOWN 写成 "structural ok"。

## 6. Router semantics & metrics（§12-§13）
旧 ROUTER_USABLE(19) 弃用为唯一数字。新 metrics：
| 指标 | /36 |
|---|---|
| EVIDENCE_ROUTABLE（有 evidence 且未否决） | 20 |
| TRANSFORM_MATERIALIZED_ANY | 13 |
| **REFERENCE_EMITTABLE_STRONG** | **9** |
| REFERENCE_PARTIAL_WITH_TRANSFORM | 4 |
| EVIDENCE_ONLY_NO_TRANSFORM | 3 |
| GLOBAL_STATE_ONLY_CANDIDATE（含 fallback candidates） | 4 |
| UNSURE（含 CONFLICT 2） | 16 |

架构师期望审计值（9 STRONG / 3 DENSE veto partial / 7 GFTT）对照：9 = 9 ✓；DENSE veto partial
实际 4（含 V24 veto 0 + DENSE 4）；GFTT 拆分后 3 evidence-only + 4 global-fallback（V23 GFTT 17 中
10 与 V24/DENSE 重叠已归类于 transform 路径，7 独立中 3 evidence-only + 4 global-fallback）。

## 7. Target diagnostic（§14-§15，emittable split）
| | STRONG(target_valid) | PARTIAL_W_T(target_valid) | EVIDENCE_ONLY(target_valid) |
|---|---|---|---|
| POS | 7 (6) | 2 (2) | 1 (1) |
| NEG | 2 (**0**) | 2 (1) | 6 (2) |

- **NEG_STRONG_REFERENCE_TARGET_VALID = 0**（25894 的 2 个 STRONG 无有效 NEG target）
- **NEG_REFERENCE_CONTROL_NOT_READY = YES** → 不得进入 GEOM threshold
- 旧 EH01 "NEG target_valid 2" 的 pair 均在 EVIDENCE_ONLY（GFTT 无 transform）——
  **不能理解为未来 GEOM 已有 NEG reference**（架构师判断证实）。

## 8. Defect 04 — post-hoc classification threshold（§16）
`eh01_result.py` 的 `if usable > 12: HIERARCHY_FEASIBLE` 已删除（违反"不设新 performance
threshold"）。R1 只输出语义状态（§17）：
- **A_EVIDENCE_HIERARCHY_ARCHITECTURE_SUPPORTED = YES**（source join 正确 / router 语义可表达 /
  conflict/veto/unknown fail-closed）
- **reference_router_output_capability = REFERENCE_ROUTER_OUTPUT_CAPABILITY_PARTIAL**
  （仅部分 route 能实际输出 transform；无 coverage gate 决定）

## 9. Source family / correlation / provenance（§18-§19）
- families：DENSE_R2=SEMANTIC_DENSE_LK · V24R1=FEATURE_LOCAL_ENSEMBLE · V23_GFTT=FEATURE_LOCAL ·
  GLOBAL=GLOBAL_CAMERA · STRUCTURAL=STRUCTURAL_VALIDATION · DINO_MNN=SEMANTIC_AVAILABILITY
- 注明 **V24R1 与 V23_GFTT 同属 feature-local 证据链，非完全独立**；禁止 source count 冒充
  independent corroboration count。
- exact provenance（无 "-era"）：V24R1=e2bb0ae/e433a90e… · V23=09e3b5b/98e74be9… ·
  GLOBAL_V2=f85b363/268695d7… · DENSE_R2=8f84735/748e3ccb… · STRUCTURAL=8f84735/b567302f… ·
  CALIBRATION10_MANIFEST=136e466/714998a4…（全部 git log --all 定位 + blob SHA，无占位符）。

## 产物
reports/storage/：DEFECT_AUDIT · SOURCE_PROVENANCE · SOURCE_FAMILIES · R2_TRANSFORMS ·
LOCAL_AGREEMENT · GLOBAL_CAPABILITY · ROUTER_SHADOW · REFERENCE_METRICS · TARGET_DIAGNOSTIC ·
RESULT（10 JSON）。
docs/：本报告。scripts/eh01r1_reference_semantics.py · eh01r1_result.py。
tests/test_eh01r1_reference.py（11 测试）。
