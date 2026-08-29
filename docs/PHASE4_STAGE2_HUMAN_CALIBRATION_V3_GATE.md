# PHASE4 STAGE 2 — HUMAN CALIBRATION V3 GATE

> 状态：**V3 简化单状态校准 UI 完成 · Smoke PASS（6 项）· 12 条校准就绪（待人工执行）· STOP**
> 日期：2026-08-29
> 背景：V2 = UI_CONTAMINATED / INVALID_FOR_CALIBRATION（重叠 128 次 / POSSIBLE 全选 / evidence 12/12 SUFFICIENT）
> 纪律：12 segment identity 不变 · AI_LOCK/V1/V2 不变（V1/V2 历史全部保留）· 不执行 Stage2.1

---

## 核心决策：只校准引擎实际可输出的 10 个标签

**不再用 21 needs + 18 values + 完整 Taxonomy 重审**。本轮唯一目标：校准当前 BusinessCognition 引擎"实际已经支持输出的标签"。

**AI_OUTPUT_VOCABULARY_V1**（从 SEM_001-007 程序化提取，`BUSINESS_COGNITION_CALIBRATION_TAXONOMY_V1.json`）：
- **5 user_needs**：STORAGE / CHARGING_POWER / GUEST_CAPACITY / DINING / OFFICE
- **5 business_values**：STORAGE_EFFICIENCY / POWER_CONVENIENCE / FLEXIBLE_CAPACITY / DINING_CONVENIENCE / WORK_FROM_HOME

⚠️ 这是 **Calibration Scope**，不是完整 Human Business Taxonomy——不得解释为 TreeCut 只有这 10 个标签。来源 = 全局 Engine Capability（非当前 segment AI 答案）→ **不构成 AI answer leakage**。

## 1. 12 segment 锁 ✅

`HUMAN_CALIBRATION_V3_MANIFEST.json`：12 段与 Adjudication V2 **set 完全相等**（`set_equal=True` 证明）。未重采样、未替换、未改 AI_LOCK、未重跑 AI Cognition——V1/V2/V3 可在同 segment 上比较稳定性。

## 2. V2 正式降级 ✅

`HUMAN24_TRUTH_RELIABILITY_STATUS.json` 记录：**HUMAN_ADJUDICATION_V2 = UI_CONTAMINATED / INVALID_FOR_CALIBRATION**（role: UI_FAILURE_DIAGNOSTIC）。**12 条原始记录全部保留，未删除。**

## 3-5. 每标签严格单状态 ✅

**UI 不再使用两个独立多选框**。每标签一行，点击循环切换：
`NOT_SUPPORTED（默认）→ CLEARLY_SUPPORTED → POSSIBLE_BUT_INSUFFICIENT → UNKNOWN → NOT_SUPPORTED`

- 同一 label **只能属于一个状态**（dict 单值结构天然互斥；保存校验强制 10 标签每恰一状态）
- 数据库层 `label_states` 为 `{label: state}` 单值映射 → **CLEARLY/POSSIBLE 重叠在结构上不可能**

## 6. 四态定义显示在 UI 顶部 ✅

| 状态 | 定义（UI 顶部直接显示） |
|---|---|
| CLEARLY_SUPPORTED | 仅根据当前视频和可靠证据，这个业务意义已经被明确证明。 |
| POSSIBLE_BUT_INSUFFICIENT | 这个方向可能成立，但当前镜头本身不足以证明。 |
| NOT_SUPPORTED | 当前视频不支持这个业务意义。 |
| UNKNOWN | 信息不足，我无法可靠判断。 |

## 7. Evidence / Confidence 无默认必选 ✅

- `evidence_sufficiency`：SUFFICIENT/PARTIAL/INSUFFICIENT/UNKNOWN，**未选禁止保存**
- `conflict_observed`：YES/NO/UNKNOWN，**未选禁止保存**（YES 时可选 conflict_type：SCENE_CONTEXT/ASR_CONTEXT/MATERIAL/OTHER）
- `review_confidence`：HIGH/MEDIUM/LOW，**未选禁止保存**；LOW 完全合法，UI 不暗示 HIGH 更好

## 8. 联动校验（非阻塞 warning，无硬上限）✅

- `evidence=INSUFFICIENT` + 存在 CLEARLY → 弹"你将证据标为不足，但同时标记了明确支持"
- `CLEARLY > 6/10` → 弹"选择了较多明确支持标签，请确认由该镜头直接证明而非可联想"
- `POSSIBLE > 5` → 弹"可能相关标签较多，请确认在判断当前镜头而非整个产品可能性"（**不设硬上限**，可保存）

## 9. 零泄漏 ✅

V3 UI 禁止显示：AI 当前 segment 输出 / AI confidence / AI rule / AI knowledge / Human V1 / Human V2 / 旧 FP·TP / 旧评分 / sampling class / 入选原因。

## 10. Evidence 显示 ✅

`[HUMAN_VERIFIED]` / `[MODEL — MEDIUM_HIGH]` / `[MODEL — LIMITED]` / `[MODEL — LOW]` / `[MODEL — VERY_LOW]`；semantic_action 仍标 VERY_LOW。

