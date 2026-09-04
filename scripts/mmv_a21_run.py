# -*- coding: utf-8 -*-
"""MMVV A2.1 — 目标身份 + 几何方向/状态 评估（7 slices；权威 runner）。

方法: L3_ROI(绑定实例) → GeometryDirectionEvidence(相对岛台优先/绝对回退, 分数化变化率)
      → TemporalStateValidator(几何优先, model_action 分离) 。
pixel 目标运动仅作证据(compensate_pair 补偿后框内差)；判定以几何通道为主。
前置: TREECUT_MMVV_A21_TARGET_BINDING.json（52/109 抽屉人工绑定）；不自动猜身份。
"""
import json, sys, time
from pathlib import Path
import cv2
import numpy as np

REPO = Path(r"C:\Users\admin\github\treecut-v13")
sys.path.insert(0, str(REPO / "src"))
from treecut.services.mmvl_master_v1 import (  # noqa: E402
    ROI, Action, FrameSemantics, MotionMetrics, TemporalEvidence,
    TargetObjectMotionRouter, TemporalStateValidator, compensate_pair,
    build_geometry_direction_evidence)

OUT = REPO / "reports" / "storage"
MAN = json.loads((OUT / "TREECUT_MMVV_A1_FRAME_MANIFEST.json").read_text(encoding="utf-8"))
ROI_ALL = json.loads((OUT / "TREECUT_MMVV_HUMAN_GT_ROI_A1.json").read_text(encoding="utf-8"))["annotations"]
BIND_FILE = OUT / "TREECUT_MMVV_A21_TARGET_BINDING.json"
DF = {"DRAWER", "UPPER_THIN_DRAWER"}
TF = {"TABLETOP", "EXTENSION_TABLETOP"}
SLICES = [
    ("52_DRAWER_OPEN", 52, "DRAWER_OPEN", [7.5, 7.75, 8.0, 10.0], "PASS"),
    ("109_ACTION_POSITIVE", 109, "DRAWER_OPEN", [0.0, 1.45], "PASS"),
    ("109_OPEN_STATE_NEGATIVE", 109, "DRAWER_OPEN", [2.9, 4.35, 5.8], "FAIL"),
    ("89_EXTEND", 89, "EXTEND", [0.0, 1.78, 3.56, 5.34, 7.12], "FAIL"),
    ("51_EXTEND", 51, "EXTEND", [0.0, 2.5, 5.0, 7.5, 10.0], "FAIL"),
    ("1985_EXTEND", 1985, "EXTEND", [1.9, 2.525, 3.15, 3.775, 4.4], "FAIL"),
    ("1986_EXTEND", 1986, "EXTEND", [1.9, 2.525, 3.15, 3.775, 4.4], "FAIL"),
]
ACT = {"EXTEND": Action.EXTEND, "DRAWER_OPEN": Action.DRAWER_OPEN}


def imread(p):
    return cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)


