# PHASE3 STAGE3 — SEMANTIC ACTION V2 + MINI BATCH 报告（三轨并行第一停点）

> 状态：**TRACK 1 ✅ / TRACK 2 ✅ / TRACK 3 如实（Semantic Action V2 未达基础能力门槛）**
> 日期：2026-08-29
> 纪律：不冻结 Bundle V2 / 不建 Fresh Holdout V2 / 不再生成 30/60/100 人工批 / Fresh Holdout V1 仅 READ-ONLY

---

## TRACK 1：3 条 Human QA 裁决 ✅（已由用户完成）

**裁决结果：3 条全部确认原标注正确（before == after，无修订）。**

| 段 | group | sequence | 裁决 |
|---|---|---|---|
| 2cf01ef8 | STATIC | PERSON_SPEAKING, OPEN_CABINET, CLOSE_CABINET, OPEN_THEN_CLOSE_DRAWER | 确认原标注 |
| bc6189b6 | SPEAKING | OPEN_SINK_COVER | 确认原标注 |
| d81be396 | STATIC | PERSON_SPEAKING, OPEN_SINK_COVER | 确认原标注 |

**含义**：`action_group` 是主类别（STATIC=静态展示/讲解，SPEAKING=人物讲解），`action_sequence` 是完整动作流 —— **两者可同时成立**（讲解中演示开柜/开盖是合理组合）。之前的 rule_check 要求 group 与任一 atomic 有交集是**过严**，实际 schema 语义允许这种组合。

✅ 已生成 `STAGE3_ACTION_QA_ADJUDICATION_LOCK.json`（revision 记录，**未覆盖** HUMAN_LOCK）；atomic action support 已重算。**Q1: 3 条 QA 完成。 Q2: 修订后 support 见 lock（无实质变化，3 条确认原值）。**

---

## TRACK 2：Mini 最小验证批 ✅（18 条，已冻结并接入 Review Center）

**TARGETED_REVIEW_STAGE3_MINI_V1**（`TARGETED_REVIEW_STAGE3_MINI_V1.json`）：

| 类别 | 配额 | 选中 | 采样依据 |
|---|---|---|---|
| OPERATE_SOCKET | 8 | 8 | ASR 插座短语 + 视觉 TRACK_SOCKET/APPLIANCE_SLOT component 证据（2 条双证据 score 3.5） |
| CUSTOMER_HOME | 5 | 5 | ASR 住宅语义 + 视觉 scene≠FACTORY（含 INSTALLATION_SITE 2 条） |
| SOLID_WOOD | 5 | 5 | ASR 实木短语（视觉 wood score 弱 -0.03~0.01，如实标注） |
| **合计** | 18 | **18** | 全独立 asset（无重复素材） |

**Near-Dup 最终审计**（`STAGE3_MINI_BATCH_FINAL_NEARDUP.json`）→ **PASS**：

| 对照 | EXACT | NEAR | UNCERTAIN |
|---|---|---|---|
| vs Calibration333 | 0 | 0 | 84（灰区） |
| vs Stage3 60 | 0 | 0 | 9 |
| vs Fresh Holdout V1 | 0 | 0 | 14（READ-ONLY leak check） |
| Mini 内部 | 0 | 0 | 0 |

✅ 已接入 Review Center（`TARGETED_REVIEW_STAGE3_MINI_V1`，blind，只显示采样目标：插座动作/客户家/实木）；done=0/18。
**Q3: Mini 批 18 条。 Q4: OPERATE_SOCKET 8 / CUSTOMER_HOME 5 / SOLID_WOOD 5。 Q5: 与 Cal/Stage3/Holdout/内部 全部 EXACT=0 NEAR=0（PASS）。**

**Mini 批目的**：验证 candidate discovery precision（插座/客户家/实木 三类发现器命中率），审核完成后再统计 precision 并决定是否继续用该发现器扩数据。

---

## TRACK 3：SemanticActionAnalyzerV2（如实：视觉状态变化产生部分增益，未达基础能力门槛）

### 实现（`semantic_action_v2.py`）
- **ObjectStateEvidence**：DRAWER(CLOSED/PARTIAL/OPEN) · CABINET_DOOR(CLOSED/OPEN) · EXTENDABLE_SECTION(RETRACTED/EXTENDED) · SINK_COVER(CLOSED/OPEN) · SOCKET(IDLE/INTERACTED)
- 状态检测：SigLIP 状态描述相似度（方案B）+ 运动几何提示（方案A，仅 hint 不定标签）
- 动作 = 状态迁移推导（CLOSED→OPEN = OPEN_DRAWER 等）；光流仅 supporting evidence

### DEV 对照（108 关键动作段，atomic 级；Q6-Q12）

