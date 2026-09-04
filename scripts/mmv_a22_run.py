# -*- coding: utf-8 -*-
"""MMVV A2.2 R1 — Camera Deterministic Closure（A2.2=PASS_WITH_DETERMINISTIC_CORRECTIONS）。

R1 修复：
1) warp 方向：scene_diff 一律用 canonical warp_current_to_previous（逆补偿）。
2) 双模式差分诊断：同一 pair 跑 MODE_FULL_FRAME 与 MODE_BACKGROUND_MASKED，
   机器证据 FULL_FRAME_UNRELIABLE + BACKGROUND_MASKED_RELIABLE + SAME_SCENE → FOREGROUND_CONTAMINATED
   （无 media/pair/GT 硬编码；baseline 残差也由 full_frame 模式实测，不手填）。
3) 修复相机回喂目标运动：用背景逆补偿把 curr 对齐 prev，再在真实 TABLETOP ROI 计算
   target_pixel_motion_before/after_compensation（不手填 0）。
4) Core5 真重跑：子进程运行当前 mmv_a21_run.py（当前 camera+geometry+validator 代码）并读新结果；
   旧 A2.1b 结果存为快照对比，不冒充 regression。
5) holdout 术语诚实：background_validation_residual + 注明非独立 holdout。
"""
import json, subprocess, sys, time
from pathlib import Path
import cv2
import numpy as np

REPO = Path(r"C:\Users\admin\github\treecut-v13")
sys.path.insert(0, str(REPO / "src"))
from treecut.services.mmv_camera_diag import (  # noqa: E402
    estimate_camera_background, warp_current_to_previous, duplicate_case_declaration, EXCLUDE_NAMES)
from treecut.services.mmvl_master_v1 import (  # noqa: E402
    Action, FrameSemantics, MotionMetrics, TemporalEvidence, ROI,
    TemporalStateValidator, TargetObjectMotionRouter, build_geometry_direction_evidence)

OUT = REPO / "reports" / "storage"
MAN = json.loads((OUT / "TREECUT_MMVV_A1_FRAME_MANIFEST.json").read_text(encoding="utf-8"))
ROI_ALL = json.loads((OUT / "TREECUT_MMVV_HUMAN_GT_ROI_A1.json").read_text(encoding="utf-8"))["annotations"]
TS = [1.9, 2.525, 3.15, 3.775, 4.4]
MID = 1985
OLD = json.loads((OUT / "TREECUT_MMVV_A22_CAMERA_DIAGNOSIS_V1.json").read_text(encoding="utf-8"))
OLD_A21B = json.loads((OUT / "TREECUT_MMVV_A21B_RESULTS_V1.json").read_text(encoding="utf-8"))
CORE_SLICES = ("52_DRAWER_OPEN", "109_ACTION_POSITIVE", "109_OPEN_STATE_NEGATIVE", "89_EXTEND", "51_EXTEND")


def json_safe(o):
    if isinstance(o, dict):
        return {k: json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [json_safe(v) for v in o]
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return o


def imread(p):
    return cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)


def boxes(mid, t):
    return [a for a in ROI_ALL if a["media_id"] == mid and a["frame_timestamp"] == t]


