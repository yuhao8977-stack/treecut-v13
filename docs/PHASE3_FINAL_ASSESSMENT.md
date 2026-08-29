# PHASE3 FINAL ASSESSMENT（Phase 3 最终毕业判定）

> 状态：**Phase 3 = PASS_WITH_LIMITATIONS · PHASE4_READY = TRUE**
> 日期：2026-08-29
> 依据：DEV 411 + Fresh Holdout V1（V1_1）+ Fresh Holdout V2（Bundle V2）双独立考试

---

## 一、双考试最终结论

| 字段 | V1_1→HoldoutV1 | V2→HoldoutV2 | 变化 |
|---|---|---|---|
| people_presence | 0%（unk 100） | **F1 90.0 / bacc 83.3** | **重大升级 ✅** |
| product_family | 51.7% | 评分无效（exam bug） | 待补验 |
| component | microF1 49.2 | **57.7** | **改善 ✅** |
| function | microF1 55.7 | **59.3** | **改善 ✅** |
| material | microF1 23.2 | 22.6 | 持平 |
| shot_role | microF1 37.3 | 36.3 | 持平（撒网） |
| scene_family | 24.1% | 评分无效 | 待补验 |
| product_variant | 0% | 评分无效 | 待补验 |
| semantic_action | group 0% | PULL_OUT 2/2 + abstain 7 | 部分信号 + 诚实 abstain |

## 二、9 字段最终评级

| 字段 | 评级 | 一句话依据 |
|---|---|---|
| people_presence | **PRODUCTION_CANDIDATE** | Fresh F1 90 / viol 0；V1 曾全 UNKNOWN |
| product_family | LIMITED（评分待补） | V1 51.7% 锚点；V2 Fresh 因 exam 缺陷无效 |
| component | **READY/LIMITED** | Fresh F1 57.7 / macro 60.4 |
| function | **READY/LIMITED** | Fresh F1 59.3 / macro 60.9 |
| scene_family | LIMITED（评分待补） | V1 24.1%；长尾 LIBRARY_GAP |
| material | EXPERIMENTAL | Fresh F1 22.6；岩板 82.4 但撒网 |
| shot_role | EXPERIMENTAL | Fresh F1 36.3；pred_avg 7.1 撒网 |
| product_variant | LIMITED（评分待补） | V1 0%；FLOATING/FLOOR LIBRARY_GAP |
| semantic_action | EXPERIMENTAL | PULL_OUT 100（2 条）+ abstain 正确；false claim 51 |

## 三、Phase3 结束条件逐项

- ✅ Bundle V2 有真实 Fresh 能力（People/Component/Function 升级在全新 30 条成立）
- ✅ 核心升级无系统性回归（material/shot_role 持平，无崩溃）
- ✅ 弱字段知道自己弱（material/shot_role/variant 诚实 LIMITED/EXPERIMENTAL）
- ✅ Semantic Action 不乱声称（NO_CLAIM abstain viol=0）
- ✅ Routing/abstention 有效（People NO 不 fallback；SA 正确 abstain）
- ⚠ 待补验：product_family/scene/variant 的 V2 Fresh 评分（exam 脚本缺陷，非架构 bug）

**结论：PASS_WITH_LIMITATIONS（允许进入 Phase 4，但携带 3 字段评分待补验的已知限制）**

## 四、PHASE4_READY = TRUE

Knowledge Brain V2 可以建立在冻结的视觉认知层上。进入 Phase 4 前：
- 无需新人工审核（无数据缺口阻塞）
- 建议先补验 product_family/scene/variant 的 V2 Fresh（AI 侧补充预测，非人工）

## 五、永久 Holdout 纪律

- Fresh Holdout V1 & V2：**永久 DO_NOT_TRAIN / DO_NOT_CALIBRATE**
- V2 表现已查看 → 未来 V3 开发若参考 V2 错误，V2 只能作 KNOWN REGRESSION BENCHMARK；真正独立验证必须建全新 Fresh Holdout
- Stage3 DEV 411：可作未来训练/校准（非 Holdout）

## 六、Phase3 最终声明

**Phase 3（视觉认知层）正式结束（PASS_WITH_LIMITATIONS）。**
TreeCut 视觉层现状：people/component/function 有真实 Fresh 能力；scene/material/shot_role/variant 有限或实验；semantic_action 诚实实验。系统知道自己会什么、不会什么 —— 这比虚假全绿有价值。

下一步：**PHASE 4 — KNOWLEDGE BRAIN V2**（行业知识 / 业务规则 / 内容角色 / 模板体系接入冻结视觉层），需你的 Phase 4 启动指令。
