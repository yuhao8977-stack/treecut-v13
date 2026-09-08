# -*- coding: utf-8 -*-
"""EH02 §6-§27: source matrix + materialized agreement graph + S1/S2/S3 router freeze
+ metrics + NEG/POS readiness + global upper bound. role-blind until router frozen.
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
ROI_JSON = OUT / "TREECUT_POSTA3_HUMAN_ROI_V1.json"
MANIFEST = OUT / "TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json"
sys.stdout.reconfigure(encoding="utf-8")

AGREE_MED_MAX = 3.0
STRUCT_SYM_P90_MAX = 12.0

FAM = {"DENSE_R2": "SEMANTIC_DENSE_LK",
       "V24R1": "FEATURE_LOCAL_ENSEMBLE",
       "GFTT_M1": "FEATURE_LOCAL",
       "GLOBAL": "GLOBAL_CAMERA",
       "STRUCTURAL": "STRUCTURAL_VALIDATION",
       "DINO_MNN": "SEMANTIC_AVAILABILITY"}
# GFTT 与 V24 同 feature-local 链，非完全独立


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def island_bbox(roi, mid, t):
    for a in roi:
        if a["media_id"] == mid and a["frame_timestamp"] == t and a["object_name"] == "ISLAND_BODY":
            return a["bbox_pixel"]
    return None


def predict_grid(T3, ib, grid=(9, 6)):
    x0, y0, x1, y1 = [float(v) for v in ib]
    xs = np.linspace(x0 + (x1 - x0) * 0.08, x0 + (x1 - x0) * 0.92, grid[0])
    ys = np.linspace(y0 + (y1 - y0) * 0.08, y0 + (y1 - y0) * 0.92, grid[1])
    gx, gy = np.meshgrid(xs, ys)
    pts = np.column_stack([gx.ravel(), gy.ravel()])
    p1p = cv2.transform(pts.reshape(-1, 1, 2).astype(np.float32),
                        np.float32(T3[:2])).reshape(-1, 2)
    return p1p


def disagreement_med(Ta3, Tb3, ib):
    pa = predict_grid(Ta3, ib)
    pb = predict_grid(Tb3, ib)
    return float(np.median(np.linalg.norm(pa - pb, axis=1)))


def t3(M2x3):
    return np.vstack([np.asarray(M2x3, dtype=np.float64), [0, 0, 1.0]])


def main():
    roi = load("TREECUT_POSTA3_HUMAN_ROI_V1.json")["annotations"]
    man = load("TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json")
    r2 = load("TREECUT_CAM01_DENSE01R2_MATCH_MATRIX.json")["pairs"]
    v24 = load("TREECUT_CAM01_V24R1_TRUE_CLIQUE_CONSENSUS.json")["pairs"]
    gftt_m1 = load("TREECUT_CAM01_EH01M1_GFTT_TRANSFORMS.json")["rows"]
    cam = load("TREECUT_POSTA3_CAMERA_PAIR_MATRIX_V2.json")["cases"]
    struct_corr = load("TREECUT_CAM01_EH02_STRUCTURAL_CORRECTED.json")["rows"]
    # semantic pairs
    r2key = {(p["case"], p["pair"]) for p in r2}
    sem = []
    for c in man["cases"]:
        ts = [f["t_s"] for f in c["frames"]]
        for i in range(len(ts) - 1):
            key = (c["media_id"], f"{ts[i]}->{ts[i+1]}")
            if key in r2key:
                sem.append(key)

    # ===== A. DENSE_R2 exact transforms (validated, rep model + thr) =====
    dense = {}
    for p in r2:
        if p.get("state") in ("DENSE_MULTI_MODEL_CONSENSUS", "DENSE_SINGLE_MODEL"):
            acc = [c for c in p.get("corr", []) if c.get("reject") == "ACCEPT"]
            if len(acc) >= 4:
                P0 = np.float32([c["p0"] for c in acc])
                P1 = np.float32([c["p1_fb"] for c in acc])
                rep = p.get("representative", "PARTIAL_AFFINE")
                thr = p.get("ransac_thr_raw", 4.0)
                if rep == "HOMOGRAPHY":
                    M, _ = cv2.findHomography(P0, P1, cv2.RANSAC, thr)
                    if M is not None:
                        dense[(p["case"], p["pair"])] = {"T3": M,
                                                         "conf": "HIGH" if p["state"] == "DENSE_MULTI_MODEL_CONSENSUS" else "MEDIUM",
                                                         "hist_state": p["state"]}
                else:
                    M, _ = cv2.estimateAffinePartial2D(P0, P1, method=cv2.RANSAC,
                                                       ransacReprojThreshold=thr)
                    if M is not None:
                        dense[(p["case"], p["pair"])] = {"T3": t3(M),
                                                         "conf": "HIGH" if p["state"] == "DENSE_MULTI_MODEL_CONSENSUS" else "MEDIUM",
                                                         "hist_state": p["state"]}
    # ===== B. V24R1 =====
    v24t = {}
    for x in v24:
        if x.get("consensus") == "MULTI_METHOD_CONSENSUS":
            rep = x.get("representative")
            md = x.get("methods", {}).get(rep, {})
            m2x3 = md.get("final_M_2x3")
            if m2x3:
                v24t[(x["case"], x["pair"])] = {"T3": t3(m2x3),
                                                "conf": "HIGH",
                                                "rep_method": rep}
    # ===== C. GFTT_M1 =====
    gftt = {}
    for r in gftt_m1:
        if r.get("status") == "GFTT_MATERIALIZED_REFERENCE_CANDIDATE":
            gftt[(r["case"], r["pair"])] = {"T3": t3(r["M2x3"]),
                                            "conf": "MEDIUM",
                                            "n": r.get("n_accepted")}
    # ===== D. global state =====
    cam_by = {}
    for c in cam:
        key = (c["case"], c["pair"])
        if key in r2key:
            cam_by[key] = (c.get("SPARSE_DIRECT") or {}).get("state") == "CAMERA_RELIABLE"
    # ===== E. structural corrected（GFTT inlier-hull）+ R2 DENSE structural 合并 =====
    # per-pair：任一 materialized source 的 DISAGREEMENT 即 veto（最严格）；CONSISTENT 优先于 UNKNOWN
    struct_by = {}
    for r in struct_corr:
        struct_by[(r["case"], r["pair"])] = (r.get("structural") or {}).get("state")
    r2s = load("TREECUT_CAM01_DENSE01R2_STRUCTURAL_VALIDATION.json")["rows"]
    for r in r2s:
        s = r.get("structural") or {}
        sym = s.get("symmetric")
        if sym and sym.get("p90") is not None:
            st = ("STRUCTURAL_CONSISTENT" if sym["p90"] <= STRUCT_SYM_P90_MAX
                  else "STRUCTURAL_DISAGREEMENT")
            key = (r["case"], r["pair"])
            cur = struct_by.get(key)
            # 合并：DISAGREEMENT 最高优先；否则 CONSISTENT 优先于 UNKNOWN
            if cur in (None, "STRUCTURAL_UNKNOWN"):
                struct_by[key] = st
            elif st == "STRUCTURAL_DISAGREEMENT" and cur != "STRUCTURAL_DISAGREEMENT":
                struct_by[key] = "STRUCTURAL_DISAGREEMENT"

    # ===== §8 agreement graph =====
    edges = []
    for (mid, pair) in sem:
        ib = island_bbox(roi, mid, float(pair.split("->")[0]))
        if not ib:
            continue
        srcs = []
        for name, tbl in (("DENSE_R2", dense), ("V24R1", v24t), ("GFTT_M1", gftt)):
            if (mid, pair) in tbl:
                srcs.append((name, tbl[(mid, pair)]["T3"]))
        if len(srcs) >= 2:
            for i in range(len(srcs)):
                for j in range(i + 1, len(srcs)):
                    med = disagreement_med(srcs[i][1], srcs[j][1], ib)
                    fam_i = FAM[srcs[i][0]]
                    fam_j = FAM[srcs[j][0]]
                    cross = fam_i != fam_j
                    edges.append({"case": mid, "pair": pair,
                                  "a": srcs[i][0], "b": srcs[j][0],
                                  "median_px": round(med, 3),
                                  "agree": med <= AGREE_MED_MAX,
                                  "cross_family": bool(cross),
                                  "same_family": not cross})
    (OUT / "TREECUT_CAM01_EH02_LOCAL_AGREEMENT_GRAPH.json").write_text(
        json.dumps({"edges": edges}, ensure_ascii=False, indent=1), encoding="utf-8")
    # conflict = any pair of gated materialized local sources disagree > 3px
    conflicts = {}
    for e in edges:
        if not e["agree"]:
            conflicts.setdefault((e["case"], e["pair"]), []).append(
                {"a": e["a"], "b": e["b"], "median_px": e["median_px"]})
    print("agreement edges:", len(edges), "| conflict pairs:", len(conflicts))

    # ===== §10-§19 router rules =====
    def has_cross_family_agree(mid, pair, source):
        """source 与任一 cross-family materialized source AGREE。"""
        for e in edges:
            if e["case"] == mid and e["pair"] == pair and e["agree"] and e["cross_family"]:
                if e["a"] == source or e["b"] == source:
                    return True
        return False

    rows = []
    for (mid, pair) in sem:
        row = {"case": mid, "pair": pair}
        dense_r = dense.get((mid, pair))
        v24_r = v24t.get((mid, pair))
        gftt_r = gftt.get((mid, pair))
        sstate = struct_by.get((mid, pair), "STRUCTURAL_UNKNOWN")
        camok = cam_by.get((mid, pair), False)
        # conflict precedence (§16)
        if (mid, pair) in conflicts:
            row.update({"route": "UNSURE_CONFLICT", "reason": "LOCAL_CONFLICT",
                        "conflict_detail": conflicts[(mid, pair)],
                        "safe_emit": False,
                        "representative": None})
            rows.append(row)
            continue
        # HIGH_CONF source present
        high_sources = []
        for nm, r in (("DENSE_R2", dense_r), ("V24R1", v24_r)):
            if r and r["conf"] == "HIGH":
                high_sources.append(nm)
        medium_sources = []
        for nm, r in (("DENSE_R2", dense_r), ("GFTT_M1", gftt_r)):
            if r and r["conf"] == "MEDIUM":
                medium_sources.append(nm)
        # RULE S1
        if high_sources and sstate != "STRUCTURAL_DISAGREEMENT":
            rep_name = high_sources[0] if len(high_sources) == 1 else "DENSE_R2" if "DENSE_R2" in high_sources else "V24R1"
            ann = "STRONG_INTERNAL_CONSENSUS"
            if sstate == "STRUCTURAL_UNKNOWN":
                ann += "_NO_STRUCTURAL_VETO_AVAILABLE"
            elif sstate == "STRUCTURAL_CONSISTENT":
                ann += "_STRUCTURAL_SUPPORTED"
            row.update({"route": "REFERENCE_STRONG", "rule": "S1",
                        "reason": f"HIGH_CONF({'+'.join(high_sources)}) no-conflict struct={sstate}",
                        "confidence_annotation": ann,
                        "safe_emit": True,
                        "representative": rep_name,
                        "representative_transform": (dense_r or v24_r or gftt_r)["T3"].tolist()
                        if (dense_r or v24_r or gftt_r) else None})
            rows.append(row)
            continue
        # RULE S2: MEDIUM + structural CONSISTENT + global reliable + no conflict
        if medium_sources and sstate == "STRUCTURAL_CONSISTENT" and camok:
            rep_name = medium_sources[0] if len(medium_sources) == 1 else "DENSE_R2" if "DENSE_R2" in medium_sources else "GFTT_M1"
            row.update({"route": "REFERENCE_STRONG", "rule": "S2",
                        "reason": f"MEDIUM({'+'.join(medium_sources)}) struct=CONSISTENT global=RELIABLE",
                        "confidence_annotation": "S2_MEDIUM_STRUCT_GLOBAL",
                        "safe_emit": True,
                        "representative": rep_name,
                        "representative_transform": (dense_r or gftt_r)["T3"].tolist()})
            rows.append(row)
            continue
        # RULE S3: MEDIUM + cross-family agree + structural != DISAGREEMENT
        if medium_sources and sstate != "STRUCTURAL_DISAGREEMENT":
            ok_cross = False
            for nm in medium_sources:
                if has_cross_family_agree(mid, pair, nm):
                    ok_cross = True
                    break
            if ok_cross:
                rep_name = medium_sources[0] if len(medium_sources) == 1 else "DENSE_R2" if "DENSE_R2" in medium_sources else "GFTT_M1"
                row.update({"route": "REFERENCE_STRONG", "rule": "S3",
                            "reason": f"MEDIUM({'+'.join(medium_sources)}) cross-family-agree struct={sstate}",
                            "confidence_annotation": "S3_CROSS_FAMILY_AGREEMENT",
                            "safe_emit": True,
                            "representative": rep_name,
                            "representative_transform": (dense_r or gftt_r)["T3"].tolist()})
                rows.append(row)
                continue
        # PARTIAL / PARTIAL_VETOED
        if dense_r or v24_r or gftt_r:
            if sstate == "STRUCTURAL_DISAGREEMENT":
                row.update({"route": "REFERENCE_PARTIAL_VETOED", "reason": "struct disagreement veto",
                            "safe_emit": False,
                            "representative": "DENSE_R2" if dense_r else "V24R1" if v24_r else "GFTT_M1",
                            "representative_transform": (dense_r or v24_r or gftt_r)["T3"].tolist()})
            else:
                row.update({"route": "REFERENCE_PARTIAL",
                            "reason": f"transform present not STRONG (struct={sstate} global={camok})",
                            "safe_emit": False,
                            "representative": "DENSE_R2" if dense_r else "V24R1" if v24_r else "GFTT_M1",
                            "representative_transform": (dense_r or v24_r or gftt_r)["T3"].tolist()})
            rows.append(row)
            continue
        # EVIDENCE_ONLY (global state / DINO only)
        if camok:
            row.update({"route": "UNSURE_EVIDENCE_ONLY", "reason": "global state only (no local transform)",
                        "safe_emit": False, "representative": None})
        else:
            row.update({"route": "UNSURE_NO_EVIDENCE", "reason": "no local/global evidence",
                        "safe_emit": False, "representative": None})
        rows.append(row)
    # freeze rules hash
    rules_txt = ("S1:HIGH+no-conflict+struct!=DISC;S2:MED+CONSISTENT+global-rel;"
                 "S3:MED+cross-family-agree+struct!=DISC;conflict-precedence;"
                 "tiebreak DENSE_R2>V24R1>GFTT_M1")
    rules_hash = hashlib.sha256(rules_txt.encode("utf-8")).hexdigest()[:16]
    # source hashes
    src_hashes = {"DENSE_R2": "8f84735/748e3ccb", "V24R1": "e2bb0ae/e433a90e",
                  "GFTT_M1": "644c206/(M1 derived)", "GLOBAL_V2": "f85b363/268695d7"}
    freeze = {"rules_hash": rules_hash,
              "rules": rules_txt,
              "source_hashes": src_hashes,
              "ROUTER_FREEZE": True,
              "36_pair_routes": rows}
    (OUT / "TREECUT_CAM01_EH02_ROUTER_FREEZE.json").write_text(
        json.dumps(freeze, ensure_ascii=False, indent=1), encoding="utf-8")
    # ===== §21 metrics =====
    rc = Counter(r["route"] for r in rows)
    strong = rc.get("REFERENCE_STRONG", 0)
    safe_emit = sum(1 for r in rows if r["safe_emit"])
    strong_cases = len({r["case"] for r in rows if r["route"] == "REFERENCE_STRONG"})
    # unique additions vs EH01R1 strong 9
    r1r = load("TREECUT_CAM01_EH01R1_ROUTER_SHADOW.json")["rows"]
    r1_strong = {(r["case"], r["pair"]) for r in r1r if r["route"] == "REFERENCE_EMITTABLE_STRONG"}
    eh2_strong = {(r["case"], r["pair"]) for r in rows if r["route"] == "REFERENCE_STRONG"}
    gftt_add = eh2_strong - r1_strong
    metrics = {"route_counts": dict(rc),
               "REFERENCE_STRONG": strong,
               "REFERENCE_PARTIAL": rc.get("REFERENCE_PARTIAL", 0),
               "REFERENCE_PARTIAL_VETOED": rc.get("REFERENCE_PARTIAL_VETOED", 0),
               "UNSURE_CONFLICT": rc.get("UNSURE_CONFLICT", 0),
               "UNSURE_EVIDENCE_ONLY": rc.get("UNSURE_EVIDENCE_ONLY", 0),
               "UNSURE_NO_EVIDENCE": rc.get("UNSURE_NO_EVIDENCE", 0),
               "safe_emit": safe_emit,
               "case_coverage_9": strong_cases,
               "gftt_new_strong_additions": sorted(f"{c} {p}" for c, p in gftt_add),
               "gftt_new_strong_count": len(gftt_add),
               "vs_eh01r1_strong_9": {"old_strong": len(r1_strong), "new_strong": strong,
                                      "delta": strong - len(r1_strong)}}
    (OUT / "TREECUT_CAM01_EH02_ROUTER_METRICS.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=1))
    # source matrix (full inventory per pair) - lightweight
    sm = []
    for (mid, pair) in sem:
        sm.append({"case": mid, "pair": pair,
                   "DENSE": bool((mid, pair) in dense),
                   "V24": bool((mid, pair) in v24t),
                   "GFTT": bool((mid, pair) in gftt),
                   "GLOBAL_state": cam_by.get((mid, pair)),
                   "STRUCTURAL": struct_by.get((mid, pair), "STRUCTURAL_UNKNOWN")})
    (OUT / "TREECUT_CAM01_EH02_SOURCE_MATRIX.json").write_text(
        json.dumps({"rows": sm}, ensure_ascii=False, indent=1), encoding="utf-8")
    # ===== §22-24 readiness (role read AFTER freeze) =====
    role_by = {c["media_id"]: c["role"] for c in man["cases"]}

    def tgt_ok(mid, t):
        b = [a for a in roi if a["media_id"] == mid and a["frame_timestamp"] == t]
        ex = [a for a in b if a["object_name"] == "EXTENSION_TABLETOP"]
        if len(ex) == 1:
            return True
        tp = [a for a in b if a["object_name"] == "TABLETOP"]
        return len(ex) == 0 and len(tp) == 1

    rd = {"POS": [], "NEG": []}
    for r in rows:
        rl = role_by.get(r["case"])
        if rl not in ("POS", "NEG"):
            continue
        if r["route"] != "REFERENCE_STRONG":
            continue
        t0, t1 = [float(x) for x in r["pair"].split("->")]
        ok = tgt_ok(r["case"], t0) and tgt_ok(r["case"], t1)
        rd[rl].append({"case": r["case"], "pair": r["pair"],
                       "target_valid": bool(ok),
                       "rule": r.get("rule"), "rep": r.get("representative")})
    neg_strong_tv = sum(1 for x in rd["NEG"] if x["target_valid"])
    pos_strong_tv = sum(1 for x in rd["POS"] if x["target_valid"])
    # NEG control
    if neg_strong_tv >= 1:
        neg_control = "PRESENT"
    else:
        neg_control = "NOT_READY"
    # unique visual families among NEG strong target-valid
    fam_map = {"DENSE_R2": "SEMANTIC_DENSE_LK", "V24R1": "FEATURE_LOCAL_ENSEMBLE",
               "GFTT_M1": "FEATURE_LOCAL"}
    neg_fams = set()
    for x in rd["NEG"]:
        if x["target_valid"]:
            neg_fams.add(fam_map.get(x["rep"], x["rep"]))
    established = neg_strong_tv >= 3 and len(neg_fams) >= 3
    neg_status = "ESTABLISHED" if established else (neg_control if neg_strong_tv >= 1 else "NOT_READY")
    readiness = {"POS_strong_target_valid": pos_strong_tv,
                 "POS_detail": rd["POS"],
                 "NEG_strong_target_valid": neg_strong_tv,
                 "NEG_detail": rd["NEG"],
                 "NEG_unique_families": sorted(neg_fams),
                 "NEG_REFERENCE_CONTROL": neg_status,
                 "NEG_REFERENCE_CONTROL_PRESENT": neg_strong_tv >= 1,
                 "NEG_REFERENCE_CONTROL_ESTABLISHED": established,
                 "note": "ESTABLISHED 需 >=3 unique visual families AND target-valid AND STRONG；"
                         "单/双样本只能 PRESENT"}
    (OUT / "TREECUT_CAM01_EH02_TARGET_READINESS.json").write_text(
        json.dumps(readiness, ensure_ascii=False, indent=1), encoding="utf-8")
    # ===== §25 global upper bound =====
    gub = {"UNSURE_or_PARTIAL_with_global_reliable": [], "already_have_local_transform": [], "no_local_transform": []}
    for r in rows:
        if r["route"] not in ("UNSURE_CONFLICT", "UNSURE_EVIDENCE_ONLY", "UNSURE_NO_EVIDENCE",
                              "REFERENCE_PARTIAL", "REFERENCE_PARTIAL_VETOED"):
            continue
        if not cam_by.get((r["case"], r["pair"])):
            continue
        has_local = bool((r["case"], r["pair"]) in dense or (r["case"], r["pair"]) in v24t
                         or (r["case"], r["pair"]) in gftt)
        entry = {"case": r["case"], "pair": r["pair"], "route": r["route"],
                 "has_local_transform": has_local}
        gub["UNSURE_or_PARTIAL_with_global_reliable"].append(entry)
        if has_local:
            gub["already_have_local_transform"].append(entry)
        else:
            gub["no_local_transform"].append(entry)
    gub["GLOBAL_MATERIALIZATION_UPPER_BOUND"] = len(gub["no_local_transform"])
    (OUT / "TREECUT_CAM01_EH02_GLOBAL_UPPER_BOUND.json").write_text(
        json.dumps(gub, ensure_ascii=False, indent=1), encoding="utf-8")
    print("readiness:", neg_status, "| NEG strong tv:", neg_strong_tv, "| POS:", pos_strong_tv)
    print("global upper bound:", gub["GLOBAL_MATERIALIZATION_UPPER_BOUND"])


if __name__ == "__main__":
    main()
