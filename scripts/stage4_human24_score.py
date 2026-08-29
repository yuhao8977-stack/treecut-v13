# -*- coding: utf-8 -*-
"""Stage 2 — Human24 打分（AI_LOCK vs 独立 Human Truth，set comparison）。

输入：
  BUSINESS_COGNITION_STAGE2_AI_LOCK.json          （AI 60/60，冻结）
  BUSINESS_COGNITION_STAGE2_HUMAN_REVIEW_V1.json  （Human24 manifest）
  stage2_business_cognition_review_v1 表          （独立 Human Truth）

核心（Gate §10）：
  Human Truth 独立于 AI claim —— Human 从完整固定 Taxonomy 勾选；
  AI 未预测但 Human 勾选的标签 → FN（Recall 真实可计算）。

多标签 set comparison（user_needs / business_values / search_intents /
shot_functions / decision_factors / trust_signals）：
  TP=AI∩Human  FP=AI−Human  FN=Human−AI  TN=Taxonomy−(AI∪Human)
  UNSUPPORTED_CLAIM_RATE = FP / (TP+FP)

Affinity（role 4 类 / theme 5 类，Human 全部维度独立 5 级评级）：
  AI 主张 = AI_LOCK 中出现的 role/theme（affinity MEDIUM）
  Human 支持 = Human 评级 STRONG/MEDIUM（WEAK/NOT_SUPPORTED/UNKNOWN = 不支持）
  exact_affinity / within_one_level / macroF1 / strong_unsupported
  注：AI 引擎仅 3 role（缺 TRAFFIC）/5 theme；TRAFFIC 视 AI 未主张。

输出：BUSINESS_COGNITION_STAGE2_SCORE_V1.json
"""
import io
import json
import os
import sqlite3
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
DB = os.path.join(DATA_ROOT, "database", "materials.db")
AI_LOCK = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_STAGE2_AI_LOCK.json")
HUMAN_MANIFEST = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_STAGE2_HUMAN_REVIEW_V1.json")
TAXONOMY = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_HUMAN_TAXONOMY_V1.json")
OUT = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_STAGE2_SCORE_V1.json")

SET_FIELDS = ["user_needs", "business_values", "search_intents", "shot_functions",
              "decision_factors", "trust_signals"]
# AI_LOCK 中对应的字段名
AI_FIELD_MAP = {"user_needs": "user_needs", "business_values": "business_values",
                "search_intents": "search_intent_candidates",
                "shot_functions": "shot_function_candidates",
                "decision_factors": None, "trust_signals": None}  # AI 无这两类输出


def _jlist(v):
    if isinstance(v, list):
        return v
    try:
        x = json.loads(v) if v else []
        return x if isinstance(x, list) else []
    except Exception:
        return []


def _jdict(v):
    if isinstance(v, dict):
        return v
    try:
        x = json.loads(v) if v else {}
        return x if isinstance(x, dict) else {}
    except Exception:
        return {}