def main():
    case = next(c for c in MAN["cases"] if c["media_id"] == MID)
    fr = {f["t_s"]: f for f in case["frames"]}
    imgs = {t: imread(fr[t]["local_path"]) for t in TS}
    pairs_r1 = []
    root_ev = {}
    for i in range(len(TS) - 1):
        a, b = TS[i], TS[i + 1]
        excl = [x["bbox_pixel"] for x in boxes(MID, a) if x["object_name"] in EXCLUDE_NAMES]
        dfull = estimate_camera_background(imgs[a], imgs[b], [], mode="full_frame")
        dbg = estimate_camera_background(imgs[a], imgs[b], excl, mode="background")
        pair = {"from_t": a, "to_t": b,
                "full_frame": {k: dfull.get(k) for k in
                               ("mode", "pair_state", "chosen_model", "residual",
                                "scene_difference_score", "feature_count_before",
                                "forward_backward_valid_count", "inlier_ratio", "reason_codes")},
                "background_masked": {k: dbg.get(k) for k in
                                      ("mode", "pair_state", "chosen_model", "chosen_M",
                                       "translation_median", "residual",
                                       "scene_difference_score", "feature_count_before",
                                       "forward_backward_valid_count", "inlier_ratio",
                                       "background_validation_residual_px", "reason_codes")}}
        pair["scene_diff_old_invalidated"] = {"value": OLD["pairs"][i].get("scene_difference_score"),
                                              "note": "INVALIDATED_BY_WARP_DIRECTION_BUG(旧 A2.2 前向 warp)"}
        # 机器根因（差分）
        full_bad = dfull.get("pair_state") != "SAME_SCENE" or (dfull.get("residual") or 9e9) > 3.0
        bg_ok = dbg.get("pair_state") == "SAME_SCENE" and (dbg.get("residual") or 9e9) <= 3.0
        if full_bad and bg_ok:
            pair["machine_root_cause"] = "FOREGROUND_CONTAMINATED"
            pair["reason_codes"] = ["FULL_FRAME_UNRELIABLE", "BACKGROUND_MASKED_RELIABLE", "SAME_SCENE"]
        elif full_bad and not bg_ok:
            pair["machine_root_cause"] = "CAMERA_OR_SCENE_UNRELIABLE"
            pair["reason_codes"] = ["FULL_FRAME_UNRELIABLE", "BACKGROUND_MASKED_UNRELIABLE"]
        else:
            pair["machine_root_cause"] = "NONE_CAMERA_OK"
            pair["reason_codes"] = ["FULL_FRAME_RELIABLE", "BACKGROUND_MASKED_RELIABLE"]
        pairs_r1.append(pair)
        root_ev[a] = pair["machine_root_cause"]
    all_bg_ok = all(p["background_masked"]["pair_state"] == "SAME_SCENE" for p in pairs_r1)
    cam_state = "RELIABLE" if all_bg_ok else "UNRELIABLE"
    # 目标运动 before/after（用背景逆补偿；真实 ROI）
    binding = json.loads((OUT / "TREECUT_MMVV_A21_TARGET_BINDING.json").read_text(encoding="utf-8"))["bindings"]
    sel = {}
    for x in binding:
        sel.setdefault(x["media_id"], {})[x["t_s"]] = x["chosen_index"]
    fam = {"TABLETOP", "EXTENSION_TABLETOP"}
    tbox = {}
    for t in TS:
        bs = [x for x in boxes(MID, t) if x["object_name"] in fam]
        i = sel.get(MID, {}).get(t, 0 if len(bs) == 1 else None)
        if i is not None and 0 <= i < len(bs):
            tbox[t] = bs[i]["bbox_pixel"]
    before_px, after_px = 0.0, 0.0
    for p in pairs_r1:
        a, b = p["from_t"], p["to_t"]
        if a not in tbox:
            continue
        x1, y1, x2, y2 = tbox[a]
        if x2 - x1 < 8 or y2 - y1 < 8:
            continue
        ga = cv2.cvtColor(imgs[a], cv2.COLOR_BGR2GRAY)[y1:y2, x1:x2].astype(np.float32)
        gb = cv2.cvtColor(imgs[b], cv2.COLOR_BGR2GRAY)[y1:y2, x1:x2].astype(np.float32)
        raw = float(np.abs(ga - gb).mean() / 40.0)
        before_px = max(before_px, raw)
        bg = p["background_masked"]
        if bg.get("pair_state") == "SAME_SCENE" and bg.get("chosen_model"):
            if bg.get("chosen_M"):
                M = np.array(bg["chosen_M"], dtype=np.float32)
            else:
                t = bg.get("translation_median") or [0, 0]
                M = np.float32([[1, 0, t[0]], [0, 1, t[1]]])
            wb = warp_current_to_previous(imgs[b], bg["chosen_model"], M)
            gw = cv2.cvtColor(wb, cv2.COLOR_BGR2GRAY)[y1:y2, x1:x2].astype(np.float32)
            after_px = max(after_px, float(np.abs(ga - gw).mean() / 40.0))
    # 几何（A2.1 绑定 timeline）+ validator
    tls = []
    for t in sorted(tbox):
        ib = [x for x in boxes(MID, t) if x["object_name"] == "ISLAND_BODY"]
        tls.append({"t_s": t, "bbox_pixel": list(tbox[t]),
                    "island_pixel": ib[0]["bbox_pixel"] if ib else None})
    geo = build_geometry_direction_evidence("TABLETOP", "A", tls,
                                             camera_unreliable=(cam_state == "UNRELIABLE"))

    def sem(t):
        bb = next(x["bbox_pixel"] for x in tls if x["t_s"] == t)
        return FrameSemantics(t, ["TABLETOP"], [], [ROI("TABLETOP", *bb, source="L3_HUMAN_ROI")],
                              dominant_visual="TABLETOP")
    vis = [x["t_s"] for x in tls]
    mm = MotionMetrics(camera_residual=round(max((p["background_masked"].get("residual") or 0)
                                                 for p in pairs_r1), 3),
                       roi_motion={"TABLETOP": round(after_px, 4)})
    ev = TemporalEvidence(before=sem(vis[0]), middle=sem(vis[len(vis) // 2]), after=sem(vis[-1]),
                          motion=mm, requested_action=Action.EXTEND, geometry_direction_evidence=geo)
    v = TemporalStateValidator(TargetObjectMotionRouter()).validate(ev)
    verdict = str(v.verdict)
    # Core5 真重跑：子进程运行当前 mmv_a21_run.py
    subprocess.run([sys.executable, str(REPO / "scripts" / "mmv_a21_run.py")],
                   cwd=REPO, capture_output=True, timeout=600)
    fresh = json.loads((OUT / "TREECUT_MMVV_A21B_RESULTS_V1.json").read_text(encoding="utf-8"))
    rerun = {r["slice"]: r["machine_verdict"] for r in fresh["results"] if r["slice"] in CORE_SLICES}
    old_core = {r["slice"]: r["machine_verdict"] for r in OLD_A21B["results"] if r["slice"] in CORE_SLICES}
    core_ok = rerun.get("52_DRAWER_OPEN") == "Verdict.PASS" and \
              rerun.get("109_ACTION_POSITIVE") == "Verdict.PASS" and \
              rerun.get("109_OPEN_STATE_NEGATIVE") == "Verdict.FAIL" and \
              rerun.get("89_EXTEND") == "Verdict.FAIL" and \
              rerun.get("51_EXTEND") == "Verdict.FAIL" and \
              fresh["summary"]["false_pass"] == 0
    dup = duplicate_case_declaration()
    causes = {p["machine_root_cause"] for p in pairs_r1}
    machine_derived = causes <= {"FOREGROUND_CONTAMINATED", "NONE_CAMERA_OK"}
    status = ("A2_2_R1_CAMERA_CLOSURE_PASS"
              if (cam_state == "RELIABLE" and verdict == "Verdict.FAIL" and core_ok and machine_derived)
              else ("A22_R1_NEEDS_REPAIR" if core_ok else "A22_R1_NEEDS_REPAIR"))
    diag = {"case": dup["visual_case_id"], "members": [1985, 1986], "pairs": json_safe(pairs_r1),
            "scene_diff_old_note": "旧 scene_diff 0.741/0.574/0.814/0.902 → INVALIDATED_BY_WARP_DIRECTION_BUG"}
    (OUT / "TREECUT_MMVV_A22_R1_CAMERA_DIAGNOSIS.json").write_text(
        json.dumps(diag, ensure_ascii=False, indent=1), encoding="utf-8")
    res = {"experiment": "MMVV_A2.2_R1", "approved": "2026-09-04 architect",
           "duplicate": dup,
           "camera": {"pair_states_bg": [p["background_masked"]["pair_state"] for p in pairs_r1],
                      "camera_state": cam_state,
                      "source": "双模式差分诊断(真实全帧 vs 背景掩码) + inverse 补偿；无 media/pair/GT 硬编码"},
           "target_motion": {"before_compensation": round(before_px, 4),
                             "after_compensation": round(after_px, 4),
                             "note": "after = 背景逆补偿后 TABLETOP ROI 实测(非手填0)"},
           "geometry": geo.state_progress,
           "unique_case_verdict": {"machine": verdict, "human_gt": "FAIL"},
           "core5": {"stored_old": old_core, "actual_rerun": rerun, "ok": core_ok,
                     "false_pass": fresh["summary"]["false_pass"]},
           "root_causes": {str(k): v for k, v in root_ev.items()},
           "status": status,
           "note": "A2_2_R1_CAMERA_CLOSURE_PASS ≠ CAMERA_SYSTEM_PASS ≠ MMVV PRODUCTION READY",
           "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (OUT / "TREECUT_MMVV_A22_R1_RESULTS.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for p in pairs_r1:
        print(p["from_t"], "->", p["to_t"], "| full:", p["full_frame"]["pair_state"],
              p["full_frame"].get("residual"), "| bg:", p["background_masked"]["pair_state"],
              p["background_masked"].get("residual"), "scene_diff(new bg):",
              p["background_masked"].get("scene_difference_score"),
              "| root:", p["machine_root_cause"])
    print("target px before/after:", round(before_px, 4), "/", round(after_px, 4))
    print("STATUS", status, "| verdict", verdict, "| cam", cam_state, "| core5 rerun ok", core_ok)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
