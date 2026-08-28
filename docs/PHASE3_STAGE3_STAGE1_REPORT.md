# Phase 3 Stage 3 — Stage 1 报告（Visual Cognition Hardening 第一停点）

- **日期**：2026-08-28 18:44 ｜ git `e8cf6fd` ｜ 基线：VISION_MODEL_BUNDLE_V1_1（LIMITED）
- **纪律**：未学习/未改 Bundle/未用 Holdout V1 调参/未进 Phase4/未全量 41814

## 已完成

1. **STEP 0**：STAGE2_BASELINE_SNAPSHOT 冻结（V1_1 成绩 + Guard；V1 Holdout 永久测试集）
2. **STEP 1**：Multi-label Overprediction Audit → **确认过预测**（预测 5-8 标签 vs 人工 1-3；4+ 标签 90-100%）
3. **STEP 2**：Multi-label Decision Policy V2 实现（Top-K+gap，CANDIDATE，待 333 验证）
4. **STEP 3 诊断**：People Fresh 0% 根因 = routing 回退 legacy（SigLIP raw 23.3%）；修复方向确认
5. **STEP 10/11**：全库候选发现 + **TARGETED_REVIEW_STAGE3 60 条**（semantic_action 15 / scene_lt 10 / material_lt 10 / function_lt 10 / pure_visual 8 / random 7；与 canonical360+holdout30 隔离、asset 唯一）
6. **STEP 14**：SigLIP 保持 baseline；People/Scene/Material/Variant/Action V2 标记 CANDIDATE

## 十三问

1. **component/function/shot_role 高 label-in 是否过预测？** → **是**（预测 avg 5.6/7.8/7.3 vs 人工 2.5/3.2/2.1；4+ 标签 100%）
2. **预测 vs 人工平均标签数？** → 预测 4.6-7.8，人工 1.0-3.2（见 audit）
3. **People 为什么 Fresh=0？** → routing 回退 legacy（对未审段无输出→全 UNKNOWN）；非 SigLIP 无能力（raw 23.3%）
4. **新 People 方案能否解决？** → **CANDIDATE**：直接采用 SigLIP raw + 轻量 person detector benchmark（下一步）；有望从 0% 提升
5. **Scene 主要错在哪？** → Fresh 24.1% vs dev 37.9（GENERALIZATION_GAP）；Calibration 98% FACTORY 高估；非工厂类别 INSUFFICIENT_SAMPLE
6. **Material 主要问题？** → 岩板主导 + 长尾 support<5（INSUFFICIENT）；microF1 ~23% 稳定但弱
7. **Product Family 是否保持？** → **是**（V1_1 Fresh 51.7% 稳定；Stage3 回归锚点）
8. **Product Variant 是否建立候选？** → CANDIDATE（需 Static+Temporal+ASR 联合，非单帧）
9. **Semantic Action 是否超 Motion Baseline？** → **否**（仍 0%；Farneback 仅 motion evidence）
10. **哪些 action 有真实语义能力？** → **无**（全部 INSUFFICIENT/未建立）
11. **Stage3 需用户再审多少？** → **约 60 条**（TARGETED_REVIEW_STAGE3，已生成候选池；待架构监工批准后启动）
12. **是否真有必要审？** → **是**：60 条聚焦 action/people/scene/material 长尾（避开 FACTORY+ISLAND+岩板+SPEAKING 密集组合）；用于 DEV/Calibration 扩展（非 Holdout）
13. **是否值得继续 Stage3？** → **是**（过预测可修、people 有修复路径、product 已稳定；场景/材质/动作需数据+方案）

## 交付物

- `MULTILABEL_OVERPREDICTION_AUDIT_V1.md` + `.json` ｜ `STAGE3_MODEL_BENCHMARK.md` ｜ 本报告
- `TARGETED_REVIEW_STAGE3.json`（60 条，DEV_ONLY/NOT_HOLDOUT）
- `STAGE2_BASELINE_SNAPSHOT.json` ｜ Policy V2 代码（CANDIDATE）

> **第一停点 STOP**：未启动 60 条人工审核、未改 Bundle、未进 Phase4。待架构监工批准后：审核 ~60 条 → Policy V2 验证 → People/Scene/Material/Variant/Action V2 开发 → Bundle V2 → FRESH_HOLDOUT_V2。
