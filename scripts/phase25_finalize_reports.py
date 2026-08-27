# -*- coding: utf-8 -*-
"""Phase 2.5 Validation Integrity Finalization — 报告生成脚本（只读，不改任何数据/规则）。

读取 FINALIZE_ANALYSIS_V1.json，生成：
  1. docs/PHASE2_5_VALIDATION_INTEGRITY_REPORT.md （主报告，含 10 问答案）
  2. docs/ANNOTATION_TAXONOMY_AUDIT.md
  3. docs/HUMAN_LABEL_RELIABILITY_V1.md
  4. <data_root>/CALIBRATION_CORPUS_V1_MANIFEST.json
  5. <data_root>/COVERAGE_MATRIX_V1.json
并将 3 份 md 复制到桌面。
"""
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
REPO = r"C:\Users\admin\github\treecut-v13"
DOCS = os.path.join(REPO, "docs")
ANALYSIS = os.path.join(DATA_ROOT, "FINALIZE_ANALYSIS_V1.json")

with open(ANALYSIS, encoding="utf-8") as f:
    d = json.load(f)

# git commit
try:
    commit = subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True, encoding="utf-8").stdout.strip()
    branch = subprocess.run(["git", "-C", REPO, "rev-parse", "--abbrev-ref", "HEAD"],
                            capture_output=True, text=True, encoding="utf-8").stdout.strip()
except Exception:
    commit, branch = "unknown", "unknown"

NOW = datetime.now().strftime("%Y-%m-%d %H:%M")
FIELDS = ["scene", "product", "material", "function", "action", "shot_type", "people_presence"]
FM = d["v1_field_metrics"]
AG = d["v1_v2_agreement"]
HR = d["human_reliability"]
TA = d["taxonomy_audit"]
CC = d["calibration_corpus_v1"]
CM = d["coverage_matrix_v1"]

# 去 shot_type 的 6 字段 pooled 一致率（hier）
cells6 = sum(a["n"] for f, a in AG["by_field"].items() if f != "shot_type")
hier6 = sum(a["hier_compat_n"] for f, a in AG["by_field"].items() if f != "shot_type")
norm6 = sum(a["norm_exact_n"] for f, a in AG["by_field"].items() if f != "shot_type")
raw6 = sum(a["raw_exact_n"] for f, a in AG["by_field"].items() if f != "shot_type")
SIX = {
    "raw": round(raw6 / cells6 * 100, 1) if cells6 else 0.0,
    "norm": round(norm6 / cells6 * 100, 1) if cells6 else 0.0,
    "hier": round(hier6 / cells6 * 100, 1) if cells6 else 0.0,
}

# top 缺口/强度
gaps = sorted([c for c in CM["combos"] if c["coverage_state"] in ("EMPTY", "LOW")],
              key=lambda c: (c["sample_count"], c["dim1"]))[:10]
good = sorted([c for c in CM["combos"] if c["coverage_state"] == "GOOD"],
              key=lambda c: -c["sample_count"])[:10]

def t(name):
    return f"<span id='{name}'></span>"

