# -*- coding: utf-8 -*-
"""Stage3 MODEL DEV — PRE-STEP 1：3 条 Human QA 二次裁决（仅 3 条，不重审 60）。

生成 STAGE3_ACTION_QA_ADJUDICATION.json（3 条），并接入 Review Center 作为
3 条二次裁决任务（只修 action_group / action_sequence / comment / status）。
裁决走 revision，不覆盖 Human Truth Lock。
"""
import json
import os
import sqlite3
import sys
from datetime import datetime

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")

QA_IDS = [
    "2cf01ef8426f41088a8016e66fc51eae",
    "bc6189b6c0684098ae5a3fc8a73f4dd8",
    "d81be396fddb4dee876de2361386f1d2",
]

# 规则：group 与 sequence 的合法映射（派生自 ACTION_MAP）
GROUP_ATOMIC_RULE = {
    "STATIC": ["STATIC_DISPLAY", "OTHER", "UNKNOWN", "NOT_APPLICABLE"],
    "SPEAKING": ["PERSON_SPEAKING", "OTHER", "UNKNOWN"],
    "EXTEND": ["PULL_OUT", "RETRACT", "PULL_OUT_THEN_RETRACT", "RETRACT_THEN_PULL_OUT", "OTHER", "UNKNOWN"],
    "DRAWER": ["OPEN_DRAWER", "CLOSE_DRAWER", "OPEN_THEN_CLOSE_DRAWER", "OTHER", "UNKNOWN"],
    "CABINET": ["OPEN_CABINET", "CLOSE_CABINET", "OTHER", "UNKNOWN"],
    "POWER_INTERACTION": ["OPERATE_SOCKET", "OTHER", "UNKNOWN"],
    "WATER_INTERACTION": ["OPEN_SINK_COVER", "OTHER", "UNKNOWN"],
    "OTHER": ["OTHER", "UNKNOWN", "NOT_APPLICABLE"],
    "UNKNOWN": ["UNKNOWN"],
}


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
    conn.close()
    by_sid = {r["segment_id"]: r for r in rows}

    items = []
    for sid in QA_IDS:
        r = by_sid[sid]
        seq = jload(r["action_sequence"])
        group = r["action_group"]
        legal = GROUP_ATOMIC_RULE.get(group, [])
        overlap = [a for a in seq if a in legal]
        conflict = not overlap and bool(seq)
        items.append({
            "segment_id": sid,
            "asset_id": r.get("asset_id", ""),
            "current_annotation": {
                "action_group": group,
                "action_sequence": seq,
                "scene_family": r.get("scene_family"),
                "product_family": r.get("product_family"),
                "people_presence": r.get("people_presence"),
                "comment": r.get("comment", ""),
                "review_status": r.get("review_status"),
            },
            "rule_check": {"group": group, "legal_atomics": legal,
                           "sequence": seq, "overlap_with_legal": overlap,
                           "conflict": conflict,
                           "note": "action_group 是主类别；sequence 是完整动作流。group 与任一 atomic 有交集即不矛盾。"},
            "adjudication_required": conflict,
            "selection_reason": "QA_ADJUDICATION_ACTION_GROUP_SEQ",
        })

    out = {
        "manifest_version": "STAGE3_ACTION_QA_ADJUDICATION",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "note": ("仅 3 条 action_group↔action_sequence 冲突二次裁决；只允许修改 "
                 "action_group / action_sequence / comment / review_status；"
                 "不显示任何 AI prediction；裁决结果走 revision，禁止覆盖 Human Truth Lock"),
        "guard": "ADJUDICATION_ONLY; DO_NOT_OVERWRITE_HUMAN_LOCK; 3 条仅",
        "rule": GROUP_ATOMIC_RULE,
        "segments": items,
    }
    p = os.path.join(DATA_ROOT, "STAGE3_ACTION_QA_ADJUDICATION.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", p)
    for it in items:
        rc = it["rule_check"]
        print(f"  {it['segment_id'][:8]} group={rc['group']} seq={rc['sequence']} "
              f"overlap={rc['overlap_with_legal']} conflict={rc['conflict']}")


if __name__ == "__main__":
    main()