| action | V1 P/R/F1 | V2 P/R/F1 | ΔF1 |
|---|---|---|---|
| OPEN_DRAWER | 100/18.2/**30.8** | 13.3/36.4/19.5 | -11.3 |
| CLOSE_DRAWER | 0/0/0 | 9.1/14.3/**11.1** | +11.1 |
| OPEN_CABINET | 0/0/0 | 0/0/0 | 0 |
| CLOSE_CABINET | 0/0/0 | 10.0/40.0/**16.0** | +16.0 |
| PULL_OUT | 72.7/15.4/25.4 | 72.7/15.4/25.4 | 0 |
| RETRACT | 0/0/0 | 0/0/0 | 0 |

**Q13: 目前真正建立的 semantic action = 0 个（6 个关键动作无一 F1≥30）。**
**Q14: 视觉 state-change 产生部分增益**（CLOSE_DRAWER 0→11.1、CLOSE_CABINET 0→16.0 且 R 40%），但 OPEN_DRAWER 退化（SigLIP 状态描述把 PARTIAL 误判 OPEN → P 崩）。**增益真实但不充分**。

**根因**：SigLIP 通用模型对"抽屉开度"这类细粒度状态区分弱（CLOSED vs PARTIAL vs OPEN 相似度过高）；方案B 需要更针对性的状态检测（如边缘/间隙几何特征）或轻量微调。

---

## 16 问答复

1. **3 条 QA 完成？** → 是，用户已裁决，全部确认原标注正确（group 主类别 + sequence 完整流可共存）
2. **修订后 Atomic Action support？** → 无实质变化（3 条确认原值），见 `STAGE3_ACTION_QA_ADJUDICATION_LOCK.json`
3. **Mini 批最终多少条？** → **18 条**（OPERATE_SOCKET 8 / CUSTOMER_HOME 5 / SOLID_WOOD 5）
4. **三类各多少？** → 8 / 5 / 5
5. **Mini 批 near-dup？** → 全部 EXACT=0 NEAR=0（Cal/Stage3/Holdout/内部），PASS
6. **V2 相比 V1 提升？** → CLOSE_DRAWER +11.1、CLOSE_CABINET +16.0；OPEN_DRAWER -11.3；净变化有限
7. **OPEN_DRAWER？** → V2 F1 19.5（P 13.3/R 36.4；状态误判 PARTIAL→OPEN）
8. **CLOSE_DRAWER？** → V2 F1 11.1（P 9.1/R 14.3，从 0 起步）
9. **OPEN_CABINET？** → 0（SigLIP 状态描述未捕获柜门开合）
10. **CLOSE_CABINET？** → V2 F1 16.0（R 40%）
11. **PULL_OUT？** → 25.4（与 V1 相同，motion hint 无增益）
12. **RETRACT？** → 0
13. **真正建立几个 semantic action？** → **0**（6 关键动作无一 F1≥30；目标"至少 3 个"未达成）
14. **视觉 state-change 增益？** → 部分真实（close 类动作从 0 起步），但 OPEN 类误判抵消 → **不足以建立基础能力**
15. **是否仍需 Mini 批 Human Truth 才能继续？** → **是**：Mini 18 条人工审核是下一步关键（验证发现器 precision + 补充真实动作样本）；Semantic Action 需更多含真实状态变化的真值
16. **是否接近冻结 VISION_STAGE3_CANDIDATE_V2？** → **接近但未达成**：People/Component/Function/ProductFamily 已 READY；**Semantic Action 是唯一技术阻塞**（需改进状态检测或等 Mini 批真值）

---

## 下一步（等你决定）

1. **你审 Mini 18 条**（Review Center → TARGETED_REVIEW_STAGE3_MINI_V1）—— 这大概率是 Phase 3 最后一批人工 DEV 标注
2. 审核后：统计三类发现器 precision（插座/客户家/实木）
3. Semantic Action V2 改进方向：① 针对开度的几何/边缘状态检测（非通用 SigLIP 描述）；② Mini 批真值加入后重估
4. 全部冻结后 → VISION_STAGE3_CANDIDATE_V2 → Bundle V2 → FRESH_HOLDOUT_V2

## 产物清单

- `TARGETED_REVIEW_STAGE3_MINI_V1.json` + `STAGE3_MINI_BATCH_DISCOVERY_AUDIT.json` + `STAGE3_MINI_BATCH_FINAL_NEARDUP.json`
- `STAGE3_ACTION_QA_ADJUDICATION_LOCK.json`
- `SEMANTIC_ACTION_ANALYZER_V2_DEV_EVAL.json`
- `src/treecut/services/semantic_action_v2.py`
- Review Center 新增：`TARGETED_REVIEW_STAGE3_MINI_V1`（18 条，0/18）
