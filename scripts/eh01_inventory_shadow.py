# -*- coding: utf-8 -*-
"""CAM01 EH01 — EVIDENCE HIERARCHY INVENTORY + SHADOW ROUTER FEASIBILITY.

不训练、不加模型、不改任何历史 gate。把已有证据源 join 到 36 semantic pairs，
建 EvidenceRecordV1、LOCAL 分层/agreement、GLOBAL fallback 检查、shadow router。
role-blind：router 冻结前不读 role；最后才 target diagnostic（不改结论）。

修正登记：
- EH01_CORRECTION_R2_STRUCT_FLAG_01：R2 只按 forward P90>12 打 DISAGREEMENT；
  EH01 按 symmetric P90（<=12 CONSISTENT / >12 DISAGREEMENT / 无=UNKNOWN）。
- EH01_CORRECTION_R2_ABLATION_02：R2 DINO_ONLY_SUBTOKEN 在 FB3 accepted 子集上评估
  → 只能叫 CONDITIONAL_DINO_ONLY_ABLATION。
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
MANIFEST = OUT / "TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json"
ROI_JSON = OUT / "TREECUT_POSTA3_HUMAN_ROI_V1.json"
sys.stdout.reconfigure(encoding="utf-8")

STRUCT_SYM_P90_MAX = 12.0  # 沿用 R2 diagnostic boundary，非新调参
AGREE_MED_MAX = 3.0        # 沿用模型分歧 <=3px 语义


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def island_bbox(roi, mid, t):
    for a in roi:
        if a["media_id"] == mid and a["frame_timestamp"] == t and a["object_name"] == "ISLAND_BODY":
            return a["bbox_pixel"]
    return None


def to_affine3x3(M2x3):
    return np.vstack([np.array(M2x3, dtype=np.float64), [0, 0, 1.0]])


def predict_grid(T, ib, grid=(9, 6)):
    """ISLAND_BODY t0 内均匀 grid 点 → transform 后 t1 预测（raw px）。"""
    x0, y0, x1, y1 = [float(v) for v in ib]
    xs = np.linspace(x0 + (x1 - x0) * 0.08, x0 + (x1 - x0) * 0.92, grid[0])
    ys = np.linspace(y0 + (y1 - y0) * 0.08, y0 + (y1 - y0) * 0.92, grid[1])
    gx, gy = np.meshgrid(xs, ys)
    pts = np.column_stack([gx.ravel(), gy.ravel()])
    ones = np.ones((len(pts), 1))
    h = np.hstack([pts, ones])
    out = (np.asarray(T, dtype=np.float64) @ h.T).T
    return out[:, :2] / out[:, 2:3]


def transform_disagreement(Ta, Tb, ib):
    pa = predict_grid(Ta, ib)
    pb = predict_grid(Tb, ib)
    d = np.linalg.norm(pa - pb, axis=1)
    return float(np.median(d)), float(np.percentile(d, 90))


def r2_transform(corr_acc):
    """从 FB3 accepted corr (p0 -> p1_fb) 全量 fit affine。返回 3x3 或 None。"""
    P0 = np.float32([c["p0"] for c in corr_acc])
    P1 = np.float32([c["p1_fb"] for c in corr_acc])
    if len(P0) < 4:
        return None
    M, _ = cv2.estimateAffinePartial2D(P0, P1, method=cv2.RANSAC,
                                       ransacReprojThreshold=4.0)
    if M is None:
        return None
    return np.vstack([M, [0, 0, 1.0]]).tolist()


def main():
    man = load("TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json")
    roi = load("TREECUT_POSTA3_HUMAN_ROI_V1.json")["annotations"]
    r2 = load("TREECUT_CAM01_DENSE01R2_MATCH_MATRIX.json")["pairs"]
    v24 = load("TREECUT_CAM01_V24R1_TRUE_CLIQUE_CONSENSUS.json")["pairs"]
    v23 = load("TREECUT_CAM01_V23_METHOD_MATRIX.json")["pairs"]
    cam = load("TREECUT_POSTA3_CAMERA_PAIR_MATRIX_V2.json")["cases"]
    r2s = load("TREECUT_CAM01_DENSE01R2_STRUCTURAL_VALIDATION.json")["rows"]

    # ===== 修正登记 =====
    corr2 = {"EH01_CORRECTION_R2_STRUCT_FLAG_01": {
                "r2_behavior": "DENSE_STRUCTURAL_DISAGREEMENT 只按 forward P90>12px",
                "eh01_rule": "symmetric P90 <=12 = STRUCTURAL_CONSISTENT; >12 = STRUCTURAL_DISAGREEMENT; 无 symmetric = STRUCTURAL_UNKNOWN",
                "boundary_not_new": "12px 沿用 R2 diagnostic boundary"},
            "EH01_CORRECTION_R2_ABLATION_02": {
                "r2_issue": "DINO_ONLY_SUBTOKEN 在 FB3 accepted correspondence subset 上评估，非全量独立 baseline",
                "eh01_label": "CONDITIONAL_DINO_ONLY_ABLATION",
                "facts_preserved": {"SEMANTIC_MATCH_SUFFICIENT": "34/36",
                                    "RAW_REFINEMENT_EFFECTIVE_CONDITIONAL": "YES"}}}
    (OUT / "TREECUT_CAM01_EH01_R2_CORRECTIONS.json").write_text(
        json.dumps(corr2, ensure_ascii=False, indent=1), encoding="utf-8")

    # ===== 36 semantic pairs 主表 =====
    sem = []
    for c in man["cases"]:
        ts = [f["t_s"] for f in c["frames"]]
        for i in range(len(ts) - 1):
            sem.append((c["media_id"], f"{ts[i]}->{ts[i+1]}"))
    # 只保留 island-present（R2 全集 36）
    r2key = {(p["case"], p["pair"]) for p in r2}
    sem = [k for k in sem if k in r2key]
    print("semantic pairs:", len(sem))

    # ===== index sources =====
    # A. DENSE01R2
    r2_by = {(p["case"], p["pair"]): p for p in r2}
    # B. V24R1 consensus (MULTI_METHOD_CONSENSUS) + transform
    v24c = {}
    for x in v24:
        if x.get("consensus") == "MULTI_METHOD_CONSENSUS":
            rep = x.get("representative")
            md = x.get("methods", {}).get(rep, {})
            m2x3 = md.get("final_M_2x3")
            rec = {"state": "TRUE_MULTI_METHOD_CONSENSUS",
                   "rep": rep,
                   "pooled_med": md.get("pooled_holdout_median"),
                   "pooled_p90": md.get("pooled_holdout_p90")}
            if m2x3:
                rec["T3"] = to_affine3x3(m2x3).tolist()
            v24c[(x["case"], x["pair"])] = rec
    # C. V23 GFTT validated
    gftt = {}
    for x in v23:
        g = x["methods"].get("GFTT_LK_LOCAL")
        if g and g.get("pair_state") == "LOCAL_ANCHOR_VALIDATED":
            gftt[(x["case"], x["pair"])] = {"state": "LOCAL_ANCHOR_VALIDATED",
                                            "med": g.get("folds", {}).get("fit0val1", {}).get("median_px"),
                                            "p90": g.get("folds", {}).get("fit0val1", {}).get("p90_px")}
    # D. camera (SPARSE_DIRECT reliable among sem)
    cam_by = {}
    for c in cam:
        key = (c["case"], c["pair"])
        if key in r2key:
            sd = c.get("SPARSE_DIRECT", {})
            cam_by[key] = sd.get("state")  # CAMERA_RELIABLE / CAMERA_UNRELIABLE
    # E. structural (R2 diagnostic per validated pair) -> symmetric rule
    struct_by = {}
    for r in r2s:
        key = (r["case"], r["pair"])
        s = r.get("structural") or {}
        sym = s.get("symmetric")
        if sym and sym.get("p90") is not None:
            st = ("STRUCTURAL_CONSISTENT" if sym["p90"] <= STRUCT_SYM_P90_MAX
                  else "STRUCTURAL_DISAGREEMENT")
        elif s.get("forward"):
            st = "STRUCTURAL_UNKNOWN"  # symmetric 缺失（如 rev 异常）按规格 UNKNOWN
        else:
            st = "STRUCTURAL_UNKNOWN"
        struct_by[key] = {"state": st, "symmetric_p90": (sym or {}).get("p90"),
                          "forward_p90": (s.get("forward") or {}).get("p90"),
                          "r2_flag": s.get("flag")}

    # ===== EvidenceRecordV1 per pair per source =====
    inventory = []
    for (mid, pair) in sem:
        t0 = float(pair.split("->")[0])
        ib = island_bbox(roi, mid, t0)
        recs = []
        # A
        rp = r2_by.get((mid, pair))
        if rp:
            acc = [c for c in rp.get("corr", []) if c.get("reject") == "ACCEPT"]
            validated = rp.get("state") in ("DENSE_MULTI_MODEL_CONSENSUS",
                                            "DENSE_SINGLE_MODEL")
            recs.append({
                "source_name": "DENSE01R2_FB3", "case": mid, "pair": pair,
                "availability": "AVAILABLE" if validated else "NOT_VALIDATED",
                "state": rp.get("state"),
                "support_size": len(acc),
                "coverage": rp.get("coverage"),
                # transform 只在通过自身正式 gate（validated）时有效；否则 None（L2 只用已过 gate 证据）
                "transform": r2_transform(acc) if validated else None,
                "provenance": {"source_commit": "8f84735",
                               "artifact": "TREECUT_CAM01_DENSE01R2_MATCH_MATRIX.json"}})
        # B
        if (mid, pair) in v24c:
            vr = v24c[(mid, pair)]
            recs.append({"source_name": "V24R1_CONSENSUS", "case": mid, "pair": pair,
                         "availability": "AVAILABLE", "state": vr["state"],
                         "rep_method": vr["rep"],
                         "residual": {"median": vr["pooled_med"], "p90": vr["pooled_p90"]},
                         "transform": vr.get("T3"),
                         "provenance": {"source_commit": "08a6d28-era",
                                        "artifact": "TREECUT_CAM01_V24R1_TRUE_CLIQUE_CONSENSUS.json"}})
        # C
        if (mid, pair) in gftt:
            gr = gftt[(mid, pair)]
            recs.append({"source_name": "GFTT_V23_WHOLE_ISLAND", "case": mid, "pair": pair,
                         "availability": "AVAILABLE", "state": gr["state"],
                         "residual": {"median": gr["med"], "p90": gr["p90"]},
                         "transform": None,  # V23 无 final_M
                         "provenance": {"source_commit": "08a6d28-era",
                                        "artifact": "TREECUT_CAM01_V23_METHOD_MATRIX.json"}})
        # D
        if (mid, pair) in cam_by:
            recs.append({"source_name": "GLOBAL_CAMERA_SPARSE", "case": mid, "pair": pair,
                         "availability": ("RELIABLE" if cam_by[(mid, pair)] == "CAMERA_RELIABLE"
                                          else "UNRELIABLE"),
                         "state": cam_by[(mid, pair)],
                         "transform": None,
                         "provenance": {"source_commit": "08a6d28-era",
                                        "artifact": "TREECUT_POSTA3_CAMERA_PAIR_MATRIX_V2.json"}})
        # E
        if (mid, pair) in struct_by:
            sr = struct_by[(mid, pair)]
            recs.append({"source_name": "STRUCTURAL_DIAGNOSTIC", "case": mid, "pair": pair,
                         "availability": "AVAILABLE", "state": sr["state"],
                         "symmetric_p90": sr["symmetric_p90"],
                         "forward_p90": sr["forward_p90"],
                         "r2_flag": sr["r2_flag"],
                         "transform": None,
                         "provenance": {"source_commit": "8f84735",
                                        "artifact": "TREECUT_CAM01_DENSE01R2_STRUCTURAL_VALIDATION.json"}})
        # F. DINO semantic availability
        if rp:
            recs.append({"source_name": "DINO_SEMANTIC_MNN", "case": mid, "pair": pair,
                         "availability": ("MATCH_SUFFICIENT" if rp.get("valid_mnn", 0) >= 12
                                          else "MATCH_INSUFFICIENT"),
                         "valid_mnn": rp.get("valid_mnn"),
                         "transform": None,
                         "provenance": {"source_commit": "8f84735",
                                        "artifact": "TREECUT_CAM01_DENSE01R2_MATCH_MATRIX.json"}})
        inventory.append({"case": mid, "pair": pair, "island_t0": ib, "records": recs})
    (OUT / "TREECUT_CAM01_EH01_SOURCE_INVENTORY.json").write_text(
        json.dumps({"pairs": inventory}, ensure_ascii=False, indent=1), encoding="utf-8")

    # ===== structural corrected counts (8 validated) =====
    val8 = [(p["case"], p["pair"]) for p in r2
            if p.get("state") in ("DENSE_MULTI_MODEL_CONSENSUS", "DENSE_SINGLE_MODEL")]
    sc = {"consistent": [], "disagreement": [], "unknown": []}
    for key in val8:
        st = struct_by.get(key, {}).get("state", "STRUCTURAL_UNKNOWN")
        sc["consistent" if st == "STRUCTURAL_CONSISTENT"
           else "disagreement" if st == "STRUCTURAL_DISAGREEMENT" else "unknown"].append(key)
    struct_corr = {"among_r2_validated_8": {k: len(v) for k, v in sc.items()},
                   "consistent_detail": sc["consistent"],
                   "disagreement_detail": sc["disagreement"],
                   "unknown_detail": sc["unknown"]}

    # ===== LOCAL agreement (pairs with >=2 local transforms) =====
    agree_rows = []
    for inv in inventory:
        key = (inv["case"], inv["pair"])
        ib = inv["island_t0"]
        locals_ = [r for r in inv["records"]
                   if r["source_name"] in ("DENSE01R2_FB3", "V24R1_CONSENSUS") and r["transform"]]
        if len(locals_) >= 2 and ib:
            row = {"case": key[0], "pair": key[1], "sources": []}
            disc = None
            for i in range(len(locals_)):
                for j in range(i + 1, len(locals_)):
                    med, p90 = transform_disagreement(locals_[i]["transform"],
                                                      locals_[j]["transform"], ib)
                    row["sources"].append({"a": locals_[i]["source_name"],
                                           "b": locals_[j]["source_name"],
                                           "median_px": round(med, 3),
                                           "p90_px": round(p90, 3)})
                    if disc is None:
                        disc = (med, p90)
            if disc:
                row["verdict"] = "LOCAL_AGREE" if disc[0] <= AGREE_MED_MAX else "LOCAL_CONFLICT"
                row["disagreement"] = {"median": round(disc[0], 3), "p90": round(disc[1], 3)}
            agree_rows.append(row)
    (OUT / "TREECUT_CAM01_EH01_LOCAL_AGREEMENT.json").write_text(
        json.dumps({"rows": agree_rows}, ensure_ascii=False, indent=1), encoding="utf-8")

    # ===== GLOBAL materialization =====
    global_rows = [{"case": k[0], "pair": k[1], "state": v} for k, v in sorted(cam_by.items())]
    n_rel = sum(1 for v in cam_by.values() if v == "CAMERA_RELIABLE")
    global_ev = {"materialized": True,
                 "artifact": "TREECUT_POSTA3_CAMERA_PAIR_MATRIX_V2.json (SPARSE_DIRECT)",
                 "per_pair_states_among_36": n_rel,
                 "rows": global_rows}
    (OUT / "TREECUT_CAM01_EH01_GLOBAL_EVIDENCE.json").write_text(
        json.dumps(global_ev, ensure_ascii=False, indent=1), encoding="utf-8")

    # ===== shadow router =====
    agree_verdict = {r["case"]: r["pair"] for r in []}
    router = []
    for inv in inventory:
        key = (inv["case"], inv["pair"])
        recs = {r["source_name"]: r for r in inv["records"]}
        # local sources with availability
        r2r = recs.get("DENSE01R2_FB3")
        v24r = recs.get("V24R1_CONSENSUS")
        gfttr = recs.get("GFTT_V23_WHOLE_ISLAND")
        camr = recs.get("GLOBAL_CAMERA_SPARSE")
        strr = recs.get("STRUCTURAL_DIAGNOSTIC")
        row = {"case": key[0], "pair": key[1]}
        local_avail = []
        if r2r and r2r["availability"] == "AVAILABLE":
            local_avail.append(("DENSE01R2", r2r["state"]))
        if v24r:
            local_avail.append(("V24R1", v24r["state"]))
        if gfttr:
            local_avail.append(("GFTT", gfttr["state"]))
        # conflict from agreement rows
        agr = next((a for a in agree_rows if a["case"] == key[0] and a["pair"] == key[1]), None)
        conflict = bool(agr and agr["verdict"] == "LOCAL_CONFLICT")
        structural_state = (strr or {}).get("state", "STRUCTURAL_UNKNOWN")
        # routing (fail-closed)
        d2 = r2r["state"] if r2r else None
        is_multi = d2 == "DENSE_MULTI_MODEL_CONSENSUS"
        is_single = d2 == "DENSE_SINGLE_MODEL"
        v24_ok = bool(v24r)
        gftt_ok = bool(gfttr)
        if conflict:
            route = "ROUTE_UNSURE_CONFLICT"
            detail = "local sources disagree"
        elif is_multi and structural_state != "STRUCTURAL_DISAGREEMENT":
            route = "ROUTE_LOCAL_STRONG"
            detail = "DENSE_R2_MULTI + structural ok"
        elif is_single and structural_state != "STRUCTURAL_DISAGREEMENT":
            route = "ROUTE_LOCAL_PARTIAL"
            detail = "DENSE_R2_SINGLE (LOCAL_SINGLE_SOURCE)"
        elif is_multi and structural_state == "STRUCTURAL_DISAGREEMENT":
            route = "ROUTE_LOCAL_PARTIAL"
            detail = "DENSE_R2_MULTI downgraded by structural veto"
        elif is_single and structural_state == "STRUCTURAL_DISAGREEMENT":
            route = "ROUTE_UNSURE_NO_EVIDENCE"
            detail = "DENSE_R2_SINGLE vetoed by structural disagreement"
        elif v24_ok and structural_state != "STRUCTURAL_DISAGREEMENT":
            route = "ROUTE_LOCAL_STRONG"
            detail = "V24R1 multi-method consensus + structural ok"
        elif v24_ok and structural_state == "STRUCTURAL_DISAGREEMENT":
            route = "ROUTE_LOCAL_PARTIAL"
            detail = "V24R1 downgraded by structural veto"
        elif gftt_ok and structural_state != "STRUCTURAL_DISAGREEMENT":
            route = "ROUTE_LOCAL_PARTIAL"
            detail = "GFTT single-source"
        elif gftt_ok and structural_state == "STRUCTURAL_DISAGREEMENT":
            route = "ROUTE_UNSURE_NO_EVIDENCE"
            detail = "GFTT vetoed by structural disagreement"
        else:
            # global fallback only for LOCAL_NONE-ish (no reliable local)
            if camr and camr["availability"] == "RELIABLE":
                route = "ROUTE_GLOBAL_RELIABLE"
                detail = "global camera fallback (no strong local)"
            else:
                route = "ROUTE_UNSURE_NO_EVIDENCE"
                detail = "no reliable local/global"
        row.update({"route": route, "detail": detail,
                    "structural": structural_state,
                    "conflict": conflict,
                    "local_avail": [f"{n}:{s}" for n, s in local_avail],
                    "global": (camr or {}).get("availability", "NOT_AVAILABLE")})
        router.append(row)
    (OUT / "TREECUT_CAM01_EH01_ROUTER_SHADOW.json").write_text(
        json.dumps({"rows": router}, ensure_ascii=False, indent=1), encoding="utf-8")

    # ===== metrics =====
    from collections import Counter
    rc = Counter(r["route"] for r in router)
    usable = rc.get("ROUTE_LOCAL_STRONG", 0) + rc.get("ROUTE_LOCAL_PARTIAL", 0) + \
             rc.get("ROUTE_GLOBAL_RELIABLE", 0)
    # raw source union (any historical source claims available)
    raw_union = 0
    for inv in inventory:
        recs = inv["records"]
        avail = [r for r in recs
                 if r["source_name"] in ("DENSE01R2_FB3", "V24R1_CONSENSUS",
                                         "GFTT_V23_WHOLE_ISLAND")
                 and r["availability"] == "AVAILABLE"]
        camok = any(r["source_name"] == "GLOBAL_CAMERA_SPARSE" and r["availability"] == "RELIABLE"
                    for r in recs)
        if avail or camok:
            raw_union += 1
    usable_cases = len({r["case"] for r in router if r["route"] in
                        ("ROUTE_LOCAL_STRONG", "ROUTE_LOCAL_PARTIAL", "ROUTE_GLOBAL_RELIABLE")})
    # unique contribution by source
    contrib = {}
    for src in ("DENSE01R2", "V24R1", "GFTT", "GLOBAL_CAMERA"):
        # pairs where this source is the ONLY reason for usable (route LOCAL_* or GLOBAL)
        for r in router:
            if src == "GLOBAL_CAMERA" and r["route"] == "ROUTE_GLOBAL_RELIABLE":
                contrib.setdefault(src, set()).add((r["case"], r["pair"]))
    # simpler: per-source available pairs
    src_avail = {}
    for inv in inventory:
        for r in inv["records"]:
            if r["source_name"] == "DENSE01R2_FB3" and r["availability"] == "AVAILABLE":
                src_avail.setdefault("DENSE_R2_MULTI_SINGLE", set()).add((inv["case"], inv["pair"]))
            if r["source_name"] == "V24R1_CONSENSUS":
                src_avail.setdefault("V24R1_CONSENSUS", set()).add((inv["case"], inv["pair"]))
            if r["source_name"] == "GFTT_V23_WHOLE_ISLAND":
                src_avail.setdefault("GFTT_V23", set()).add((inv["case"], inv["pair"]))
            if r["source_name"] == "GLOBAL_CAMERA_SPARSE" and r["availability"] == "RELIABLE":
                src_avail.setdefault("GLOBAL_CAMERA", set()).add((inv["case"], inv["pair"]))
    # unique: pairs only this source provides among usable routes
    usable_keys = {(r["case"], r["pair"]) for r in router if r["route"] in
                   ("ROUTE_LOCAL_STRONG", "ROUTE_LOCAL_PARTIAL", "ROUTE_GLOBAL_RELIABLE")}
    unique = {}
    for src, keys in src_avail.items():
        others = set().union(*(v for k2, v in src_avail.items() if k2 != src))
        unique[src] = len((keys & usable_keys) - others)
    metrics = {"pairs_36": len(router),
               "route_counts": dict(rc),
               "ROUTER_USABLE": usable,
               "RAW_SOURCE_UNION": raw_union,
               "case_coverage_9": usable_cases,
               "source_available_pairs": {k: len(v) for k, v in src_avail.items()},
               "source_unique_contribution": unique,
               "structural_corrected": struct_corr,
               "local_agreement": {"pairs_compared": len(agree_rows),
                                   "agree": sum(1 for a in agree_rows if a.get("verdict") == "LOCAL_AGREE"),
                                   "conflict": sum(1 for a in agree_rows if a.get("verdict") == "LOCAL_CONFLICT")}}
    (OUT / "TREECUT_CAM01_EH01_EVIDENCE_MATRIX.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
