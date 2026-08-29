# -*- coding: utf-8 -*-
"""Stage 2.1 — Fresh18 AI_LOCK（Candidate V2.1 先锁）。

运行 BusinessCognitionV2_1 on Fresh18，记录 engine_version/rule_version/
knowledge_snapshot/timestamp/hash。锁定后禁止修改。
"""
import hashlib
import io
import json
import os
import sqlite3
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
DB = os.path.join(DATA_ROOT, "database", "materials.db")
FRESH = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_FRESH_VALIDATION_V1.json")
OUT = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_FRESH_V1_AI_LOCK.json")


def jload(s):
    if isinstance(s, list):
        return s
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except Exception:
        return []


def main():
    sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")
    from treecut.services.business_cognition_v2_1 import BusinessCognitionServiceV2_1

    fresh = json.load(open(FRESH, encoding="utf-8"))
    segs = fresh["segments"]

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
    conn.close()

    svc = BusinessCognitionServiceV2_1()
    results = []
    missing = []
    for s in segs:
        sid = s["segment_id"]
        t = pool.get(sid)
        if t is None:
            missing.append(sid)
            continue
        # 用 manifest 冻结证据（与 Human 审核同源）
        fe = s.get("frozen_evidence", {})
        sc = {"action_sequence": jload(t.get("action_sequence")),
              "component": jload(t.get("component_multi")),
              "function": jload(t.get("function_multi")),
              "scene_family": t.get("scene_family"),
              "people_presence": t.get("people_presence"),
              "material": jload(t.get("material_multi")),
              "shot_role": jload(t.get("shot_role_multi"))}
        bc = svc.cognize(sid, sc, asr_text=fe.get("asr_text", ""))
        bc["evidence_structure_class"] = s["evidence_structure_class"]
        results.append(bc)
    print(f"Fresh18 AI: {len(results)}/{len(segs)} | 缺失 {missing}")

    # 统计
    from collections import Counter
    st = Counter()
    for r in results:
        for c in r["business_claims"]:
            st[c["claim_status"]] += 1
    print("claim_status 分布:", dict(st))
    storage = Counter()
    for r in results:
        for c in r["business_claims"]:
            if c["claim_value"] in ("STORAGE", "STORAGE_EFFICIENCY"):
                storage[c["claim_status"]] += 1
    print("Storage claims:", dict(storage))

    payload = json.dumps(results, ensure_ascii=False, sort_keys=True)
    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    lock = {
        "manifest": "BUSINESS_COGNITION_FRESH_V1_AI_LOCK",
        "engine_version": "BusinessCognitionV2_1 (Candidate)",
        "rule_version": "STAGE2_1_GATES_V1 (EvidenceStrengthV2 + Storage/Power Gate + UtteranceContext)",
        "knowledge_snapshot": "KNOWLEDGE_SNAPSHOT_V1_2 (a9ac59f60e13a0bc8bb6949f99884202d3e3e3872d7c3c153e09cc00b5e79eec)",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sha256": h,
        "guard": "FRESH_AI_LOCKED; 锁定后禁止修改; Human 盲审不显示此结果",
        "count": len(results),
        "claim_status_distribution": dict(st),
        "storage_claim_status": dict(storage),
        "results": results,
    }
    json.dump(lock, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT)
    print("sha256:", h)
    svc.ks.unload()


if __name__ == "__main__":
    main()
