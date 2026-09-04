# -*- coding: utf-8 -*-
"""MMVV A2.1 — Target Identity + Geometry Direction/State 重跑（7 slices）。

前置: reports/storage/TREECUT_MMVV_A21_TARGET_BINDING.json（52/109 抽屉实例人工绑定）。
若缺少绑定帧 → 不自动猜身份，输出 AWAITING_BINDING 清单后退出(exit 2)。
机器输入仅: timestamps + L3 ROI 坐标 + instance binding + island 相对几何 + canonical camera；
不使用 Human GT 动作；model_action 与机器几何通道分离。
"""
import json, sys
from pathlib import Path
import cv2
import numpy as np

REPO = Path(r"C:\Users\admin\github\treecut-v13")
sys.path.insert(0, str(REPO / "src"))
from treecut.services.mmvl_master_v1 import (  # noqa: E402
    ROI, Action, FrameSemantics, MotionMetrics, TemporalEvidence,
    TargetObjectMotionRouter, TemporalStateValidator, compensate_pair,
    build_geometry_direction_evidence, bind_target_timeline)

OUT = REPO / "reports" / "storage"
MAN = json.loads((OUT / "TREECUT_MMVV_A1_FRAME_MANIFEST.json").read_text(encoding="utf-8"))
ROI_ALL = json.loads((OUT / "TREECUT_MMVV_HUMAN_GT_ROI_A1.json").read_text(encoding="utf-8"))["annotations"]
BIND_FILE = OUT / "TREECUT_MMVV_A21_TARGET_BINDING.json"
DOCS = REPO / "docs"

DRAWER_FAM = {"DRAWER", "UPPER_THIN_DRAWER"}
TABLETOP_FAM = {"TABLETOP", "EXTENSION_TABLETOP"}
MOVING = {"HAND", "PERSON", "SOCKET_MODULE", "TRACK_SOCKET", "OTHER_MOVING_PART"}
CANON = {"EXTENSION_TABLETOP": "TABLETOP", "UPPER_THIN_DRAWER": "DRAWER"}

SLICES = [
    {"id": "52_DRAWER_OPEN", "media": 52, "action": "DRAWER_OPEN", "target_fam": DRAWER_FAM,
     "frames_t": [7.5, 7.75, 8.0, 10.0], "gt": "PASS"},
    {"id": "109_ACTION_POSITIVE", "media": 109, "action": "DRAWER_OPEN", "target_fam": DRAWER_FAM,
     "frames_t": [0.0, 1.45], "gt": "PASS"},
    {"id": "109_OPEN_STATE_NEGATIVE", "media": 109, "action": "DRAWER_OPEN", "target_fam": DRAWER_FAM,
     "frames_t": [2.9, 4.35, 5.8], "gt": "FAIL"},
    {"id": "89_EXTEND", "media": 89, "action": "EXTEND", "target_fam": TABLETOP_FAM,
     "frames_t": [0.0, 1.78, 3.56, 5.34, 7.12], "gt": "FAIL"},
    {"id": "51_EXTEND", "media": 51, "action": "EXTEND", "target_fam": TABLETOP_FAM,
     "frames_t": [0.0, 2.5, 5.0, 7.5, 10.0], "gt": "FAIL"},
    {"id": "1985_EXTEND", "media": 1985, "action": "EXTEND", "target_fam": TABLETOP_FAM,
     "frames_t": [1.9, 2.525, 3.15, 3.775, 4.4], "gt": "FAIL", "cam_uncertain": True},
    {"id": "1986_EXTEND", "media": 1986, "action": "EXTEND", "target_fam": TABLETOP_FAM,
     "frames_t": [1.9, 2.525, 3.15, 3.775, 4.4], "gt": "FAIL", "cam_uncertain": True},
]
ACT = {"EXTEND": Action.EXTEND, "DRAWER_OPEN": Action.DRAWER_OPEN}


def imread(p):
    return cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)


def norm_diff(a, b):
    return float(np.abs(a.astype(np.float32) - b.astype(np.float32)).mean() / 40.0)


def boxes_at(media, t):
    return [a for a in ROI_ALL if a["media_id"] == media and a["frame_timestamp"] == t]


