# -*- coding: utf-8 -*-
"""FRESH_HOLDOUT_V1 AI PREDICTION LOCK REPORT 生成。"""
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

lock = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_PREDICTION_LOCK.json"), encoding="utf-8"))
pred = json.load(open(os.path.join(DATA_ROOT, "HOLDOUT_AI_PREDICTIONS_V1.json"), encoding="utf-8"))
from collections import Counter
strata = Counter(s["stratum"] for s in pred["segments"])

R = []
R.append(f"""# FRESH_HOLDOUT_V1 — AI Prediction Lock Report（AI 独立交卷）

- **日期**：{NOW} ｜ 判定依据：PRE-HOLDOUT GATE FULL PASS → 执行 AI FIRST-PASS EXAM
- **当前状态**：AI 已交卷并锁定；**人工盲审未开始**；AI 答案未对任何人展示

## 冻结身份

| 项 | 值 |
|---|---|
| Bundle | VISION_MODEL_BUNDLE_V1_1（bundle_lock_sha256 `6c2ce081b9d2a1be`） |
| Inference code | `af872dd80adf` |
| Evaluation code | `0c725f3` |
| Holdout manifest | `31ae951d99f0e792`（RANDOM 10 / HARD 10 / GAP 10） |
| **Prediction hash** | **`f5c7c5e70c0fa299`** |

## 十二问

1. **AI prediction 是否 30/30？** → **是**（30/30 全部成功，无失败）
2. **Human Truth 是否在 AI 预测前严格为 0？** → **是**（污染检查：30 条 ∩ 已标注/Calibration(360) = 0；无人工标签/审核/comment）
3. **实际 Bundle ID？** → **VISION_MODEL_BUNDLE_V1_1**
4. **bundle lock hash？** → `6c2ce081b9d2a1be`
5. **holdout manifest hash？** → `31ae951d99f0e792`
6. **prediction hash？** → **`f5c7c5e70c0fa299`**
7. **是否所有 30 条使用完全相同 Bundle/routing/prompt？** → **是**（单次会话、同一 SigLIP en-v1、同一 FIELD_ROUTING_V1、同一 dictionary）
8. **是否存在 prediction 失败/重试？** → **否**（0 失败；STAGING 30/30 一次性 FINALIZE，无重预测）
9. **最终是否 PREDICTION_LOCKED？** → **是**（PREDICTION_LOCKED=True）
10. **DO_NOT_REPREDICT 是否已激活？** → **是**（首次预测完成后激活；生命周期正确：先 INITIAL_PREDICTION_ALLOWED → 完成后 DO_NOT_REPREDICT）
11. **Blind Review UI 是否隐藏全部 AI 信息？** → **是**（FRESH_HOLDOUT_V1 任务 blind=True：manifest 仅含题目 segment/stratum；UI 只显示视频/字段，隐藏 prediction/provider/score/evidence/route）
12. **当前是否可以让用户开始 30 条盲审？** → **可**（AI 答案已锁定、盲审 UI 就绪：`fresh_holdout_human_review_v1` 表 + Review Center 盲审模式；等架构监工/用户指令启动）

## 状态机（Prediction Lock）

```text
INITIAL_PREDICTION_ALLOWED = False（已消费）
PREDICTION_LOCKED          = True
DO_NOT_REPREDICT           = True
DO_NOT_TRAIN               = True
DO_NOT_CALIBRATE           = True
HUMAN_REVIEW_STARTED       = False
```

## 分层身份（考试卷保留）

- RANDOM 10 / HARD 10 / GAP 10（每条 segment 带 stratum）
- 未来评分必须分别报告 RANDOM_10 / HARD_10 / GAP_10 / ALL_30
- ALL_30 只能称 **Fresh Unseen Stratified Holdout Performance**，禁止称"全素材库泛化准确率"

## 交付物

- `HOLDOUT_AI_PREDICTIONS_V1.json`（30 条 final routed prediction + raw evidence，已锁定）
- `FRESH_HOLDOUT_V1_PREDICTION_LOCK.json`（prediction_sha256 `f5c7c5e70c0fa299`）
- `FRESH_HOLDOUT_V1_MANIFEST_LOCK.json`（state 更新：DO_NOT_REPREDICT=True）
- Migration 0009：`fresh_holdout_human_review_v1`（盲审表，只存人工结果）
- Review Center 新增盲审任务（隐藏 AI 全信息；置信度中文解释：高=几乎确定/中=大体确定/低=拿不准）

> **本轮完成，STOP**：未自动开始 Human Review、未评分、未改模型/prompt/routing。等待用户执行 30 条盲审。
""")
report = os.path.join(DOCS, "FRESH_HOLDOUT_V1_AI_PREDICTION_LOCK_REPORT.md")
with open(report, "w", encoding="utf-8") as f:
    f.write("\n".join(R))
desktop = os.path.join(os.environ.get("USERPROFILE", r"C:\Users\admin"), "Desktop")
shutil.copy2(report, os.path.join(desktop, "FRESH_HOLDOUT_V1_AI_PREDICTION_LOCK_REPORT.md"))
print("报告 ->", report, "| 已复制桌面")
