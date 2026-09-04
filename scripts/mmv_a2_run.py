# -*- coding: utf-8 -*-
"""MMVV A2 — 人工 ROI 动作验证实验（7 slices；架构师批准 2026-09-04）。

边界(架构师 12 条)：
- 验证实验，不调参/不修算法；固定 200 L3_HUMAN_ROI / 32 帧 / 7 slices。
- 只用: human ROI → canonical compensate_pair → 目标运动(人工框排除掩码) → TemporalStateValidator → Direction。
- 禁止: Qwen/heuristic/自动检测/阈值调整/改 verdict/改 GT/Enforcement/PilotV3/Blind/Stage9。
- 机器结果与人工预期分开报告；失败照实报，不自动修。
输出: reports/storage/TREECUT_MMVV_A2_RESULTS_V1.json + docs/TREECUT_MMVV_A2_REPORT.md
"""
import json, sys
from pathlib import Path
import cv2
import numpy as np

REPO = Path(r"C:\Users\admin\github\treecut-v13")
sys.path.insert(0, str(REPO / "src"))
from treecut.services.mmvl_master_v1 import (  # noqa: E402
    ROI, Action, FrameSemantics, MotionMetrics, TemporalEvidence,
    TargetObjectMotionRouter, TemporalStateValidator, compensate_pair)

OUT = REPO / "reports" / "storage"
MAN = json.loads((OUT / "TREECUT_MMVV_A1_FRAME_MANIFEST.json").read_text(encoding="utf-8"))
ROI_ALL = json.loads((OUT / "TREECUT_MMVV_HUMAN_GT_ROI_A1.json").read_text(encoding="utf-8"))["annotations"]
DOCS = REPO / "docs"

DRAWER_FAM = {"DRAWER", "UPPER_THIN_DRAWER"}
TABLETOP_FAM = {"TABLETOP", "EXTENSION_TABLETOP"}
MOVING_CLASSES = {"HAND", "PERSON", "SOCKET_MODULE", "TRACK_SOCKET", "OTHER_MOVING_PART"}
# 人工标签 → 模块 canonical 词汇（runner 接线层；不改模块/阈值/判定）
CANON = {"EXTENSION_TABLETOP": "TABLETOP", "UPPER_THIN_DRAWER": "DRAWER"}

# 7 slices（架构师批准集）
SLICES = [
    {"id": "52_DRAWER_OPEN", "media": 52, "action": "DRAWER_OPEN",
     "frames_t": [7.5, 7.75, 8.0, 10.0], "target_fam": DRAWER_FAM,
     "human_gt": "DRAWER_OPEN (PASS)", "frames_note": "7.5=预备无抽屉; 7.75(AUX2)=首现外移; 8.0(AUX1)=明显拉出; 10.0=全开"},
    {"id": "109_ACTION_POSITIVE", "media": 109, "action": "DRAWER_OPEN",
     "frames_t": [0.0, 1.45], "target_fam": DRAWER_FAM,
     "human_gt": "DRAWER_OPEN (PASS)", "frames_note": "帧0 PARTIAL_OPEN→帧1 FULL_OPEN"},
    {"id": "109_OPEN_STATE_NEGATIVE", "media": 109, "action": "DRAWER_OPEN",
     "frames_t": [2.9, 4.35, 5.8], "target_fam": DRAWER_FAM,
     "human_gt": "NOT_OPEN_ACTION (FAIL DRAWER_OPEN)", "frames_note": "帧2-4 已打开静止讲解"},
    {"id": "89_EXTEND", "media": 89, "action": "EXTEND",
     "frames_t": [0.0, 1.78, 3.56, 5.34, 7.12], "target_fam": TABLETOP_FAM,
     "human_gt": "NOT_EXTEND (FAIL)", "frames_note": "人讲解；桌板静止"},
    {"id": "51_EXTEND", "media": 51, "action": "EXTEND",
     "frames_t": [0.0, 2.5, 5.0, 7.5, 10.0], "target_fam": TABLETOP_FAM,
     "human_gt": "NOT_EXTEND (FAIL)", "frames_note": "静态产品讲解"},
    {"id": "1985_EXTEND", "media": 1985, "action": "EXTEND",
     "frames_t": [1.9, 2.525, 3.15, 3.775, 4.4], "target_fam": TABLETOP_FAM,
     "human_gt": "NOT_EXTEND (FAIL)", "frames_note": "手/插座模块操作，桌板静止"},
    {"id": "1986_EXTEND", "media": 1986, "action": "EXTEND",
     "frames_t": [1.9, 2.525, 3.15, 3.775, 4.4], "target_fam": TABLETOP_FAM,
     "human_gt": "NOT_EXTEND (FAIL)", "frames_note": "手操作插座，桌板静止"},
]
ACT = {"EXTEND": Action.EXTEND, "DRAWER_OPEN": Action.DRAWER_OPEN}