def measure_box_diff(fr_a, fr_b, box, exclude):
    wb, cam = compensate_pair(fr_a, fr_b)
    x1, y1, x2, y2 = box
    if x2 - x1 < 8 or y2 - y1 < 8:
        return cam, 0.0
    ga = cv2.cvtColor(fr_a, cv2.COLOR_BGR2GRAY)
    gb = cv2.cvtColor(wb, cv2.COLOR_BGR2GRAY)
    ca = ga[y1:y2, x1:x2].astype(np.float32)
    cb = gb[y1:y2, x1:x2].astype(np.float32)
    mask = np.ones(ca.shape, dtype=bool)
    for ex in exclude:
        ox1, oy1, ox2, oy2 = ex
        ix1, iy1 = max(x1, ox1), max(y1, oy1)
        ix2, iy2 = min(x2, ox2), min(y2, oy2)
        if ix2 > ix1 and iy2 > iy1:
            mask[iy1 - y1:iy2 - y1, ix1 - x1:ix2 - x1] = False
    m = norm_diff(ca[mask], cb[mask]) if mask.sum() else 0.0
    return cam, m


def load_binding():
    if not BIND_FILE.exists():
        return {}
    doc = json.loads(BIND_FILE.read_text(encoding="utf-8"))
    out = {}
    for b in doc.get("bindings", []):
        out[(b["media_id"], b["t_s"])] = b.get("chosen_index")
    return out


