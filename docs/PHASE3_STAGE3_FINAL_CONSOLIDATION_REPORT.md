# PHASE3 STAGE3 — FINAL CONSOLIDATION REPORT（Bundle V2 FREEZE + Holdout V2 题目冻结）

> 状态：**Phase3 Stage3 = COMPLETE ✅（DATA/DEV WORK COMPLETE）**
> 日期：2026-08-29
> 判定：NO_MORE_MANUAL_REVIEW_FOR_STAGE3 · 冻结 VISION_MODEL_BUNDLE_V2 · 冻结 FRESH_HOLDOUT_V2 题目（未 AI 作答）
> 纪律：未训练/未调参/未用 Holdout V1 调参/未进 Phase4/未全量 41814/未在 Bundle 冻结前生成 V2 prediction

---

## 0. Final Bookkeeping（FACTORY 398/399）

**FACTORY=398 正确**（用真实 segment_id 重算，`STAGE3_FACTORY_BOOKKEEPING.json`）：

| dataset | unique | valid | FACTORY | UNKNOWN | EXCLUDED |
|---|---|---|---|---|---|
| Calibration333 | 333 | 333 | 327 | 3 | 0 |
| Stage3 V3_1 | 60 | 59 | **53** | 5 | 1（a678c4b5） |
| Mini18 | 18 | 18 | 18 | 0 | 0 |
| **合并** | **411** | **410** | **398** | 8 | 1 |

**解释 399 之谜**：`327+54+18=399` 的 54 是**含 EXCLUDED 的行数**（Stage3 60 条中 a678c4b5 EXCLUDED 且 scene=FACTORY）；过滤后 Stage3 FACTORY=53 → **327+53+18=398** ✓。报告 398 无误，无需修正；唯一补充：明确 EXCLUDED 不进分母。

**Q1 最终值：FACTORY=398。 Q2：Stage3 最终 DEV unique segment = 411（Cal333 333 + V3_1 60 + Mini18 18，去重后无交集）。**

---

## 1. Stage3 开发数据身份冻结（STAGE3_FINAL_DEV_SNAPSHOT.json）

- **snapshot_sha256 = `f4d2a8f594175b4eef533734a0f5261be20dee6909961c01bc1a11bf240cdfd2`**
- Cal333 manifest + Stage3 V3_1 Human Lock（`a6cc7f30…`）+ Mini18 Human Lock（`9838bf58…`）+ QA Adjudication Lock
- 总 DEV 411 段；dictionary ANNOTATION_DICTIONARY_V2_1
- Bundle V2 模型选择必须可追溯到此 Snapshot

---

## 2-13. 9 字段 Final Routing（VISION_MODEL_BUNDLE_V2_LOCK.json）

| 字段 | 状态 | Primary | Policy/阈值 | DEV 证据 | 已知限制 |
|---|---|---|---|---|---|
| people_presence | **READY** | PeopleAnalyzerV2(YOLOv8n) | conf **0.70** | F1 94.2 / bacc 86.4 | FP 3 hard-case；无身份输出 |
| product_family | **READY/LIMITED_READY** | SigLIP EN | top-1 | Cal 52.7% / S3 72.7% | V1_1 锚点 51.7% 只作回归参考 |
| component | **READY_CANDIDATE** | SigLIP | V2 Top3/gap0.10/min0.02 | F1 35.9 / macroF1 53.2 | F1 中等 |
| function | **READY_CANDIDATE** | SigLIP | V2 | F1 33.2 / macroF1 52.6 | 同上 |
| scene_family | **LIMITED** | SigLIP | top-1 | FACTORY 398 偏科 | 长尾 LIBRARY_GAP |
| material | **EXPERIMENTAL/FALLBACK** | SigLIP | **V1**（V2 已证退化） | F1 22.2 | 实木/奢石/大理石/不锈钢/玻璃 INSUFFICIENT |
| shot_role | **EXPERIMENTAL** | SigLIP | **V1**（V3 未达门槛） | F1 36.9 / pred_avg 7.0 | KNOWN_OVERPREDICTION_RISK |
| product_variant | **LIMITED** | SigLIP | conservative top-1 | EXTENDABLE 有证据 | FLOATING/FLOOR LIBRARY_GAP |
| semantic_action | **EXPERIMENTAL** | SemanticActionRouterV2 | per-action | 见 router | state-change 未解决 |

**People 路由（Q3/Q4）**：
- Primary：PeoplePresenceAnalyzerV2（YOLOv8n conf=0.70）
- **YOLO 正常运行无 person 检测 = 合法 NO，绝不 fallback SigLIP**（已修复原 bug：`if hits:` 空时误触发 fallback）
- SigLIP fallback 仅限技术失败（YOLO runtime/frame/detector 异常），此时可用 SigLIP 或 UNKNOWN

**SemanticActionRouterV2 per-action（Q10/Q11）**：

