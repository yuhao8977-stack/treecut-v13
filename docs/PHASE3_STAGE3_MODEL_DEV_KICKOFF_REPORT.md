# PHASE3 STAGE3 — MODEL DEVELOPMENT KICKOFF 最终报告（DUAL TRACK）

> 生成：2026-08-28 · 提交 `e607f93`（push 完成）
> 判定：POST-REVIEW DATA VALUE AUDIT = **PASS** → 进入 DUAL TRACK 模型开发
> 纪律：不默认建 25/30/60 人工批 · 不建 Bundle V2 / Fresh Holdout V2 / Phase4 / 全量 41814 · Fresh Holdout V1 仅 READ-ONLY 参考

---

## 一、PRE-STEP 0：支持量口径核验（你发现的疑点已查明）

**问题**：报告自称 Calibration333，却出现 FACTORY 352 / 岩板 356（单标签超过 333）。

**根因**：统计误用了 `canonical_human_truth is_current=1` **全表 360 段**，而非 Calibration333 manifest 的 333 段。多出的 27 段是早期批次 SINGLE_REVIEW 段（25 段 FACTORY），不在 manifest 内。

| 来源 | unique 段 | FACTORY | 岩板(occurrence) |
|---|---|---|---|
| canonical360 全表（误用，已弃） | 360 | 352 | 356 |
| **Calibration333（manifest 交集，正确）** | **333** | **327** | **331** |

✅ 修正后所有单标签 support ≤ 333、单标签类别总和 = unique 数（无违规）；多标签明确为 label occurrence。
✅ 只修统计口径，**未改任何 Human Truth**。
✅ 产物：`SUPPORT_COUNT_INTEGRITY_AUDIT.json`；`STAGE3_POST_REVIEW_LABEL_SUPPORT.json` 已修正。

**修正后 Action 开发门槛（Cal333 + Stage3 有效 59）**：
PERSON_SPEAKING 211 · PULL_OUT 52 · RETRACT 36 · STATIC_DISPLAY 46 · OPEN_DRAWER 12 · OPEN_CABINET 11 · CLOSE_CABINET 10 → **READY_FOR_DEV**；CLOSE_DRAWER 7 → LIMITED；OPERATE_SOCKET 2 / OPEN_SINK_COVER 4 → INSUFFICIENT。

---

## 二、PRE-STEP 1：3 条 Human QA 二次裁决（已生成，待你裁决）

规则判定（action_group ↔ action_sequence 合法映射）3 条全部 **conflict=True**：

| 段 | group | sequence | 判定 |
|---|---|---|---|
| 2cf01ef8 | STATIC | PERSON_SPEAKING, OPEN_CABINET, CLOSE_CABINET, OPEN_THEN_CLOSE_DRAWER | 矛盾 |
| bc6189b6 | SPEAKING | OPEN_SINK_COVER | 矛盾 |
| d81be396 | STATIC | PERSON_SPEAKING, OPEN_SINK_COVER | 矛盾 |

✅ 已生成 `STAGE3_ACTION_QA_ADJUDICATION.json`（3 条）并接入 Review Center（`STAGE3_ACTION_QA_ADJUDICATION` 任务）：只允许修改 action_group / action_sequence / comment / status，**不显示 AI 预测**，走 revision 不覆盖 Human Lock。**你只需裁决这 3 条，不必重审 60。**

---

## 三、TRACK A：模型开发（已 READY 的能力立即开发）

### A1+A2 PeoplePresenceAnalyzerV2 ✅ READY_CANDIDATE
- 新实现：`people_analyzer_v2.py`（YOLOv8n person 检测 primary + SigLIP fallback）
- 输出：YES / NO / UNKNOWN + `max_person_conf / frame_hit_count / frames_sampled`；**不输出姓名/年龄/性别/身份**
- **A2 threshold DEV tuning**（POST-REVIEW DEV TUNING DATA，重新对 387 有效段跑 YOLO）：

| conf | TP/FP/TN/FN | P | R | Sp | F1 | bacc |
|---|---|---|---|---|---|---|
| 0.40 | 273/36/77/1 | 88.3 | 99.6 | 68.1 | 93.7 | 83.9 |
| 0.50 | 273/34/79/1 | 88.9 | 99.6 | 69.9 | 94.0 | 84.8 |
| **0.70 冻结** | **270/29/84/4** | **90.3** | **98.5** | **74.3** | **94.2** | **86.4** |

- **最终 threshold = 0.70**（F1 最高且 FP 最少）；分集合 CAL333 F1 94.6 / STAGE3 F1 92.1
- 冻结参数写入 `PEOPLE_ANALYZER_V2_DEV_EVAL.json`

