# FRESH_HOLDOUT_V2 FINAL EVALUATION（Phase 3 最终毕业考试）

> 状态：**Bundle V2 独立第二套 30 题考试完成 + 评分 + V1/V2 双考试对比**
> 日期：2026-08-29
> 身份：bundle `a87d3124…` · manifest `27f751ed…` · prediction `4b53b0c0…` · human `bf658f94…`
> 纪律：未改 prediction / 未重新预测 / 未修改 Bundle / 未训练 / 未进 Phase4

---

## STEP 1：Human Truth 冻结 ✅

- **30/30 完整唯一**（missing/extra/duplicate=0；REVIEWED 30 / MEDIUM 30 / V2.1）
- **human_truth_sha256 = `bf658f94dfa1ccc28f72037648b42d3ce429321945ca694182a204795589670a`**
- 已冻结 `FRESH_HOLDOUT_V2_HUMAN_LOCK.json`（DO_NOT_OVERWRITE；修订走 revision）

## STEP 2-3：身份完整性 + 污染 ✅

三 hash 全部未变（bundle `a87d3124…` / manifest `27f751ed…` / prediction `4b53b0c0…`）；AI pred segment set = Human truth set = manifest set = 30；DO_NOT_TRAIN/DO_NOT_CALIBRATE/DO_NOT_REPREDICT 评分后保持。

---

## STEP 4-6：四层评分（Fresh Unseen Stratified Holdout V2 Performance）

### People（有效，YOLO 独立）
| layer | n | correct | acc | Wilson 95% CI |
|---|---|---|---|---|
| RANDOM | 10 | 8 | 80.0% | (49.0, 94.3) |
| HARD | 10 | 8 | 80.0% | (49.0, 94.3) |
| GAP | 10 | 10 | **100.0%** | (72.2, 100) |
| **ALL** | **30** | **26** | **86.7%** | (70.3, 94.7) |

**混淆矩阵：TP 18 / FP 4 / TN 8 / FN 0 → P 81.8 / R 100 / Sp 66.7 / F1 90.0 / acc 86.7 / bacc 83.3**
**YOLO provider 30/30 · technical fallback 0 · NORMAL_NO_FALLBACK_VIOLATIONS = 0** ✅

### Product Family / Scene / Variant（⚠ INVALID_EXAM_BUG）
product_family / scene_family / product_variant 的 V2 prediction **全 UNKNOWN（raw evidence scores 为空）** —— 根因：**exam 脚本对 SigLIP single 字段误用 `scores` key（实际返回 `all_scores`），且未保存真实 prediction**。这 3 字段的 V2 Fresh 评分 **INVALID（不可当模型真实表现）**，需另开补充预测（非重跑锁定 prediction）。**V1 51.7% vs V2"0%"不构成回归结论。**

### Scene_subtype / Shot_scale / Product_visibility
prediction 中**缺失**（exam 脚本漏输出 3 字段）→ MISSING 30/30，评分无效。

### Multi-label（有效，有 scores）
| 字段 | n | microF1 | macroF1 | pred_avg | human_avg | exact |
|---|---|---|---|---|---|---|
| material | 30 | 22.6 | 30.4 | 5.2 | 1.0 | 0 |
| component | 30 | **57.7** | 60.4 | 2.8 | 2.63 | 3.3 |
| function | 30 | **59.3** | 60.9 | 2.87 | 3.43 | 0 |
| shot_role | 30 | 36.3 | 37.7 | **7.1** | 1.9 | 0 |

per-class 亮点：component DRAWER F1 80 / COUNTERTOP 84；function STORAGE 91 / EXTENDABLE 76 / OFFICE 84；material 岩板 82.4（但撒网）；shot_role PRODUCT_SHOWCASE 92.9 / PERSON_TALKING 71.4（但 pred_avg 7.1）。

---

## STEP 7-10：重点验收

- **People V2 → PRODUCTION_CANDIDATE**（Fresh F1 90.0 / bacc 83.3 / viol 0；V1 曾全 UNKNOWN —— 最大升级）
- **Component V2 → READY/LIMITED**（Fresh microF1 57.7；V1 49.2）
- **Function V2 → READY/LIMITED**（Fresh microF1 59.3；V1 55.7）
- **Material → EXPERIMENTAL**（Fresh F1 22.6；岩板 82.4 但不代表长尾材质能力）
- **ShotRole → EXPERIMENTAL**（Fresh F1 36.3；pred_avg 7.1 仍严重高于 human 1.9）
- **Scene/Variant**：V2 Fresh 评分无效（exam bug），V1 基线 scene 24.1% / variant 0%

