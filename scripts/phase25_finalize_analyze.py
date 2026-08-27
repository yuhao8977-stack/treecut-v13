# -*- coding: utf-8 -*-
"""Phase 2.5 Validation Integrity Finalization — 分析脚本 v3（只读）。

v3 修正：
  A. truth[sid] = v2 完整标注优先，否则 v1（修复 fc404d7b 类 v2 空提交丢 v1 有效标注）；
  B. 词典归一化（v1 粗粒度类别 ↔ v2 原子描述，审计假设映射，标注 CANDIDATE）：
     scene 工厂∋工厂展示区；action 讲解/演示∋人物讲解、拉出/展开∋{打开抽屉,关闭抽屉,…}、
     收纳/关闭∋{关闭抽屉,缩回}、其他∋{静态展示,打开柜门,…}；function 收纳∋抽屉收纳 等。
     一致率三层：raw exact / norm（归一化后一致）/ hier（含层级兼容）。
  C. v2 CALIBRATION 资格增加 7 字段完整性（排除 2 条 v2 空提交：b3757ee9 视频无法播放、fc404d7b）。

产出：<data_root>/FINALIZE_ANALYSIS_V1.json
"""
import json
import os
import sqlite3
import sys
from collections import Counter

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")

FIELDS = ["scene", "product", "material", "function", "action", "shot_type", "people_presence"]
UNKNOWN_VALS = {"", "UNKNOWN", "未知", "-", "N/A", "null", "None", "none", "无"}

# ---- 审计词典映射（v2 原子/子场景 → v1 粗粒度类别；仅供一致性计算，不修改任何标签）----
DICT_V1_TO_V2_MEMBERS = {
    "scene": {"工厂": ["工厂", "工厂展示区"], "展厅": ["展厅"], "客户家": ["客户家"]},
    "action": {
        "讲解/演示": ["讲解/演示", "人物讲解"],
        "拉出/展开": ["拉出/展开", "打开抽屉", "关闭抽屉", "打开+关闭抽屉", "打开抽屉+关闭抽屉",
                      "拉出", "拉出+缩回", "缩回+拉出", "伸缩"],
        "收纳/关闭": ["收纳/关闭", "关闭抽屉", "缩回", "缩回+拉出", "拉出+缩回"],
        "其他": ["其他", "静态展示", "打开柜门", "打开水槽盖拿起水龙头"],
    },
    "function": {
        "其他": ["其他", "用电", "嵌入电器", "未展示功能", "水槽"],
        "收纳": ["收纳", "抽屉收纳", "抽屉"],
        "伸缩": ["伸缩"],
        "轨道插座": ["轨道插座"],
        "隐藏电器": ["隐藏电器"],
    },
}
# 反查：v2 词 → v1 类别
_NORM = {}
for _f, _cls in DICT_V1_TO_V2_MEMBERS.items():
    _NORM[_f] = {}
    for _v1, _members in _cls.items():
        for _m in _members:
            _NORM[_f][_m] = _v1


def norm(v):
    if v is None:
        return ""
    return str(v).strip().replace(" ", "").replace("\u3000", "")


def is_unknown(v):
    return norm(v) in UNKNOWN_VALS


def raw_eq(a, b):
    return norm(a) == norm(b)


def norm_eq(field, a, b):
    """归一化后一致：v1 粗类 vs v2 原子（同义/子类归父）。"""
    na, nb = norm(a), norm(b)
    if na == nb:
        return True
    m = _NORM.get(field, {})
    return bool(m.get(na)) and m.get(na) == m.get(nb)


def hier_compat(field, a, b):
    """层级兼容（product 父-子 + 词典子类归父）。"""
    if raw_eq(a, b) or norm_eq(field, a, b):
        return True
    a, b = norm(a), norm(b)
    if not a or not b:
        return False
    prod_parent = {"岛台": ["伸缩岛台", "悬浮岛台"], "收纳柜": ["抽屉"]}
    for p, kids in prod_parent.items():
        if (a == p and b in kids) or (b == p and a in kids):
            return True
    return False