def imread(p):
    return cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)

def norm_diff(a, b):
    return float(np.abs(a.astype(np.float32) - b.astype(np.float32)).mean() / 40.0)

def boxes_at(media, t):
    return [a for a in ROI_ALL if a["media_id"] == media and a["frame_timestamp"] == t]

def measure_pair(fr_a, fr_b, boxes_a, boxes_b):
    """compensate_pair → 逐对象掩码运动（目标框内剔除其它运动类）。返回 dict."""
    wb, cam = compensate_pair(fr_a, fr_b)
    res = {"camera_model": cam.model, "translation_px": round(cam.translation_px, 3),
           "inlier_ratio": round(cam.inlier_ratio, 3), "feature_residual": round(cam.residual, 3),
           "reliable": bool(cam.reliable)}
    motion = {}
    ga = cv2.cvtColor(fr_a, cv2.COLOR_BGR2GRAY)
    gb = cv2.cvtColor(wb, cv2.COLOR_BGR2GRAY)
    # 用帧a的框做区域（目标随时间移动时两帧都有框则取并集区域，剔除另帧非同类）
    used = set()
    allb = boxes_a + boxes_b
    for b in allb:
        name = b["object_name"]
        if name in used:
            continue
        used.add(name)
        x1, y1, x2, y2 = b["bbox_pixel"]
        w = x2 - x1; h = y2 - y1
        if w < 8 or h < 8:
            continue
        crop_a = ga[y1:y2, x1:x2].astype(np.float32)
        crop_b = gb[y1:y2, x1:x2].astype(np.float32)
        mask = np.ones(crop_a.shape, dtype=bool)
        for o in allb:
            if o["object_name"] == name:
                continue
            ox1, oy1, ox2, oy2 = o["bbox_pixel"]
            ix1, iy1 = max(x1, ox1), max(y1, oy1)
            ix2, iy2 = min(x2, ox2), min(y2, oy2)
            if ix2 > ix1 and iy2 > iy1 and o["object_name"] in MOVING_CLASSES:
                mask[iy1 - y1:iy2 - y1, ix1 - x1:ix2 - x1] = False
        m = norm_diff(crop_a[mask], crop_b[mask]) if mask.sum() else 0.0
        motion[CANON.get(name, name)] = round(max(motion.get(CANON.get(name, name), 0.0), m), 4)
    return res, motion

def geometry(obj_name, boxes_by_t):
    """人工框几何轨迹（每帧 center/edges）。"""
    traj = []
    for t in sorted(boxes_by_t):
        hits = [b for b in boxes_by_t[t] if b["object_name"] == obj_name]
        if not hits:
            continue
        b = hits[0]["bbox_pixel"]
        traj.append({"t_s": t, "center_x": (b[0] + b[2]) / 2.0, "center_y": (b[1] + b[3]) / 2.0,
                     "left": b[0], "right": b[2], "top": b[1], "bottom": b[3],
                     "w": b[2] - b[0], "h": b[3] - b[1]})
    return traj