def main():
    ai = json.load(open(AI_LOCK, encoding="utf-8"))
    man = json.load(open(HUMAN_MANIFEST, encoding="utf-8"))
    tax = json.load(open(TAXONOMY, encoding="utf-8"))
    ai_by_sid = {r["segment_id"]: r for r in ai["results"]}
    human_ids = [s["segment_id"] for s in man["segments"]]

    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = {}
    try:
        for r in conn.execute(f"SELECT * FROM stage2_business_cognition_review_v1 WHERE segment_id IN "
                              f"({','.join('?' * len(human_ids))})", human_ids):
            rows[r["segment_id"]] = dict(r)
    except sqlite3.OperationalError:
        pass
    conn.close()
    print(f"Human24: {len(human_ids)} 条 | 已评审 {len(rows)} 条")
    if not rows:
        print("尚未有人工评审结果，无法打分。")
        return

    # 全量 Taxonomy 作为 TN 分母（只对 Human24 实际评审过的段）
    tax_ids = {}
    for fld in SET_FIELDS:
        tax_ids[fld] = [x["id"] for x in tax.get(fld, [])]

    # ---------------- 多标签 set comparison ----------------
    set_stats = {fld: {"tp": 0, "fp": 0, "fn": 0, "tn": 0} for fld in SET_FIELDS}
    unsupported = []   # AI 主张但 Human 未勾选
    missed = []        # Human 勾选但 AI 未主张（FN）
    by_class = {c: {"tp": 0, "fp": 0, "fn": 0} for c in
                ("STRONG_SINGLE_EVIDENCE", "MULTI_SOURCE_AGREEMENT", "CONFLICTING_EVIDENCE",
                 "WEAK_EVIDENCE", "NEGATIVE_RULE_TRIGGER", "AMBIGUOUS_MULTI_PURPOSE")}
    per_seg = []

    for s in man["segments"]:
        sid = s["segment_id"]
        if sid not in rows:
            continue
        h = rows[sid]
        a = ai_by_sid[sid]
        cls = s["challenge_class"]
        row_stat = {"segment_id": sid, "class": cls, "overall_unknown": h.get("overall_unknown", "")}
        for fld in SET_FIELDS:
            human_set = set(_jlist(h.get(fld)))
            ai_field = AI_FIELD_MAP[fld]
            ai_set = set(_jlist(a.get(ai_field))) if ai_field else set()
            tp = len(human_set & ai_set)
            fp = len(ai_set - human_set)
            fn = len(human_set - ai_set)
            tn = len(set(tax_ids[fld]) - (human_set | ai_set))
            set_stats[fld]["tp"] += tp; set_stats[fld]["fp"] += fp
            set_stats[fld]["fn"] += fn; set_stats[fld]["tn"] += tn
            by_class[cls]["tp"] += tp; by_class[cls]["fp"] += fp; by_class[cls]["fn"] += fn
            for x in (ai_set - human_set):
                unsupported.append({"segment_id": sid, "class": cls, "field": fld, "name": x})
            for x in (human_set - ai_set):
                missed.append({"segment_id": sid, "class": cls, "field": fld, "name": x})
            row_stat[f"{fld}_ai"] = sorted(ai_set)
            row_stat[f"{fld}_human"] = sorted(human_set)
        per_seg.append(row_stat)

    # ---------------- Affinity（role 4 / theme 5） ----------------
    AFFINITY_ORDER = ["STRONG", "MEDIUM", "WEAK", "NOT_SUPPORTED", "UNKNOWN"]
    LEVEL = {l: i for i, l in enumerate(AFFINITY_ORDER)}
    role_stats = {"exact": 0, "within_one": 0, "total": 0, "tp": 0, "fp": 0, "fn": 0,
                  "strong_unsupported": []}
    theme_stats = {"exact": 0, "within_one": 0, "total": 0, "tp": 0, "fp": 0, "fn": 0,
                   "strong_unsupported": []}

    def affinity_metrics(st, dims, ai_affinity, human_affinity, label):
        """dim：维度清单；AI 主张集合（affinity MEDIUM）；Human 评级 dict。"""
        for d in dims:
            st["total"] += 1
            ai_claims = d in ai_affinity
            hv = (human_affinity.get(d) or "UNKNOWN").upper()
            human_support = hv in ("STRONG", "MEDIUM")
            if ai_claims and human_support:
                st["tp"] += 1
            elif ai_claims and not human_support:
                st["fp"] += 1
                if hv == "NOT_SUPPORTED":
                    st["strong_unsupported"].append({"dim": d, "human": hv})
            elif not ai_claims and human_support:
                st["fn"] += 1
            # exact / within-one（仅对 AI 主张的维度）
            if ai_claims and hv in LEVEL:
                ai_lvl = LEVEL["MEDIUM"]
                st["total"] += 0  # total 已在上面计
                if hv == "MEDIUM":
                    st["exact"] += 1
                if abs(ai_lvl - LEVEL[hv]) <= 1:
                    st["within_one"] += 1

    for s in man["segments"]:
        sid = s["segment_id"]
        if sid not in rows:
            continue
        h = rows[sid]
        a = ai_by_sid[sid]
        # AI role/theme 主张（AI_LOCK 的 affinity 列表）
        ai_roles = {x["role"] for x in a.get("content_role_affinity", [])}
        ai_themes = {x["theme"] for x in a.get("mother_theme_affinity", [])}
        human_roles = _jdict(h.get("role_affinity"))
        human_themes = _jdict(h.get("theme_affinity"))
        affinity_metrics(role_stats, [r["id"] for r in tax["content_roles"]],
                         ai_roles, human_roles, "role")
        affinity_metrics(theme_stats, [t["id"] for t in tax["mother_themes"]],
                         ai_themes, human_themes, "theme")

    # ---------------- 汇总 ----------------
    print("\n===== Human24 打分（独立 Human Truth vs AI_LOCK）=====")
    for fld in SET_FIELDS:
        st = set_stats[fld]
        prec = st["tp"] / (st["tp"] + st["fp"]) if (st["tp"] + st["fp"]) else 0.0
        rec = st["tp"] / (st["tp"] + st["fn"]) if (st["tp"] + st["fn"]) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        ucr = st["fp"] / (st["tp"] + st["fp"]) if (st["tp"] + st["fp"]) else 0.0
        print(f"  {fld}: TP={st['tp']} FP={st['fp']} FN={st['fn']} TN={st['tn']} | "
              f"P={prec:.3f} R={rec:.3f} F1={f1:.3f} UCR={ucr:.3f}")

    # 总 need+value 合并（Stage2 最核心指标）
    agg = {k: set_stats["user_needs"][k] + set_stats["business_values"][k]
           for k in ("tp", "fp", "fn", "tn")}
    prec = agg["tp"] / (agg["tp"] + agg["fp"]) if (agg["tp"] + agg["fp"]) else 0.0
    rec = agg["tp"] / (agg["tp"] + agg["fn"]) if (agg["tp"] + agg["fn"]) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    ucr = agg["fp"] / (agg["tp"] + agg["fp"]) if (agg["tp"] + agg["fp"]) else 0.0
    print(f"\n[needs+values 合并] TP={agg['tp']} FP={agg['fp']} FN={agg['fn']} TN={agg['tn']}")
    print(f"  Precision={prec:.3f} Recall={rec:.3f} F1={f1:.3f} UNSUPPORTED_CLAIM_RATE={ucr:.3f}")
    print(f"  Human-only FN 数（AI 漏检）: {len(missed)} | AI 主张 Human 不支持: {len(unsupported)}")

    print("\nAffinity:")
    for nm, st in (("role", role_stats), ("theme", theme_stats)):
        print(f"  {nm}: exact={st['exact']}/{st['total']} within_one={st['within_one']}/{st['total']} "
              f"TP={st['tp']} FP={st['fp']} FN={st['fn']} strong_unsupported={len(st['strong_unsupported'])}")

    # ---------------- 输出 ----------------
    out = {
        "manifest": "BUSINESS_COGNITION_STAGE2_SCORE_V1",
        "method": "独立 Human Truth（完整固定 Taxonomy 勾选） vs AI_LOCK；set comparison；"
                  "Human-only label → FN；Recall 真实可计算",
        "reviewed": len(per_seg), "total": len(human_ids),
        "set_fields": {fld: {**st,
                             "precision": round(st["tp"] / (st["tp"] + st["fp"]), 4) if (st["tp"] + st["fp"]) else 0.0,
                             "recall": round(st["tp"] / (st["tp"] + st["fn"]), 4) if (st["tp"] + st["fn"]) else 0.0,
                             "f1": round(2 * (st["tp"] / (st["tp"] + st["fp"]) if (st["tp"] + st["fp"]) else 0.0) *
                                         (st["tp"] / (st["tp"] + st["fn"]) if (st["tp"] + st["fn"]) else 0.0) /
                                         ((st["tp"] / (st["tp"] + st["fp"]) if (st["tp"] + st["fp"]) else 0.0) +
                                          (st["tp"] / (st["tp"] + st["fn"]) if (st["tp"] + st["fn"]) else 0.0)), 4)
                                         if ((st["tp"] / (st["tp"] + st["fp"]) if (st["tp"] + st["fp"]) else 0.0) +
                                             (st["tp"] / (st["tp"] + st["fn"]) if (st["tp"] + st["fn"]) else 0.0)) else 0.0,
                             "unsupported_claim_rate": round(st["fp"] / (st["tp"] + st["fp"]), 4) if (st["tp"] + st["fp"]) else 0.0}
                        for fld, st in set_stats.items()},
        "aggregate_needs_values": {"tp": agg["tp"], "fp": agg["fp"], "fn": agg["fn"], "tn": agg["tn"],
                                   "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4),
                                   "unsupported_claim_rate": round(ucr, 4)},
        "unsupported_claims": unsupported,
        "human_only_missed_by_ai": missed,   # = FN 明细
        "affinity": {"role": role_stats, "theme": theme_stats},
        "by_class": by_class,
        "per_segment": per_seg,
        "guard": "Human24 仅评审打分；不得在同 24 上重调规则后声称新准确率；"
                 "同 24 将成为 KNOWN_DEV_BENCHMARK",
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT)


if __name__ == "__main__":
    main()