def main():
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    out = {}

    snap = conn.execute("SELECT * FROM validation_snapshots ORDER BY created_at DESC LIMIT 1").fetchone()
    out["snapshot"] = dict(snap) if snap else None

    ai_rows = {r["target_id"]: r for r in conn.execute(
        "SELECT * FROM semantic_annotations WHERE status='candidate'")}
    hu_rows = {r["target_id"]: r for r in conn.execute("SELECT * FROM human_annotations")}
    v2_rows = {r["segment_id"]: r for r in conn.execute("SELECT * FROM human_annotation_v2")}
    bnd_rows = {r["segment_id"]: r for r in conn.execute("SELECT * FROM segment_boundary_reviews")}

    common = sorted(set(ai_rows) & set(hu_rows))
    all_sids = sorted(set(hu_rows) | set(v2_rows))
    out["v1_pair_n"] = len(common)
    out["total_unique_segments"] = len(all_sids)

    def complete(r):
        return all(not is_unknown(r[f]) for f in FIELDS)

    # truth：v2 完整优先，否则 v1
    truth = {}
    for sid in all_sids:
        if sid in v2_rows and complete(v2_rows[sid]):
            truth[sid] = v2_rows[sid]
        else:
            truth[sid] = hu_rows[sid]
    out["truth_gap_n"] = sum(1 for s in all_sids if not complete(truth[s]))
    out["truth_gap_segments"] = [s for s in all_sids if not complete(truth[s])]

    v1_empty = [s for s in hu_rows if not complete(hu_rows[s])]
    out["v1_unlabeled_n"] = len(v1_empty)
    usable = {s for s, r in bnd_rows.items() if r["usable_as_edit_unit"] == 1}
    out["boundary"] = {
        "usable_n": len(usable),
        "usable_dist": dict(Counter(r["usable_as_edit_unit"] for r in bnd_rows.values())),
        "not_usable_n": len(bnd_rows) - len(usable),
    }

    # ---------------- 1. V1 指标（AI vs v1 human，300） ----------------
    v1_field_metrics = {}
    for f in FIELDS:
        hv_n, ans, unk, cor, wr, judge = 0, 0, 0, 0, 0, 0
        cm = Counter()
        for sid in common:
            hv, av = norm(hu_rows[sid][f]), norm(ai_rows[sid][f])
            if hv and not is_unknown(hv):
                hv_n += 1
            if is_unknown(av):
                unk += 1
                if hv and not is_unknown(hv):
                    judge += 1
            else:
                ans += 1
                if hv == av:
                    cor += 1
                else:
                    wr += 1
                cm[(av, hv or "(空)")] += 1
        v1_field_metrics[f] = {
            "human_valid_n": hv_n, "ai_answered_n": ans, "ai_unknown_n": unk,
            "correct_n": cor, "wrong_n": wr,
            "conditional_accuracy": round(cor / ans * 100, 1) if ans else 0.0,
            "effective_correct_rate": round(cor / hv_n * 100, 1) if hv_n else 0.0,
            "unknown_but_human_judgeable": judge,
            "confusion_top": cm.most_common(12),
        }
    out["v1_field_metrics"] = v1_field_metrics
    T = {k: sum(m[k] for m in v1_field_metrics.values())
         for k in ("human_valid_n", "ai_answered_n", "ai_unknown_n", "correct_n",
                   "unknown_but_human_judgeable")}
    out["v1_macro"] = {
        **T,
        "pooled_effective": round(T["correct_n"] / T["human_valid_n"] * 100, 1) if T["human_valid_n"] else 0.0,
        "pooled_conditional": round(T["correct_n"] / T["ai_answered_n"] * 100, 1) if T["ai_answered_n"] else 0.0,
        "macro_effective": round(sum(m["effective_correct_rate"] for m in v1_field_metrics.values()) / len(FIELDS), 1),
        "macro_conditional": round(sum(m["conditional_accuracy"] for m in v1_field_metrics.values()) / len(FIELDS), 1),
    }

    # ---------------- 2. people_presence 修复验证 ----------------
    out["people_presence"] = {
        "mapping_fixed": "people_presence -> semantic_annotations.people_presence 直读重算",
        "metrics": v1_field_metrics["people_presence"],
        "v1_report_bug": "V1 报告曾因 SQL 别名 a_people vs 代码查找 a_people_presence 致 ai_answered=0 → 0%；已修复且有测试",
    }

    # ---------------- 3. AI Confidence 审计 ----------------
    conf_buckets = [(0.0, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]
    bstats = {}
    for sid in common:
        try:
            cf = float(ai_rows[sid]["confidence"]) if ai_rows[sid]["confidence"] is not None else -1.0
        except (TypeError, ValueError):
            cf = -1.0
        for f in FIELDS:
            av, hv = norm(ai_rows[sid][f]), norm(hu_rows[sid][f])
            if is_unknown(av):
                continue
            key = next((f"{lo:.1f}-{hi:.1f}" for lo, hi in conf_buckets if lo <= cf < hi), "missing")
            bs = bstats.setdefault(key, {"answered": 0, "correct": 0})
            bs["answered"] += 1
            bs["correct"] += 1 if hv == av else 0
    conf_audit = {k: {"ai_answered_n": v["answered"], "correct_n": v["correct"],
                      "conditional_accuracy": round(v["correct"] / v["answered"] * 100, 1) if v["answered"] else 0.0}
                  for k, v in sorted(bstats.items())}
    out["confidence_audit"] = {"buckets": conf_audit,
                               "calibration_status": "NOT_CALIBRATED_SCORE — 原始分数未校准，不得当概率使用"}

    # ---------------- 4. v1 vs v2 一致率（三层） ----------------
    overlap = sorted(set(v2_rows) & set(hu_rows))
    comparable = [s for s in overlap if complete(hu_rows[s])]
    backfilled = [s for s in overlap if not complete(hu_rows[s])]
    # v2 中完整标注条数（排除空提交）
    v2_complete = [s for s in v2_rows if complete(v2_rows[s])]
    out["v1_v2_agreement"] = {
        "overlap_n": len(overlap), "comparable_n": len(comparable),
        "backfilled_n": len(backfilled), "backfilled_segments": backfilled,
        "v2_complete_n": len(v2_complete),
        "v2_empty_submissions": [s for s in v2_rows if not complete(v2_rows[s])],
        "dictionary_drift": {
            "note": "v1 粗粒度类别 vs v2 原子动作/子场景，属词典版本漂移而非人工分歧；"
                    "审计映射标注 CANDIDATE（DICT_V1_TO_V2_MEMBERS），未修改任何标签",
            "v1_scene": dict(Counter(norm(hu_rows[s]["scene"]) or "(空)" for s in hu_rows)),
            "v2_scene": dict(Counter(norm(v2_rows[s]["scene"]) or "(空)" for s in v2_rows)),
            "v1_action": dict(Counter(norm(hu_rows[s]["action"]) or "(空)" for s in hu_rows)),
            "v2_action": dict(Counter(norm(v2_rows[s]["action"]) or "(空)" for s in v2_rows)),
            "v1_function": dict(Counter(norm(hu_rows[s]["function"]) or "(空)" for s in hu_rows)),
            "v2_function": dict(Counter(norm(v2_rows[s]["function"]) or "(空)" for s in v2_rows)),
        },
        "by_field": {}, "pooled": {},
    }
    agg = {"raw": 0, "norm": 0, "hier": 0, "cells": 0}
    for f in FIELDS:
        r_ = sum(1 for s in comparable if raw_eq(v2_rows[s][f], hu_rows[s][f]))
        n_ = sum(1 for s in comparable if norm_eq(f, v2_rows[s][f], hu_rows[s][f]))
        h_ = sum(1 for s in comparable if hier_compat(f, v2_rows[s][f], hu_rows[s][f]))
        agg["raw"] += r_; agg["norm"] += n_; agg["hier"] += h_; agg["cells"] += len(comparable)
        out["v1_v2_agreement"]["by_field"][f] = {
            "n": len(comparable), "raw_exact_n": r_, "norm_exact_n": n_, "hier_compat_n": h_,
            "raw_exact_rate": round(r_ / len(comparable) * 100, 1) if comparable else 0.0,
            "norm_exact_rate": round(n_ / len(comparable) * 100, 1) if comparable else 0.0,
            "hier_rate": round(h_ / len(comparable) * 100, 1) if comparable else 0.0,
        }
    out["v1_v2_agreement"]["pooled"] = {
        "raw_exact_rate": round(agg["raw"] / agg["cells"] * 100, 1) if agg["cells"] else 0.0,
        "norm_exact_rate": round(agg["norm"] / agg["cells"] * 100, 1) if agg["cells"] else 0.0,
        "hier_rate": round(agg["hier"] / agg["cells"] * 100, 1) if agg["cells"] else 0.0,
    }
    cases = []
    for s in comparable:
        for f in FIELDS:
            v1v, v2v = norm(hu_rows[s][f]), norm(v2_rows[s][f])
            if not hier_compat(f, v1v, v2v):
                cases.append({"segment_id": s, "field": f, "v1": v1v or "(空)", "v2": v2v or "(空)"})
    out["v1_v2_agreement"]["true_disagreement_cells"] = len(cases)
    out["v1_v2_agreement"]["true_disagreement_cases"] = cases[:100]

    # ---------------- 5. Human Reliability ----------------
    out["human_reliability"] = {
        "method": ("42 条 v1 完整标注段 × v2 独立盲复核，三层一致率；"
                   "18 条 v1 未标注段由 v2 补齐（含 2 条 v2 空提交：b3757ee9 视频无法播放、fc404d7b）"),
        "by_field": {f: {k: a[k] for k in ("raw_exact_rate", "norm_exact_rate", "hier_rate")}
                     for f, a in out["v1_v2_agreement"]["by_field"].items()},
        "pooled": out["v1_v2_agreement"]["pooled"],
        "human_confidence_dist": dict(Counter(r["human_confidence"] or "" for r in v2_rows.values())),
        "review_status_dist": dict(Counter(r["review_status"] or "" for r in v2_rows.values())),
        "observation": ("v2 全为 MEDIUM/REVIEWED → 无法按 confidence/status 分层；"
                        "分层可信度证据不足（CANDIDATE）。另 2 条 v2 空提交暴露审核表单未做必填校验"),
    }

    # ---------------- 6. Taxonomy（truth 表）+ AI UNKNOWN ----------------
    obj_in_func, act_in_func = Counter(), Counter()
    prod_dist, scene_dist = Counter(), Counter()
    for sid in all_sids:
        t = truth[sid]
        fn, ac, pr, sc = norm(t["function"]), norm(t["action"]), norm(t["product"]), norm(t["scene"])
        if fn in ("抽屉", "柜门", "台面", "插座", "水槽", "轨道"):
            obj_in_func[fn] += 1
        if ac in ("收纳", "伸缩", "展示"):
            act_in_func[ac] += 1
        prod_dist[pr or "(空)"] += 1
        scene_dist[sc or "(空)"] += 1
    ai_unk = {f: sum(1 for s in common if is_unknown(ai_rows[s][f])) for f in FIELDS}
    out["taxonomy_audit"] = {
        "annotations_scanned": len(all_sids),
        "object_in_function": dict(obj_in_func),
        "action_in_function": dict(act_in_func),
        "product_value_dist": prod_dist.most_common(),
        "scene_value_dist": scene_dist.most_common(),
        "human_truth_unknown": {f: sum(1 for s in all_sids if is_unknown(truth[s][f])) for f in FIELDS},
        "ai_unknown_rate_300": {f: round(n / 300 * 100, 1) for f, n in ai_unk.items()},
        "schema_v2_notes": (
            "product 拆 product_family(岛台)/product_variant(伸缩岛台)；"
            "function 组件词(抽屉×30/水槽×1) 迁 component 列；"
            "action 原子化(v2 已演示 11 种原子动作) 建议 Schema V2 采用；"
            "AI material/shot_type/action 高 UNKNOWN；"
            "human 真值在 v2 补齐后基本无 UNKNOWN（仅 2 条坏段）"),
    }

    # ---------------- 7. CALIBRATION_CORPUS_V1 ----------------
    eligible, excluded = [], []
    for sid in common:  # v1
        reason = []
        missing = [f for f in FIELDS if is_unknown(hu_rows[sid][f])]
        if missing:
            reason.append(f"v1 字段缺失:{missing}")
        if sid not in usable:
            reason.append("boundary usable!=1")
        if reason:
            excluded.append({"segment_id": sid, "source": "v1_300", "reason": ";".join(reason)})
        else:
            eligible.append({"segment_id": sid, "source": "v1_300",
                             "human_confidence": "MEDIUM(default)", "review_status": "REVIEWED(default)"})
    for sid in sorted(v2_rows):  # v2
        r = v2_rows[sid]
        reason = []
        if not complete(r):
            reason.append(f"v2 空提交:{r['comment'] or '无备注'}")
        if r["review_status"] in ("NEEDS_SECOND_REVIEW", "EXCLUDED"):
            reason.append(f"status={r['review_status']}")
        if r["human_confidence"] not in ("HIGH", "MEDIUM"):
            reason.append(f"conf={r['human_confidence']}")
        if reason:
            excluded.append({"segment_id": sid, "source": "v2_60", "reason": ";".join(reason)})
        else:
            eligible.append({"segment_id": sid, "source": "v2_60",
                             "human_confidence": r["human_confidence"], "review_status": r["review_status"]})
    excl_reason = Counter()
    for e in excluded:
        first = e["reason"].split(";")[0]
        excl_reason[first] += 1
    out["calibration_corpus_v1"] = {
        "rule": ("v1: 7 字段完整 + boundary usable==1（默认 MEDIUM/REVIEWED）；"
                 "v2: 7 字段完整 + HIGH/MEDIUM + REVIEWED/GOLD；NEEDS_SECOND_REVIEW/EXCLUDED/空提交排除"),
        "eligible_n": len(eligible), "excluded_n": len(excluded),
        "v1_eligible_n": sum(1 for e in eligible if e["source"] == "v1_300"),
        "v2_eligible_n": sum(1 for e in eligible if e["source"] == "v2_60"),
        "eligible": eligible, "excluded": excluded,
        "excluded_reason_top": excl_reason.most_common(),
        "evidence_note": ("42 条 v1∩v2 可比 = 双盲复核交叉证据；16 条 v2 补齐 = 单次审核；"
                          "其余 274 条 v1 = 单次审核"),
    }

    # ---------------- 8. COVERAGE_MATRIX_V1 ----------------
    el_sids = {e["segment_id"] for e in eligible}
    dims = [("scene", "product"), ("product", "material"), ("scene", "action"),
            ("product", "function"), ("scene", "shot_type"), ("material", "function"),
            ("scene", "material"), ("product", "action")]
    TH = {"EMPTY": 0, "LOW": 5, "MEDIUM": 20, "GOOD": 50}
    combos = []
    for d1, d2 in dims:
        cnt = Counter()
        for sid in el_sids:
            v1v, v2v = norm(truth[sid][d1]), norm(truth[sid][d2])
            if is_unknown(v1v) or is_unknown(v2v):
                continue
            cnt[(v1v, v2v)] += 1
        for (a, b), n in cnt.most_common(60):
            state = "EMPTY" if n < TH["EMPTY"] else ("LOW" if n < TH["LOW"] else ("MEDIUM" if n < TH["MEDIUM"] else "GOOD"))
            combos.append({"dim1": d1, "dim1_value": a, "dim2": d2, "dim2_value": b,
                           "sample_count": n, "coverage_state": state})
    out["coverage_matrix_v1"] = {
        "thresholds": TH, "combos": combos, "total_combos": len(combos),
        "state_counts": dict(Counter(c["coverage_state"] for c in combos)),
    }

    with open(os.path.join(DATA_ROOT, "FINALIZE_ANALYSIS_V1.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("OK ->", os.path.join(DATA_ROOT, "FINALIZE_ANALYSIS_V1.json"))
    print("comparable:", len(comparable), "| backfilled:", len(backfilled),
          "| truth_gap:", out["truth_gap_n"], "| eligible:", len(eligible),
          "| combos:", len(combos))


if __name__ == "__main__":
    main()
