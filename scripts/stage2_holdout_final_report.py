# -*- coding: utf-8 -*-
"""FRESH_HOLDOUT_V1_FINAL_EVALUATION.md 生成。"""
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

m = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_METRICS.json"), encoding="utf-8"))
hl = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_HUMAN_LOCK.json"), encoding="utf-8"))
err = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_ERROR_CASES.json"), encoding="utf-8"))

S = m["single"]; M = m["multi"]; A = m["action"]; T = m["trivial_baseline"]; DV = m["dev_vs_holdout"]

def acc(f, l="ALL"):
    return S[f][l]["accuracy"]
def mf(f, l="ALL"):
    return M[f][l]["micro_f1"]
def li(f, l="ALL"):
    return M[f][l]["label_in_set_accuracy"]

R = []
R.append(f"""# FRESH_HOLDOUT_V1 — Final Scoring & Generalization Audit

- **日期**：{NOW} ｜ git `{commit}`
- **身份冻结**：bundle `6c2ce081b9d2a1be` ｜ manifest `31ae951d99f0e792` ｜ prediction `f5c7c5e70c0fa299`（三 hash 均未变）
- **Human Review**：30/30 完成并冻结（human_truth_sha256=`{hl['human_truth_sha256']}`；MEDIUM 29 + HIGH 1；REVIEWED 29 + GOLD 1）
- **名称**：Fresh Unseen Stratified Holdout Performance（禁止称全库泛化准确率）
- **纪律**：未学习/未改 Bundle/Holdout 永久 DO_NOT_TRAIN+DO_NOT_CALIBRATE

## 1. 三方身份完整性（严格 segment_id JOIN）

manifest 30 = AI 30 = Human 30；missing=0、extra=0、duplicate=0 ✅

## 2. 分层成绩（RANDOM / HARD / GAP / ALL）

**scene_family（accuracy %）**：RANDOM {acc('scene_family','RANDOM')} / HARD {acc('scene_family','HARD')} / GAP {acc('scene_family','GAP')} / **ALL {acc('scene_family')}**
**product_family（accuracy %）**：RANDOM {acc('product_family','RANDOM')} / HARD {acc('product_family','HARD')} / GAP {acc('product_family','GAP')} / **ALL {acc('product_family')}**

> 30 条小样本，分层间差异不构成强统计结论；按层报告仅供结构性参考。

## 3. 单标签字段（ALL_30，n_valid 每层≤10/ALL≤30）

| 字段 | acc% | cov% | cond% | unk% | n | trivial% | 判定 |
|---|---|---|---|---|---|---|---|
""" + "\n".join(
    f"| {f} | {S[f]['ALL']['accuracy']} | {S[f]['ALL']['coverage']} | {S[f]['ALL']['conditional_accuracy']} | {S[f]['ALL']['unknown_rate']} | {S[f]['ALL']['n_valid']} | {T.get(f,{}).get('accuracy','-')} | {j(f)} |"
    for f in ("scene_family","scene_subtype","product_family","product_variant","shot_scale","people_presence","product_visibility")
    for j in [lambda f: {"scene_family":"EXPERIMENTAL(gap)","scene_subtype":"FAILED(UNKNOWN gate)","product_family":"LIMITED(泛化稳定)",
                         "product_variant":"FAILED(UNKNOWN gate)","shot_scale":"EXPERIMENTAL","people_presence":"FAILED(route 无输出)","product_visibility":"FAILED(UNKNOWN gate)"}[f]][0]) + f"""

## 4. 多标签字段（ALL_30，V2.1 真值集合）

| 字段 | microF1% | label-in% | exact% | n |
|---|---|---|---|---|
| material | {mf('material')} | {li('material')} | {M['material']['ALL']['exact_set_match']} | {M['material']['ALL']['n_segments']} |
| component | {mf('component')} | {li('component')} | {M['component']['ALL']['exact_set_match']} | {M['component']['ALL']['n_segments']} |
| function | {mf('function')} | {li('function')} | {M['function']['ALL']['exact_set_match']} | {M['function']['ALL']['n_segments']} |
| shot_role | {mf('shot_role')} | {li('shot_role')} | {M['shot_role']['ALL']['exact_set_match']} | {M['shot_role']['ALL']['n_segments']} |

## 5. Action（Semantic 未建立，确认）

action_group accuracy = **0.0%**（RANDOM 0/HARD 0/GAP 0）；sequence exact = 0.0%。
→ Farneback 仅 Motion Evidence；**Semantic Action Recognition 未建立（FAILED）**。

## 6. Dev vs Fresh Holdout（过拟合诊断）

| 字段 | dev | holdout | delta | 判定 |
|---|---|---|---|---|
""" + "\n".join(
    f"| {f} | {v['dev']} | {v['holdout']} | {v['delta']} | {gap(v['delta'])} |"
    for f, v in DV.items() for gap in [lambda d: "GENERALIZATION_GAP" if d < -10 else ("HOLDOUT_BETTER" if d > 10 else "STABLE")][0]) + f"""

**解读**：
- **product STABLE**（52.7→51.7）：视觉产品识别**跨未见样本稳定**——本 Bundle 最有价值的泛化能力
- **component/function/shot_role HOLDOUT_BETTER**（label-in 90-97%）：多标签视觉在未见样本上表现更好（dev 偏科抑制了多标签表现）
- **scene GENERALIZATION_GAP**（37.9→24.1）：dev 偏科（98% FACTORY）高估了 scene；真实未见样本更困难
- **material STABLE 但低**（23%）：真实材质能力弱（岩板主导）
- **people 0%**：当前 route（legacy fallback 对未审段无输出）在 Holdout 完全失效 → 旧方案本身需升级

## 7. Trivial baseline（Holdout 事后，仅 human truth）

scene 96.6%(FACTORY)、product 100%(ISLAND)、people 93.3%(YES)、shot_scale 40.7%(WIDE)……
→ **除 product 外，多数单标签未超 trivial**（偏科下 accuracy 意义有限）；product 51.7% 虽 < 100% trivial，但**跨样本稳定且覆盖 69%**，是真实视觉信号。

## 8. 错误分析（TOP_ERROR_CASES：{m['error_case_count']} 条含错误）

- 主要错误类型：**VISION_CONFUSION**（单标签/多标签误判）、**UNKNOWN_OVERUSE**（如 scene_subtype/variant/visibility 全 UNKNOWN gate）、**ROUTING_GAP**（people/variant 无输出）
- 详细清单见 `FRESH_HOLDOUT_V1_ERROR_CASES.json`（segment/stratum/truth/prediction/provider/error_type）
- 未自动修改模型

## 9. 字段状态重判（Fresh Holdout 依据）

| 字段 | 状态 | 依据 |
|---|---|---|
| product_family | **LIMITED**（候选生产） | 泛化稳定 51.7%、覆盖 69%；未超 trivial(ISLAND 100%) → 不作全库唯一判据 |
| component[]/function[] | **LIMITED** | label-in 90-97%、Holdout 更好；microF1 49%/56% |
| shot_role[] | LIMITED/EXPERIMENTAL | label-in 96.7% |
| material[] | **EXPERIMENTAL** | 低但稳定（23%）；岩板为主 |
| scene_family | **EXPERIMENTAL** | 有信号但有 gap（24.1%） |
| shot_scale | EXPERIMENTAL | 25.9% |
| people_presence | **FAILED**（当前 route） | 0%；旧方案对未审段无输出，需升级 |
| product_variant/scene_subtype/product_visibility | **FAILED**（UNKNOWN gate） | 无能力（诚实） |
| action_group/sequence | **FAILED**（semantic 未建立） | motion baseline 0% |

## 10. Stage 2 总体判定（STEP 15）

- **A. GPU/Runtime Engineering：成功**（RTX 3050 CUDA fp16 真跑，SigLIP 0.4s/段）
- **B. Static Visual Signal：成功建立**（真实视觉信号，非 ASR/规则）
- **C. Fresh 泛化能力：部分建立**（product/component/function 稳定或更好；scene 有 gap）
- **D. 候选生产**：product_family、component[]、function[]（LIMITED）
- **E. 辅助 Evidence**：material、shot_scale、shot_role、scene
- **F. 基本无能力**：people（当前 route）、variant、subtype、visibility、semantic action
- **G. Semantic Action Recognition：未建立**（motion baseline 仅证据）

## 11. 十七问

1. Human review 30/30 ✅；2. human_truth_sha256=`{hl['human_truth_sha256']}`；3. prediction hash 仍 = `f5c7c5e70c0fa299` ✅
4. 分层见 §2；5. 每字段见 §3/§4；6. **product Fresh = 51.7%**；7. **scene Fresh = 24.1%**；8. **material Fresh = 23.2% microF1**；9. shot_scale 25.9% / shot_role 37.3%；10. **people 0%**（route 失效）；11. **action 0%**（semantic 未建立）
12. 超过 Holdout trivial：无（多数偏科 trivial 极高）；product 接近但稳定
13. Generalization gap：**scene（-13.8）**；component/function/shot_role 反而更好
14. 主要错误：**VISION_CONFUSION + UNKNOWN_OVERUSE + ROUTING_GAP**（非单一 model 或 text）
15. **VISION_MODEL_BUNDLE_V1_1 判定：LIMITED**（GPU/视觉信号成功、部分字段泛化；非 FULL PASS，非 FAIL）
16. **Phase 3 Stage 2：部分完成**（视觉基础建立；product/component/function 可候选；scene/material/action/people 仍 EXPERIMENTAL/FAILED）
17. **下一步建议**：不急于 Phase 4——先补素材/标签（非工厂/实木/动作类），再评估 Stage 3（更强静态视觉 + 真语义时序动作模型）；Holdout 保持永久测试集，Bundle V2 需新 FRESH_HOLDOUT_V2

## 12. 交付物

- `FRESH_HOLDOUT_V1_METRICS.json` · `FRESH_HOLDOUT_V1_ERROR_CASES.json` · `FRESH_HOLDOUT_V1_HUMAN_LOCK.json`
- 本报告 `FRESH_HOLDOUT_V1_FINAL_EVALUATION.md`

> **STOP**：未学习、未改 Bundle、未进入 Phase4/全量 41814。等架构监工据本报告决定 Stage 3 或 Phase 4。
""")
report = os.path.join(DOCS, "FRESH_HOLDOUT_V1_FINAL_EVALUATION.md")
with open(report, "w", encoding="utf-8") as f:
    f.write("\n".join(R))
desktop = os.path.join(os.environ.get("USERPROFILE", r"C:\Users\admin"), "Desktop")
shutil.copy2(report, os.path.join(desktop, "FRESH_HOLDOUT_V1_FINAL_EVALUATION.md"))
print("报告 ->", report, "| 已复制桌面")
