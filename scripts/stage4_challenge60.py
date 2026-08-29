# -*- coding: utf-8 -*-
"""Stage 2 — Challenge60 冻结（六类各 10）。

六类（Cal/Stage3/Mini，禁 Holdout，不与 Validation43 重叠）：
  STRONG_SINGLE_EVIDENCE / MULTI_SOURCE_AGREEMENT / CONFLICTING_EVIDENCE /
  WEAK_EVIDENCE / NEGATIVE_RULE_TRIGGER / AMBIGUOUS_MULTI_PURPOSE
采样不按"系统预测对不对"选，按 evidence 结构特征选。

CONFLICTING_EVIDENCE 定义：ASR 话语（家里/客户家/我家…）与 FACTORY 视觉场景
矛盾的段 —— 系统应降级为 UNKNOWN/CONFLICT，而非自信推断家庭场景结论。
"""
import io
import json
import os
import random
import sqlite3
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
DB = os.path.join(DATA_ROOT, "database", "materials.db")
RNG = random.Random(20260829)

HOME_WORDS = ("客户家", "家里", "自己家", "我家", "客户的家", "业主家", "业主的家", "家里面")
CLASSES = ("STRONG_SINGLE_EVIDENCE", "MULTI_SOURCE_AGREEMENT", "CONFLICTING_EVIDENCE",
           "WEAK_EVIDENCE", "NEGATIVE_RULE_TRIGGER", "AMBIGUOUS_MULTI_PURPOSE")


def jload(s):
    if isinstance(s, list):
        return s
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except Exception:
        return []


