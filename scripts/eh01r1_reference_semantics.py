# -*- coding: utf-8 -*-
"""CAM01 EH01 R1 — REFERENCE MATERIALIZATION + ROUTER SEMANTICS CORRECTION.

修正 EH01 4 缺陷（§2-§4/§8/§16）：
- 精确 R2 representative transform：按 R2 MATCH_MATRIX 每 validated pair 的
  representative model + ransac_thr_raw + FB3 accepted corr 重建（不固定 4px/不强制 affine），
  重建两次验证确定性。
- 语义拆分：EVIDENCE_AVAILABLE / TRANSFORM_MATERIALIZED / REFERENCE_EMITTABLE_STRONG /
  REFERENCE_PARTIAL_WITH_TRANSFORM / EVIDENCE_ONLY_NO_TRANSFORM / GLOBAL_STATE_ONLY_CANDIDATE。
- global：GLOBAL_STATE_MATERIALIZED vs GLOBAL_TRANSFORM_MATERIALIZED 分开。
- 删除 post-hoc >12 classification。
role-blind：router 冻结前不读 role。
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
ROI_JSON = OUT / "TREECUT_POSTA3_HUMAN_ROI_V1.json"
sys.stdout.reconfigure(encoding="utf-8")

STRUCT_SYM_P90_MAX = 12.0
AGREE_MED_MAX = 3.0

# 每 source 的权威 commit/blob（git log --all 定位，见 EH01R1_SOURCE_PROVENANCE）
PROV = {
    "DENSE01R2_FB3": {"commit": "8f84735",
                      "blob": "748e3ccba54603e428461319fb0291416379ac48"},
    "DENSE01R2_STRUCTURAL": {"commit": "8f84735",
                             "blob": "b567302ff1523ec7c1d62fcea4dd2cf36a551777"},
    "V24R1_CONSENSUS": {"commit": "e2bb0ae",
                        "blob": "e433a90e9b1c6ced681690e60d61fe059f116d53"},
    "V23_GFTT": {"commit": "09e3b5b",
                 "blob": "98e74be9973097e7e02cc708482c1be5ea1d4da7"},
    "GLOBAL_CAMERA_V2": {"commit": "f85b363",
                         "blob": "268695d759e327029156f5a5f87faad17ef9adb3"},
    "CALIBRATION10_MANIFEST": {"commit": "136e466",
                               "blob": "714998a4da64252a8a107459cb68b7cb32e2b13c"},
}


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def island_bbox(roi, mid, t):
    for a in roi:
        if a["media_id"] == mid and a["frame_timestamp"] == t and a["object_name"] == "ISLAND_BODY":
            return a["bbox_pixel"]
    return None


def to_hom(M2x3):
    return np.vstack([np.array(M2x3, dtype=np.float64), [0, 0, 1.0]])


def predict_grid(T, ib, grid=(9, 6)):
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


def r2_exact_materialize(pair_rec, thr, model):
    """按 R2 正式 pipeline：representative model + pair ransac_thr_raw + FB3 accepted corr。
    返回 (T3x3, n_corr, model_used, thr_used) 或 None。"""
    acc = [c for c in pair_rec.get("corr", []) if c.get("reject") == "ACCEPT"]
    if len(acc) < 4:
        return None
    P0 = np.float32([c["p0"] for c in acc])
    P1 = np.float32([c["p1_fb"] for c in acc])
    if model == "HOMOGRAPHY":
        M, _ = cv2.findHomography(P0, P1, cv2.RANSAC, thr)
        if M is None:
            return None
        return M, len(acc), model, thr
    else:
        M, _ = cv2.estimateAffinePartial2D(P0, P1, method=cv2.RANSAC,
                                           ransacReprojThreshold=thr)
        if M is None:
            return None
        return np.vstack([M, [0, 0, 1.0]]), len(acc), model, thr


def main():
    man = load("TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json")
    roi = load("TREECUT_POSTA3_HUMAN_ROI_V1.json")["annotations"]
    r2 = load("TREECUT_CAM01_DENSE01R2_MATCH_MATRIX.json")["pairs"]
    v24 = load("TREECUT_CAM01_V24R1_TRUE_CLIQUE_CONSENSUS.json")["pairs"]
    v23 = load("TREECUT_CAM01_V23_METHOD_MATRIX.json")["pairs"]
    cam = load("TREECUT_POSTA3_CAMERA_PAIR_MATRIX_V2.json")["cases"]
    r2s = load("TREECUT_CAM01_DENSE01R2_STRUCTURAL_VALIDATION.json")["rows"]

    # ===== DEFECT AUDIT =====
    defects = {
        "EH01_DEFECT_USABLE_CONFLATES_EVIDENCE_AND_REFERENCE_01": {
            "detail": "ROUTER_USABLE = STRONG+PARTIAL+GLOBAL 把无 transform 的 evidence(如 GFTT null)计入 usable",
            "r1_fix": "拆 EVIDENCE_AVAILABLE / TRANSFORM_MATERIALIZED / REFERENCE_EMITTABLE_STRONG / "
                      "REFERENCE_PARTIAL_WITH_TRANSFORM / EVIDENCE_ONLY_NO_TRANSFORM"},
        "EH01_DEFECT_R2_TRANSFORM_RECONSTRUCTION_02": {
            "detail": "EH01 r2_transform() 固定 PARTIAL_AFFINE + 4px，非 R2 正式 pipeline",
            "r1_fix": "按 R2 representative model + pair ransac_thr_raw + FB3 corr 重建；不得固定 4px/强制 affine"},
        "EH01_DEFECT_GLOBAL_STATE_ONLY_03": {
            "detail": "GLOBAL 只 materialize RELIABLE/UNRELIABLE state，无 transform",
            "r1_fix": "拆 GLOBAL_STATE_MATERIALIZED(YES) / GLOBAL_TRANSFORM_MATERIALIZED(NO)"},
        "EH01_DEFECT_POSTHOC_FEASIBLE_THRESHOLD_04": {
            "detail": "eh01_result.py 新增 if usable>12 -> HIERARCHY_FEASIBLE，违反不设新 performance threshold",
            "r1_fix": "删除该 classification；R1 只输出语义状态 A/B/C/D 不设 coverage gate"}}
    (OUT / "TREECUT_CAM01_EH01R1_DEFECT_AUDIT.json").write_text(
        json.dumps({"EH01_RESULT_PENDING_REFERENCE_SEMANTICS_CORRECTION": True,
                    "defects": defects}, ensure_ascii=False, indent=1), encoding="utf-8")

    # ===== provenance =====
    (OUT / "TREECUT_CAM01_EH01R1_SOURCE_PROVENANCE.json").write_text(
        json.dumps(PROV, ensure_ascii=False, indent=1), encoding="utf-8")

    # ===== source families =====
    fam = {"DENSE01R2_FB3": "SEMANTIC_DENSE_LK",
           "V24R1_CONSENSUS": "FEATURE_LOCAL_ENSEMBLE",
           "V23_GFTT": "FEATURE_LOCAL",
           "GLOBAL_CAMERA": "GLOBAL_CAMERA",
           "STRUCTURAL": "STRUCTURAL_VALIDATION",
           "DINO_MNN": "SEMANTIC_AVAILABILITY",
           "note": "V24R1(FEATURE_LOCAL_ENSEMBLE) 与 V23_GFTT(FEATURE_LOCAL) 同属 feature-local 证据链，非完全独立；"
                   "禁止用 source count 冒充 independent corroboration count"}
    (OUT / "TREECUT_CAM01_EH01R1_SOURCE_FAMILIES.json").write_text(
        json.dumps(fam, ensure_ascii=False, indent=1), encoding="utf-8")

    # ===== 36 semantic pairs 主表 =====
    r2key = {(p["case"], p["pair"]) for p in r2}
    sem = []
    for c in man["cases"]:
        ts = [f["t_s"] for f in c["frames"]]
        for i in range(len(ts) - 1):
            key = (c["media_id"], f"{ts[i]}->{ts[i+1]}")
            if key in r2key:
                sem.append(key)

    # ===== §4 精确 R2 materialization =====
    r2_by = {(p["case"], p["pair"]): p for p in r2}
    r2_mats = {}
    for (mid, pair) in sem:
        rp = r2_by.get((mid, pair))
        if not rp:
            continue
        validated = rp.get("state") in ("DENSE_MULTI_MODEL_CONSENSUS", "DENSE_SINGLE_MODEL")
        rec = {"case": mid, "pair": pair, "state": rp.get("state"),
               "validated": validated}
        if validated:
            rep = rp.get("representative", "PARTIAL_AFFINE")
            thr = rp.get("ransac_thr_raw")
            # 重建两次验证确定性
            T1 = r2_exact_materialize(rp, thr, rep)
            T2 = r2_exact_materialize(rp, thr, rep)
            ib = island_bbox(roi, mid, float(pair.split("->")[0]))
            det_ok = False
            if T1 and T2 and ib:
                med, _ = transform_disagreement(T1[0], T2[0], ib)
                det_ok = med < 1e-6
            rec.update({"representative": rep, "thr_raw": thr,
                        "model_used": rep, "thr_used": thr,
                        "n_fb3_corr": T1[1] if T1 else None,
                        "deterministic_rebuild": det_ok,
                        "matrix": T1[0].tolist() if T1 else None,
                        "materialized": bool(T1 and det_ok),
                        "materialization_status": ("TRANSFORM_MATERIALIZED" if (T1 and det_ok)
                                                   else "TRANSFORM_MATERIALIZATION_FAILED"),
                        "provenance": PROV["DENSE01R2_FB3"]})
            r2_mats[(mid, pair)] = rec
        else:
            rec.update({"materialized": False, "matrix": None,
                        "materialization_status": "NOT_VALIDATED"})
            r2_mats[(mid, pair)] = rec
    (OUT / "TREECUT_CAM01_EH01R1_R2_TRANSFORMS.json").write_text(
        json.dumps({"rows": [v for k, v in sorted(r2_mats.items())]},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    n_mat = sum(1 for v in r2_mats.values() if v.get("materialized"))
    print("R2 exact materialized:", n_mat, "/ 8 validated")

    # ===== V24R1 transform (不 refit) =====
    v24_by = {}
    for x in v24:
        if x.get("consensus") == "MULTI_METHOD_CONSENSUS":
            rep = x.get("representative")
            md = x.get("methods", {}).get(rep, {})
            m2x3 = md.get("final_M_2x3")
            v24_by[(x["case"], x["pair"])] = {
                "state": "TRUE_MULTI_METHOD_CONSENSUS", "rep": rep,
                "T": to_hom(m2x3) if m2x3 else None,
                "med": md.get("pooled_holdout_median"),
                "p90": md.get("pooled_holdout_p90")}

    # ===== GFTT V23 (无 transform) =====
    gftt_by = {}
    for x in v23:
        g = x["methods"].get("GFTT_LK_LOCAL")
        if g and g.get("pair_state") == "LOCAL_ANCHOR_VALIDATED":
            gftt_by[(x["case"], x["pair"])] = {"state": "LOCAL_ANCHOR_VALIDATED",
                                               "med": (g.get("folds", {}).get("fit0val1") or {}).get("median_px")}

    # ===== global state only =====
    cam_by = {}
    for c in cam:
        key = (c["case"], c["pair"])
        if key in r2key:
            cam_by[key] = (c.get("SPARSE_DIRECT") or {}).get("state")

    # ===== structural =====
    struct_by = {}
    for r in r2s:
        key = (r["case"], r["pair"])
        s = r.get("structural") or {}
        sym = s.get("symmetric")
        if sym and sym.get("p90") is not None:
            st = ("STRUCTURAL_CONSISTENT" if sym["p90"] <= STRUCT_SYM_P90_MAX
                  else "STRUCTURAL_DISAGREEMENT")
        else:
            st = "STRUCTURAL_UNKNOWN"
        struct_by[key] = {"state": st, "symmetric_p90": (sym or {}).get("p90"),
                          "forward_p90": (s.get("forward") or {}).get("p90")}

    # ===== §6 local agreement (只比有 transform 的源) =====
    agree_rows = []
    for (mid, pair) in sem:
        ib = island_bbox(roi, mid, float(pair.split("->")[0]))
        if not ib:
            continue
        locs = []
        rm = r2_mats.get((mid, pair))
        if rm and rm.get("materialized"):
            locs.append(("DENSE_R2_EXACT", rm["matrix"]))
        vr = v24_by.get((mid, pair))
        if vr and vr.get("T") is not None:
            locs.append(("V24R1_EXACT", vr["T"]))
        if len(locs) >= 2:
            med, p90 = transform_disagreement(locs[0][1], locs[1][1], ib)
            agree_rows.append({"case": mid, "pair": pair,
                               "sources": [l[0] for l in locs],
                               "median_px": round(med, 3), "p90_px": round(p90, 3),
                               "verdict": "LOCAL_AGREE" if med <= AGREE_MED_MAX
                               else "LOCAL_CONFLICT"})
    (OUT / "TREECUT_CAM01_EH01R1_LOCAL_AGREEMENT.json").write_text(
        json.dumps({"rows": agree_rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    ag = {r["verdict"]: 0 for r in agree_rows}
    for r in agree_rows:
        ag[r["verdict"]] += 1
    print("R1 local agreement:", ag)

    # ===== §8-9 global capability =====
    glob = {"GLOBAL_STATE_MATERIALIZED": True,
            "GLOBAL_TRANSFORM_MATERIALIZED": False,
            "state_artifact": "TREECUT_POSTA3_CAMERA_PAIR_MATRIX_V2.json (SPARSE_DIRECT)",
            "transform_note": "V2 只含 RELIABLE/UNRELIABLE state，无最终 transform matrix",
            "GLOBAL_TRANSFORM_MATERIALIZATION_REQUIRED": True,
            "per_pair_state": {f"{k[0]} {k[1]}": v for k, v in sorted(cam_by.items())}}
    (OUT / "TREECUT_CAM01_EH01R1_GLOBAL_CAPABILITY.json").write_text(
        json.dumps(glob, ensure_ascii=False, indent=1), encoding="utf-8")

    # ===== §11-13 route semantics + metrics =====
    # 预计算 agreement verdict map
    agv = {(r["case"], r["pair"]): r["verdict"] for r in agree_rows}
    router = []
    for (mid, pair) in sem:
        rp = r2_by.get((mid, pair))
        row = {"case": mid, "pair": pair}
        st_r2 = rp.get("state") if rp else None
        is_multi = st_r2 == "DENSE_MULTI_MODEL_CONSENSUS"
        is_single = st_r2 == "DENSE_SINGLE_MODEL"
        v24_ok = (mid, pair) in v24_by
        gftt_ok = (mid, pair) in gftt_by
        rm = r2_mats.get((mid, pair), {})
        r2_mat = bool(rm.get("materialized"))
        # conflict 仅当有 materialized transform 的两源都比过
        verdict = agv.get((mid, pair))
        conflict = verdict == "LOCAL_CONFLICT"
        strr = struct_by.get((mid, pair))
        sstate = (strr or {}).get("state", "STRUCTURAL_UNKNOWN")
        camok = cam_by.get((mid, pair)) == "CAMERA_RELIABLE"
        # 分类
        if conflict:
            route = "LOCAL_CONFLICT"
        elif is_multi and r2_mat and sstate != "STRUCTURAL_DISAGREEMENT":
            route = "REFERENCE_EMITTABLE_STRONG"
        elif is_multi and r2_mat and sstate == "STRUCTURAL_DISAGREEMENT":
            route = "REFERENCE_PARTIAL_WITH_TRANSFORM"   # veto 降级但 matrix 在
        elif is_single and r2_mat and sstate != "STRUCTURAL_DISAGREEMENT":
            route = "REFERENCE_EMITTABLE_STRONG"          # SINGLE 有 matrix + 无 veto
        elif is_single and r2_mat and sstate == "STRUCTURAL_DISAGREEMENT":
            route = "REFERENCE_PARTIAL_WITH_TRANSFORM"
        elif v24_ok and v24_by[(mid, pair)].get("T") is not None and sstate != "STRUCTURAL_DISAGREEMENT":
            route = "REFERENCE_EMITTABLE_STRONG"
        elif v24_ok and v24_by[(mid, pair)].get("T") is not None and sstate == "STRUCTURAL_DISAGREEMENT":
            route = "REFERENCE_PARTIAL_WITH_TRANSFORM"
        elif gftt_ok and camok:
            # §9B：LOCAL_PARTIAL(evidence-only) + global reliable state → GLOBAL_FALLBACK_CANDIDATE_STATE_ONLY
            # （global 有 state 无 transform → 不能升级 emittable）
            route = "GLOBAL_FALLBACK_CANDIDATE_STATE_ONLY"
        elif gftt_ok:
            route = "EVIDENCE_ONLY_NO_TRANSFORM"          # GFTT 无 matrix 且 global 也不可靠
        elif camok:
            route = "GLOBAL_STATE_ONLY_CANDIDATE"         # LOCAL_NONE + global state
        else:
            route = "UNSURE_NO_EVIDENCE"
        row.update({"route": route, "r2_state": st_r2,
                    "r2_transform": r2_mat, "v24_transform": bool(v24_ok and v24_by.get((mid, pair), {}).get("T") is not None),
                    "gftt_evidence": gftt_ok, "global_state": camok,
                    "structural": sstate, "conflict": conflict})
        router.append(row)
    (OUT / "TREECUT_CAM01_EH01R1_ROUTER_SHADOW.json").write_text(
        json.dumps({"rows": router}, ensure_ascii=False, indent=1), encoding="utf-8")

    from collections import Counter
    rc = Counter(r["route"] for r in router)
    emittable_strong = rc.get("REFERENCE_EMITTABLE_STRONG", 0)
    partial_w_t = rc.get("REFERENCE_PARTIAL_WITH_TRANSFORM", 0)
    evidence_only = rc.get("EVIDENCE_ONLY_NO_TRANSFORM", 0)
    global_state_only = rc.get("GLOBAL_STATE_ONLY_CANDIDATE", 0) + \
                         rc.get("GLOBAL_FALLBACK_CANDIDATE_STATE_ONLY", 0)
    unsure = rc.get("UNSURE_NO_EVIDENCE", 0) + rc.get("LOCAL_CONFLICT", 0)
    transform_any = emittable_strong + partial_w_t
    # evidence routable = 任何有 evidence 且未完全否决（不含纯 UNSURE）
    evidence_routable = emittable_strong + partial_w_t + evidence_only + global_state_only
    metrics = {"pairs_36": len(router),
               "route_counts": dict(rc),
               "EVIDENCE_ROUTABLE": evidence_routable,
               "TRANSFORM_MATERIALIZED_ANY": transform_any,
               "REFERENCE_EMITTABLE_STRONG": emittable_strong,
               "REFERENCE_PARTIAL_WITH_TRANSFORM": partial_w_t,
               "EVIDENCE_ONLY_NO_TRANSFORM": evidence_only,
               "GLOBAL_STATE_ONLY_CANDIDATE": global_state_only,
               "GLOBAL_FALLBACK_CANDIDATE_STATE_ONLY_detail": rc.get("GLOBAL_FALLBACK_CANDIDATE_STATE_ONLY", 0),
               "UNSURE": unsure,
               "LOCAL_CONFLICT": rc.get("LOCAL_CONFLICT", 0),
               "old_EH01_reference": {"LOCAL_STRONG": 9, "LOCAL_PARTIAL": 10,
                                      "ROUTER_USABLE": 19},
               "old_vs_new_note": "ROUTER_USABLE(19) 弃用为唯一数字；见上拆分"}
    (OUT / "TREECUT_CAM01_EH01R1_REFERENCE_METRICS.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