### A3+A4+A5 SemanticActionAnalyzerV1 ⚠ EXPERIMENTAL（如实）
- 新实现：`semantic_action_v1.py`（规则基 state-change + ASR/OCR 精确短语 + component hints + 光流仅作 motion evidence）
- **架构纪律**：禁 Farneback→semantic label；禁"收纳"作 RETRACT 强证据；输出 atomic 级（不 group 冒充 atomic）
- DEV（390 段，atomic 级）：

| action | support | P | R | F1 |
|---|---|---|---|---|
| OPEN_DRAWER | 11 | 100 | 18.2 | **30.8** |
| PULL_OUT | 52 | 53.3 | 15.4 | 23.9 |
| OTHER | 67 | 19.9 | 97.0 | 33.1 |
| RETRACT / CLOSE_DRAWER / OPEN_CABINET / CLOSE_CABINET / PERSON_SPEAKING / STATIC_DISPLAY / OPEN_SINK_COVER | — | — | — | **0（ASR 未命中，需补视觉状态证据）** |

- **结论**：仅 OPEN_DRAWER（P100）/ PULL_OUT（弱）/ OTHER 兜底建立初能力；整体 **EXPERIMENTAL**，V1 证明 ASR 覆盖不足 → Semantic Action 需接入 B2 的视觉状态变化证据后才能上 READY。

### A6+A7+A8+A9 Multi-label 合并 DEV
| 字段 | 策略 | 合并 DEV | 判定 |
|---|---|---|---|
| component | V2（Top3+gap0.10+min0.02） | F1 35.9 / macroF1 53.2 / pred 2.66 vs human 1.43 | **READY_CANDIDATE** |
| function | V2 | F1 33.2 / macroF1 52.6 | **READY_CANDIDATE** |
| material | V1（阈值 0.06） | F1 22.2（MIXED/弱） | **EXPERIMENTAL / FALLBACK**（不强行升级） |
| shot_role | V1（V3 网格未达门槛） | F1 36.9 / pred_avg 7.0（过预测） | **EXPERIMENTAL**（保留 V1） |
| product_family | SigLIP | Cal333 52.7% / Stage3 72.7% vs Holdout 51.7% | **READY_CANDIDATE**（无退化） |

产物：`MULTILABEL_STAGE3_DEV_EVAL.json`

---

## 四、TRACK B：数据缺口发现（不生成真值，只找候选）

改进发现器（禁"收纳"/"家"子串；component-aware）在 **40,595 段候选池** 上的结果：

| 缺口 | 候选 | 唯一 asset | 状态 |
|---|---|---|---|
| **OPERATE_SOCKET** | **1,940** | **908** | ✅ CANDIDATES_FOUND（插座素材其实丰富！旧发现器漏了） |
| **CUSTOMER_HOME** | **2,367** | **819** | ✅ CANDIDATES_FOUND |
| **SOLID_WOOD（实木）** | **801** | **335** | ✅ CANDIDATES_FOUND |
| OPEN_SINK_COVER | 5 | 2 | ⚠ WEAK（不足） |
| SHOWROOM | 6 | 2 | ⚠ WEAK（不足） |
| CLOSE_DRAWER | **0** | 0 | ❌ LIBRARY_DATA_GAP（素材库确实没有） |

**关键结论**：OPERATE_SOCKET / CUSTOMER_HOME / SOLID_WOOD **候选充足** → 值得小批验证 precision；CLOSE_DRAWER 及 FLOATING/FLOOR / 奢石/大理石/不锈钢/玻璃 / INSTALLATION_SITE 标 **LIBRARY_DATA_GAP**（不再靠人工标注解决）。产物：`STAGE3_DATA_GAP_DISCOVERY_V2.json`

**B6 最小批触发**：总高质量唯一候选 >>15 且 ≥3 类可增 support → **触发**；建议 **15-20 条**（非默认 25-30），只从高质量唯一候选抽样验证发现器 precision。

---

## 五、VISION_STAGE3_CANDIDATE_V2 逐字段状态（非 Bundle V2）

| 字段 | Primary | Fallback | 状态 |
|---|---|---|---|
| people_presence | PeopleAnalyzerV2（YOLO conf 0.70） | SigLIP | **READY_CANDIDATE** |
| component / function | SigLIP V2 | — | **READY_CANDIDATE** |
| product_family | SigLIP | — | **READY_CANDIDATE** |
| action_sequence | SemanticActionV1（规则基） | — | **EXPERIMENTAL** |
| material / shot_role | SigLIP V1 | — | **EXPERIMENTAL / FALLBACK** |
| scene_family / product_variant | SigLIP | — | **LIMITED**（长尾素材缺失） |
| FLOATING/FLOOR · 奢石/大理石/不锈钢/玻璃 · INSTALLATION_SITE · CLOSE_DRAWER | — | — | **LIBRARY_GAP** |

