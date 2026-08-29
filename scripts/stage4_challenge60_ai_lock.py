# -*- coding: utf-8 -*-
"""Stage 2 — AI Business Cognition 60/60 锁定（AI_LOCK）。

Challenge60 的 60 段，用 BusinessCognitionServiceV2 从头生成业务认知：
evidence packet → conflicts → BusinessClaimV2（status/confidence）→
content_role_affinity / mother_theme_affinity / search_intent_candidates。
输出 AI_LOCK 冻结文件（后续 Human Review 只评审、不修改 AI 输出）。
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
DB = os.path.join(DATA_ROOT, "database", "materials.db")
CHALLENGE = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_STAGE2_CHALLENGE_V1.json")
OUT = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_STAGE2_AI_LOCK.json")


def jload(s):
    if isinstance(s, list):
        return s
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except Exception:
        return []


def main():
    import sqlite3
    from treecut.services.knowledge_service import KnowledgeService
    from treecut.services.business_cognition_v2 import BusinessCognitionServiceV2

    challenge = json.load(open(CHALLENGE, encoding="utf-8"))
    segs = challenge["segments"]
    print(f"Challenge60 读入 {len(segs)} 段 | 类别: {challenge['class_counts']}")

    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    # segment 时间窗（asset_id / start / end）
    seg_times = {}
    for r in conn.execute("SELECT segment_id, asset_id, start_ms, end_ms FROM segments"):
        seg_times[r["segment_id"]] = (r["asset_id"], r["start_ms"], r["end_ms"])

    # transcripts（ASR）
    tr_by_asset = {}
    for r in conn.execute("SELECT asset_id, start_ms, end_ms, text_corrected FROM transcripts "
                          "WHERE text_corrected IS NOT NULL AND text_corrected != ''"):
        tr_by_asset.setdefault(r["asset_id"], []).append((r["start_ms"], r["end_ms"], r["text_corrected"]))
    # ocr_text（按 asset + 时间窗）
    ocr_by_asset = {}
    for r in conn.execute("SELECT asset_id, frame_timestamp_ms, text FROM ocr_text WHERE text IS NOT NULL AND text != ''"):
        ocr_by_asset.setdefault(r["asset_id"], []).append((r["frame_timestamp_ms"], r["text"]))

    # 视觉认知（canonical 池作为 seg_cog 输入，与 Challenge60 同一来源）
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

    def seg_texts(sid):
        meta = seg_times.get(sid)
        if not meta:
            return "", ""
        asset_id, s0, s1 = meta
        asr_parts, ocr_parts = [], []
        for (t0, t1, txt) in tr_by_asset.get(asset_id, []):
            if t1 >= s0 and t0 <= s1:
                asr_parts.append(txt)
        for (ts, txt) in ocr_by_asset.get(asset_id, []):
            if s0 <= ts <= s1:
                ocr_parts.append(txt)
        return " ".join(asr_parts), " ".join(ocr_parts)

    ks = KnowledgeService()
    svc = BusinessCognitionServiceV2(ks)
    print("V1.2 知识就绪: facts=", len(ks.retrieve_facts()), "| active rules=", len(ks.retrieve_active_rules()))

    results = []
    missing = []
    for s in segs:
        sid = s["segment_id"]
        t = pool.get(sid)
        if t is None:
            missing.append(sid)
            continue
        seg_cog = {
            "action_sequence": jload(t.get("action_sequence")),
            "component": jload(t.get("component_multi")),
            "function": jload(t.get("function_multi")),
            "scene_family": t.get("scene_family"),
            "people_presence": t.get("people_presence"),
            "material": jload(t.get("material_multi")),
            "shot_role": jload(t.get("shot_role_multi")),
        }
        asr_text, ocr_text = seg_texts(sid)
        bc = svc.cognize(sid, seg_cog, asr_text=asr_text, ocr_text=ocr_text,
                         asset_id=seg_times.get(sid, ("", 0, 0))[0] if sid in seg_times else "")
        bc["challenge_class"] = s["challenge_class"]
        results.append(bc)

    print(f"AI cognition 完成 {len(results)}/{len(segs)} | 缺失 {missing}")

    # 统计
    from collections import Counter
    st = Counter()
    for r in results:
        for c in r["business_claims"]:
            st[c["claim_status"]] += 1
    n_need = sum(1 for r in results if r["user_needs"])
    n_val = sum(1 for r in results if r["business_values"])
    n_role = sum(1 for r in results if r["content_role_affinity"])
    n_theme = sum(1 for r in results if r["mother_theme_affinity"])
    n_intent = sum(1 for r in results if r["search_intent_candidates"])
    n_conflict = sum(1 for r in results if r["conflicts"])
    print("claim_status 分布:", dict(st))
    print(f"覆盖: user_needs {n_need} | business_values {n_val} | role_affinity {n_role} | "
          f"theme_affinity {n_theme} | search_intent {n_intent} | conflicts {n_conflict}")

    out = {
        "manifest": "BUSINESS_COGNITION_STAGE2_AI_LOCK",
        "lock_kind": "AI_LOCK",
        "knowledge_snapshot": "KNOWLEDGE_SNAPSHOT_V1_2 (a9ac59f60e13a0bc8bb6949f99884202d3e3e3872d7c3c153e09cc00b5e79eec)",
        "engine": "BusinessCognitionServiceV2 + EvidenceResolverV1 + ConflictResolverV1 + BusinessClaimV2",
        "guard": "AI 输出冻结；Human Business Review 只评审不修改 AI 输出；SEGMENT_SCOPE 仅产出 affinity/candidates，无 primary",
        "count": len(results),
        "claim_status_distribution": dict(st),
        "coverage": {"user_needs": n_need, "business_values": n_val,
                     "content_role_affinity": n_role, "mother_theme_affinity": n_theme,
                     "search_intent_candidates": n_intent, "conflicts": n_conflict},
        "results": results,
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT)
    ks.unload()


if __name__ == "__main__":
    main()
