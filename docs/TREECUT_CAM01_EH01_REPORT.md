# TREECUT CAM01 EH01 — Evidence Hierarchy Inventory + Shadow Router Feasibility 报告

- 基线：main @ `8f84735`（工作树 clean）
- 性质：**inventory + shadow routing**；不训练、不加模型、不改任何历史 gate；无动作判定
  （EXTEND/RETRACT/STATIC 均不输出）；不接入 GEOM/MMVV；role-blind 至 router 冻结后。
- 历史正式状态：DENSE_ENDPOINT_ROUTE_CLOSED=TRUE · DENSE_ENDPOINT_CAPABILITY=NOT_ESTABLISHED ·
  LOW_LEVEL_LOCAL_ANCHOR_EXHAUSTED=TRUE · SEMANTIC_BOX_ANCHOR_NOT_SUFFICIENT=TRUE · A3 sealed。

## 0. 结论速览
- **ROUTER_USABLE = 19/36**（DENSE R2 单源 8/36 → +11，无任何 gate 放宽）
  - LOCAL_STRONG **9** · LOCAL_PARTIAL **10** · GLOBAL_RELIABLE fallback **0**
  - UNSURE_CONFLICT **2** · UNSURE_NO_EVIDENCE **15**
- case coverage **8/9**
- **EH01 classification = HIERARCHY_FEASIBLE**
- NEXT_CAPABILITY_CANDIDATE = **EH02_ROUTER_CALIBRATION**（不自动开始）

## 1. R2 corrections（§4/§5）
### EH01_CORRECTION_R2_STRUCT_FLAG_01
R2 只按 **forward P90>12px** 打 DENSE_STRUCTURAL_DISAGREEMENT。EH01 按规格改用 **symmetric P90**
（≤12=CONSISTENT / >12=DISAGREEMENT / 无 symmetric=UNKNOWN；12px 沿用 R2 boundary 非新调参）。
代码重算 8 个 R2 validated pair：
- **CONSISTENT 3**：12095 5.191→7.416（sym P90 3.28）· 3571 4.299→6.142（7.10）· 3571 6.142→7.984（6.69）
- **DISAGREEMENT 5**：3571 1.842→4.299（**25.73**，R2 漏标）· 3571 7.984→10.441（39.35）·
  10000 0.768→1.793（15.69）· 25894 0.718→1.676（16.03）· 25894 3.112→4.07（**25.98**，R2 漏标）
- UNKNOWN 0

### EH01_CORRECTION_R2_ABLATION_02
R2 的 DINO_ONLY_SUBTOKEN 只在 FB3 accepted 子集上评估 → 只能叫 **CONDITIONAL_DINO_ONLY_ABLATION**，
不得当独立全量 baseline。保留事实：SEMANTIC_MATCH_SUFFICIENT=34/36 · RAW_REFINEMENT_EFFECTIVE_CONDITIONAL=YES。

## 2. Evidence sources joined（36 semantic pairs）
| source | artifact | 可用集 | transform |
|---|---|---|---|
| A DENSE01R2_FB3 | R2 MATCH_MATRIX（8f84735） | 8（6 MULTI+2 SINGLE） | ✅（FB3 corr refit，仅 validated） |
| B V24R1_CONSENSUS | V24R1 TRUE_CLIQUE（12 pair，4 方法 true clique） | 12 | ✅（representative final_M_2x3） |
| C GFTT_V23_WHOLE_ISLAND | V23 METHOD_MATRIX | 17（validated） | ❌（V23 无 final_M） |
| D GLOBAL_CAMERA_SPARSE | POSTA3 CAMERA_PAIR_MATRIX_V2 | 12 RELIABLE /36 | ❌（仅状态） |
| E STRUCTURAL_DIAGNOSTIC | R2 STRUCTURAL_VALIDATION | 8 | ❌（VETO 角色） |
| F DINO_SEMANTIC_MNN | R2 MATCH_MATRIX | 34/36 MATCH_SUFFICIENT | ❌（availability only） |

缺失一律 UNKNOWN/NOT_AVAILABLE，未填 0 冒充。

## 3. LOCAL 分层与 agreement（§6/§7）
- 双 transform 可比较 pair（DENSE validated ∩ V24R1，均有已过 gate 的 transform）= **5**：
  3 AGREE（med 1.59–2.46px：27433 7.246/10.352、3571 4.299/6.142、3571 6.142/7.984 等）·
  **2 CONFLICT**（12095 5.191→7.416 med 5.48px；25894 3.112→4.07 med 5.35px）→ 判 UNSURE_CONFLICT。
