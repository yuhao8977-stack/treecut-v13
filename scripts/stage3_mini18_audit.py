# -*- coding: utf-8 -*-
"""Stage3 MINI18 POST-REVIEW — STEP 1-13 完整审计。

STEP1: 完整性校验（missing/extra/duplicate=0）
STEP2: 冻结 Mini18 Human Truth Lock（human_truth_sha256）
STEP3: 三类采样目标真实命中（candidate_precision）
STEP4-6: OPERATE_SOCKET/CUSTOMER_HOME/SOLID_WOOD 逐类真实结果 + FP 原因
STEP7: 真实 support 更新（Cal333 + Stage3 + Mini18 分集合合并，禁 >333 错误）
STEP8: 发现器价值判定
STEP9: FP 原因分类
STEP10: Mini18 对 Semantic Action 的影响
STEP11: 是否还需人工审核
STEP12: Stage3 Final Consolidation 输入
STEP13: 输出
"""
import hashlib
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")

SINGLE = ["scene_family", "scene_subtype", "product_family", "product_variant",
          "action_group", "shot_scale", "people_presence", "product_visibility"]
MULTI = ["material_multi", "component_multi", "function_multi", "shot_role_multi"]


def jload(s):
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except Exception:
        return []


def main():
    # ---- 数据 ----
    mini = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_MINI_V1.json"), encoding="utf-8"))
    mini_sids = [s["segment_id"] for s in mini["segments"]]
    cal = json.load(open(os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V2_MANIFEST.json"), encoding="utf-8"))
    cal_sids = {s["segment_id"] for s in cal["segments"]}
    tman = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V3_1.json"), encoding="utf-8"))
    t_sids = [s["segment_id"] for s in tman["segments"]]

    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    ph = ",".join("?" * len(mini_sids))
    mini_rows = [dict(r) for r in conn.execute(f"SELECT * FROM targeted_human_review_v1 WHERE segment_id IN ({ph})", mini_sids)]
    cal_rows = [dict(r) for r in conn.execute("SELECT * FROM canonical_human_truth WHERE is_current=1")]
    ph2 = ",".join("?" * len(t_sids))
    s3_rows = [dict(r) for r in conn.execute(f"SELECT * FROM targeted_human_review_v1 WHERE segment_id IN ({ph2})", t_sids)]
    conn.close()

    # ---- STEP 1: 完整性 ----
    db_sids = [r["segment_id"] for r in mini_rows]
    missing = [s for s in mini_sids if s not in set(db_sids)]
    extra = [r for r in db_sids if r not in set(mini_sids)]
    dup = [s for s in set(mini_sids) if mini_sids.count(s) > 1]
    join = {"manifest_count": len(mini_sids), "human_count": len(mini_rows),
            "missing": missing, "extra": extra, "duplicate": dup,
            "pass": not missing and not extra and not dup}
    status_c = dict(Counter(r["review_status"] for r in mini_rows))
    conf_c = dict(Counter(r["human_confidence"] for r in mini_rows))
    dict_c = dict(Counter(r["dictionary_version"] for r in mini_rows))
    print("STEP1:", join["pass"], status_c, conf_c, dict_c)

    # ---- STEP 2: Human Truth Lock ----
    by_sid = {r["segment_id"]: r for r in mini_rows}
    lock_segments = []
    for sid in sorted(mini_sids):
        r = by_sid[sid]
        lock_segments.append({
            "segment_id": sid,
            "scene_family": r["scene_family"], "scene_subtype": r["scene_subtype"],
            "product_family": r["product_family"], "product_variant": r["product_variant"],
            "material": jload(r["material_multi"]), "component": jload(r["component_multi"]),
            "function": jload(r["function_multi"]), "action_group": r["action_group"],
            "action_sequence": jload(r["action_sequence"]), "shot_scale": r["shot_scale"],
            "shot_role": jload(r["shot_role_multi"]), "people_presence": r["people_presence"],
            "product_visibility": r["product_visibility"], "quality": r.get("quality"),
            "human_confidence": r["human_confidence"], "review_status": r["review_status"],
            "comment": r.get("comment", ""), "operator": r.get("operator", "")})
    truth_payload = {"manifest": "TARGETED_REVIEW_STAGE3_MINI_V1",
                     "dictionary_version": "ANNOTATION_DICTIONARY_V2_1",
                     "segments": lock_segments}
    canon = json.dumps(truth_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    human_sha = hashlib.sha256(canon).hexdigest()
    lock = {"manifest_version": "TARGETED_REVIEW_STAGE3_MINI_V1_HUMAN_LOCK",
            "frozen_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "human_truth_sha256": human_sha, "count": len(lock_segments),
            "review_status_distribution": status_c,
            "human_confidence_distribution": conf_c,
            "dictionary_version": dict_c,
            "guard": "DO_NOT_OVERWRITE; 修订走 revision/adjudication",
            "segments": lock_segments}
    lp = os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_MINI_V1_HUMAN_LOCK.json")
    json.dump(lock, open(lp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("STEP2: lock ->", lp, "sha:", human_sha)

    # ---- STEP 3-6: 三类候选真实命中 ----
    tgt_map = {s["segment_id"]: s["sampling_target"] for s in mini["segments"]}
    # 审核前候选证据（discovery audit）
    disc = json.load(open(os.path.join(DATA_ROOT, "STAGE3_MINI_BATCH_DISCOVERY_AUDIT.json"), encoding="utf-8"))
    ev_map = {}
    for cat in ("OPERATE_SOCKET", "CUSTOMER_HOME", "SOLID_WOOD"):
        for seg in disc["per_category"].get(cat, {}).get("segments", []):
            ev_map[seg["segment_id"]] = {"category": cat, "evidence": seg.get("evidence", []),
                                         "score": seg.get("score")}

    def seq_has(r, atom):
        return atom in jload(r.get("action_sequence"))

    def mat_has(r, lab):
        return lab in jload(r.get("material_multi"))

    cats = ["OPERATE_SOCKET", "CUSTOMER_HOME", "SOLID_WOOD"]
    per_cat = {}
    for cat in cats:
        cands = [s for s in mini_sids if tgt_map.get(s) == cat]
        tp, tn, unk, excl = 0, 0, 0, 0
        details = []
        for sid in cands:
            r = by_sid[sid]
            status = r["review_status"]
            if status == "EXCLUDED":
                excl += 1
                details.append({"sid": sid, "hit": False, "reason": "EXCLUDED", "truth": {}})
                continue
            if cat == "OPERATE_SOCKET":
                hit = seq_has(r, "OPERATE_SOCKET")
            elif cat == "CUSTOMER_HOME":
                hit = r["scene_family"] == "CUSTOMER_HOME"
            else:  # SOLID_WOOD
                hit = mat_has(r, "实木")
            if r.get("scene_family") == "UNKNOWN" and r.get("material_multi") in ("[]", "[\"UNKNOWN\"]"):
                unk += 1
                hit = None
            if hit:
                tp += 1
            elif hit is False:
                tn += 1
            details.append({"sid": sid, "hit": hit,
                            "evidence": ev_map.get(sid, {}).get("evidence", []),
                            "truth_scene": r.get("scene_family"),
                            "truth_material": jload(r.get("material_multi")),
                            "truth_seq": jload(r.get("action_sequence")),
                            "truth_group": r.get("action_group")})
        prec = tp / (tp + tn) * 100 if (tp + tn) else 0.0
        per_cat[cat] = {"candidate_count": len(cands), "truth_positive": tp,
                        "truth_negative": tn, "unknown": unk, "excluded": excl,
                        "candidate_precision": round(prec, 1), "details": details}
        print(f"STEP3 [{cat}] cand={len(cands)} TP={tp} TN={tn} UNK={unk} EXCL={excl} precision={prec:.1f}%")

    # ---- STEP 7: 真实 support（三集合分别 + 合并）----
    def single(rs, f):
        return dict(Counter(r.get(f) for r in rs if r.get(f)))

    def multi(rs, f):
        return dict(Counter(l for r in rs for l in jload(r.get(f))))

    cal333 = [r for r in cal_rows if r["segment_id"] in cal_sids]
    s3_valid = [r for r in s3_rows if r["review_status"] != "EXCLUDED"]
    mini_valid = [r for r in mini_rows if r["review_status"] != "EXCLUDED"]
    support = {}
    for f in SINGLE:
        support[f] = {"cal333": single(cal333, f), "stage3_60": single(s3_valid, f),
                      "mini18": single(mini_valid, f)}
    for f in MULTI:
        support[f] = {"cal333": multi(cal333, f), "stage3_60": multi(s3_valid, f),
                      "mini18": multi(mini_valid, f)}
    support["_action_sequence"] = {"cal333": multi(cal333, "action_sequence"),
                                   "stage3_60": multi(s3_valid, "action_sequence"),
                                   "mini18": multi(mini_valid, "action_sequence")}
    combined = {}
    for f in SINGLE + MULTI + ["_action_sequence"]:
        m = Counter(support[f]["cal333"])
        for part in ("stage3_60", "mini18"):
            for k, v in support[f][part].items():
                m[k] += v
        combined[f] = dict(m)
    support["combined"] = combined
    # 重点字段
    for atom in ("OPERATE_SOCKET", "OPEN_SINK_COVER", "CLOSE_DRAWER",
                 "OPEN_DRAWER", "CLOSE_CABINET", "PULL_OUT", "RETRACT"):
        print(f"STEP7 action[{atom}]: cal={support['_action_sequence']['cal333'].get(atom,0)} "
              f"s3={support['_action_sequence']['stage3_60'].get(atom,0)} "
              f"mini={support['_action_sequence']['mini18'].get(atom,0)} "
              f"combined={combined['_action_sequence'].get(atom,0)}")
    print(f"STEP7 scene[CUSTOMER_HOME]: cal={support['scene_family']['cal333'].get('CUSTOMER_HOME',0)} "
          f"s3={support['scene_family']['stage3_60'].get('CUSTOMER_HOME',0)} "
          f"mini={support['scene_family']['mini18'].get('CUSTOMER_HOME',0)} "
          f"combined={combined['scene_family'].get('CUSTOMER_HOME',0)}")
    print(f"STEP7 material[实木]: cal={support['material_multi']['cal333'].get('实木',0)} "
          f"s3={support['material_multi']['stage3_60'].get('实木',0)} "
          f"mini={support['material_multi']['mini18'].get('实木',0)} "
          f"combined={combined['material_multi'].get('实木',0)}")

    # ---- STEP 8-9: 发现器判定 + FP 原因 ----
    def fp_reason(cat, det):
        reasons = []
        for x in det:
            if x["hit"]:
                continue
            ev = " ".join(str(e) for e in x.get("evidence", []))
            if cat == "OPERATE_SOCKET":
                reasons.append("COMPONENT_NOT_ACTION" if ("TRACK_SOCKET" in ev or "APPLIANCE_SLOT" in ev)
                               else "ASR_KEYWORD_FALSE_POSITIVE")
            elif cat == "CUSTOMER_HOME":
                reasons.append("SCENE_CONTEXT_FALSE_POSITIVE")
            else:
                reasons.append("WOOD_TEXTURE_FALSE_POSITIVE" if "wood_scores" in ev
                               else "LOCAL_MATERIAL_NOT_PRIMARY")
        return dict(Counter(reasons))

    verdict8 = {}
    for cat in cats:
        p = per_cat[cat]["candidate_precision"]
        if p >= 50:
            v = "GOOD_DISCOVERY"
        elif p >= 20:
            v = "USABLE_WITH_FILTER"
        elif p > 0:
            v = "LOW_PRECISION"
        else:
            v = "FAILED_DISCOVERY"
        verdict8[cat] = v
        print(f"STEP8 [{cat}] precision={p}% -> {v}")

    fp_analysis = {cat: fp_reason(cat, per_cat[cat]["details"]) for cat in cats}
    print("STEP9 FP 原因:", json.dumps(fp_analysis, ensure_ascii=False))

    # ---- STEP 10: Mini18 对 Semantic Action ----
    op_new = support["_action_sequence"]["mini18"].get("OPERATE_SOCKET", 0)
    op_combined = combined["_action_sequence"].get("OPERATE_SOCKET", 0)
    sa_impact = {"OPERATE_SOCKET_new_truth": op_new, "combined_after": op_combined,
                 "status": ("READY_FOR_DEV" if op_combined >= 10 else
                            "LIMITED" if op_combined >= 5 else "INSUFFICIENT_SAMPLE"),
                 "note": "Mini18 只补 OPERATE_SOCKET 动作；不解决 OPEN/CLOSE_DRAWER/CABINET/PULL/RETRACT state-change"}
    print("STEP10:", sa_impact)

    # ---- STEP 11: 是否还需人工审核 ----
    gaps = {}
    for atom in ("OPERATE_SOCKET", "OPEN_SINK_COVER", "CLOSE_DRAWER"):
        tot = combined["_action_sequence"].get(atom, 0)
        gaps[atom] = tot
    # 候选池条件：仅当该类别在素材库有大量候选（>20 unique asset）且接近门槛才 MAYBE
    disc2 = json.load(open(os.path.join(DATA_ROOT, "STAGE3_DATA_GAP_DISCOVERY_V2.json"), encoding="utf-8"))
    pool_assets = {
        "OPERATE_SOCKET": disc2["gaps"].get("OPERATE_SOCKET", {}).get("unique_asset_count", 0),
        "OPEN_SINK_COVER": disc2["gaps"].get("OPEN_SINK_COVER", {}).get("unique_asset_count", 0),
        "CLOSE_DRAWER": disc2["gaps"].get("CLOSE_DRAWER", {}).get("unique_asset_count", 0),
    }
    verdict11 = "NO_MORE_MANUAL_REVIEW_FOR_STAGE3"
    note11 = "默认不再人工批"
    for a in gaps:
        if 5 <= gaps[a] < 10 and pool_assets.get(a, 0) >= 20:
            verdict11 = "MAYBE_MINOR_BATCH_LE10"
            note11 = f"{a} 候选池充足({pool_assets[a]} asset) 且 support {gaps[a]} 接近门槛 → 可考虑 <=10 条"
            break
    print("STEP11:", verdict11, note11, gaps, "pool_assets:", pool_assets)

    # ---- STEP 12: Final Consolidation 输入 ----
    consolidation = {
        "people_presence": "READY_CANDIDATE",
        "product_family": "READY_CANDIDATE",
        "component": "READY_CANDIDATE",
        "function": "READY_CANDIDATE",
        "scene_family": "LIMITED",
        "material": "EXPERIMENTAL",
        "shot_role": "EXPERIMENTAL",
        "product_variant": "LIMITED",
        "semantic_action": "EXPERIMENTAL",
    }
    print("STEP12:", json.dumps(consolidation, ensure_ascii=False))

    # ---- 输出 ----
    res = {"manifest": "STAGE3_MINI18_DISCOVERY_PRECISION",
           "join": join, "status": status_c, "confidence": conf_c,
           "human_truth_sha256": human_sha,
           "per_category": per_cat,
           "discovery_verdict": verdict8,
           "fp_reason_analysis": fp_analysis,
           "semantic_action_impact": sa_impact,
           "review_verdict": {"verdict": verdict11, "note": note11, "gaps": gaps},
           "consolidation_input": consolidation}
    p = os.path.join(DATA_ROOT, "STAGE3_MINI18_DISCOVERY_PRECISION.json")
    json.dump(res, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", p)

    # STAGE3_FINAL_LABEL_SUPPORT.json
    sp = os.path.join(DATA_ROOT, "STAGE3_FINAL_LABEL_SUPPORT.json")
    json.dump({"manifest": "STAGE3_FINAL_LABEL_SUPPORT", "support": support,
               "note": "Cal333(333) + Stage3(有效) + Mini18(有效) 分集合统计后合并；多标签为 occurrence"},
              open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", sp)

    # STAGE3_FINAL_CONSOLIDATION_INPUT.json
    cp = os.path.join(DATA_ROOT, "STAGE3_FINAL_CONSOLIDATION_INPUT.json")
    json.dump({"manifest": "STAGE3_FINAL_CONSOLIDATION_INPUT",
               "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
               "field_status": consolidation,
               "discovery_verdict": verdict8,
               "semantic_action_status": "EXPERIMENTAL",
               "review_verdict": verdict11,
               "note": "Final Consolidation 输入；本轮未改任何 Routing/Policy/模型"},
              open(cp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", cp)


if __name__ == "__main__":
    main()
