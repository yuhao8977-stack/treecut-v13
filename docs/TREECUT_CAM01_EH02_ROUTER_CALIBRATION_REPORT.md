# TREECUT CAM01 EH02 — Router Calibration + M1 Inlier-Support Correction 报告

- 基线：main @ `644c206`（工作树 clean）
- 性质：**router calibration (V2)** + M1 inlier-support correction。role-blind 至 router 冻结。
  不进入 GEOM/不跑 Tracker/不加模型/不改历史 source gate/不 materialize Global/不加 NEG 样本。
- 正式输入：EH01R1 STRONG=9/PARTIAL；EH01M1 GFTT 17 replay+materialize；NEG materialized
  target-valid 1641 2.642→3.434 + 2543 1.202→1.717。

## 0. 结论速览
- M1 materialization preserved：**YES**（17/17 matrix 重建一致）
- M1 report conflict identity **corrected**（GFTT↔V24 conflict = 25894 3.112→4.07，非 12095 5.191）
- GFTT structural：old 7 CONSISTENT/10 DISAGREEMENT → **corrected 7 CONSISTENT/9 DISAGREEMENT/1 UNKNOWN**
  （verdict changed 1：1641 2.642→3.434 DISAGREEMENT→UNKNOWN——inlier hull 后 t1 结构边支撑不足）
- **REFERENCE_STRONG = 8/36** · PARTIAL 1 · PARTIAL_VETOED 11 · CONFLICT 2 · NO_EVIDENCE 14
- safe_emit **8** · case coverage 6/9
- **NEG strong target-valid = 1（2543 1.202→1.717 via S2）→ NEG_REFERENCE_CONTROL = PRESENT**
- NEG_REFERENCE_CONTROL_ESTABLISHED = NO（需 ≥3 unique visual families）
- GLOBAL_TRANSFORM_NEEDED = NO · GLOBAL_MATERIALIZATION_UPPER_BOUND = 0
- ROUTER_RULESET_FROZEN = YES

## 1. Stage 0A — M1 agreement report correction（§1）
登记 EH02_CORRECTION_M1_AGREEMENT_REPORT_01。M1 REPORT/final 写错 GFTT↔V24 conflict 身份。
以 TREECUT_CAM01_EH01M1_LOCAL_AGREEMENT.json 为准代码重算：
- GFTT↔V24：9 AGREE / **1 CONFLICT = 25894 3.112→4.07**（med 4.245px）/ 7 not-comparable
  （12095 5.191→7.416 实为 AGREE med 0.001px——V24 representative 多为 GFTT_LK_LOCAL 同源）
- GFTT↔DENSE：3 AGREE / 2 CONFLICT（12095 5.191、25894 3.112）——与 M1 报告一致
旧报告未修改，correction artifact 已生成。

## 2. Stage 0B — inlier support hull（§2-§5）
登记 EH02_CORRECTION_M1_STRUCT_HULL_02。M1 structural hull 用全部 FB≤3 accepted tracks（含
RANSAC outlier）；修正为只用 fit-all materialization **RANSAC inliers**。
- §3 rebuild：17/17 matrix 与 M1 完全一致（fixed-grid disagreement < 1e-6，
  EH02_M1_TRANSFORM_REBUILD_MISMATCH 未触发）；每 pair 保存 ransac_inlier_mask/inlier
  indices/inlier p0/p1（EH02_GFTT_INLIERS.json）
- §4 inlier support hull：convexHull(inlier P0/P1) + 14px margin（continuity 未调）+
  clip ISLAND_BODY + 排除其它 L3 ROI
- §5 label（symP90≤12 CONSISTENT/>12 DISAGREEMENT/无=UNKNOWN，12 未调）：
  old 7C/10D/0U → **corrected 7C/9D/1U**
  - verdict changed：**1641 2.642→3.434 DISAGREEMENT→UNKNOWN**（inlier n=16，t1 结构边仅 1——
    inlier hull 收缩后边支撑不足；不再主动 veto，亦无结构支持）
  - 2543 1.202→1.717：CONSISTENT（sym P90=2.324px 干净，n_inl=21）

## 3. Source inventory & agreement graph（§6-§8）
- A DENSE_R2 exact（8f84735/EH01R1）· B V24R1（e2bb0ae）· C GFTT_M1（644c206）·
  D GLOBAL state only · E corrected structural（合并 GFTT inlier-hull + R2 DENSE symmetric）·
  F DINO semantic support only。GLOBAL state 未冒充 transform。
- agreement graph 20 edges；conflict pairs **2**：12095 5.191→7.416（GFTT↔DENSE）、
  25894 3.112→4.07（GFTT↔V24 + GFTT↔DENSE）。same/cross-family 均已标注。