def main():
    binding = load_binding()
    missing = []
    for sl in SLICES:
        mid = sl["media"]
        fam = sl["target_fam"]
        case = next(c for c in MAN["cases"] if c["media_id"] == mid)
        for t in sl["frames_t"]:
            bs = [b for b in boxes_at(mid, t) if b["object_name"] in fam]
            if len(bs) <= 1:
                continue  # 单框无需绑定；0 框=该帧目标不可见(如52@7.5 预备帧)，不算缺失
            if (mid, t) not in binding or binding[(mid, t)] is None:
                missing.append({"media": mid, "t_s": t, "n_boxes": len(bs)})
    if missing:
        (OUT / "TREECUT_MMVV_A21_AWAITING_BINDING.json").write_text(
            json.dumps({"status": "AWAITING_BINDING", "missing": missing,
                        "url": "http://127.0.0.1:8933/a21/bind"}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        print("AWAITING_BINDING frames:", missing)
        sys.exit(2)

    results = []
    for sl in SLICES:
        mid = sl["media"]
        action = ACT[sl["action"]]
        fam = sl["target_fam"]
        case = next(c for c in MAN["cases"] if c["media_id"] == mid)
        frames = [next(x for x in case["frames"] if x["t_s"] == t) for t in sl["frames_t"]]
        imgs = {f["t_s"]: imread(f["local_path"]) for f in frames}
        # 目标实例框（绑定）与岛台框 per t
        target_idx = {}
        for t in sl["frames_t"]:
            bs = [b for b in boxes_at(mid, t) if b["object_name"] in fam]
            target_idx[t] = binding.get((mid, t), 0 if len(bs) == 1 else None)
        tgt_box = {t: (boxes_at(mid, t)[target_idx[t]]["bbox_pixel"] if target_idx[t] is not None else None)
                   for t in sl["frames_t"]}
        island_box = {}
        for t in sl["frames_t"]:
            ibs = [b["bbox_pixel"] for b in boxes_at(mid, t) if b["object_name"] == "ISLAND_BODY"]
            island_box[t] = ibs[0] if ibs else None
        # 像素运动（目标框内、排除其它所有人/手/插座/其它抽屉）
        pair_ev = []
        target_motion = 0.0
        agg = {}
        cam_bad = False
        cam_max_res = 0.0
        for i in range(len(frames) - 1):
            ta, tb = frames[i]["t_s"], frames[i + 1]["t_s"]
            box_a = tgt_box.get(ta)
            if box_a is None:
                continue
            excl = []
            for b in boxes_at(mid, ta):
                if b["bbox_pixel"] != box_a and (b["object_name"] in MOVING or b["object_name"] in DRAWER_FAM | TABLETOP_FAM):
                    excl.append(b["bbox_pixel"])
            cam, m = measure_box_diff(imgs[ta], imgs[tb], box_a, excl)
            target_motion = max(target_motion, m)
            cam_max_res = max(cam_max_res, cam.residual)
            cam_bad = cam_bad or (not cam.reliable) or cam.residual > 3.0
            pair_ev.append({"from_t": ta, "to_t": tb, "target_motion": round(m, 4),
                            "camera_model": cam.model, "translation_px": round(cam.translation_px, 3),
                            "inlier_ratio": round(cam.inlier_ratio, 3),
                            "feature_residual": round(cam.residual, 3), "reliable": bool(cam.reliable)})
        # 其它对象运动（供隔离证据）
        others = {}
        for t in sl["frames_t"]:
            for b in boxes_at(mid, t):
                if b["object_name"] in MOVING:
                    others[b["object_name"]] = True
        cam_unreliable = sl.get("cam_uncertain", False) or cam_bad or cam_max_res > 3.0
        # 几何证据（同实例时间线，含 island）
        tl = []
        for t in sorted(tgt_box):
            if tgt_box[t] is None:
                continue
            tl.append({"t_s": t, "bbox_pixel": list(tgt_box[t]),
                       "island_pixel": list(island_box[t]) if island_box.get(t) else None})
        target_canon = CANON.get(next(iter(sl["target_fam"] & {b["object_name"] for b in boxes_at(mid, sl["frames_t"][0])}), None) or "DRAWER")
        geo = build_geometry_direction_evidence(target_canon, "A", tl, camera_unreliable=cam_unreliable)
        # validator
        def sem(ts):
            bs = boxes_at(mid, ts)
            names = [CANON.get(b["object_name"], b["object_name"]) for b in bs]
            return FrameSemantics(ts, names, [],
                                  [ROI(CANON.get(b["object_name"], b["object_name"]), *b["bbox_pixel"], source="L3_HUMAN_ROI")
                                   for b in bs], dominant_visual=target_canon)
        vis_ts = [t for t in sl["frames_t"] if tgt_box.get(t) is not None]
        mm = MotionMetrics(global_motion_px=0.0, camera_residual=round(cam_max_res, 3),
                           roi_motion={target_canon: round(target_motion, 3),
                                       **{k: None for k in others}})
        ev = TemporalEvidence(before=sem(vis_ts[0]), middle=sem(vis_ts[len(vis_ts) // 2]),
                              after=sem(vis_ts[-1]), motion=mm,
                              requested_action=action, model_action=Action.UNKNOWN,
                              geometry_direction_evidence=geo)
        v = TemporalStateValidator(TargetObjectMotionRouter()).validate(ev)
        results.append({
            "slice": sl["id"], "media_id": mid, "requested": sl["action"],
            "frames_used": [f["frame"] for f in frames], "frame_timestamps": [f["t_s"] for f in frames],
            "target_object": target_canon, "instance_id": "A",
            "target_visible_frames": len(vis_ts),
            "camera": {"max_feature_residual": round(cam_max_res, 3), "unreliable": cam_unreliable},
            "pair_evidence": pair_ev,
            "target_motion": round(target_motion, 4),
            "moving_objects_present": sorted(others),
            "geometry_direction_evidence": {
                "direction_action": geo.direction_action, "state_progress": geo.state_progress,
                "geometry_change_present": geo.geometry_change_present,
                "relative_motion_present": geo.relative_motion_present,
                "confidence_class": geo.confidence_class, "reason_codes": geo.reason_codes,
                "visibility_progression": geo.visibility_progression,
                "raw_openness_sequence": geo.raw_features.get("sequence", [])},
            "mandatory": dict(v.mandatory), "reason_codes": list(v.reason_codes),
            "machine_verdict": str(v.verdict), "human_gt": sl["gt"]})
    ok_map = {"52_DRAWER_OPEN": "PASS", "109_ACTION_POSITIVE": "PASS", "109_OPEN_STATE_NEGATIVE": "FAIL",
              "89_EXTEND": "FAIL", "51_EXTEND": "FAIL", "1985_EXTEND": "FAIL", "1986_EXTEND": "FAIL"}
    for r in results:
        exp = ok_map[r["slice"]]
        mv = r["machine_verdict"]
        r["expected_human"] = exp
        r["machine_matches_human"] = (mv == ("Verdict.PASS" if exp == "PASS" else "Verdict.FAIL"))
        r["false_pass"] = mv == "Verdict.PASS" and exp != "PASS"
        r["false_fail"] = mv == "Verdict.FAIL" and exp == "PASS"
        r["unsure"] = mv == "Verdict.UNSURE"
    doc = {"experiment": "MMVV_A2.1",
           "inputs": {"human_roi": 200, "frames": 32, "slices": 7, "binding": True},
           "method": "L3 ROI + instance binding + island-relative geometry -> GeometryDirectionEvidence -> TemporalStateValidator",
           "no_threshold_tuning": True, "geometry_tolerances": "documented provisional (_GEOM_*)",
           "results": results,
           "summary": {"match": sum(1 for r in results if r["machine_matches_human"]),
                       "false_pass": sum(1 for r in results if r["false_pass"]),
                       "false_fail": sum(1 for r in results if r["false_fail"]),
                       "unsure": sum(1 for r in results if r["unsure"])}}
    (OUT / "TREECUT_MMVV_A21_RESULTS_V1.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in results:
        print(r["slice"], "->", r["machine_verdict"], "| GT:", r["expected_human"],
              "| geo:", r["geometry_direction_evidence"]["direction_action"],
              r["geometry_direction_evidence"]["state_progress"],
              "| tgt_motion:", r["target_motion"], "| codes:", r["reason_codes"])
    print("SUMMARY", doc["summary"])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
