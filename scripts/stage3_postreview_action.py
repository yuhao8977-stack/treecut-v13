# -*- coding: utf-8 -*-
"""Stage3 POST-REVIEW — STEP 4/5：Semantic Action 真实增量 + Action 候选命中质量。

STEP4：逐原子动作 existing(333) / stage3_60 / combined；检查 CLOSE_CABINET、OPERATE_SOCKET 是否仍 0。
STEP5：审核前保存的 candidate_action_reason（STAGE3_ACTION_CANDIDATE_SUPPORT.json，V2 池）vs 人工真值。
注意：候选池是 V2 的 60（部分被 V3_1 替换）；命中质量 = 候选在 V3_1 中的人工真值，仅对重叠段有效。
"""
import json
import os
import sqlite3
import sys
from collections import Counter

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")

ATOMICS = ["PULL_OUT", "RETRACT", "OPEN_DRAWER", "CLOSE_DRAWER", "OPEN_CABINET",
           "CLOSE_CABINET", "OPERATE_SOCKET", "OPEN_SINK_COVER",
           "STATIC_DISPLAY", "PERSON_SPEAKING", "OTHER", "UNKNOWN"]


def jload(s):
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except Exception:
        return []


def main():
    man = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V3_1.json"), encoding="utf-8"))
    man_sids = [s["segment_id"] for s in man["segments"]]
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    ph = ",".join("?" * len(man_sids))
    rows = [dict(r) for r in conn.execute(f"SELECT * FROM targeted_human_review_v1 WHERE segment_id IN ({ph})", man_sids)]
    cal = [dict(r) for r in conn.execute("SELECT * FROM canonical_human_truth WHERE is_current=1")]
    conn.close()

    # ---- STEP 4: 原子动作增量（从 action_sequence 多标签统计）----
    cal_seq = Counter()
    for r in cal:
        for a in jload(r.get("action_sequence")):
            cal_seq[a] += 1
    s3_seq = Counter()
    for r in rows:
        for a in jload(r.get("action_sequence")):
            s3_seq[a] += 1
    # action_group 单值也要
    cal_grp = Counter(r["action_group"] for r in cal if r.get("action_group"))
    s3_grp = Counter(r["action_group"] for r in rows if r.get("action_group"))

    print("=== STEP 4: Semantic Action 真实增量（action_sequence 原子）===")
    action_out = {}
    for a in ATOMICS:
        before = cal_seq.get(a, 0)
        new = s3_seq.get(a, 0)
        action_out[a] = {"existing_support_before": before,
                         "stage3_60_truth_count": new,
                         "combined_support_after": before + new}
        print(f"  {a:20s} before={before:4d} new60={new:4d} combined={before+new}")
    print("  action_group 333:", dict(cal_grp))
    print("  action_group 60 :", dict(s3_grp))

    gap_status = {}
    for a in ("CLOSE_CABINET", "OPERATE_SOCKET"):
        tot = action_out[a]["combined_support_after"]
        gap_status[a] = ("LIBRARY_GAP" if tot == 0 else
                         "COVERED" if tot >= 10 else f"PARTIAL({tot})")
        print(f"  GAP 检查 {a}: combined={tot} -> {gap_status[a]}")

    # ---- STEP 5: Action 候选命中质量 ----
    cand = json.load(open(os.path.join(DATA_ROOT, "STAGE3_ACTION_CANDIDATE_SUPPORT.json"), encoding="utf-8"))
    cand_rows = {c["segment_id"]: c for c in cand["candidates"]}
    man_by_sid = {r["segment_id"]: r for r in rows}
    print("\n=== STEP 5: Action 候选命中质量（候选 reason vs 人工真值）===")
    # 候选 = V2 池；V3_1 中仍保留的段才可对照
    hit_stats = {}
    total_cand = 0
    for sid, c in cand_rows.items():
        if sid not in man_by_sid:
            continue
        total_cand += 1
        reasons = c.get("action_reason", [])
        truth = set(jload(man_by_sid[sid].get("action_sequence")))
        for reason in reasons:
            if reason == "ACTION_KEYWORD_MISS":
                continue
            s = hit_stats.setdefault(reason, {"candidate": 0, "truth_hit": 0, "truth_all": 0})
            s["candidate"] += 1
            s["truth_all"] += 1
            if reason in truth:
                s["truth_hit"] += 1
    print(f"可对照候选段（V2∩V3_1）: {total_cand}")
    cand_precision = {}
    for k, v in sorted(hit_stats.items()):
        p = v["truth_hit"] / v["candidate"] * 100 if v["candidate"] else 0
        cand_precision[k] = {**v, "candidate_precision": round(p, 1)}
        print(f"  {k:18s} candidate={v['candidate']:3d} truth_hit={v['truth_hit']:3d} precision={p:.1f}%")

    out = {"manifest": "STAGE3_ACTION_TRUTH_AUDIT",
           "step4_action_increment": action_out,
           "action_group_cal333": dict(cal_grp), "action_group_stage3_60": dict(s3_grp),
           "gap_status": gap_status,
           "step5_candidate_precision": cand_precision,
           "note": "STEP5 仅对 V2 候选 ∩ V3_1 的段有效（替换段无候选 reason）；candidate_precision 是发现器命中率，非 prediction accuracy"}
    p = os.path.join(DATA_ROOT, "STAGE3_ACTION_TRUTH_AUDIT.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n->", p)


if __name__ == "__main__":
    main()