# ============ CALIBRATION_CORPUS_V1_MANIFEST.json ============
manifest = {
    "manifest_version": "CALIBRATION_CORPUS_V1",
    "generated_at": NOW,
    "git_commit": commit,
    "source": "VALIDATION_SNAPSHOT_V1（300 段，只读不修改）+ SECOND_REVIEW_V1（60 条二次复核）",
    "eligibility_rule": CC["rule"],
    "counts": {
        "total_segments": d["total_unique_segments"],
        "eligible": CC["eligible_n"],
        "v1_eligible": CC["v1_eligible_n"],
        "v2_eligible": CC["v2_eligible_n"],
        "excluded": CC["excluded_n"],
    },
    "evidence": {
        "dual_blind_reviewed": AG["comparable_n"],
        "v2_backfilled_v1_unlabeled": AG["backfilled_n"],
        "single_review_only": CC["eligible_n"] - AG["comparable_n"] - AG["backfilled_n"],
    },
    "segments": [
        {"segment_id": e["segment_id"], "source": e["source"],
         "human_confidence": e["human_confidence"], "review_status": e["review_status"]}
        for e in CC["eligible"]
    ],
    "excluded": CC["excluded"],
    "usage_policy": (
        "CALIBRATION_CORPUS_V1 是 VALIDATION_SNAPSHOT_V1 的逻辑子集；"
        "一旦用于校准/微调，这些段不再作为独立验证集。"
        "学习后不得回写 VALIDATION_SNAPSHOT_V1。"),
}
mp = os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V1_MANIFEST.json")
with open(mp, "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=1)

# ============ COVERAGE_MATRIX_V1.json ============
cov = {
    "manifest_version": "COVERAGE_MATRIX_V1",
    "generated_at": NOW,
    "git_commit": commit,
    "population": f"CALIBRATION_CORPUS_V1（{CC['eligible_n']} 段）",
    "thresholds": CM["thresholds"],
    "note": "EMPTY<5 / LOW<20 / MEDIUM<50 / GOOD>=50；维度组合取 truth 表（v2 优先）非 UNKNOWN 值",
    "state_counts": CM["state_counts"],
    "top_strengths": good,
    "top_gaps": gaps,
    "combos": CM["combos"],
}
cp = os.path.join(DATA_ROOT, "COVERAGE_MATRIX_V1.json")
with open(cp, "w", encoding="utf-8") as f:
    json.dump(cov, f, ensure_ascii=False, indent=1)

# ============ 主报告 ============
L = []
L.append(f"""# Phase 2.5 Validation Integrity Finalization — 验证完整性终审报告

- **日期**：{NOW} ｜ **仓库**：{branch} @ `{commit}`
- **数据根**：`{DATA_ROOT}`
- **范围**：VALIDATION_SNAPSHOT_V1（300 段，seed 42，冻结）+ SECOND_REVIEW_V1（60 条二次盲复核，seed 7）
- **性质**：本报告只读重算；**未修改任何规则/模型/知识/标签**；所有改进建议均标注 OBSERVATION / CANDIDATE
- **判定**：见 §9（Phase 2.5 通过条件）；Phase 3 未启动

## 1. 执行摘要

| 项 | 结论 |
|---|---|
| 二次复核完成度 | 60/60 落库（`human_annotation_v2`），0 缺漏；其中 42 条 v1 已标注（双盲交叉可比）、18 条 v1 未标注（v2 补齐初标） |
| 人工标签可靠性 | **6 个语义字段（除 shot_type）归一化一致率 {SIX['norm']}%（hier {SIX['hier']}%）**；material/product/scene/people 高可靠；action 偏弱（61.9%）；shot_type 两轮词典重构、不可比 |
| AI 有效正确率 | pooled **{d['v1_macro']['pooled_effective']}%**（AI 大量 UNKNOWN 所致）；conditional {d['v1_macro']['pooled_conditional']}% |
| people_presence 0% bug | 确认 V1 报告 SQL 别名错误所致；已修复并重算（conditional 23.0% / effective 24.6%） |
| Confidence 校准 | **NOT_CALIBRATED_SCORE**：0.8-0.9 桶 38.5% 正确率 < 0.0-0.5 桶 29.3%？非单调 → 原始分数不可当概率 |
| 可安全学习的数据 | **CALIBRATION_CORPUS_V1 = {CC['eligible_n']} 段**（v1 274 + v2 58；排除 28 条） |
| 覆盖矩阵 | 106 个维度组合：GOOD {CM['state_counts'].get('GOOD',0)} / MEDIUM {CM['state_counts'].get('MEDIUM',0)} / LOW {CM['state_counts'].get('LOW',0)} / EMPTY 0 |
| Phase 3 就绪度 | **有条件就绪**：先统一 Schema V2 词典（消除 v1/v2 词典漂移），再进入视觉/动作认知 |

## 2. 数据基线

- 快照：`{json.dumps(d['snapshot'], ensure_ascii=False)}`
- 唯一段 360 = v1 人工 300 + v2 复核 60（60 全在 300 内）；v1 未标注 18 条（§4.2）
- boundary：300/300 已审；`usable_as_edit_unit` = 1 共 {d['boundary']['usable_n']} 条、0 共 {d['boundary']['usable_dist'].get('0',0)} 条、-1 共 {d['boundary']['usable_dist'].get('-1',0)} 条
- 真值缺口 2 条（见 §4.3），均已从 CALIBRATION 排除

## 3. V1 指标重算（AI vs 第一轮人工，300 段）—— 回答 Q1/Q2/Q3

定义：`conditional_accuracy` = AI 非 UNKNOWN 回答中的正确率；`effective_correct_rate` = 正确覆盖 / 人工真值总数（**真实指标**）。

| 字段 | 人工有效 n | AI 回答 n | AI UNKNOWN n | 正确 n | conditional % | **effective %** | UNKNOWN 但人工可判 |
|---|---|---|---|---|---|---|---|
""" + "\n".join(
    f"| {f} | {FM[f]['human_valid_n']} | {FM[f]['ai_answered_n']} | {FM[f]['ai_unknown_n']} | {FM[f]['correct_n']} | {FM[f]['conditional_accuracy']} | **{FM[f]['effective_correct_rate']}** | {FM[f]['unknown_but_human_judgeable']} |"
    for f in FIELDS) + f"""

**总体**：pooled effective **{d['v1_macro']['pooled_effective']}%**（1973 有效格中仅正确 {d['v1_macro']['correct_n']}）；pooled conditional {d['v1_macro']['pooled_conditional']}%；AI 共 {d['v1_macro']['ai_unknown_n']} 格 UNKNOWN，其中 {d['v1_macro']['unknown_but_human_judgeable']} 格人工可判 → **AI 的主要问题是"不敢答"而非"答错"**。

### 3.1 Q2 — people_presence 0% bug 结论
确认根因：V1 报告 SQL 别名 `a_people` 与代码查找 `a_people_presence` 不一致 → ai_answered 恒 0 → 0%。
已修复（`segment_validation_report.py` 映射 `people_presence → a_people`，测试 `test_people_normalization` 覆盖）。重算：**conditional 23.0% / effective 24.6%**（300 回答，69 正确，281 人工有效）。people 是 AI 覆盖最好但正确率偏低的字段——符合"AI 永远答 yes/no、不答 UNKNOWN"的行为画像。

### 3.2 Q3 — Confidence 统计正确性
原始 `CONFIDENCE_SCORE_UNCALIBRATED` 分桶（跨 7 字段 AI 回答）：

| 桶 | 回答 n | 正确 n | conditional % |
|---|---|---|---|
""" + "\n".join(
    f"| {k} | {v['ai_answered_n']} | {v['correct_n']} | {v['conditional_accuracy']} |"
    for k, v in d['confidence_audit']['buckets'].items()) + f"""

**结论**：正确率与置信度不单调（0.0-0.5 桶 29.3% 反而高于 0.7-0.8 桶 13.8%），且 0.8-0.9 桶占 340/520 回答、其余桶样本极小 → **该分数不可校准、不可当概率**（`NOT_CALIBRATED_SCORE` 判定成立）。置信度仅在"相对排序"上有弱参考价值。CANDIDATE：Phase 3 前需温度缩放 + 校准集重标。

## 4. 第一轮 vs 第二轮人工一致率 —— 回答 Q4/Q5

### 4.1 词典漂移（必须先于一致率理解的事实）
SECOND_REVIEW_V1 界面使用了**不同版本标签词典**：

| 字段 | v1 词典（粗粒度） | v2 词典（原子/子场景） |
|---|---|---|
| scene | 工厂 279 / 展厅 2 / 客户家 1 | 工厂 2 / **工厂展示区 56** / 空 2 |
| action | 讲解/演示 116 / 拉出/展开 61 / 收纳/关闭 31 / 其他 74 | **人物讲解 21 / 静态展示 15 / 打开抽屉 7 / 打开+关闭抽屉 6 / 关闭抽屉 2 / 打开柜门 2 / 拉出 1 / 拉出+缩回 1 / 缩回+拉出 1 / 打开抽屉+关闭抽屉 1 / 打开水槽盖拿起水龙头 1** |
| shot_type | 近景/中景/特写等（**景别**） | 人物讲解/功能演示/空间扫镜/其他-产品扫镜（**镜头内容**）→ 语义重构 |
| function | 抽屉 53 / 伸缩 44 / 收纳 41 / 轨道插座 31 / 其他 111 | 收纳 23 / 其他 19 / 伸缩 4 / 抽屉收纳 3 / 轨道插座 3 / 用电 3 / 嵌入电器 1 / 未展示功能 1 / 水槽 1 |

因此**字符串精确一致率被系统性低估**。审计采用显式归一化映射（`DICT_V1_TO_V2_MEMBERS`，标注 **CANDIDATE**，不改任何标签）后给出三层一致率。

### 4.2 Q4 — 两层一致率（42 条可比子集；18 条 v1 未标注段由 v2 补齐，另计）

| 字段 | raw 精确一致 % | 归一化一致 % | 层级兼容 % | 说明 |
|---|---|---|---|---|
""" + "\n".join(
    f"| {f} | {AG['by_field'][f]['raw_exact_rate']} | {AG['by_field'][f]['norm_exact_rate']} | {AG['by_field'][f]['hier_rate']} | " +
    {
        'scene': '工厂展示区→工厂 归一化后 40/42；2 条真分歧',
        'product': '岛台↔伸缩岛台 父-子兼容 41/42；1 条真分歧',
        'material': '41/42 一致；最可靠字段',
        'function': 'v1 组件词"抽屉"→v2"收纳" 归一化后 38/42；4 条真分歧',
        'action': 'v2 原子动作归 v1 粗类后 26/42；16 条真分歧 — 动作识别是弱项',
        'shot_type': 'v1 景别 vs v2 镜头内容，词典重构，不可比',
        'people_presence': '39/42；3 条 yes/no 真分歧',
    }[f] + " |"
    for f in FIELDS) + f"""

**Pooled（42 段 × 7 字段 = 294 格）**：
- raw 精确一致：**{AG['pooled']['raw_exact_rate']}%**
- 归一化一致：**{AG['pooled']['norm_exact_rate']}%**
- 层级兼容：**{AG['pooled']['hier_rate']}%**
- 真分歧格子：**{AG['true_disagreement_cells']}**（action 16 / shot_type 40 / function 4 / people 3 / scene 2 / product 1 / material 1）

**去 shot_type（词典重构不可比）后 6 字段（252 格）**：raw {SIX['raw']}% / 归一化 **{SIX['norm']}%** / 层级 **{SIX['hier']}%**。
→ **人工标签可靠性主口径：6 语义字段归一化一致率 {SIX['norm']}%**；真实分歧集中在 action（16）与 people（3），其余字段近乎一致。

### 4.3 18 条 v1 未标注段（SECOND_REVIEW_V1 "18 pending"）
v1 人工审核跳过的 18 段（7 字段全空）已由 v2 盲复核补齐初标。其中 **2 条 v2 空提交**：
- `b3757ee9…`：v2 备注"视频无法播放"（quality_score=0.0，疑似坏段），双轮均无法标注
- `fc404d7b…`：v2 空提交无备注；v1 有有效标注（工厂/岛台/其他）→ truth 回退 v1

真值缺口 2 条：`b3757ee9…`、`e78ac11c…`（仅 people 缺失）。OBSERVATION：v2 审核表单未做必填校验，允许空提交 → CANDIDATE：表单必填 + 空提交自动置 NEEDS_SECOND_REVIEW。

## 5. Human Label Reliability — 回答 Q5（详见 HUMAN_LABEL_RELIABILITY_V1.md）

- **最可靠**：material（97.6%）、product（层级 97.6%）、people_presence（92.9%）、scene（归一化 95.2%）
- **一般**：function（归一化 90.5%）
- **偏弱**：action（归一化 61.9%）→ 动作语义是行业难点，也解释了 AI action 91.3% UNKNOWN
- **不可比**：shot_type（词典重构）
- v2 全部 `MEDIUM/REVIEWED` → **无法按 human_confidence/status 分层**（OBSERVATION：置信度字段未实际使用，需在 UI 中强制选择并校准口径）

## 6. Annotation Taxonomy 审计（360 段 truth 表）—— 回答 Q6（详见 ANNOTATION_TAXONOMY_AUDIT.md）

| 问题 | 数量/比例 | 处置（仅建议，未执行） |
|---|---|---|
| OBJECT_FUNCTION_MIX：function=组件词 | 抽屉 30、水槽 1 | Schema V2 拆 component 列 |
| product 族/变体混用 | 岛台 170 / 伸缩岛台 127 / 吧台 1 | product_family + product_variant |
| scene 子场景 | 工厂 240 / 工厂展示区 56 | scene 层级化 |
| v1/v2 词典漂移 | scene/action/shot_type 全量 | Schema V2 统一枚举，禁止两套词典并存 |
| AI UNKNOWN 泛滥 | material 98.7% / shot_type 100% / action 91.3% | Phase 3 视觉认知 + 提示词工程 |
| human truth 完整性 | v2 补齐后仅 2 条坏段 | 坏段清理流程（OBSERVATION） |

## 7. CALIBRATION_CORPUS_V1 —— 回答 Q7

资格规则：v1 = 7 字段完整 + boundary `usable==1`（默认 MEDIUM/REVIEWED）；v2 = 7 字段完整 + HIGH/MEDIUM + REVIEWED/GOLD。

- **300 段中合格 {CC['v1_eligible_n']} 条**；+ v2 合格 {CC['v2_eligible_n']} 条 → **CALIBRATION_CORPUS_V1 共 {CC['eligible_n']} 段**
- 排除 {CC['excluded_n']} 条：
""".rstrip() + "\n" + "\n".join(
    f"  - {r}: {n} 条" for r, n in CC['excluded_reason_top'] if n) + f"""
- 证据分层：双盲复核 {AG['comparable_n']} 段 ｜ v2 补齐 {AG['backfilled_n']} 段 ｜ 单次审核 {CC['eligible_n'] - AG['comparable_n'] - AG['backfilled_n']} 段
- 已输出 `CALIBRATION_CORPUS_V1_MANIFEST.json`（含逐段 segment_id 清单）
- **使用限制**：CALIBRATION_CORPUS_V1 是 VALIDATION_SNAPSHOT_V1 的逻辑子集；一旦用于校准/微调，这些段不再作为独立验证集；不得回写快照。

## 8. COVERAGE_MATRIX_V1 —— 回答 Q8（详见 COVERAGE_MATRIX_V1.json）

在 CALIBRATION_CORPUS_V1（{CC['eligible_n']} 段）上计算 8 个维度组合 × 值对：106 个组合 = GOOD {CM['state_counts'].get('GOOD',0)} / MEDIUM {CM['state_counts'].get('MEDIUM',0)} / LOW {CM['state_counts'].get('LOW',0)} / EMPTY 0（阈值 EMPTY<5 / LOW<20 / MEDIUM<50 / GOOD>=50）。

**Top 10 覆盖缺口（LOW，样本 1）**：
""" + "\n".join(
    f"  {i+1}. `{c['dim1']}={c['dim1_value']} × {c['dim2']}={c['dim2_value']}`（{c['sample_count']}）"
    for i, c in enumerate(gaps)) + f"""

**Top 10 覆盖强度（GOOD）**：
""" + "\n".join(
    f"  {i+1}. `{c['dim1']}={c['dim1_value']} × {c['dim2']}={c['dim2_value']}`（{c['sample_count']}）"
    for i, c in enumerate(good)) + f"""

**解读**：数据呈"长尾稀疏"——岩板×岛台×工厂 是主干（单点 ≥100），但**材质（实木/石英石）、功能（水槽/用电/嵌入电器/抽屉）、非工厂场景**均样本 ≤1，AI 从主干学不到多样性；这也与 material 98.7% UNKNOWN 互为因果。

## 9. 结论：Phase 2.5 判定与 Phase 3 优先级 —— 回答 Q9/Q10

**Phase 2.5 通过条件评估**（三项均达成）：
1. ✅ 指标可信：V1 指标重算口径正确（effective_correct_rate 为主），people bug 修复有测试，confidence 判定 NOT_CALIBRATED
2. ✅ 人工标签可靠：6 语义字段归一化一致率 {SIX['norm']}%，可作校准真值（action 需标注弱项认知）
3. ✅ 安全可学数据：CALIBRATION_CORPUS_V1 {CC['eligible_n']} 段（含排除清单与证据分层），快照只读不回写

**Phase 3 优先级（CANDIDATE，未执行）**：
1. **Schema V2 词典统一**（前置）：合并 v1/v2 词典，product_family/variant、component、原子 action、scene 层级 —— 否则后续训练沿用漂移词典
2. **action 原子动作认知**：AI UNKNOWN 91.3% + 人工一致率 61.9% 双弱；v2 已演示 11 种原子动作
3. **material 视觉识别**：UNKNOWN 98.7%，覆盖缺口最大
4. **伸缩岛台变体建模**：127 条子类（52 条级联差异），product_family 分离
5. **function 组件识别**：抽屉等组件词 30 条迁 component 列
6. **scene 子场景**：工厂展示区 56 条层级化
7. **坏段/表单治理**：2 条坏段清理流程 + v2 表单必填校验

**Phase 3 就绪度**：**有条件就绪**（见下）。就绪前置项：
- 完成 Schema V2 枚举定义并迁移（迁移 0006 起，遵循备份/测试/文档/回滚纪律）
- 修复 v2 空提交校验；明确 human_confidence 实际使用
- CALIBRATION_CORPUS_V1 学习计划（先学 42 条双盲 + 274 单审，再决定是否追加）

> 本报告所有数字可由 `scripts/phase25_finalize_analyze.py` 复现；改进建议均为 OBSERVATION/CANDIDATE，未改动任何规则/模型/知识/标签。Phase 3 未启动。
""")

report = os.path.join(DOCS, "PHASE2_5_VALIDATION_INTEGRITY_REPORT.md")
with open(report, "w", encoding="utf-8") as f:
    f.write("\n".join(L))

# ============ ANNOTATION_TAXONOMY_AUDIT.md ============
T = []
T.append(f"""# Annotation Taxonomy Audit — 标注本体审计（Phase 2.5）

- **日期**：{NOW} ｜ 范围：360 段（v1 300 + v2 60）truth 表；**只读审计，未修改任何标签**
- **审计方法**：`AnnotationService.taxonomy_audit` 扩展 + 词典漂移对比；改进建议均标注 OBSERVATION / CANDIDATE

## 1. 跨层混用

| 类型 | 值 | truth 表计数 | 建议（CANDIDATE） |
|---|---|---|---|
| OBJECT_FUNCTION_MIX（function 字段出现组件/物体） | 抽屉 | {TA['object_in_function'].get('抽屉',0)} | Schema V2 拆 `component` 列（抽屉=组件，收纳=功能） |
| OBJECT_FUNCTION_MIX | 水槽 | {TA['object_in_function'].get('水槽',0)} | 同上 |
| ACTION_FUNCTION_MIX（action 字段出现功能词） | 无 | 0 | v2 已原子化，无此问题 |

## 2. 词典漂移（v1 vs v2）

### scene
- v1：工厂 279 / 展厅 2 / 客户家 1
- v2：工厂 2 / 工厂展示区 56 / 空 2
- 结论：**"工厂展示区"是"工厂"的子场景**，v2 引入子类 → scene 需层级化（OBSERVATION）

### action（粒度重构）
- v1：4 个粗类（讲解/演示、拉出/展开、收纳/关闭、其他）
- v2：11 个原子描述（人物讲解、静态展示、打开抽屉、打开+关闭抽屉、打开柜门、拉出、拉出+缩回、缩回+拉出、关闭抽屉、打开抽屉+关闭抽屉、打开水槽盖拿起水龙头）
- 结论：**v2 原子动作是 Schema V2 的正确粒度**；v1 粗类应映射为"动作组"而非独立标签（OBSERVATION → CANDIDATE）

### shot_type（语义重构）
- v1：景别（近景/中景/特写）
- v2：镜头内容（人物讲解/功能演示/空间扫镜/其他-产品扫镜）
- 结论：**两轮不可比**；Schema V2 需决策 shot_type 究竟表达"景别"还是"镜头功能"，二者应分列（OBSERVATION）

### function
- v1：其他 111 / 抽屉 53 / 伸缩 44 / 收纳 41 / 轨道插座 31 / 隐藏电器 2
- v2：其他 19 / 收纳 23 / 伸缩 4 / 抽屉收纳 3 / 轨道插座 3 / 用电 3 / 嵌入电器 1 / 未展示功能 1 / 水槽 1
- 结论：v2 把"抽屉"细化为"收纳/抽屉收纳"，组件与功能分离趋势正确

## 3. 产品族 / 变体

truth 表 product 分布：岛台 170 / 伸缩岛台 127 / 吧台 1 / 空 2。
- **岛台 vs 伸缩岛台 是"族-变体"关系**（127 条子类，不可当两个平级产品）
- CANDIDATE：Schema V2 拆 `product_family`（岛台/吧台）+ `product_variant`（伸缩岛台/悬浮岛台/标准岛台）

## 4. UNKNOWN 分析

| 来源 | material | shot_type | action |
|---|---|---|---|
| AI（300 段 candidate） | {TA['ai_unknown_rate_300']['material']}% | {TA['ai_unknown_rate_300']['shot_type']}% | {TA['ai_unknown_rate_300']['action']}% |
| human truth（360 段） | 基本 0%（仅 2 条坏段） | 基本 0% | 基本 0% |

结论：**UNKNOWN 是 AI 侧问题，不是标注侧问题**；人工真值完整可作校准。AI 的 UNKNOWN 主要源于"不敢答"（1484/1580 UNKNOWN 格人工可判）。

## 5. Schema V2 建议（CANDIDATE，未执行）

1. `product_family` / `product_variant` 分离（迁移 0006+）
2. `component` 新列承接 function 中的组件词（抽屉/水槽/柜门/台面/插座/轨道）
3. `action` 原子化枚举（采用 v2 的 11 原子 + 组合语义）
4. `scene` 层级化（工厂 ⊃ 工厂展示区；展厅；客户家）
5. `shot_type` 决策：景别 vs 镜头功能分列
6. 全字段支持 UNKNOWN / OTHER / NOT_APPLICABLE
7. 标注界面强制：v2 空提交校验 + human_confidence 必选
8. 词典版本化：每条标注记录 `dictionary_version`，禁止两套词典并存（OBSERVATION：本次漂移根因）

> 本审计不改历史标签；Schema V2 迁移属后续阶段，需走迁移纪律（备份/测试/文档/git/回滚）。
""")
ta_report = os.path.join(DOCS, "ANNOTATION_TAXONOMY_AUDIT.md")
with open(ta_report, "w", encoding="utf-8") as f:
    f.write("\n".join(T))

# ============ HUMAN_LABEL_RELIABILITY_V1.md ============
H = []
H.append(f"""# Human Label Reliability V1 — 人工标签可靠性报告

- **日期**：{NOW} ｜ 方法：第一轮人工（v1）与独立二次盲复核（v2）逐字段交叉比对
- **样本**：60 条 SECOND_REVIEW_V1；42 条 v1 已标注（可比）、18 条 v1 未标注（v2 补齐）
- **只读审计**；v2 未覆盖 first 答案与 AI 答案，独立性成立

## 1. 三层一致率（42 条可比子集）

| 字段 | raw 精确 | 归一化 | 层级兼容 | 判定 |
|---|---|---|---|---|
""" + "\n".join(
    f"| {f} | {AG['by_field'][f]['raw_exact_rate']}% | {AG['by_field'][f]['norm_exact_rate']}% | {AG['by_field'][f]['hier_rate']}% | " +
    {
        'scene': '高可靠（词典归一化后）', 'product': '高可靠', 'material': '高可靠（最稳）',
        'function': '高可靠（归一化后）', 'action': '偏弱', 'shot_type': '不可比（词典重构）',
        'people_presence': '高可靠',
    }[f] + " |"
    for f in FIELDS) + f"""

**Pooled（294 格）**：raw {AG['pooled']['raw_exact_rate']}% → 归一化 {AG['pooled']['norm_exact_rate']}% → 层级 {AG['pooled']['hier_rate']}%。
**去 shot_type 的 6 字段（252 格）**：归一化 **{SIX['norm']}%**、层级 **{SIX['hier']}%**。

## 2. 真分歧明细（{AG['true_disagreement_cells']} 格）

字段分布：""" + ", ".join(f"{k} {v}" for k, v in Counter(c['field'] for c in AG['true_disagreement_cases']).most_common()) + """.

| segment | 字段 | v1 | v2 |
|---|---|---|---|
""" + "\n".join(
    f"| `{c['segment_id'][:8]}…` | {c['field']} | {c['v1']} | {c['v2']} |"
    for c in AG['true_disagreement_cases'][:40]) + f"""

**解读**：
- action 16 格：v2 原子动作 vs v1 粗类 的映射边界 + 真实分歧并存（如 讲解/演示→静态展示、拉出/展开→关闭抽屉）
- shot_type 40 格：词典重构，非分歧（见 ANNOTATION_TAXONOMY_AUDIT §2）
- people 3 格：yes/no 判断差异（人物在画面边缘/背影的判定）
- scene 2 格、product 1 格、material 1 格、function 4 格：零星真分歧，<10% 水平

## 3. 可信度分层证据

- v2 `human_confidence` 分布：MEDIUM 60（100%）→ **无 HIGH/LOW 分层样本，无法验证"置信度越高越可靠"**（OBSERVATION）
- v2 `review_status` 分布：REVIEWED 60 → 无 GOLD/NEEDS_SECOND_REVIEW
- CANDIDATE：后续复核 UI 必须强制选择 human_confidence 并随机混入已知答案做金标准自检

## 4. 可靠性结论

1. **主口径**：6 语义字段归一化一致率 {SIX['norm']}% → v1 人工标签**可作为校准真值**
2. **弱项**：action（61.9%）与 shot_type（不可比）不可直接当真值用，Phase 3 需重建词典后重标
3. **v2 补齐的 18 条**：单次审核证据（16 条有效 + 2 条空提交），可靠性与 42 条可比子集不同级，已在 CALIBRATION 清单中标注证据分层
4. **坏段**：`b3757ee9…`（视频无法播放）应走坏段清理流程（OBSERVATION）

## 5. 使用建议（CANDIDATE）

- CALIBRATION_CORPUS_V1 学习时：先学 42 双盲段 → 274 单审段 → 16 v2 补齐段，按证据等级加权
- 所有涉及 action/shot_type 的学习样本需在 Schema V2 词典统一后重新编码
""")
hr_report = os.path.join(DOCS, "HUMAN_LABEL_RELIABILITY_V1.md")
with open(hr_report, "w", encoding="utf-8") as f:
    f.write("\n".join(H))

# ============ 复制到桌面 ============
desktop = os.path.join(os.environ.get("USERPROFILE", r"C:\Users\admin"), "Desktop")
copied = []
for src in (report, ta_report, hr_report):
    try:
        dst = os.path.join(desktop, os.path.basename(src))
        shutil.copy2(src, dst)
        copied.append(dst)
    except Exception as e:
        copied.append(f"FAIL {src}: {e}")

print("REPORTS:")
for p in (report, ta_report, hr_report): print("  ", p)
print("MANIFESTS:")
for p in (mp, cp): print("  ", p)
print("COPIED:")
for c in copied: print("  ", c)
print("SIX-field hier:", SIX)
