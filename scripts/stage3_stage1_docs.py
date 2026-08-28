# -*- coding: utf-8 -*-
"""Stage 3 第一停点报告生成（3 份 + TARGETED_REVIEW_STAGE3 已生成）。"""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
REPO = r"C:\Users\admin\github\treecut-v13"
DOCS = os.path.join(REPO, "docs")
commit = subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"],
                        capture_output=True, text=True, encoding="utf-8").stdout.strip()
NOW = datetime.now().strftime("%Y-%m-%d %H:%M")

ov = json.load(open(os.path.join(DATA_ROOT, "MULTILABEL_OVERPREDICTION_AUDIT_V1.json"), encoding="utf-8"))
tg = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3.json"), encoding="utf-8"))

# ============ MULTILABEL_OVERPREDICTION_AUDIT_V1.md ============
A = []
A.append(f"""# Multi-label Overprediction Audit V1（Stage 3 STEP 1）

- **日期**：{NOW} ｜ 数据：Calibration333 + Fresh Holdout30（AI final routed prediction vs Human truth）
- **结论（铁证）**：**存在系统性过预测（撒网）**——AI 平均输出 5-8 个标签，人工 1-3 个。

## 1. 标签数统计

| 字段 | 人工 avg(ho) | 预测 avg(ho) | delta | 预测 1 标签% | 预测 4+ 标签% | 判定 |
|---|---|---|---|---|---|---|
""" + "\n".join(
    f"| {f} | {v['holdout_human']['avg']} | {v['holdout_prediction']['avg']} | {v['holdout_overprediction_avg_delta']} | {v['holdout_prediction']['pct_1label']}% | {v['holdout_prediction']['pct_4plus']}% | **{v['verdict']}** |"
    for f, v in ov["fields"].items()) + f"""

| 字段 | 人工 avg(cal) | 预测 avg(cal) |
|---|---|---|
""" + "\n".join(
    f"| {f} | {v['calibration_human']['avg']} | {v['calibration_prediction']['avg']} |"
    for f, v in ov["fields"].items()) + f"""

## 2. 解读

- Holdout：material 预测 4.63 vs 人工 0.97；function 预测 7.83 vs 人工 3.23；shot_role 预测 7.33 vs 人工 2.13
- **预测 1 标签比例 = 0%**（全部输出 ≥3 标签），4+ 标签 90-100% → **label-in 90-97% 的"高命中"是撒网假象**，precision 被稀释（microF1 仅 23-56%）
- 之前 `_classify_multi_emb` 的 `s >= top1 - 0.06` 阈值过宽 → 几乎全选

## 3. 处置（CANDIDATE，STEP 2）

- **Multi-label Decision Policy V2**（已实现于 `static_vision_v2.MULTI_POLICY`）：per-field Top-K（material 2 / component 3 / function 3 / shot_role 3）+ score gap 0.10 + min score
- 阈值**只能在 Calibration333 调整**（禁止用 Holdout V1）；本审计已确认问题，Policy V2 的 333 验证在 Stage3 下一轮执行
- 预期：压缩预测集 → label-in 略降但 precision/microF1 显著升
""")
with open(os.path.join(DOCS, "MULTILABEL_OVERPREDICTION_AUDIT_V1.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(A))

# ============ STAGE3_MODEL_BENCHMARK.md ============
MB = []
MB.append(f"""# Stage 3 Model Benchmark（第一停点）

- **日期**：{NOW} ｜ 基线：VISION_MODEL_BUNDLE_V1_1（SigLIP base，EN prompt）

## People V2 诊断（STEP 3，CANDIDATE）

Fresh 30 people 成绩 0% 的**直接根因**：routing 回退 legacy（旧方案对未审段无输出 → 全 UNKNOWN）。
SigLIP raw（未回退时）在 Holdout30：acc 23.3%（cov 63.3%，YES recall 21%）。
→ 修复方向：People V2 **直接采用 SigLIP raw 输出**（不再 fallback legacy），并 benchmark 轻量 person detector（下一步）。

## Scene / Material / Variant / Semantic Action（CANDIDATE）

- Scene V2：multi-frame 聚合已启用（5 帧均值）；Fresh 24.1%（dev 37.9）gap 分析见 STAGE3_STAGE1 报告；balanced slice 需素材（非工厂极少 → INSUFFICIENT_SAMPLE）
- Material V2：global+crop/texture 证据链 CANDIDATE（素材长尾 INSUFFICIENT：实木等 support<5）
- Product Variant：联合 Static+Temporal+ASR 判断 CANDIDATE
- Semantic Action：Object+Motion+Fusion（DRAWER+外拉→OPEN_DRAWER 等）CANDIDATE；本轮确认 Farneback 仅为 motion evidence

## 约束

- 所有 Stage3 结果必须与 V1_1 比较（STAGE2_BASELINE_SNAPSHOT.json）
- product_family 不得退化（V1_1 Fresh 51.7% 为回归锚点）
- 模型更换须真实下载/加载/GPU 推理（禁凭排行换）
""")
with open(os.path.join(DOCS, "STAGE3_MODEL_BENCHMARK.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(MB))

# ============ PHASE3_STAGE3_STAGE1_REPORT.md ============
S = []
S.append(f"""# Phase 3 Stage 3 — Stage 1 报告（Visual Cognition Hardening 第一停点）

- **日期**：{NOW} ｜ git `{commit}` ｜ 基线：VISION_MODEL_BUNDLE_V1_1（LIMITED）
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
""")
with open(os.path.join(DOCS, "PHASE3_STAGE3_STAGE1_REPORT.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(S))

desktop = os.path.join(os.environ.get("USERPROFILE", r"C:\Users\admin"), "Desktop")
for fn in ("PHASE3_STAGE3_STAGE1_REPORT.md", "MULTILABEL_OVERPREDICTION_AUDIT_V1.md", "STAGE3_MODEL_BENCHMARK.md"):
    shutil.copy2(os.path.join(DOCS, fn), os.path.join(desktop, fn))
    print("copied ->", os.path.join(desktop, fn))