| action | provider | F1 | 状态 |
|---|---|---|---|
| OPEN_DRAWER | V1_RULE | 30.8 | V1 优于 V2 |
| PULL_OUT | V1_RULE_SIMPLE | 25.4 | V1/V2 相近，用简单稳定 |
| CLOSE_DRAWER | V2_STATE_EXPERIMENTAL | 11.1 | V2 非零能力 |
| CLOSE_CABINET | V2_STATE_EXPERIMENTAL | 16.0 | V2 真实增益 |
| **OPEN_CABINET** | **NO_CLAIM** | 0 | **禁声称已有能力** |
| **RETRACT** | **NO_CLAIM** | 0 | **禁声称已有能力** |
| OPERATE_SOCKET | INSUFFICIENT_SAMPLE | — | support=2 |
| OPEN_SINK_COVER | INSUFFICIENT_SAMPLE | — | support=4 |
| PERSON_SPEAKING/STATIC_DISPLAY | MOTION_BASELINE | — | motion 仅 evidence |
| OTHER | DEFAULT | 33.1 | 兜底 |

**Q5-Q9 答复**：见上表（product_family 保留 SigLIP EN + V1_1 锚点；component/function V2；material 保留 V1 因 V2 退化；shot_role 保留 V1 因 V3 无法减撒网保 F1；scene/variant LIMITED）。

---

## 14-16. Bundle V2 Freeze（VISION_MODEL_BUNDLE_V2_LOCK.json）

- **bundle_lock_sha256 = `01b7afa9b75986c53bf871005b47f3f3e4e565b2c22c086c5065164d7187aec9`**（64 位，重算自洽）
- git_code_commit = `c4ff7e5b…` · stage3_dev_snapshot_hash = `f4d2a8f5…`
- 定义：**截至 Stage3 结束每字段 best-known frozen route 的不可变组合**；LIMITED/EXPERIMENTAL/FALLBACK 允许共存
- 通过条件全部满足：route 冻结、model/prompt/policy 冻结、QA 完成、DEV 数据身份冻结、无未解决评估 bug、不再 Stage3 tuning

**Q12 9 字段状态**：READY×4（people/product_family/component/function）+ LIMITED×2（scene/variant）+ EXPERIMENTAL×3（material/shot_role/semantic_action）。
**Q13 lock sha256**：`01b7afa9…`。 **Q14：Phase3 Stage3 = COMPLETE。**

---

## 17. Stage3 最终结论 + Backlog

**Semantic Action 不再阻塞 Bundle V2**（如实 EXPERIMENTAL）。Future Improvement Backlog（future V3 / 新数据到达时处理，非当前 blocker）：
- fine-grained object state detection（几何/边缘/开度）
- semantic action temporal model
- scene / material / variant long-tail
- shot-role overprediction

---

## 18-23. Fresh Holdout V2 题目冻结

- 30 条：RANDOM 10 / HARD 10 / GAP 10（全独立 asset）
- **manifest_sha256 = `27f751ed402f81e2c3477341ad562218f2b67cf1902c764d5735397767d9e64b`**
- 与 Cal333 + Stage3 60 + Mini18 + Holdout V1 30 全部 segment/asset 隔离
- **GAP 不伪造不存在的类别**（FLOATING/奢石/INSTALLATION_SITE 不强行入卷；代表 semantic action / scene / material / variant / shot-role 薄弱区域）
- **model-answer blind**：只用 metadata/embedding diversity/motion 分层，未查看 Bundle V2 prediction
- near-dup 正式审计：EXACT=0 / NEAR=0（结果见 FRESH_HOLDOUT_V2_NEARDUP_AUDIT.json）

---

## 20 问答复（Q1-Q20 见各节）

1. FACTORY=**398**（327+53+18；399 是含 EXCLUDED 的加法） 2. DEV unique=**411**
3. People route=YOLOv8n conf 0.70 4. **YOLO NO 不触发 SigLIP fallback**（已修复；仅技术失败 fallback）
5. product_family=SigLIP EN + V1_1 锚点 6. component/function=V2
7. material 保留 V1（V2 退化 F1 10.1 vs 22.0） 8. shot_role 保留 V1（V3 无法减撒网保 F1）
9. scene/variant=LIMITED 10. semantic_action=SemanticActionRouterV2 per-action
11. **OPEN_CABINET / RETRACT 禁声称已有能力**（F1=0）；OPERATE_SOCKET/OPEN_SINK_COVER INSUFFICIENT
12. READY×4 / LIMITED×2 / EXPERIMENTAL×3
13. bundle_lock_sha256=`01b7afa9…` 14. **Stage3 COMPLETE** 15. **无任何 Human Review 需要**
16. Holdout V2=30 条完全未见 17. RANDOM 10 / HARD 10 / GAP 10
18. 与全部 DEV/HoldoutV1 EXACT=0 NEAR=0（见 FRESH_HOLDOUT_V2_NEARDUP_AUDIT.json）
19. manifest_sha256=`27f751ed…`
20. **待架构监工检查后**才允许 V2 AI FIRST-PASS EXAM（当前 STOP）

---

## 产物

- `STAGE3_FACTORY_BOOKKEEPING.json` · `STAGE3_FINAL_DEV_SNAPSHOT.json`
- `VISION_MODEL_BUNDLE_V2_LOCK.json`（sha `01b7afa9…`）+ `docs/VISION_MODEL_BUNDLE_V2.md`
- `FRESH_HOLDOUT_V2_MANIFEST_LOCK.json` + `FRESH_HOLDOUT_V2_NEARDUP_AUDIT.json`
- 修复：`people_analyzer_v2.py`（YOLO NO 不再 fallback SigLIP）
- 本报告 `docs/PHASE3_STAGE3_FINAL_CONSOLIDATION_REPORT.md`