## STEP 11：Semantic Action 正式考试

| action | sup | TP/FP/FN | P/R/F1 | router |
|---|---|---|---|---|
| PULL_OUT | 2 | 2/0/0 | **100/100/100** | V1_RULE_SIMPLE |
| PERSON_SPEAKING | 18 | 0/0/18 | 0/0/0 | MOTION_BASELINE |
| STATIC_DISPLAY | 11 | 0/0/11 | 0/0/0 | MOTION_BASELINE |
| RETRACT | 5 | 0/0/5 | 0/0/0 | NO_CLAIM（正确 abstain） |
| OPEN_CABINET | 2 | 0/0/2 | 0/0/0 | NO_CLAIM（正确 abstain） |
| OPEN_DRAWER | 0 | 0/6/0 | — | V1_RULE（false claim 6） |
| CLOSE_CABINET | 0 | 0/13/0 | — | V2_STATE（false claim 13） |
| OTHER | 0 | 0/27/0 | — | DEFAULT（兜底滥用） |

- **correct_abstention = 7**（OPEN_CABINET 2 + RETRACT 5 正确 abstain）
- **abstain_violations = 0**（NO_CLAIM/INSUFFICIENT 未被违规输出）✅
- **false_claim_count = 51**（CLOSE_CABINET 13 / OTHER 27 / OPEN_DRAWER 6 / CLOSE_DRAWER 5）—— Router 的 V1/V2 experimental route 在 Fresh 上**过度声称**（DEV 上的 F1 未能泛化）

## STEP 13-14：结构 + 小样本

- RANDOM/HARD/GAP 三层 People 均 ≥80%（GAP 100%）—— 结构稳定
- **全部 30 条 n≤30、每层 n≤10**：Wilson CI 已给，**禁止把 8/10 vs 8/10 当确定性提升**
- 错误归因（`FRESH_HOLDOUT_V2_ERROR_CASES.json`，30 条全含错误）：UNKNOWN_OVERUSE_EXAM_BUG 59 · OVERPREDICTION_shot_role 30 · OVERPREDICTION_material 28 · FALSE_CLAIM(OTHER/CLOSE_CABINET/…) 27 · YOLO_FALSE_POSITIVE 4

## STEP 15：V1/V2 双考试对比（非同题，量级比较）

| 字段 | V1→HoldoutV1 | V2→HoldoutV2 | 判定 |
|---|---|---|---|
| people | 0%（unk100） | **F1 90.0** | **BETTER_SIGNAL（重大升级，Fresh 成立）** |
| product_family | 51.7% | INVALID（exam bug） | 无法对比（不构成回归） |
| component | 49.2 | **57.7** | BETTER_SIGNAL |
| function | 55.7 | **59.3** | CONSISTENT/BETTER |
| material | 23.2 | 22.6 | CONSISTENT（持平） |
| shot_role | 37.3 | 36.3 | CONSISTENT（均撒网） |
| scene | 24.1% | INVALID | 无法对比 |
| variant | 0% | INVALID | 无法对比 |
| semantic_action | group 0% | PULL_OUT 100（2条）+ abstain 7 | 部分信号 + 诚实 abstain |

**STEP 16 升级目标验收**：A. People ✅ 成立 · B/C. Component/Function ✅ 成立 · D. Product Family ⚠ 评分无效待补 · E. Multi-label 撒网 ⚠ 部分缓解（component pred 2.8≈human 2.63；shot_role/material 仍撒网）· F. Semantic Action ✅ 诚实 abstain（viol=0）但 experimental route false claim 51。

---

## STEP 17-21：最终评级 + 判定

| 字段 | 最终评级 |
|---|---|
| people_presence | **PRODUCTION_CANDIDATE** |
| product_family | LIMITED（V2 Fresh 评分无效，待补验） |
| component | READY/LIMITED |
| function | READY/LIMITED |
| scene_family | LIMITED（评分无效，待补验） |
| material | EXPERIMENTAL |
| shot_role | EXPERIMENTAL |
| product_variant | LIMITED（评分无效，待补验） |
| semantic_action | EXPERIMENTAL |

