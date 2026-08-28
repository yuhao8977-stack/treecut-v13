# -*- coding: utf-8 -*-
"""PRE-HOLDOUT FINAL CHECK 报告生成 + Action 矛盾标注。"""
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

abl = json.load(open(os.path.join(DATA_ROOT, "FIELD_ABLATION_V1.json"), encoding="utf-8"))
lock = json.load(open(os.path.join(DATA_ROOT, "VISION_MODEL_BUNDLE_V1_1_LOCK.json"), encoding="utf-8"))
hlock = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_MANIFEST_LOCK.json"), encoding="utf-8"))
temp = json.load(open(os.path.join(DATA_ROOT, "TEMPORAL_ACTION_EVAL_V1.json"), encoding="utf-8"))

# Action 矛盾修复：DRAWER 统计如实保留 + UNRELIABLE 标注
temp["per_group"]["DRAWER"]["unreliable"] = True
temp["per_group"]["DRAWER"]["unreliable_reason"] = (
    "observed F1=1.0 (support=11) 是运动阈值巧合：光流把高运动一律判 DRAWER，"
    "而 DRAWER 真值恰为高运动段；但真值最多的 SPEAKING(sup=160) F1=0 证明模型无语义区分能力。"
    "统计事实保留，标注 UNRELIABLE_OBSERVED_RESULT，不代表学会 DRAWER 动作。")
temp["action_group_accuracy"] = round(temp["action_group_accuracy"], 1)
with open(os.path.join(DATA_ROOT, "TEMPORAL_ACTION_EVAL_V1.json"), "w", encoding="utf-8") as f:
    json.dump(temp, f, ensure_ascii=False, indent=1)

