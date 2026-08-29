# -*- coding: utf-8 -*-
"""Stage3 TRACK 1 — QA 裁决后：生成 STAGE3_ACTION_QA_ADJUDICATION_LOCK.json。

用法：用户完成 3 条裁决后运行。
- 读取 targeted_human_review_v1 中 3 条 QA 段的最新（裁决后）action_group/action_sequence
- 生成 revision（不覆盖 Human Truth Lock）：新文件记录裁决前后对照
- 重新计算受影响的 action_group/action_sequence/atomic action support
"""
import json
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")

QA_IDS = [
    "2cf01ef8426f41088a8016e66fc51eae",
    "bc6189b6c0684098ae5a3fc8a73f4dd8",
    "d81be396fddb4dee876de2361386f1d2",
]


def jload(s):
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except Exception:
        return []


def main():
    # 原始（裁决前）来自 HUMAN_LOCK
    lock = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V3_1_HUMAN_LOCK.json"), encoding="utf-8"))
    orig = {s["segment_id"]: s for s in lock["segments"]}

    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    # 裁决后 = 当前表内最新行（人工保存覆盖了 targeted_human_review_v1）
    ph = ",".join("?" * len(QA_IDS))
    rows = [dict(r) for r in conn.execute(f"SELECT * FROM targeted_human_review_v1 WHERE segment_id IN ({ph})", QA_IDS)]
    conn.close()
    cur = {r["segment_id"]: r for r in rows}

    revisions = []
    changed = []
    for sid in QA_IDS:
        o = orig.get(sid, {})
        c = cur.get(sid, {})
        # HUMAN_LOCK 的 seq 已是 list；表内是 JSON 字符串
        o_seq = o.get("action_sequence") if isinstance(o.get("action_sequence"), list) else jload(o.get("action_sequence"))
        c_seq = c.get("action_sequence") if isinstance(c.get("action_sequence"), list) else jload(c.get("action_sequence"))
        rev = {
            "segment_id": sid,
            "before": {"action_group": o.get("action_group"), "action_sequence": o_seq},
            "after": {"action_group": c.get("action_group"), "action_sequence": c_seq,
                      "comment": c.get("comment", ""), "review_status": c.get("review_status"),
                      "human_confidence": c.get("human_confidence")},
        }
        if rev["before"] != rev["after"]:
            changed.append(sid)
        revisions.append(rev)

    # 重新计算受影响的 atomic action support（Cal333 + Stage3 有效 + QA 裁决后）
    tman = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V3_1.json"), encoding="utf-8"))
    t_sids = [s["segment_id"] for s in tman["segments"]]
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    seq_counter = Counter()
    for r in conn.execute("SELECT action_sequence FROM canonical_human_truth WHERE is_current=1"):
        for a in jload(r["action_sequence"]):
            seq_counter[a] += 1
    ph2 = ",".join("?" * len(t_sids))
    for r in conn.execute(f"SELECT action_sequence, review_status FROM targeted_human_review_v1 WHERE segment_id IN ({ph2})", t_sids):
        if r["review_status"] != "EXCLUDED":
            for a in jload(r["action_sequence"]):
                seq_counter[a] += 1
    conn.close()
    support_after = dict(seq_counter)

    out = {
        "manifest": "STAGE3_ACTION_QA_ADJUDICATION_LOCK",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "human_truth_sha256_original": lock.get("human_truth_sha256"),
        "note": "3 条 QA 裁决 revision；原始 Human Truth Lock 未覆盖（仅追加 revision 记录）",
        "revisions": revisions,
        "changed_segments": changed,
        "atomic_action_support_after": support_after,
    }
    p = os.path.join(DATA_ROOT, "STAGE3_ACTION_QA_ADJUDICATION_LOCK.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", p)
    print("changed:", changed)
    for r in revisions:
        print(f"  {r['segment_id'][:8]} {r['before']['action_group']}->{r['after']['action_group']} "
              f"{r['before']['action_sequence']}->{r['after']['action_sequence']}")


if __name__ == "__main__":
    main()
