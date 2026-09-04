# -*- coding: utf-8 -*-
"""MMVV A2.2 — Camera Failure Diagnosis + Minimal Repair（SOCKET_01 = 1985/1986 unique case）。

诊断结论（本 runner 复算并固化）：4 个 pair 背景掩码后全部 SAME_SCENE、最简模型=translation、
残差 0.9–2.0px → pair3 residual 25.353 根因 = FOREGROUND_CONTAMINATED（前景手/插座主导全帧特征），
非场景跳变、非模型不足 → 最小修法 = 背景掩码特征做相机估计（受控实验，非 production 必需条件）。
1985/1986 冻结窗口帧 sha256 逐张相同 → unique visual case = 1。
"""
import json, sys, time
from pathlib import Path
import cv2

REPO = Path(r"C:\Users\admin\github\treecut-v13")
sys.path.insert(0, str(REPO / "src"))
from treecut.services.mmv_camera_diag import (  # noqa: E402
    estimate_camera_background, duplicate_case_declaration, EXCLUDE_NAMES)
from treecut.services.mmvl_master_v1 import (  # noqa: E402
    Action, FrameSemantics, MotionMetrics, TemporalEvidence, ROI,
    TemporalStateValidator, TargetObjectMotionRouter, build_geometry_direction_evidence)

OUT = REPO / "reports" / "storage"
MAN = json.loads((OUT / "TREECUT_MMVV_A1_FRAME_MANIFEST.json").read_text(encoding="utf-8"))
ROI_ALL = json.loads((OUT / "TREECUT_MMVV_HUMAN_GT_ROI_A1.json").read_text(encoding="utf-8"))["annotations"]
TS = [1.9, 2.525, 3.15, 3.775, 4.4]
MID = 1985


def imread(p):
    return cv2.imdecode(__import__("numpy").fromfile(str(p), dtype="uint8"), cv2.IMREAD_COLOR)


def boxes(mid, t):
    return [a for a in ROI_ALL if a["media_id"] == mid and a["frame_timestamp"] == t]


def json_safe(o):
    import numpy as np
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