---

## 六、16 问答复（完整）

1. **FACTORY352/岩板356 来源？** → canonical360 全表误用（27 段早期批次）；正确 Cal333 = FACTORY 327 / 岩板 331
2. **修正后真实 support？** → 见 PRE-STEP 0（Cal333 严格 333 段；Action 门槛：8 类 READY / CLOSE_DRAWER LIMITED / OPERATE_SOCKET 2 / OPEN_SINK_COVER 4）
3. **3 条 QA 冲突？** → 全部 conflict=True，已生成 3 条裁决任务接入 Review Center，待你裁决
4. **People V2 最终 DEV？** → 合并 387 段 F1 94.2 / bacc 86.4（CAL333 94.6 / STAGE3 92.1）
5. **最终 People threshold？** → **0.70**（Stage3 DEV 冻结）
6. **Semantic Action 真正建立能力？** → OPEN_DRAWER（P100）、PULL_OUT（弱）、OTHER（兜底）；整体 EXPERIMENTAL
7. **仍不足的 Atomic？** → RETRACT / CLOSE_DRAWER / OPEN_CABINET / CLOSE_CABINET / OPEN_SINK_COVER / PERSON_SPEAKING / STATIC_DISPLAY
8. **Component/Function V2 成立？** → 是（macroF1 53.2 / 52.6，READY_CANDIDATE）
9. **ShotRole 减少撒网？** → 否（V3 网格 F1 降 >2pt，保留 V1 EXPERIMENTAL）
10. **Material 仍 Fallback？** → 是（V1 F1 22.2，EXPERIMENTAL/FALLBACK）
11. **Product Family 保持？** → 是（52.7 / 72.7 vs 51.7 锚点，无退化）
12. **缺口数据高质量候选？** → OPERATE_SOCKET 1940 / CUSTOMER_HOME 2367 / SOLID_WOOD 801（唯一 asset 908/819/335）；OPEN_SINK_COVER 5 / SHOWROOM 6 / CLOSE_DRAWER 0
13. **是否还需用户审核？** → 需要**极小批**（非默认 25-30）
14. **最小 Batch 多少？** → **15-20 条**（从 OPERATE_SOCKET / CUSTOMER_HOME / SOLID_WOOD 高质量唯一候选抽样验证 precision）
15. **如果不需要，为什么？** → 不适用；但纯 LIBRARY_GAP 类（CLOSE_DRAWER / FLOATING/FLOOR / 奢石等）不再靠审核
16. **是否具备冻结 Bundle V2 条件？** → **尚不具备**：Semantic Action 仍 EXPERIMENTAL（需补视觉状态证据）、3 条 QA 未裁决、Material/ShotRole 为 EXPERIMENTAL。冻结条件：Semantic Action ≥3 类 F1≥30 + QA 裁决完 + 小批验证完 → 才建 VISION_MODEL_BUNDLE_V2 → FRESH_HOLDOUT_V2

---

## 七、产物清单（DATA_ROOT / docs / src）

- `SUPPORT_COUNT_INTEGRITY_AUDIT.json` · `STAGE3_ACTION_QA_ADJUDICATION.json`
- `PEOPLE_ANALYZER_V2_DEV_EVAL.json` · `SEMANTIC_ACTION_ANALYZER_V1_DEV_EVAL.json`
- `MULTILABEL_STAGE3_DEV_EVAL.json` · `STAGE3_DATA_GAP_DISCOVERY_V2.json`
- `STAGE3_POST_REVIEW_LABEL_SUPPORT.json`（口径已修正）
- `src/treecut/services/people_analyzer_v2.py` · `semantic_action_v1.py`
- `docs/VISION_STAGE3_CANDIDATE_V2.md` · `docs/PHASE3_STAGE3_MODEL_DEVELOPMENT_REPORT.md`
- 测试 **157 passed**（新增 9 个模型开发回归测试）

## 八、下一步（等你决定）

1. **你裁 3 条 QA**（Review Center → STAGE3_ACTION_QA_ADJUDICATION）
2. 是否让我**抽 15-20 条最小批**（OPERATE_SOCKET / CUSTOMER_HOME / SOLID_WOOD 高质量唯一候选）验证发现器 precision —— 不默认建 30
3. Semantic Action V1 补**视觉状态变化证据**（B2 发现器同源）后重估
4. 全部冻结后才建 VISION_MODEL_BUNDLE_V2 → FRESH_HOLDOUT_V2