- LOCAL_STRONG 9（pair 列表见 ROUTER_SHADOW.json）= DENSE_R2_MULTI+structural-ok（3571 4.299→6.142、
  6.142→7.984）∪ V24R1 consensus 无 veto 无 conflict（27433 7.246→10.352、10.352→13.458、
  12095 7.416→9.64、9.64→12.607、21674 1.201→2.803、9697 1.236→2.885、25894 1.676→2.394）——
  全部已过自身历史 gate。
- LOCAL_PARTIAL 10 = DENSE MULTI/SINGLE 被结构 veto 降级（3571 1.842→4.299、7.984→10.441、
  25894 0.718→1.676）+ GFTT single-source（1641 2.642→3.434、2543 1.202→1.717、12095 2.225→5.191、
  9697 2.885/4.121/5.357、25894 2.394→3.112）+ V24R1 结构 veto（如适用，见矩阵）。
- DENSE SINGLE 10000 0.768→1.793 被结构 veto → UNSURE_NO_EVIDENCE（如实降级，不计 usable）。
- GLOBAL_RELIABLE fallback **0**：无 pair 处于"无可靠 local 且 global reliable"（12 个 camera
  reliable pair 均有 local 证据，global 从未被需要——观察非调整）。

## 4. Shadow router（§13/§16）
- RAW_SOURCE_UNION = **22/36**（任意历史源声称可用）
- ROUTER_USABLE = **19/36**（conflict 2 + structural veto 若干后真正可输出）
- **差异诚实呈现：raw union 22 ≠ usable 19**（3 pair 被 conflict/veto 消化，未冒充 coverage）
- route 分布：LOCAL_STRONG 9 · LOCAL_PARTIAL 10 · UNSURE_CONFLICT 2 · UNSURE_NO_EVIDENCE 15

## 5. Target diagnostic（§17/§18，router 冻结后读 role，不改 router）
strict target contract（EXTENSION_TABLETOP 或 TABLETOP 唯一）：
- **POS**：usable 10 · target_valid **9**（未来 GEOM 在 POS 有 9/16 pair 可获可靠 reference）
- **NEG**：usable 9 · target_valid **2**（NEG 多数无 target 或 target 无效——符合 NEG 语义）
（只报 reference 可用性，不做动作判定。）

## 6. 判定（§19/§20）
- ROUTER_USABLE 19 明显高于 DENSE R2 8/36（+11）
- 无 gate 放宽（全部继承各源历史 gate；12px 结构边界沿用 R2）
- UNSURE/conflict 语义清晰（conflict 2 明确列出）
- global 已 materialize（12/36 reliable，非 blocked）
→ **HIERARCHY_FEASIBLE**
- NEXT_CAPABILITY_CANDIDATE = **EH02_ROUTER_CALIBRATION**（下一轮才做，不自动开始；
  若未来 EH02 后 coverage 仍不足再评估 TEMPORAL_LEARNED_TRACKER 填 UNSURE 缺口）

## 7. 限制与注记
- GFTT 17 为 single-source PARTIAL（V23 无 transform，无法参与 agreement 双源验证；
  V23 bakeoff 自身 status=LOCAL_ANCHOR_FEATURE_BAKEOFF_FAILED——17 为方法内 validated 数，
  非生产级候选冻结）。
- LOCAL_PARTIAL 含"结构 veto 降级"与"GFTT 单源"两类，置信度低于 STRONG；
  19/36 的 usable 是"至少一个已过自身 gate 的 local 证据且无冲突/无结构否决"，
  其中 STRONG-only 为 9/36。HIERARCHY_FEASIBLE 判据用 usable(19)（架构师 §19 口径），
  但报告同时披露 STRONG=9，供架构师对 EH02 目标校准。
- 无新 performance PASS threshold；本轮为架构可行性，非生产 gate。

## 产物
reports/storage/：SOURCE_INVENTORY · R2_CORRECTIONS · EVIDENCE_MATRIX · LOCAL_AGREEMENT ·
GLOBAL_EVIDENCE · ROUTER_SHADOW · TARGET_DIAGNOSTIC · RESULT（8 JSON）。
docs/：本报告。scripts/eh01_inventory_shadow.py · eh01_result.py。