def boxes(mid, t):
    return [a for a in ROI_ALL if a["media_id"] == mid and a["frame_timestamp"] == t]


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
    results = []
    for sid, mid, act_s, ts, gt in SLICES:
        fam = DF if act_s == "DRAWER_OPEN" else TF
        obj = "DRAWER" if act_s == "DRAWER_OPEN" else "TABLETOP"
        case = next(c for c in MAN["cases"] if c["media_id"] == mid)
        # 目标实例框（绑定；单框默认0）
        chosen = {}
        for t in ts:
            bs = [b for b in boxes(mid, t) if b["object_name"] in fam]
            i = binding.get((mid, t))
            if i is None and len(bs) == 1:
                i = 0
            chosen[t] = (bs[i]["bbox_pixel"] if i is not None and 0 <= i < len(bs) else None)
        # pixel 目标运动（补偿后框内差，排除其它运动类框；证据仅用）
        imgs = {}
        px = 0.0
        for t in ts:
            f = next(x for x in case["frames"] if x["t_s"] == t)
            imgs[t] = imread(f["local_path"])
        prev_t = None
        for t in ts:
            if chosen.get(t) is None:
                continue
            if prev_t is not None and prev_t in imgs and t in imgs:
                wb, _cam = compensate_pair(imgs[prev_t], imgs[t])
                x1, y1, x2, y2 = chosen[t]
                if x2 - x1 >= 8 and y2 - y1 >= 8:
                    ga = cv2.cvtColor(imgs[prev_t], cv2.COLOR_BGR2GRAY)[y1:y2, x1:x2].astype(np.float32)
                    gb = cv2.cvtColor(wb, cv2.COLOR_BGR2GRAY)[y1:y2, x1:x2].astype(np.float32)
                    px = max(px, float(np.abs(ga - gb).mean() / 40.0))
            prev_t = t
        # 几何证据
        ibox = {}
        for t in ts:
            ib = [b for b in boxes(mid, t) if b["object_name"] == "ISLAND_BODY"]
            ibox[t] = ib[0]["bbox_pixel"] if ib else None
        tls = [{"t_s": t, "bbox_pixel": list(chosen[t]),
                "island_pixel": list(ibox[t]) if ibox.get(t) else None}
               for t in sorted(chosen) if chosen.get(t) is not None]
        cam_unrel = mid in (1985, 1986)
        geo = build_geometry_direction_evidence(obj, "A", tls, camera_unreliable=cam_unrel)

        def sem(t):
            bb = next(x["bbox_pixel"] for x in tls if x["t_s"] == t)
            return FrameSemantics(t, [obj], [], [ROI(obj, *bb, source="L3_HUMAN_ROI")], dominant_visual=obj)
        vis = [x["t_s"] for x in tls]
        mm = MotionMetrics(camera_residual=0.0, roi_motion={obj: round(px, 4)})
        ev = TemporalEvidence(before=sem(vis[0]), middle=sem(vis[len(vis) // 2]), after=sem(vis[-1]),
                              motion=mm, requested_action=ACT[act_s], geometry_direction_evidence=geo)
        v = TemporalStateValidator(TargetObjectMotionRouter()).validate(ev)
        mv = str(v.verdict)
        results.append({
            "slice": sid, "media_id": mid, "requested": act_s, "frames_used": ts,
            "target_object": obj, "instance_id": "A",
            "bound_geometry": {"abs_area_seq": geo.raw_features.get("abs_seq"),
                               "rel_seq": geo.raw_features.get("rel_seq"),
                               "mode": geo.raw_features.get("mode")},
            "geometry_direction_evidence": {
                "direction_action": geo.direction_action, "state_progress": geo.state_progress,
                "geometry_change_present": geo.geometry_change_present,
                "relative_motion_present": geo.relative_motion_present,
                "confidence_class": geo.confidence_class, "reason_codes": geo.reason_codes,
                "visibility_progression": geo.visibility_progression},
            "pixel_target_motion": round(px, 4),
            "mandatory": dict(v.mandatory), "reason_codes": list(v.reason_codes),
            "machine_verdict": mv, "human_gt": gt,
            "match": (mv == ("Verdict.PASS" if gt == "PASS" else "Verdict.FAIL")),
            "false_pass": mv == "Verdict.PASS" and gt != "PASS",
            "false_fail": mv == "Verdict.FAIL" and gt == "PASS",
            "unsure": mv == "Verdict.UNSURE"})
        print(sid, "->", mv, "| GT:", gt, "| geo:", geo.direction_action, geo.state_progress,
              "| px:", round(px, 3), "| codes:", v.reason_codes)
    doc = {"experiment": "MMVV_A2.1", "approved": "2026-09-04 architect",
           "method": "L3 ROI + binding -> GeometryDirectionEvidence (island-rel preferred, abs fallback) -> validator geometry-first",
           "no_threshold_tuning": True, "results": results,
           "summary": {"match": sum(1 for r in results if r["match"]),
                       "false_pass": sum(1 for r in results if r["false_pass"]),
                       "false_fail": sum(1 for r in results if r["false_fail"]),
                       "unsure": sum(1 for r in results if r["unsure"])},
           "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (OUT / "TREECUT_MMVV_A21_RESULTS_V1.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("SUMMARY", doc["summary"])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