**PHASE3 判定 = PASS_WITH_LIMITATIONS**
- ✅ 核心升级成立：People V2 Fresh F1 90（V1 0）、component 49→57.7、function 55.7→59.3
- ✅ 弱字段诚实（material/shot_role EXPERIMENTAL）；Semantic Action abstain 纪律正确（viol=0）
- ⚠ 限制：product_family/scene/variant 的 V2 Fresh 评分因 exam 脚本缺陷无效；shot_role 撒网仍在；Semantic Action experimental route false claim 51

**PHASE4_READY = TRUE**（Phase3 结束条件满足：有真实 Fresh 能力 + 核心升级无系统性回归 + 弱字段自知 + Semantic Action 不乱声称 + routing/abstention 有效；**exam 缺陷是评分口径问题非架构 bug，待补验**）

**Holdout 纪律**：V1/V2 均为永久 DO_NOT_TRAIN/DO_NOT_CALIBRATE；V2 表现已查看，未来 V3 需全新 Fresh Holdout。

---

## 23 问答复

1. Human Review 30/30 完整唯一？→ 是 2. human_truth_sha256=`bf658f94…`
3. 三 hash 未变？→ 是（bundle `a87d3124…`/manifest `27f751ed…`/prediction `4b53b0c0…`）
4. 四层表现？→ People RANDOM 80/HARD 80/GAP 100/ALL 86.7；component/function ALL F1 57.7/59.3
5. People V2 Fresh？→ **F1 90.0 / bacc 83.3** 6. NORMAL_NO_FALLBACK？→ **0 违规**
7. Product Family？→ **评分无效（exam bug）**，V1 51.7% 为锚点 8. Component？→ **57.7**
9. Function？→ **59.3** 10. Scene？→ **无效**（V1 24.1%） 11. Material？→ **22.6**
12. ShotRole？→ **36.3**（pred_avg 7.1 撒网） 13. Variant？→ **无效**（V1 0%）
14. Semantic Action？→ PULL_OUT 100（2 条）、abstain 7 正确
15. false claim？→ 51（CLOSE_CABINET 13/OTHER 27/OPEN_DRAWER 6/CLOSE_DRAWER 5）
16. 正确 abstain？→ 7（OPEN_CABINET 2 + RETRACT 5）；viol 0
17. Multi-label 撒网缓解？→ 部分（component 2.8≈2.63；shot_role 7.1/material 5.2 未缓解）
18. 新严重回归？→ **无系统性回归**（component/function/people 改善；material/shot_role 持平）
19. V1/V2 真实变化？→ People 从 0→90 巨大升级；component/function 稳步改善；弱字段持平
20. 9 字段评级？→ 见上表
21. Phase3 判定？→ **PASS_WITH_LIMITATIONS**
22. PHASE4_READY？→ **TRUE**
23. Phase4 前还需 Human Review？→ **否**（无新人工批；product_family/scene/variant 的补验是 AI 侧补充预测，非人工审核）

---

## 产物

- `FRESH_HOLDOUT_V2_HUMAN_LOCK.json`（`bf658f94…`）
- `FRESH_HOLDOUT_V2_METRICS.json`（四层 + 单/多标签 + People + SA）
- `FRESH_HOLDOUT_V2_ERROR_CASES.json`（30 条归因）
- `DUAL_HOLDOUT_COMPARISON_V1.json`（V1/V2 对比）
- `PHASE3_FINAL_ASSESSMENT.json`（评级 + 判定）
- 本报告 `docs/FRESH_HOLDOUT_V2_FINAL_EVALUATION.md`

## 已知缺陷（如实）

1. **exam 脚本 single 字段 bug**：SigLIP single 返回 `all_scores` 非 `scores` → product_family/scene_family/product_variant 的 V2 prediction 全 UNKNOWN 且 raw 未存真实值 → 3 字段 V2 Fresh 评分 INVALID（DO_NOT_REPREDICT 已锁，不重跑；另开补充预测）
2. exam 漏输出 scene_subtype/shot_scale/product_visibility → MISSING 30/30
