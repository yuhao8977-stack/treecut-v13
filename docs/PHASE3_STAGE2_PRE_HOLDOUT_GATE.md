# Phase 3 Stage 2 — PRE-HOLDOUT READINESS GATE

- **日期**：2026-08-28 17:11 ｜ git `ed9907c` ｜ 判定：GPU/Vision Engineering PASS；Gate 本报告补齐后待架构监工复核
- **禁止**：30 条人工盲审未开始；AI 答案未锁定；未用 holdout 调参

## 1-4. 指标定义与 Trivial Baseline（全部统一口径 = accuracy，另有 macroF1/coverage/cond/eff/unk 明细）

**场景（scene_family）**：SigLIP(EN) 各指标 = accuracy **27.1%** / macroF1 见 FIELD_ABLATION / coverage **55.6%** / conditional **48.6%** / effective 27.1% / UNKNOWN 15.8% / n_valid 462
- **Always-FACTORY trivial = 98.2%** → **SigLIP 27.1% << 98.2%（accuracy 口径下 FAILED vs trivial）**——偏科所致；真实视觉信号（覆盖 55.6%）成立，但 **不得称"提升"**，标 EXPERIMENTAL
- 此前"19.7% eff" = **effective_correct_rate（=accuracy，因本字段无 UNKNOWN 真值）**；修正英文 prompt 后为 27.1%

**公平对比（同批 333 段、同英文 prompt）**：**SigLIP 27.1% vs CLIP 14.1%** → SigLIP 真实 1.9 倍优于 CLIP（此前 20vs333 比较不成立，已废弃）

**material**：microF1 22.1%（P13.3/R64.8）；**Always-岩板 trivial microF1 ≈ 99.4%** → SigLIP << trivial；
per-class：岩板(sup=331) F1 78.6；**实木(sup=1)/奢石/大理石/肤感/不锈钢/玻璃(sup=0) 全部 INSUFFICIENT_SAMPLE**

**product_family**：SigLIP 42.6% > baseline 28.8%（**真实超旧方案**）；trivial(ISLAND)=99.4%

**people**：SigLIP 6.0% < baseline 19.6%（**退化 → FALLBACK**）；trivial(YES)=71.2%

**shot_scale**：SigLIP 25.8%（trivial 27.6%）；**component/function/shot_role**：24.4%/21.5%/19.9%（均 < trivial，EXPERIMENTAL）

## 5. Multi-label 评估口径修正（Fresh Holdout 前必须确定）

当前 exact_set_match=0 根因：**truth 为单值、prediction 为集合**，exact 要求完全相等几乎不可能。
**修正规则（V1）**：
1. 真值（canonical 单值）视为**单元素集合**（如 岩板 → {岩板}）；
2. 单标签主指标 = **集合包含命中（label-in-set accuracy）**：prediction ∋ truth；
3. micro/macro F1 按集合 TP/FP/FN 计算（现行）；
4. exact_set_match 仅作严格参考，不作为通过标准；
5. **正式 Holdout 评价采用：label-in-set accuracy + microF1 + per-class（support≥5）**，写入待建 HOLDOUT_EVAL 协议。

## 6. Ablation（TEXT vs VISION vs MULTIMODAL）

- **TEXT_ONLY** = baseline（rules+clip-v1，ASR/OCR/规则主导）
- **VISION_ONLY** = SigLIP(EN)（英文 prompt，GPU）
- **MULTIMODAL** = 字段级 best-known-route 组合（= FIELD_ROUTING_V1 的 primary 集合；完整 Fusion V2 加权融合标注 CANDIDATE，下轮实现）
- 结论：**product 42.6%（vision）> 28.8%（text）→ vision 真实增益**；scene/component/function/shot_role 视觉信号存在但未超 trivial；**people 视觉退化**；component/function 提升**部分来自 ASR 关键词**（融合口径），非纯视觉——报告如实区分。

## 7. Temporal 重新定性

- Farneback 正式名：**Temporal Motion Baseline V1**（motion magnitude/direction/change evidence）
- 实测：action_group accuracy **3.3%**（331 有效；DRAWER 11 支持 F1=100 纯巧合；SPEAKING 160 支持 F1=0）；sequence exact 0.9%
- **结论：非语义动作识别器**；action 走 motion evidence + 静态视觉 + ASR + fusion（EXPERIMENTAL）

## 8. Holdout 近重复审计（SigLIP embedding，代表帧）

- **EXACT 1 对**（sim 0.9995）：`994c9c8e…`(low_evidence) ~ Calibration `fc961eab…` → **已替换**
- **NEAR 1 对**（0.9521）：`aed254a0…` ~ `7316e048…` → **已替换**
- 替换后 30 条仍 = 10 random + 10 low_evidence + 10 coverage_gap，segment/asset 均唯一，与 360 零重叠
- UNCERTAIN 75 对（0.88-0.92）→ 素材库同风格画面，不判重复（记录）

## 9. Bundle 版本

- `VISION_MODEL_BUNDLE_V1` **保留为 CANDIDATE SNAPSHOT**（勿删）
- 本次修改：SigLIP prompt 中→英（**已重跑 333**）、字段路由、temporal 职责 → 创建 **VISION_MODEL_BUNDLE_V1_1** 并冻结（模型参数未变，仅 routing/prompt/职责）

## 10-13. 十三问

1. scene 19.7% 是什么指标？ → **effective_correct_rate（=accuracy）**；英文 prompt 修正后 27.1%
2. Always-FACTORY 同指标？ → **98.2%**
3. SigLIP 是否超过 trivial？ → **否（27.1% < 98.2%），EXPERIMENTAL**（视觉信号在，偏科扭曲 accuracy）
4. material 13.6% 具体？ → 中文 prompt 旧值；英文 prompt 后 **microF1 22.1%**
5. Always-岩板？ → **microF1 ≈99.4%**
6. multi-label 口径修正？ → **是（label-in-set accuracy + per-class(sup≥5) 规则已定）**
7. 哪些字段 Vision-only 真增益？ → **product（42.6>28.8）**；scene/component/function/shot_role 有信号未超 trivial；people 无
8. product 最终 route？ → **primary=SigLIP(EN)（42.6% > 28.8%）**，fallback=旧规则；variant=FALLBACK
9. Farneback 是 motion baseline 还是 semantic action？ → **motion baseline（action_group 3.3%）**
10. 哪些 action 样本足够？ → **无**（SPEAKING 160 但 0%；EXTEND 75；其余 <20；无 support≥5 且 F1>0 的类）
11. 30 条视觉近重复？ → **2 对已替换**；当前 30 条 CLEAN（审计记录）
12. 最终 Bundle 版本？ → **VISION_MODEL_BUNDLE_V1_1**
13. 是否满足锁 AI 预测并开始盲审？ → **条件满足**（routing/口径/隔离就绪）；等架构监工批准后执行：Bundle V1_1 → 30 条 AI 预测 → hash 锁定 → DO_NOT_REPREDICT → 人工盲审

## 交付物
- `FIELD_ROUTING_V1.md` · `PHASE3_STAGE2_PRE_HOLDOUT_GATE.md`（本报告）
- `FIELD_ABLATION_V1.json` · `TEMPORAL_ACTION_EVAL_V1.json` · `HOLDOUT_NEAR_DUP_AUDIT.json`
- `FRESH_HOLDOUT_V1_CANDIDATES.json`（rev2，已替换 2 条）
- `VISION_MODEL_BUNDLE_V1_1.md`

> 完成后停止：未启动人工盲审、未锁 AI 答案、未用 holdout 调参。等待架构监工复核后进入盲审协议。