def main():
    results = []
    for sl in SLICES:
        mid = sl["media"]
        action = ACT[sl["action"]]
        case = next(c for c in MAN["cases"] if c["media_id"] == mid)
        frames = []
        for t in sl["frames_t"]:
            f = next(x for x in case["frames"] if x["t_s"] == t)
            frames.append({"t_s": t, "path": f["local_path"], "frame": f["frame"]})
        imgs = {f["t_s"]: imread(f["path"]) for f in frames}
        boxes_by_t = {f["t_s"]: boxes_at(mid, f["t_s"]) for f in frames}
        pair_ev = []
        motion_agg = {}
        cam_agg = {"max_translation_px": 0.0, "max_feature_residual": 0.0, "models": [], "reliable_all": True}
        for i in range(len(frames) - 1):
            ta, tb = frames[i]["t_s"], frames[i + 1]["t_s"]
            if ta not in imgs or tb not in imgs:
                continue
            cam, mot = measure_pair(imgs[ta], imgs[tb], boxes_by_t[ta], boxes_by_t[tb])
            pair_ev.append({"from_t": ta, "to_t": tb, **cam, "motion": mot})
            for k, v in mot.items():
                motion_agg[k] = round(max(motion_agg.get(k, 0.0), v), 4)
            cam_agg["max_translation_px"] = max(cam_agg["max_translation_px"], cam["translation_px"])
            cam_agg["max_feature_residual"] = max(cam_agg["max_feature_residual"], cam["feature_residual"])
            cam_agg["models"].append(cam["camera_model"])
            cam_agg["reliable_all"] = cam_agg["reliable_all"] and cam["reliable"]
        # 目标几何轨迹（human 框，机器可见输入）
        target_name = next((n for n in sl["target_fam"]
                            if any(b["object_name"] == n for t in boxes_by_t for b in boxes_by_t[t])), None)
        target_name_canon = CANON.get(target_name, target_name) if target_name else None
        geo = geometry(target_name, boxes_by_t) if target_name else []
        # 组装 TemporalEvidence：before/middle/after（机器可见帧）
        vis_frames = [f for f in frames if any(b["object_name"] in sl["target_fam"] for b in boxes_by_t[f["t_s"]])]
        if not vis_frames:
            vis_frames = frames
        def sem(t):
            bs = boxes_by_t.get(t, [])
            names = [CANON.get(b["object_name"], b["object_name"]) for b in bs]
            return FrameSemantics(timestamp_s=t,
                                  objects=names,
                                  states=[],
                                  rois=[ROI(CANON.get(b["object_name"], b["object_name"]), *b["bbox_pixel"],
                                            source="L3_HUMAN_ROI") for b in bs],
                                  dominant_visual=target_name_canon)
        before = sem(vis_frames[0]["t_s"])
        middle = sem(vis_frames[len(vis_frames) // 2]["t_s"])
        after = sem(vis_frames[-1]["t_s"])
        metrics = MotionMetrics(global_motion_px=round(cam_agg["max_translation_px"], 3),
                                camera_residual=round(cam_agg["max_feature_residual"], 3),
                                roi_motion={k: round(v, 3) for k, v in motion_agg.items()})
        ev = TemporalEvidence(before=before, middle=middle, after=after, motion=metrics,
                              requested_action=action, model_action=Action.UNKNOWN)
        tv = TemporalStateValidator(TargetObjectMotionRouter())
        vres = tv.validate(ev)
        verdict = str(vres.verdict)
        results.append({
            "slice": sl["id"], "media_id": mid, "requested": sl["action"],
            "frames_used": [f["frame"] for f in frames],
            "frame_timestamps": [f["t_s"] for f in frames],
            "target_object": target_name,
            "target_visible_frames": len(vis_frames),
            "camera": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in cam_agg.items()},
            "pair_evidence": pair_ev,
            "roi_motion": {k: round(v, 3) for k, v in motion_agg.items()},
            "target_geometry_trajectory": geo,
            "state_transition": {},  # 机器无状态序列注入 → 由 motion/geometry 隐式
            "direction_evidence": {"note": "方向证据=目标几何位移(逐帧 center/edges), 机器未注入人工状态"},
            "mandatory": dict(vres.mandatory),
            "reason_codes": list(vres.reason_codes),
            "machine_verdict": verdict,
            "human_gt": sl["human_gt"],
            "frames_note": sl["frames_note"],
        })
    # 汇总一致性
    ok_map = {"52_DRAWER_OPEN": "PASS", "109_ACTION_POSITIVE": "PASS",
              "109_OPEN_STATE_NEGATIVE": "FAIL", "89_EXTEND": "FAIL", "51_EXTEND": "FAIL",
              "1985_EXTEND": "FAIL", "1986_EXTEND": "FAIL"}
    for r in results:
        exp = ok_map[r["slice"]]
        mv = r["machine_verdict"]
        r["expected_human"] = exp
        r["machine_matches_human"] = (mv == ("Verdict.PASS" if exp == "PASS" else "Verdict.FAIL"))
        r["false_pass"] = mv == "Verdict.PASS" and exp != "PASS"
        r["false_fail"] = mv in ("Verdict.FAIL",) and exp == "PASS"
        r["unsure"] = mv == "Verdict.UNSURE"
    doc = {"experiment": "MMVV_A2", "approved": "2026-09-04 architect",
           "inputs": {"human_roi": 200, "frames": 32, "slices": 7},
           "method": "L3_HUMAN_ROI → compensate_pair → per-object masked motion → TemporalStateValidator",
           "no_threshold_tuning": True, "machine_vs_human_separate": True,
           "results": results,
           "summary": {"false_pass": sum(1 for r in results if r["false_pass"]),
                       "false_fail": sum(1 for r in results if r["false_fail"]),
                       "unsure": sum(1 for r in results if r["unsure"]),
                       "match": sum(1 for r in results if r["machine_matches_human"])}}
    (OUT / "TREECUT_MMVV_A2_RESULTS_V1.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in results:
        print(r["slice"], "->", r["machine_verdict"], "| GT:", r["expected_human"],
              "| motion:", r["roi_motion"], "| cam:", r["camera"]["max_feature_residual"], "| codes:", r["reason_codes"])
    print("SUMMARY", doc["summary"])

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