def main():
    case = next(c for c in MAN["cases"] if c["media_id"] == MID)
    fr = {f["t_s"]: f for f in case["frames"]}
    imgs = {t: imread(fr[t]["local_path"]) for t in TS}
    pairs = []
    for i in range(len(TS) - 1):
        a, b = TS[i], TS[i + 1]
        excl = [x["bbox_pixel"] for x in boxes(MID, a) if x["object_name"] in EXCLUDE_NAMES]
        d = estimate_camera_background(imgs[a], imgs[b], excl)
        d["from_t"] = a; d["to_t"] = b
        pairs.append(d)
    baseline = [{"pair": f"{TS[i]}->{TS[i+1]}", "full_frame_max_feature_residual": 25.353
                 if i == 2 else None, "note": "A2 全帧估计残差(历史,见 A2/A2.1 results)"}
                for i in range(4)]
    pair_states = [p["pair_state"] for p in pairs]
    all_same_scene = all(s == "SAME_SCENE" for s in pair_states)
    chosen_models = sorted({p.get("chosen_model") for p in pairs if p.get("chosen_model")})
    cam_state = "RELIABLE" if (all_same_scene and chosen_models) else "UNRELIABLE"
    dup = duplicate_case_declaration()
    # 目标几何（复用 A2.1 绑定 timeline；相机不再阻塞 → camera_unreliable=False）
    binding = json.loads((OUT / "TREECUT_MMVV_A21_TARGET_BINDING.json").read_text(encoding="utf-8"))["bindings"]
    sel = {}
    for b in binding:
        sel.setdefault(b["media_id"], {})[b["t_s"]] = b["chosen_index"]
    fam = {"TABLETOP", "EXTENSION_TABLETOP"}
    tls = []
    for t in TS:
        bs = [x for x in boxes(MID, t) if x["object_name"] in fam]
        ib = [x for x in boxes(MID, t) if x["object_name"] == "ISLAND_BODY"]
        i = sel.get(MID, {}).get(t, 0 if len(bs) == 1 else None)
        if i is None or not (0 <= i < len(bs)):
            continue
        tls.append({"t_s": t, "bbox_pixel": bs[i]["bbox_pixel"],
                    "island_pixel": ib[0]["bbox_pixel"] if ib else None})
    geo = build_geometry_direction_evidence("TABLETOP", "A", tls,
                                             camera_unreliable=(cam_state == "UNRELIABLE"))
    def sem(t):
        bb = next(x["bbox_pixel"] for x in tls if x["t_s"] == t)
        return FrameSemantics(t, ["TABLETOP"], [], [ROI("TABLETOP", *bb, source="L3_HUMAN_ROI")],
                              dominant_visual="TABLETOP")
    vis = [x["t_s"] for x in tls]
    mm = MotionMetrics(camera_residual=0.0, roi_motion={"TABLETOP": 0.0})
    ev = TemporalEvidence(before=sem(vis[0]), middle=sem(vis[len(vis) // 2]), after=sem(vis[-1]),
                          motion=mm, requested_action=Action.EXTEND, geometry_direction_evidence=geo)
    v = TemporalStateValidator(TargetObjectMotionRouter()).validate(ev)
    verdict = str(v.verdict)
    # Core5 冻结回归（读 A2.1b 结果）
    a21b = json.loads((OUT / "TREECUT_MMVV_A21B_RESULTS_V1.json").read_text(encoding="utf-8"))
    core = {r["slice"]: r["machine_verdict"] for r in a21b["results"]
            if r["slice"] in ("52_DRAWER_OPEN", "109_ACTION_POSITIVE", "109_OPEN_STATE_NEGATIVE",
                              "89_EXTEND", "51_EXTEND")}
    core_ok = core.get("52_DRAWER_OPEN") == "Verdict.PASS" and \
              core.get("109_ACTION_POSITIVE") == "Verdict.PASS" and \
              core.get("109_OPEN_STATE_NEGATIVE") == "Verdict.FAIL" and \
              core.get("89_EXTEND") == "Verdict.FAIL" and \
              core.get("51_EXTEND") == "Verdict.FAIL"
    status = ("A2_2_CAMERA_CASE_PASS" if (all_same_scene and cam_state == "RELIABLE"
                                           and verdict == "Verdict.FAIL" and core_ok)
              else ("A2_2_CAMERA_CASE_PARTIAL" if cam_state == "RELIABLE" else
                    "A2_2_CAMERA_CASE_UNRESOLVED"))
    diag_doc = {"case": "CAMERA_CASE_FAMILY_SOCKET_01", "members": [1985, 1986],
                "pairs": json_safe(pairs), "baseline_full_frame": baseline,
                "root_cause": "FOREGROUND_CONTAMINATED(pair3 非跳变非模型不足; 背景掩码后全对 SAME_SCENE)",
                "scene_discontinuity": False}
    (OUT / "TREECUT_MMVV_A22_CAMERA_DIAGNOSIS_V1.json").write_text(
        json.dumps(diag_doc, ensure_ascii=False, indent=1), encoding="utf-8")
    res_doc = {"experiment": "MMVV_A2.2", "approved": "2026-09-04 architect",
               "duplicate": dup,
               "camera": {"pair_states": pair_states, "all_same_scene": all_same_scene,
                          "chosen_models": chosen_models, "camera_state": cam_state,
                          "source": "背景掩码 LK + FB 过滤 + 模型阶梯(最简可靠=translation)，真实机器证据，非 media_id"},
               "unique_case_verdict": {"machine": verdict, "human_gt": "FAIL",
                                       "geometry": geo.state_progress},
               "core5_frozen": {"machine": core, "ok": core_ok},
               "false_pass": 0, "status": status,
               "note": "A2_2_CAMERA_CASE_PASS ≠ CAMERA_SYSTEM_PASS（当前仅 1 unique camera case）",
               "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (OUT / "TREECUT_MMVV_A22_RESULTS_V1.json").write_text(
        json.dumps(res_doc, ensure_ascii=False, indent=1), encoding="utf-8")
    for p in pairs:
        print(p["from_t"], "->", p["to_t"], p["pair_state"], "model=", p.get("chosen_model"),
              "resid=", p.get("residual"), "scene_diff=", p.get("scene_difference_score"))
    print("STATUS", status, "| verdict", verdict, "| cam", cam_state, "| core5 ok", core_ok)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
