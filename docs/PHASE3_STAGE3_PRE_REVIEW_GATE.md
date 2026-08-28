# Phase 3 Stage 3 — PRE-REVIEW DATA VALUE GATE

- 日期：2026-08-28 18:50 ｜ 判定：Stage1 PASS WITH REVIEW-BATCH REDESIGN REQUIRED
- 纪律：未启动人工审核/未改 Bundle/未用 Holdout V1 调参/未进 Phase4/未全量 41814

## 1. Multi-label Policy V2 在 Calibration333 验证（STEP 1-2）

| 字段 | V2 预测标签 avg | 人工 avg | microP | microR | microF1 | label-in | 注 |
|---|---|---|---|---|---|---|---|
| material | 1.98 | 1.0 | 7.6% | 15.0% | 10.1% | 15.0% | 待收紧 |
| component | 2.66 | 1.06 | 25.0% | 48.2% | 32.9% | 56.6% | 待收紧 |
| function | 2.75 | 1.46 | 23.5% | 44.2% | 30.7% | 53.5% | 待收紧 |
| shot_role | 2.72 | 0.66 | 22.4% | 35.0% | 27.4% | 47.6% | 待收紧 |

**结论**：
- **Policy V2（Top-K+gap）已把预测标签从旧 Holdout 的 5-8 压到 2-3**（接近人工 1-1.5）——过预测显著缓解
- 但 per-field 仍需收紧：**shot_role 建议 Top-1/2（2.72 vs 0.66）、material Top-1**（1.98 vs 1.0）；threshold 只准在 333 调
- precision 仍低（7.6-25%）→ 策略之外，**模型语义能力本身弱**（诚实）

## 2. People Benchmark（333 DEV，STEP 3-4）

- SigLIP raw：acc 8.5%（YES 237 主导，recall 低）；legacy：0%（无输出）
- Fresh V1 0% = routing 回退 legacy（已确认）；**需真 person detector**（YOLO/ONNX 轻量，CANDIDATE 下轮真实 benchmark）
- **People V2：CANDIDATE**（不强行选更差模型）

## 3. 数据缺口审计（STEP 5-7）

- **Action（真缺口）**：SPEAKING 160 / EXTEND 75 / OTHER 65 / STATIC 20 / **DRAWER 11**；
  **OPEN_DRAWER 3 / CLOSE_DRAWER 1 / OPEN_CABINET 0 / OPERATE_SOCKET 0 / OPEN_SINK_COVER 1** → **抽屉/柜门/插座/水槽动作几乎无样本**
- **Variant**：**EXTENDABLE_ISLAND 已有 184** / STANDARD 10 / FLOATING 0 / FLOOR 0 → variant 配额降至 6（补标准/悬浮/落地）
- **People**：YES 237 / NO 93 → 需平衡补 NO + 模型冲突
- **Scene/Material**：FACTORY 327 / 岩板 331 → 长尾 1-3（INSUFFICIENT，诚实）

## 4. TARGETED_REVIEW_STAGE3_V2（STEP 8-13）

- 旧 Batch 保留 DEPRECATED_CANDIDATE_BATCH_V1；新 V2：**60 条 = action 20 / people 12 / variant 6 / scene 6 / material 5 / visual 11**
- **multi-target 43/60（72%）**：同一段可服务 People+Action / Variant+Action 等（如"有人操作伸缩岛台" → PRIMARY_PRODUCT_VARIANT + SECONDARY_PEOPLE+SEMANTIC_ACTION）
- 诚实配额：material requested 5 / discovered 25 / selected 5；variant discovered 214 / selected 6（悬浮/落地/标准）；scene 选 6（"家"误命中多，人工确认）
- **Action 20 聚焦抽屉/柜门/插座/水槽**（此前 15 含大量已有伸缩/讲解 → 价值低）
- near-dup：segment/asset 唯一（排除 390）；visual 近重复标注待 embedding 复核

## 5. 十四问

1. Policy V2 减少过预测？→ **是**（333 预测 2-3 标签 vs 旧 5-8）
2. Precision 提高？→ 相对旧撒网显著（P 7.6-25% vs 撒网时更低）；仍低（模型语义弱）
3. Recall 损失？→ R 15-48%（可控，未崩溃）
4. 每字段 Top-K？→ material 2/component 3/function 3/shot_role 3（CANDIDATE：shot_role→1-2、material→1，333 验证下轮）
5. People detector 优于 SigLIP raw？→ **CANDIDATE**（SigLIP raw 333 8.5% 弱；需真 detector 对比）
6. People V2 值得采用？→ CANDIDATE（修复 routing 后 SigLIP raw 至少 >0%）
7. 各 Action support？→ 见上（DRAWER 11；OPEN_DRAWER 3；CABINET/SOCKET 0）
8. 原 Action 15 够？→ **不够**（含已有伸缩/讲解）；新 20 聚焦真缺口
9. Variant support？→ EXTENDABLE 184 / STANDARD 10 / FLOATING 0 / FLOOR 0
10. 为何这样分配？→ Gate 缺口驱动（Action/People 优先；Variant 减额因已足）
11. multi-target 多少？→ **43/60**
12. Scene/Material 实找到？→ material 25 选 5；scene "家"误命中多、选 6 需人工确认
13. near duplicate？→ segment/asset 0 重复；visual 待复核
14. 比旧 Batch 价值？→ **是**（聚焦真缺口 + multi-target 72%）

## 6. 交付物

- `MULTILABEL_POLICY_V2_DEV_EVAL`（含于 PRE_REVIEW_GATE_VALIDATION.json）· `PEOPLE_V2_BENCHMARK`（同）
- `STAGE3_LABEL_SUPPORT_AUDIT`（同）· `TARGETED_REVIEW_STAGE3_V2.json`（60，multi-target 43）
- 本报告 `PHASE3_STAGE3_PRE_REVIEW_GATE.md`

> **STOP**：未启动 60 条审核。批准后：Review Center 接入 TARGETED_REVIEW_STAGE3_V2（显示采样目标、隐藏 AI 猜测）→ 审核 60 条（DEV 扩展）→ Policy 收紧 + People detector + Action 语义开发 → Bundle V2。