def main():
    # 已用段（Validation43 + Holdout 排除）
    v43 = json.load(open(os.path.join(DATA_ROOT, "KNOWLEDGE_BRAIN_STAGE1_VALIDATION_SET.json"), encoding="utf-8"))
    used = {s["segment_id"] for s in v43["segments"]}
    hold = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_MANIFEST_LOCK.json"), encoding="utf-8"))
    used |= {s["segment_id"] for s in hold["strata"]}
    hold2 = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V2_MANIFEST_LOCK.json"), encoding="utf-8"))
    used |= {s["segment_id"] for s in hold2["strata"]}

    # 数据池
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    pool = {}
    for r in conn.execute("SELECT segment_id, action_sequence, component_multi, function_multi, "
                          "scene_family, people_presence, material_multi, shot_role_multi "
                          "FROM canonical_human_truth WHERE is_current=1"):
        pool[r["segment_id"]] = dict(r)
    for f in ("TARGETED_REVIEW_STAGE3_V3_1.json", "TARGETED_REVIEW_STAGE3_MINI_V1.json"):
        m = json.load(open(os.path.join(DATA_ROOT, f), encoding="utf-8"))
        sids = [s["segment_id"] for s in m["segments"]]
        ph = ",".join("?" * len(sids))
        for r in conn.execute(f"SELECT segment_id, action_sequence, component_multi, function_multi, "
                              f"scene_family, people_presence, material_multi, shot_role_multi, review_status "
                              f"FROM targeted_human_review_v1 WHERE segment_id IN ({ph})", sids):
            if r["review_status"] != "EXCLUDED":
                pool[r["segment_id"]] = dict(r)

    # segment 时间窗 + transcripts（ASR 原文）
    seg_times = {}
    for r in conn.execute("SELECT segment_id, asset_id, start_ms, end_ms FROM segments"):
        seg_times[r["segment_id"]] = (r["asset_id"], r["start_ms"], r["end_ms"])
    tr_by_asset = {}
    for r in conn.execute("SELECT asset_id, start_ms, end_ms, text_corrected FROM transcripts "
                          "WHERE text_corrected IS NOT NULL AND text_corrected != ''"):
        tr_by_asset.setdefault(r["asset_id"], []).append((r["start_ms"], r["end_ms"], r["text_corrected"]))
    conn.close()

    def seg_asr_text(sid):
        meta = seg_times.get(sid)
        if not meta:
            return ""
        asset_id, s0, s1 = meta
        parts = []
        for (t0, t1, txt) in tr_by_asset.get(asset_id, []):
            if t1 >= s0 and t0 <= s1:
                parts.append(txt)
        return " ".join(parts)

    cands = [sid for sid in pool if sid not in used]
    print("候选池（非 Holdout、非 Validation43）:", len(cands))

    def classify_seg(sid):
        t = pool[sid]
        comp = jload(t.get("component_multi"))
        func = jload(t.get("function_multi"))
        scene = t.get("scene_family")
        seq = jload(t.get("action_sequence"))
        asr = seg_asr_text(sid)
        has_drawer = "DRAWER" in comp
        has_door = "CABINET_DOOR" in comp
        has_socket = "TRACK_SOCKET" in comp
        # 1. CONFLICTING：ASR 话语（家里/客户家）vs FACTORY 场景 —— 话语↔视觉矛盾
        if scene == "FACTORY" and any(w in asr for w in HOME_WORDS):
            return "CONFLICTING_EVIDENCE"
        # 2. NEGATIVE_RULE：插座存在（NR001/NR005 触发点）
        if has_socket:
            return "NEGATIVE_RULE_TRIGGER"
        # 3. STRONG_SINGLE：单组件 + 匹配功能（强单证据）
        if len(comp) == 1 and ((has_drawer and "STORAGE" in func) or (has_door and "STORAGE" in func)):
            return "STRONG_SINGLE_EVIDENCE"
        # 4. MULTI_SOURCE：多组件或多功能域（多个信号一致）
        if len(comp) >= 2 or len(func) >= 2:
            return "MULTI_SOURCE_AGREEMENT"
        # 5. WEAK：无组件（仅动作/仅功能，弱信号）
        if not comp:
            return "WEAK_EVIDENCE"
        # 6. AMBIGUOUS：其余（OTHER/OTHER、单组件无匹配等）
        return "AMBIGUOUS_MULTI_PURPOSE"

    buckets = {k: [] for k in CLASSES}
    for sid in cands:
        buckets[classify_seg(sid)].append(sid)
    print("bucket sizes:", {k: len(v) for k, v in buckets.items()})

    # 每类抽 10（随机种子固定）
    selected = []
    for k in CLASSES:
        lst = list(buckets[k])
        RNG.shuffle(lst)
        picked = lst[:10]
        selected.extend(picked)
        print(f"  {k}: 池 {len(lst)} -> 选 {len(picked)}")
    print("选中总数:", len(selected))

    # 生成 Challenge manifest（含类别标注 + 采样特征 + ASR 原文）
    segs = []
    for sid in selected:
        t = pool[sid]
        segs.append({
            "segment_id": sid,
            "challenge_class": classify_seg(sid),
            "stratum": "CAL/STAGE3/MINI",
            "evidence_features": {
                "component_multi": jload(t.get("component_multi")),
                "function_multi": jload(t.get("function_multi")),
                "scene_family": t.get("scene_family"),
                "material_multi": jload(t.get("material_multi")),
                "action_sequence": jload(t.get("action_sequence")),
                "asr_text": seg_asr_text(sid),
            },
        })
    challenge = {"manifest": "BUSINESS_COGNITION_STAGE2_CHALLENGE_V1",
                 "generated_at": "2026-08-29",
                 "guard": "DEV_ONLY; NOT_HOLDOUT; NOT_VALIDATION43; 按 evidence 结构采样，非按预测",
                 "class_spec": "STRONG_SINGLE=单组件+匹配功能; MULTI_SOURCE=多组件/多功能域; "
                               "CONFLICTING=ASR话语(家里/客户家)vs FACTORY场景; WEAK=无组件弱信号; "
                               "NEGATIVE=TRACK_SOCKET触发负规则; AMBIGUOUS=其余多义",
                 "count": len(segs),
                 "class_counts": dict(Counter(s["challenge_class"] for s in segs)),
                 "segments": segs}
    p = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_STAGE2_CHALLENGE_V1.json")
    json.dump(challenge, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", p)
    print("类别分布:", challenge["class_counts"])
    assert challenge["class_counts"] == {k: 10 for k in CLASSES}, "六类必须各 10"


if __name__ == "__main__":
    main()
