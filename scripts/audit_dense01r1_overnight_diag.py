# -*- coding: utf-8 -*-
"""DENSE01R1 OVERNIGHT — DETERMINISM CHECK (§25) & LK TAXONOMY (§10/§11) & TOKEN AUDIT (§5)
& SOFTMAX (§8) & MATCH QUALITY (§7) & TEMPORAL GAP (§21) & CAMERA/VIEW (§22)。

全部 role-blind：只按 media_id/pair 处理，不读 role 分支。
输入：TREECUT_DENSE01R1_OVERNIGHT_REPLAY_{replay1,replay2}.json + manifest + ROI。
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
MANIFEST = OUT / "TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json"
ROI_JSON = OUT / "TREECUT_POSTA3_HUMAN_ROI_V1.json"
sys.stdout.reconfigure(encoding="utf-8")


def pct(a, q):
    a = np.asarray(a, dtype=np.float64)
    return round(float(np.percentile(a, q)), 3) if len(a) else None


def main():
    r1 = json.loads((OUT / "TREECUT_DENSE01R1_OVERNIGHT_REPLAY_replay1.json")
                    .read_text(encoding="utf-8"))
    r2 = json.loads((OUT / "TREECUT_DENSE01R1_OVERNIGHT_REPLAY_replay2.json")
                    .read_text(encoding="utf-8"))
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    # media_id -> frames t_s（temporal gap）
    ts_by = {c["media_id"]: [f["t_s"] for f in c["frames"]] for c in man["cases"]}
    roi = json.loads(ROI_JSON.read_text(encoding="utf-8"))["annotations"]

    # ---------- §25 determinism ----------
    p1 = {p["pair"]: p for p in r1["pairs"]}
    p2 = {p["pair"]: p for p in r2["pairs"]}
    det = {"replay1_tag": r1["tag"], "replay2_tag": r2["tag"], "seed2": r2.get("seed"),
           "n_pairs": len(r1["pairs"])}
    mism = []
    for k in p1:
        a, b = p1[k], p2[k]
        d = {}
        if a.get("valid_mnn") != b.get("valid_mnn"):
            d["valid_mnn"] = (a.get("valid_mnn"), b.get("valid_mnn"))
        if a.get("lk_attempted") != b.get("lk_attempted"):
            d["lk_attempted"] = (a.get("lk_attempted"), b.get("lk_attempted"))
        if a.get("lk_accepted_prod_semantics") != b.get("lk_accepted_prod_semantics"):
            d["lk_accepted"] = (a.get("lk_accepted_prod_semantics"),
                                b.get("lk_accepted_prod_semantics"))
        if a.get("state") != b.get("state"):
            d["state"] = (a.get("state"), b.get("state"))
        # corr 级 MNN/LK 明细（抽样比较 counts）
        ca, cb = a.get("corr", []), b.get("corr", [])
        if len(ca) != len(cb):
            d["corr_len"] = (len(ca), len(cb))
        if d:
            mism.append({"case": a["case"], "pair": k, "diffs": d})
    det["mismatches"] = mism
    det["nondeterminism_found"] = len(mism) > 0
    # 状态级一致性
    ca1 = Counter(p.get("state") for p in r1["pairs"])
    ca2 = Counter(p.get("state") for p in r2["pairs"])
    det["state_counts_1"] = dict(ca1)
    det["state_counts_2"] = dict(ca2)
    det["state_counts_equal"] = ca1 == ca2
    (OUT / "TREECUT_DENSE01R1_OVERNIGHT_DETERMINISM.json").write_text(
        json.dumps(det, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- §10 LK rejection taxonomy (from replay1) ----------
    tax = Counter()
    fb_stats = []
    seed_corr = []
    accepted_corr_px = []
    fb_rejected = {"n": 0, "fb_vals": []}
    for p in r1["pairs"]:
        for x in p.get("corr", []):
            if not x.get("fwd_ok"):
                tax["FWD_STATUS_FAIL"] += 1
                continue
            if not x.get("in_island"):
                tax["DEST_OUTSIDE_ISLAND"] += 1
                continue
            if x.get("in_dynamic"):
                tax["DEST_DYNAMIC_CONTAM"] += 1
                continue
            fb = x.get("fb_px")
            if fb is None:
                tax["BWD_STATUS_FAIL"] += 1
                continue
            tax["ACCEPTED"] += 1
            fb_stats.append(fb)
            if x.get("p1_lk"):
                accepted_corr_px.append(x.get("corr_px"))
            if fb > 3.0:
                fb_rejected["n"] += 1
                fb_rejected["fb_vals"].append(round(fb, 2))
            if len(seed_corr) < 400:
                seed_corr.append({"case": p["case"], "pair": p["pair"],
                                  "i0": x["i0"], "j1": x["j1"],
                                  "p0": x["p0"], "p1_sub": x["p1_sub"],
                                  "p1_lk": x.get("p1_lk"),
                                  "corr_px": x.get("corr_px"), "fb_px": x.get("fb_px")})
    tax_json = {"taxonomy": dict(tax),
                "accepted_total": tax["ACCEPTED"],
                "fb_over_3_of_accepted": fb_rejected["n"],
                "fb_pooled": {"n": len(fb_stats), "median": pct(fb_stats, 50),
                              "p90": pct(fb_stats, 90), "p95": pct(fb_stats, 95),
                              "max": (round(float(max(fb_stats)), 3) if fb_stats else None)},
                "accepted_corr_mag": {"n": len(accepted_corr_px),
                                      "median": pct(accepted_corr_px, 50),
                                      "p90": pct(accepted_corr_px, 90),
                                      "p95": pct(accepted_corr_px, 95),
                                      "max": (round(float(max(accepted_corr_px)), 3)
                                              if accepted_corr_px else None)}}
    (OUT / "TREECUT_DENSE01R1_OVERNIGHT_LK_AUDIT.json").write_text(
        json.dumps(tax_json, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_DENSE01R1_OVERNIGHT_LK_SEED_SAMPLE.json").write_text(
        json.dumps({"sample": seed_corr}, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- §11 LK quality per pair ----------
    lkq = []
    for p in r1["pairs"]:
        fbs = []
        cps = []
        for x in p.get("corr", []):
            if x.get("fwd_ok") and x.get("in_island") and not x.get("in_dynamic") \
                    and x.get("fb_px") is not None:
                fbs.append(x["fb_px"])
                if x.get("corr_px") is not None:
                    cps.append(x["corr_px"])
        lkq.append({"case": p["case"], "pair": p["pair"],
                    "n_accepted": len(fbs),
                    "fb": {"median": pct(fbs, 50), "p90": pct(fbs, 90),
                           "p95": pct(fbs, 95), "max": (round(float(max(fbs)), 3) if fbs else None)},
                    "corr_mag": {"median": pct(cps, 50), "p90": pct(cps, 90),
                                 "p95": pct(cps, 95)}})
    (OUT / "TREECUT_DENSE01R1_OVERNIGHT_LK_QUALITY_MAP.json").write_text(
        json.dumps({"per_pair": lkq}, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- §5 token domain audit（每 frame 计数从 replay 汇总） ----------
    tok_rows = []
    for p in r1["pairs"]:
        t = p.get("token")
        if t:
            tok_rows.append({"case": p["case"], "pair": p["pair"],
                             "total": t["total"], "cvm0": t["cvm0"], "cvm1": t["cvm1"],
                             "dyn0": t["dyn0"], "dyn1": t["dyn1"],
                             "valid0": t["valid0"], "valid1": t["valid1"]})
    (OUT / "TREECUT_DENSE01R1_OVERNIGHT_TOKEN_DOMAIN_AUDIT.json").write_text(
        json.dumps({"rows": tok_rows}, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- §8 softmax subtoken audit（coarse token vs soft target） ----------
    shifts = []
    soft_rows = []
    for p in r1["pairs"]:
        for x in p.get("corr", []):
            pt = x.get("p1_token"); ps = x.get("p1_sub")
            if pt and ps:
                sh = float(np.hypot(ps[0] - pt[0], ps[1] - pt[1]))
                shifts.append(sh)
                if len(soft_rows) < 20:
                    soft_rows.append({"case": p["case"], "pair": p["pair"],
                                      "coarse_token_raw": pt, "soft_raw": ps,
                                      "shift_px": round(sh, 3)})
    soft = {"n_total": len(shifts),
            "shift_median_px": pct(shifts, 50),
            "shift_p90_px": pct(shifts, 90),
            "shift_max_px": (round(float(max(shifts)), 3) if shifts else None),
            "sample_20": soft_rows,
            "note": "coarse token 中心 vs softmax 3x3 亚 token 目标"}
    (OUT / "TREECUT_DENSE01R1_OVERNIGHT_SOFTMAX_AUDIT.json").write_text(
        json.dumps(soft, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- §7 match quality profile（从 MNN sim + 位移） ----------
    mq = []
    for p in r1["pairs"]:
        sims = [x["sim"] for x in p.get("corr", [])]
        mq.append({"case": p["case"], "pair": p["pair"],
                   "mnn": p.get("valid_mnn"),
                   "sim": {"median": pct(sims, 50), "p10": pct(sims, 10),
                           "p90": pct(sims, 90)},
                   "cov_all": p.get("coverage")})
    (OUT / "TREECUT_DENSE01R1_OVERNIGHT_MATCH_QUALITY.json").write_text(
        json.dumps({"per_pair": mq}, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- §21 temporal gap ----------
    tg = []
    for p in r1["pairs"]:
        t0, t1 = [float(x) for x in p["pair"].split("->")]
        dt = round(t1 - t0, 3)
        st = p.get("state")
        med = p90 = None
        for mdl in ("PARTIAL_AFFINE", "HOMOGRAPHY"):
            md = p.get("models", {}).get("DINO_LK", {}).get(mdl)
            if md and "folds" in md:
                ms = [fv.get("med") for fv in md["folds"].values() if fv.get("med") is not None]
                ps = [fv.get("p90") for fv in md["folds"].values() if fv.get("p90") is not None]
                if ms:
                    med = min(ms) if med is None else min(med, min(ms))
                if ps:
                    p90 = min(ps) if p90 is None else min(p90, min(ps))
        tg.append({"case": p["case"], "pair": p["pair"], "dt": dt,
                   "state": st, "best_med": med, "best_p90": p90,
                   "lk_acc": p.get("lk_accepted_prod_semantics"),
                   "lk_att": p.get("lk_attempted")})
    bins = {"<1s": [], "1-2s": [], "2-3s": [], ">3s": []}
    for r in tg:
        dt = r["dt"]
        key = "<1s" if dt < 1 else "1-2s" if dt < 2 else "2-3s" if dt < 3 else ">3s"
        bins[key].append(r)
    bin_stats = {}
    for k, rows in bins.items():
        meds = [r["best_med"] for r in rows if r["best_med"] is not None]
        p90s = [r["best_p90"] for r in rows if r["best_p90"] is not None]
        bin_stats[k] = {"n": len(rows),
                        "n_validated": sum(1 for r in rows if r["state"] in
                                           ("DENSE_MULTI_MODEL_CONSENSUS", "DENSE_SINGLE_MODEL")),
                        "med_median": pct(meds, 50) if meds else None,
                        "p90_median": pct(p90s, 50) if p90s else None,
                        "lk_acc_rate": (round(sum(r["lk_acc"] or 0 for r in rows) /
                                              max(1, sum(r["lk_att"] or 0 for r in rows)), 3)
                                        if rows else None)}
    (OUT / "TREECUT_DENSE01R1_OVERNIGHT_TEMPORAL_GAP.json").write_text(
        json.dumps({"per_pair": tg, "buckets": bin_stats}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    # ---------- §22 camera/view change（bbox displacement/size ratio） ----------
    cam = []
    for p in r1["pairs"]:
        t0, t1 = [float(x) for x in p["pair"].split("->")]
        b0 = [a for a in roi if a["media_id"] == p["case"] and a["frame_timestamp"] == t0
              and a["object_name"] == "ISLAND_BODY"]
        b1 = [a for a in roi if a["media_id"] == p["case"] and a["frame_timestamp"] == t1
              and a["object_name"] == "ISLAND_BODY"]
        if not (len(b0) == 1 and len(b1) == 1):
            continue
        r0 = b0[0]["bbox_pixel"]; r1_ = b1[0]["bbox_pixel"]
        c0 = ((r0[0] + r0[2]) / 2, (r0[1] + r0[3]) / 2)
        c1 = ((r1_[0] + r1_[2]) / 2, (r1_[1] + r1_[3]) / 2)
        disp = float(np.hypot(c1[0] - c0[0], c1[1] - c0[1]))
        w0 = max(1e-9, r0[2] - r0[0]); h0 = max(1e-9, r0[3] - r0[1])
        w1 = max(1e-9, r1_[2] - r1_[0]); h1 = max(1e-9, r1_[3] - r1_[1])
        ar0, ar1 = w0 / h0, w1 / h1
        cam.append({"case": p["case"], "pair": p["pair"],
                    "bbox_center_disp_raw": round(disp, 2),
                    "size_ratio": round((w1 * h1) / (w0 * h0), 3),
                    "aspect_change": round(abs(ar1 - ar0) / max(ar0, 1e-9), 3),
                    "state": p.get("state")})
    (OUT / "TREECUT_DENSE01R1_OVERNIGHT_CAMERA_VIEW.json").write_text(
        json.dumps({"per_pair": cam}, ensure_ascii=False, indent=1), encoding="utf-8")

    print(json.dumps({"nondeterminism_found": det["nondeterminism_found"],
                      "state_equal": det["state_counts_equal"],
                      "lk_taxonomy": dict(tax),
                      "lk_fb_pooled": tax_json["fb_pooled"],
                      "soft_shift_median": soft["shift_median_px"],
                      "temporal_buckets": bin_stats}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
