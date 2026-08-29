# -*- coding: utf-8 -*-
"""Stage 2.1 — Known V3 Replay + Secondary36 Behavior Diff（旧 V2 vs Candidate V2.1）。

输出 1：BUSINESS_COGNITION_V3_KNOWN_DEV_REPLAY_V2_1.json
  V3 12 条上运行 Candidate V2.1（KNOWN_DEV，非成绩）：
  - 检查原 Storage 错误是否按预期 SUPPORTED → CANDIDATE/WEAK/UNKNOWN
  - 检查 V3 原 29 个 CLEARLY 正确 claim 是否保持 SUPPORTED 或合理降级

输出 2：BUSINESS_COGNITION_STAGE2_SECONDARY_DEV_V1.json
  Challenge60 剩余 36（非 Holdout/Validation43/Human24/V3）：
  旧 V2 vs Candidate V2.1 行为 diff：
  SUPPORTED/CANDIDATE/WEAK/UNKNOWN/BLOCKED 计数、per-label transition、
  Storage claim reduction、Power transition、Negative violation、Conflict count
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
V3_MANIFEST = os.path.join(DATA_ROOT, "HUMAN_CALIBRATION_V3_MANIFEST.json")
CHALLENGE = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_STAGE2_CHALLENGE_V1.json")
HUMAN24_MANIFEST = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_STAGE2_HUMAN_REVIEW_V1.json")
OUT_REPLAY = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_V3_KNOWN_DEV_REPLAY_V2_1.json")
OUT_SEC = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_STAGE2_SECONDARY_DEV_V1.json")


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
    from treecut.services.business_cognition_v2 import BusinessCognitionServiceV2
    from treecut.services.business_cognition_v2_1 import BusinessCognitionServiceV2_1

    # ---- 数据池 ----
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

    # segment 时间窗 + transcripts（ASR 原文，与 V3 Human 审核所见一致）
    seg_times = {}
    for r in conn.execute("SELECT segment_id, asset_id, start_ms, end_ms FROM segments"):
        seg_times[r["segment_id"]] = (r["asset_id"], r["start_ms"], r["end_ms"])
    tr_by_asset = {}
    for r in conn.execute("SELECT asset_id, start_ms, end_ms, text_corrected FROM transcripts "
                          "WHERE text_corrected IS NOT NULL AND text_corrected != ''"):
        tr_by_asset.setdefault(r["asset_id"], []).append((r["start_ms"], r["end_ms"], r["text_corrected"]))
    conn.close()

    def seg_asr(sid):
        meta = seg_times.get(sid)
        if not meta:
            return ""
        asset_id, s0, s1 = meta
        parts = []
        for (t0, t1, txt) in tr_by_asset.get(asset_id, []):
            if t1 >= s0 and t0 <= s1:
                parts.append(txt)
        return " ".join(parts)

    def seg_cog(t, sid=None):
        return {"action_sequence": jload(t.get("action_sequence")),
                "component": jload(t.get("component_multi")),
                "function": jload(t.get("function_multi")),
                "scene_family": t.get("scene_family"),
                "people_presence": t.get("people_presence"),
                "material": jload(t.get("material_multi")),
                "shot_role": jload(t.get("shot_role_multi"))}

    v2 = BusinessCognitionServiceV2()
    v21 = BusinessCognitionServiceV2_1()

    # ================= 1. V3 Known Dev Replay =================
    v3_man = json.load(open(V3_MANIFEST, encoding="utf-8"))
    v3_ids = [s["segment_id"] for s in v3_man["segments"]]
    replay = []
    storage_fixed = []
    regression_risk = []
    for sid in v3_ids:
        if sid not in pool:
            continue
        sc = seg_cog(pool[sid])
        bc = v21.cognize(sid, sc, asr_text=seg_asr(sid))
        replay.append({"segment_id": sid,
                       "claims": [{"category": c["claim_category"], "value": c["claim_value"],
                                   "status": c["claim_status"], "grade": c["evidence_grade"]}
                                  for c in bc["business_claims"]]})
    # 检查 Storage 修复 + 非 Storage 回归
    v3_human = {}
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    for r in conn.execute("SELECT * FROM stage2_business_cognition_calibration_v3"):
        v3_human[r["segment_id"]] = json.loads(r["label_states"] or "{}")
    conn.close()

    for r in replay:
        sid = r["segment_id"]
        st_map = {c["value"]: c["status"] for c in r["claims"]}
        # Storage: 原 V3 判 FALSE 的 4 个 SUPPORTED 是否降级
        for lab in ("STORAGE", "STORAGE_EFFICIENCY"):
            if v3_human.get(sid, {}).get(lab) == "NOT_SUPPORTED" and st_map.get(lab) == "SUPPORTED":
                storage_fixed.append({"segment_id": sid[:12], "label": lab,
                                      "still_supported": True})
        # 回归检查：V3 原 CLEARLY（29 个中）在 V2.1 是否被大范围降级（非 Storage 良好路径）
        for lab, state in v3_human.get(sid, {}).items():
            if state == "CLEARLY_SUPPORTED" and st_map.get(lab) not in ("SUPPORTED",):
                # 允许 Storage 类合理降级；非 Storage 降级 → 标注意
                if lab not in ("STORAGE", "STORAGE_EFFICIENCY"):
                    regression_risk.append({"segment_id": sid[:12], "label": lab,
                                            "v3": "CLEARLY_SUPPORTED", "v21": st_map.get(lab)})
    print("V3 Replay: storage_fixed 仍 SUPPORTED:", len(storage_fixed),
          "| 非 Storage 回归风险:", len(regression_risk), regression_risk[:6])

    replay_out = {"manifest": "BUSINESS_COGNITION_V3_KNOWN_DEV_REPLAY_V2_1",
                  "guard": "KNOWN_DEV; CONTAMINATED_FOR_EVALUATION; NOT_INDEPENDENT; "
                           "NO_GENERALIZATION_CLAIM; 仅检查 Storage 修复方向 + 回归风险",
                  "engine": "BusinessCognitionV2_1 (Candidate)", "count": len(replay),
                  "storage_still_supported_where_false": storage_fixed,
                  "non_storage_regression_risk": regression_risk,
                  "per_segment": replay}
    json.dump(replay_out, open(OUT_REPLAY, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT_REPLAY)

    # ================= 2. Secondary36 Behavior Diff =================
    ai_lock = json.load(open(AI_LOCK, encoding="utf-8"))
    used = {s["segment_id"] for s in v3_man["segments"]}
    for f in ("KNOWLEDGE_BRAIN_STAGE1_VALIDATION_SET.json", "FRESH_HOLDOUT_V1_MANIFEST_LOCK.json",
              "FRESH_HOLDOUT_V2_MANIFEST_LOCK.json"):
        d = json.load(open(os.path.join(DATA_ROOT, f), encoding="utf-8"))
        used |= {s["segment_id"] for s in (d.get("segments", d.get("strata", [])))}
    hm = json.load(open(HUMAN24_MANIFEST, encoding="utf-8"))
    used |= {s["segment_id"] for s in hm["segments"]}
    # Challenge60 剩余 36（排除 V3 12 与其他）
    ch = json.load(open(CHALLENGE, encoding="utf-8"))
    sec_ids = [s["segment_id"] for s in ch["segments"] if s["segment_id"] not in used][:36]
    print("Secondary36 段数:", len(sec_ids))

    old_v2_by_sid = {r["segment_id"]: r for r in ai_lock["results"]}
    sec = []
    for sid in sec_ids:
        if sid not in pool:
            continue
        sc = seg_cog(pool[sid])
        bc_old = old_v2_by_sid.get(sid)
        old_status = Counter()
        if bc_old:
            old_status = Counter(c["claim_status"] for c in bc_old["business_claims"])
        bc_new = v21.cognize(sid, sc, asr_text=seg_asr(sid))
        new_status = Counter(c["claim_status"] for c in bc_new["business_claims"])
        sec.append({"segment_id": sid,
                    "old_v2_status": dict(old_status),
                    "v21_status": dict(new_status),
                    "v21_claims": [{"category": c["claim_category"], "value": c["claim_value"],
                                    "status": c["claim_status"]} for c in bc_new["business_claims"]]})

    # 汇总
    agg_old = Counter()
    agg_new = Counter()
    storage_trans = Counter()
    power_trans = Counter()
    dining_office_trans = Counter()
    for s in sec:
        for st, n in s["old_v2_status"].items():
            agg_old[st] += n
        for st, n in s["v21_status"].items():
            agg_new[st] += n
        for c in s["v21_claims"]:
            if c["value"] in ("STORAGE", "STORAGE_EFFICIENCY"):
                storage_trans[c["status"]] += 1
            elif c["value"] in ("CHARGING_POWER", "POWER_CONVENIENCE"):
                power_trans[c["status"]] += 1
            elif c["value"] in ("DINING", "OFFICE", "DINING_CONVENIENCE", "WORK_FROM_HOME"):
                dining_office_trans[c["status"]] += 1
    print("\nSecondary36 状态分布：")
    print("  旧 V2:", dict(agg_old))
    print("  V2.1:", dict(agg_new))
    print("  Storage claim (V2.1):", dict(storage_trans))
    print("  Power claim (V2.1):", dict(power_trans))
    print("  Dining/Office (V2.1):", dict(dining_office_trans))

    sec_out = {"manifest": "BUSINESS_COGNITION_STAGE2_SECONDARY_DEV_V1",
               "guard": "STAGE2_SECONDARY_DEV; 无 Human Truth; 仅行为 diff（旧 V2 vs V2.1）",
               "count": len(sec),
               "aggregate_old_v2": dict(agg_old),
               "aggregate_v21": dict(agg_new),
               "storage_claim_status": dict(storage_trans),
               "power_claim_status": dict(power_trans),
               "dining_office_claim_status": dict(dining_office_trans),
               "per_segment": sec}
    json.dump(sec_out, open(OUT_SEC, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT_SEC)
    v2.ks.unload()
    v21.ks.unload()


if __name__ == "__main__":
    main()