R = []
R.append(f"""# Phase 3 Stage 2 — PRE-HOLDOUT METRIC INTEGRITY FINAL CHECK

- **日期**：{NOW} ｜ git `{commit}` ｜ 判定：GPU/Vision PASS；Gate = PASS WITH METRIC-INTEGRITY FIX（本报告核验）
- **禁止**：未锁 AI 答案、未开始人工盲审、未用 Holdout 调参

## 1. scene n_valid=462 根因（硬阻塞已查明并修复）

**根因**：`stage2_gate.py` 单标签评估中，预测错误样本**同时 `fp+=1` 与 `fn+=1`**，`n_valid = tp+fp+fn` 使分母翻倍（scene: 125+132+205=462）。这是**评估代码 bug，非数据 join 问题**：
- canonical is_current=1 恰 360 行、无重复 sid；333 段 scene 真值有效=330（3 UNKNOWN）
- multi 字段不受影响（标签级 TP/FP/FN + 段级 valid 分开）

**修复**：`n_valid = tp + fp + unk`（样本数）；`fn = fp + unk`（真值类未命中）单独用于 recall/macroF1。已修正代码并**用同一批冻结预测重跑**。

## 2. 修正后指标（全部 ≤333，n_unique_segment 口径）

| 字段 | n | baseline acc | **stage2 acc** | stage2 cov | stage2 cond | stage2 unk | trivial |
|---|---|---|---|---|---|---|---|
| scene | 330 | 3.9% | **37.9%** | 77.9% | 48.6% | 22.1% | 98.2% (FACTORY) |
| product_family | 332 | 28.9% | **52.7%** | 76.5% | 68.9% | 23.5% | 99.4% (ISLAND) |
| shot_scale | 303 | 0% | **35.3%** | 71.9% | 49.1% | 28.1% | 27.6% (WIDE) |
| people | 330 | 20.0% | 8.5% | 50.3% | 16.9% | 49.7% | 71.2% (YES) |

multi（microF1，n 不变）：material 22.1% / component 24.4% / function 21.5% / shot_role 19.9%；per-class 见 FIELD_ABLATION（岩板 F1 78.6；实木等 INSUFFICIENT_SAMPLE）

**修正影响**：先前 27.1%/42.6%/25.8%/6.0% 均**低估**（分母翻倍）——修正后更高；**结论方向不变**。

## 3. 之前哪些指标受影响？

- 单标签 4 字段（scene/product/shot_scale/people）的 accuracy/coverage/unk/n_valid **全部受影响**（分母翻倍 → 数值低估）
- multi 字段（material/component/function/shot_role）**不受影响**
- Trivial baseline（用 len(rows)=333 或 majority 计数）不受影响（未用 hv）

## 4. Field Routing 是否需要变化？

**不需要**（关系未变，按指令不擅自改）：
- product：修正后 52.7% > baseline 28.9%（READY_FOR_HOLDOUT，但 **≠ PRODUCTION_READY**，不接管全库）
- people：8.5% < baseline 20.0%（**FALLBACK 不变**）
- scene/其余：EXPERIMENTAL 不变

## 5. Action 矛盾解释（DRAWER support=11 / F1=100）

**统计事实如实保留**：DRAWER support=11、observed F1=1.0。
**UNRELIABLE_OBSERVED_RESULT 标注**：光流把高运动段一律判 DRAWER，DRAWER 真值恰为高运动 → F1=100 是运动阈值巧合；真值最多的 SPEAKING（support=160）F1=0 → 模型无语义区分能力。**不因"好看"保留，不因"不好看"删除**——如实报告并解释。
- action_group 总体 accuracy **3.3%**（331 有效）→ Farneback = **Temporal Motion Baseline V1**（非语义 action 分类器）
- **无任何 support≥5 且语义可信的 action 类**（SPEAKING 160 但 0%；EXTEND 75 但 0%；DRAWER 11 为伪高）

## 6. Bundle 不可变身份（LOCK）

- **VISION_MODEL_BUNDLE_V1_1_LOCK.json** 已生成：
  - bundle_id=VISION_MODEL_BUNDLE_V1_1 ｜ git_code_commit=`{lock['git_code_commit']}`
  - static=google/siglip-base-patch16-224（en-v1）｜ prompt_hash=`{lock['prompt_hash'][:12]}`
  - field_routing=FIELD_ROUTING_V1 ｜ dictionary=V2.1 ｜ calibration_manifest_hash=`{lock['calibration_manifest_hash'][:12]}`
  - **bundle_lock_sha256 = `{lock['bundle_lock_sha256']}`**
- 30 条 AI 预测必须引用 bundle_id + bundle_lock_sha256

## 7. Holdout 试卷 LOCK

- **FRESH_HOLDOUT_V1_MANIFEST_LOCK.json**：30 条（RANDOM 10 / HARD 10 / GAP 10）、segment+asset 唯一、与 360 零重叠、近重复 2 对已替换
- **manifest_sha256 = `{hlock['manifest_sha256']}`**
- guard：DO_NOT_TRAIN / DO_NOT_CALIBRATE / DO_NOT_REPREDICT（锁释放前）
- **仅锁"试卷题目"，尚未生成 AI 答案**

## 8. 九问回答

1. scene n_valid 曾为 462？ → 评估代码单标签 fn/fp 双计导致分母翻倍（125+132+205=462）；非 join 重复
2. 正确 evaluation unique segment？ → **333**（每字段 n_valid ≤333：scene 330 / product 332 / shot_scale 303 / people 330）
3. 修正后 scene/product/material？ → scene 37.9% / product 52.7% / material microF1 22.1%
4. 哪些指标受影响？ → 单标签 4 字段 accuracy/coverage/unk/n_valid（低估）；multi 与 trivial 不受影响
5. Field Routing 需变化？ → **否**（product>baseline、people<baseline 关系未变）
6. DRAWER F1=100 与"无有效 action"矛盾？ → 统计保留 + UNRELIABLE（运动阈值巧合；SPEAKING 160/0% 证无语义能力）；action_group 3.3% → motion baseline
7. Bundle lock hash？ → **`{lock['bundle_lock_sha256']}`**
8. Holdout manifest hash？ → **`{hlock['manifest_sha256']}`**
9. 是否满足"锁 AI 预测 → 盲审"？ → **条件满足**（指标口径修正、routing 稳定、双 LOCK 就绪）；等架构监工批准后：Bundle V1_1 → 30 条 AI 预测 → 落库 hash 锁定 → 人工盲审

## 交付物

- `PHASE3_STAGE2_PRE_HOLDOUT_FINAL_CHECK.md`（本报告）
- `FIELD_ABLATION_V1.json`（修正）· `TEMPORAL_ACTION_EVAL_V1.json`（UNRELIABLE 标注）
- `VISION_MODEL_BUNDLE_V1_1_LOCK.json` · `FRESH_HOLDOUT_V1_MANIFEST_LOCK.json`

> **完成后停止**：未生成 Holdout AI prediction、未盲审、未用 Holdout 调参。等待架构监工 FINAL PASS → 执行"AI 先考 30 题 → 锁答案 → 人工盲审"协议。
""")
report = os.path.join(DOCS, "PHASE3_STAGE2_PRE_HOLDOUT_FINAL_CHECK.md")
with open(report, "w", encoding="utf-8") as f:
    f.write("\n".join(R))
desktop = os.path.join(os.environ.get("USERPROFILE", r"C:\Users\admin"), "Desktop")
shutil.copy2(report, os.path.join(desktop, "PHASE3_STAGE2_PRE_HOLDOUT_FINAL_CHECK.md"))
print("报告 ->", report)
print("已复制桌面")