## 11-12. V3 新表 + 保存校验 ✅

新表 `stage2_business_cognition_calibration_v3`（不覆盖 v1/v2 表）：segment_id / label_states_json / evidence_sufficiency / conflict_observed / conflict_type / review_confidence / review_duration_seconds / comment / schema_version / created_at。
保存校验：10 标签每恰一状态（禁止缺失/重复/双状态/非法值）。

## 13. V3 评分语义 ✅

| AI SUPPORTED vs Human | 结果 |
|---|---|
| CLEARLY_SUPPORTED | **SUPPORTED_TRUE（TP）** |
| POSSIBLE_BUT_INSUFFICIENT | **OVERCONFIDENT_CLAIM**（非 TP） |
| NOT_SUPPORTED | **SUPPORTED_FALSE（FP）** |
| UNKNOWN | **SUPPORTED_HUMAN_UNKNOWN**（不进 precision 分母，单独统计） |

## 14. Calibration 指标（scorer 已实现）

`SUPPORTED_TRUE / SUPPORTED_OVERCONFIDENT / SUPPORTED_FALSE / SUPPORTED_HUMAN_UNKNOWN` +
`supported_precision_clear / overconfidence_rate / false_claim_rate` + 每 label 结果。

## 15. Human Reliability 比较（V1 vs V3；V2 仅诊断）

V1 标签 → V3 CLEARLY / POSSIBLE / NOT_SUPPORTED / UNKNOWN 迁移统计。特别回答：**V1 把多少"关联性"误标成"明确支持"**。

## 16. 原 6 FP 重判（V3 最终状态）

STORAGE / STORAGE_EFFICIENCY / CHARGING_POWER / POWER_CONVENIENCE 逐项给 V3 状态；**search_intent = NOT_REVIEWED**（本轮不审）。

## 17. V3 可否作为 Calibration Truth

综合 review_confidence / evidence_sufficiency / label sparsity / V1→V3 迁移 / 内部语义一致性 / duration 异常 / UNKNOWN 使用情况 → 允许 `CALIBRATION_TRUTH_RELIABLE / PARTIALLY_RELIABLE / UNRELIABLE`（**不机械用 0.85**）。

## 18. Smoke Test（Gate §21）✅ 全 PASS

- **A** 词汇表 10 标签、CUSTOMIZATION 不在（UI 不显示）✅
- **B** STORAGE=CLEARLY + POWER_CONVENIENCE=POSSIBLE 保存 → label_states 单状态互斥 ✅
- **C** evidence 未选 → 禁止保存 ✅
- **D** confidence 未选 → 禁止保存 ✅
- **E** AI SUPPORTED POWER_CONVENIENCE vs Human POSSIBLE → **OVERCONFIDENT 不得 TP** ✅
- **F** mock 已删除 ✅

## 19. 13 问答复

1. **V2 标记 UI_CONTAMINATED？** → **是**（数据保留）
2. **V3 只审 10 标签？** → **是**（5 needs + 5 values，引擎程序化提取）
3. **不再审 39 个？** → **是**
4. **每标签严格单状态？** → **是**（循环按钮，dict 互斥）
5. **CLEARLY/POSSIBLE 重叠不可能？** → **是**（结构级保证）
6. **Evidence 无默认必选？** → **是**
7. **Confidence 无默认必选？** → **是**
8. **过度多选提示无硬限制？** → **是**（3 条非阻塞 warning）
9. **AI/V1/V2 零泄漏？** → **是**
10. **12 segment identity 不变？** → **是**（set_equal=True）
11. **AI SUPPORTED vs Human POSSIBLE → OVERCONFIDENT 非 TP？** → **是**（smoke E 验证）
12. **Smoke Test 全 PASS？** → **是**（A-F 六项）
13. **可正式开始 V3 12 条？** → **是（READY）**

## 产物
- `BUSINESS_COGNITION_CALIBRATION_TAXONOMY_V1.json`（10 标签，引擎提取）
- `HUMAN_CALIBRATION_V3_MANIFEST.json`（12 段锁）
- `HUMAN24_TRUTH_RELIABILITY_STATUS.json`（V2=UI_CONTAMINATED 标记）
- `src/treecut/services/phase3_review_ui.py`（`_CalibrationV3Form` + `validate_calibration_v3`）
- `src/treecut/services/annotation_governance.py`（`save_business_cognition_calibration_v3` 新表）
- `src/treecut/services/review_center.py`（HUMAN_CALIBRATION_V3 任务）
- `scripts/stage4_calibration_taxonomy.py` · `stage4_calibration_v3_manifest.py` · `stage4_calibration_v3_score.py` · `stage4_calibration_v3_smoke.py`
- `tests/test_stage2_cognition.py`（24）
- 本报告 `docs/PHASE4_STAGE2_HUMAN_CALIBRATION_V3_GATE.md`

## 停点

**STOP** —— 等你状态正常时，GUI 人工审核中心 → **Stage2 Human Calibration V3（12 条·10 标签单状态校准）** → 完成 12 条 → 运行 `stage4_calibration_v3_score.py`。未自动开始人工审核 · **Stage2.1 继续冻结** · 未进 Stage3。