## 4. Router rules & freeze（§9-§20）
- confidence：HIGH=V24 consensus/DENSE multi；MEDIUM=DENSE single/GFTT validated materialized
- S1（HIGH+无 conflict+struct≠DISC）、S2（MEDIUM+CONSISTENT+global reliable）、
  S3（MEDIUM+cross-family agree+struct≠DISC）pre-frozen；conflict precedence 最高；
  tie-break DENSE_R2>V24R1>GFTT_M1；STRUCTURAL_UNKNOWN = NO_STRUCTURAL_VETO_AVAILABLE
  （不得写 CONFIRMED）
- **structural 合并语义**：per-pair 任一 materialized source 的 DISAGREEMENT 即 veto——
  修正后 25894 1.676→2.394（V24 源，R2 symP90=17.5）与 27433 10.352→13.458（GFTT/V24 同源，
  symP90=17.4）从 EH01R1 strong 掉出 → PARTIAL_VETOED（EH01R1 因无 structural 曾放行，EH02 如实 veto）
- ROUTER_FREEZE.json 含 rules hash/source hashes/36 pair route/rep transform/reason codes。

## 5. Metrics（§21）
| 状态 | /36 |
|---|---|
| REFERENCE_STRONG | **8** |
| REFERENCE_PARTIAL | 1 |
| REFERENCE_PARTIAL_VETOED | 11 |
| UNSURE_CONFLICT | 2 |
| UNSURE_EVIDENCE_ONLY | 0 |
| UNSURE_NO_EVIDENCE | 14 |
| safe_emit | 8 |
| case coverage /9 | 6 |

vs EH01R1 strong=9：**net -1**（25894 1.676、27433 10.352 因 corrected structural veto 掉出；
GFTT M1 新增 strong **1 = 2543 1.202→1.717 via S2**）。3571 1.842/7.984（DENSE MULTI 但 R2
structural DISAGREEMENT）正确降为 PARTIAL_VETOED，未错误升级。

## 6. NEG/POS readiness（§22-§24）
strict target contract（router 冻结后才读 role）：
- **NEG strong target-valid = 1：2543 1.202→1.717**（S2：GFTT CONSISTENT + global RELIABLE）
- **1641 2.642→3.434 = REFERENCE_PARTIAL**（structural UNKNOWN + global unreliable，不满足 S2；
  GFTT transform 保留为 matrix 诊断价值）
- POS strong target-valid = 5
- **NEG_REFERENCE_CONTROL = PRESENT**（1 strong target-valid）
- NEG_REFERENCE_CONTROL_ESTABLISHED = NO（需 ≥3 unique visual families——当前仅 1）
- 不进入 GEOM；即使 2543 升级 strong 也不得开 GEOM threshold。

## 7. Global fallback（§25-§26）
- UNSURE/PARTIAL 中带 GLOBAL reliable state 的 pair：0 个无 local transform
- **GLOBAL_MATERIALIZATION_UPPER_BOUND = 0**（materialize global transform 当前最多影响 0 pair）
- **GLOBAL_TRANSFORM_NEEDED = NO**（2543 已有 GFTT transform + global state support；
  无需为任何 pair 先 materialize global）

## 8. Targeted negative set（§27，recommendation only）
NEG_REFERENCE_CONTROL_ESTABLISHED=NO → 建议候选（cal10 外 human-reviewed NO_ACTION，11 个：
1019/1025/103/1600/1638/1639/2163/2208/2211/2492/26023；src1 卖点展示类为主 + 26023 src4 工厂），
供未来补强 NEG control（≥3 unique families）使用。**不自动加样本/画 ROI/运行。**

## 9. 判定（§28）
- ROUTER_RULESET_FROZEN = YES
- NEG_REFERENCE_CONTROL = **PRESENT**（非 ESTABLISHED）
- GLOBAL_TRANSFORM_NEEDED = NO
- 无新 coverage PASS gate；分类非 coverage 判定。

## 10. NEXT_BLOCKER
**TARGETED_NEGATIVE_REFERENCE_SET**（需 ≥3 unique visual families 的 NEG strong control 才能
ESTABLISHED；候选清单见 §8）。等待架构师决定是否批准样本补强任务（非自动）。

## 产物
reports/storage/：M1_CORRECTIONS · GFTT_INLIERS · STRUCTURAL_CORRECTED · SOURCE_MATRIX ·
LOCAL_AGREEMENT_GRAPH · ROUTER_CONFIG · ROUTER_FREEZE · ROUTER_METRICS · TARGET_READINESS ·
GLOBAL_UPPER_BOUND · RESULT（11 JSON）+ ROUTER_GALLERY.html。
docs/：本报告。scripts/eh02_corrections.py · eh02_inlier_structural.py · eh02_router_freeze.py ·
eh02_result.py。tests/test_eh02_router.py。
