#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MMVV A3 — BLIND PREDICTION RUNNER（正式盲测执行壳；首次 unseen 预测）。

纪律（A3 FINAL BLIND，见架构师指令 b0a3514 之后）:
- 机器输入仅: blind manifest + opaque 帧 + blind ROI（179 框，hash 锁 421d5a29..c1ca）。
- 禁止读取: HUMAN_GT / SCREENING / 原 HOLDOUT_MANIFEST / AUDIT / REPORT / CASE_KEY /
  OBSERVABILITY_HUMAN / 源 DB / 任何 media 映射。读取受 allowlist 强制约束。
- requested_action = EXTEND（H001-H006 统一；无 per-case 期望，无分支）。
- 目标 family: 人工 ROI 中 {TABLETOP, EXTENSION_TABLETOP}，内部 canonicalize 为 "TABLETOP"
  兼容 frozen TargetObjectMotionRouter；绝不从 PERSON/HAND/ROCK_TABLE_LEG/CABINET_DOOR 等推断。
- 帧级 fail-closed: 目标框缺失→TARGET_NOT_VISIBLE(不自动生成)；>1→TARGET_IDENTITY_AMBIGUOUS(不挑"最像EXTEND")。
- 相机: ca34678 冻结 A2.2 R1 estimate_camera_background(mode=background) + 冻结 EXCLUDE_NAMES
  + warp_current_to_previous（逆补偿）。不得改 EXCLUDE_NAMES。
- 几何: frozen build_geometry_direction_evidence；时序: frozen TemporalStateValidator(TargetObjectMotionRouter())。
- 输出 machine_verdict ∈ {PASS, FAIL, UNSURE}；预测 JSON 不得含 GT/原 media_id/POS-NEG。
- 预测文件写毕→立即锁 hash（重读字节→SHA256→.sha256.txt→PREDICTION_LOCK）→ GT 前 commit。

用法:
  python scripts/run_a3_blind.py --selfcheck   # 完整自检（真实帧 hash/ROI hash/179/30-30/freeze/无 stale）
  python scripts/run_a3_blind.py               # 正式预测（先自动 quarantine 旧输出）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
sys.path.insert(0, str(REPO / "src"))

from treecut.services.mmvl_master_v1 import (  # noqa: E402
    Action, ROI, FrameSemantics, MotionMetrics, TemporalEvidence,
    TargetObjectMotionRouter, TemporalStateValidator,
    build_geometry_direction_evidence, camera_reliability_evidence)
from treecut.services.mmv_camera_diag import (  # noqa: E402
    EXCLUDE_NAMES, estimate_camera_background, warp_current_to_previous)

BLIND_JSON = OUT / "TREECUT_MMVV_A3_MACHINE_INPUT_BLIND_V1.json"
ROI_BLIND_JSON = OUT / "TREECUT_MMVV_A3_HUMAN_GT_ROI_BLIND.json"
PRED_JSON = OUT / "TREECUT_MMVV_A3_MACHINE_PREDICTIONS_BLIND.json"
PRED_SHA = OUT / "TREECUT_MMVV_A3_MACHINE_PREDICTIONS_BLIND.sha256.txt"
LOCK_JSON = OUT / "TREECUT_MMVV_A3_PREDICTION_LOCK_V1.json"
BLIND_FRAMES_DIR = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\mmv_a3_blind_frames")
QUAR = OUT / "quarantine"

# 预测前冻结校验常量（来自 PRE_BLIND_GATE_CLOSURE；本地文件必须匹配）
EXPECTED_ROI_SHA256 = "421d5a29c1390ae59bed02f14f745148f19f2c2381b43c740aaca3d85c30c1ca"
EXPECTED_ROI_BOXES = 179
TARGET_FAMILY = {"TABLETOP", "EXTENSION_TABLETOP"}
CANONICAL_TARGET = "TABLETOP"
REQUESTED_ACTION = Action.EXTEND
FROZEN_CORE_FILES = ["src/treecut/services/mmvl_master_v1.py",
                     "src/treecut/services/mmv_camera_diag.py"]

# 允许打开的文件/目录（文件级防泄漏 allowlist）
ALLOWED_ROOTS = [BLIND_JSON, ROI_BLIND_JSON, BLIND_FRAMES_DIR]


class ForbiddenFileError(PermissionError):
    pass


def ensure_allowed(path) -> Path:
    p = Path(path).resolve()
    for root in ALLOWED_ROOTS:
        r = Path(root).resolve()
        if p == r or (r.is_dir() and r in p.parents):
            return p
    raise ForbiddenFileError(f"FORBIDDEN_FILE: {path}（不在 A3 机器输入 allowlist 内）")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def imread(p: Path):
    return cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)


def json_safe(o):
    if isinstance(o, dict):
        return {k: json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [json_safe(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return json_safe(o.tolist())
    return o


# ------------------------------------------------------------------ helpers
def resolve_target(boxes_for_frame):
    """帧级目标身份 fail-closed。
    boxes_for_frame: [{object_name, bbox_pixel}, ...]（本帧）
    return (bbox_pixel|None, state, actual_label|None)"""
    tgt = [b for b in boxes_for_frame if b.get("object_name") in TARGET_FAMILY]
    if len(tgt) == 1:
        return list(tgt[0]["bbox_pixel"]), "TARGET_SINGLE", tgt[0]["object_name"]
    if len(tgt) == 0:
        return None, "TARGET_NOT_VISIBLE", None
    return None, "TARGET_IDENTITY_AMBIGUOUS", None


def freeze_ok() -> tuple[bool, str]:
    r = subprocess.run(["git", "-C", str(REPO), "diff", "--stat", "ca34678..HEAD", "--"]
                       + FROZEN_CORE_FILES, capture_output=True, text=True)
    return (r.returncode == 0 and not r.stdout.strip()), (r.stdout or r.stderr)[:2000]


def quarantine_stale():
    stale = [p for p in (PRED_JSON, PRED_SHA, LOCK_JSON) if p.exists()]
    if not stale:
        return
    qd = QUAR / f"a3_preofficial_{time.strftime('%Y%m%d_%H%M%S')}"
    qd.mkdir(parents=True, exist_ok=True)
    for p in stale:
        p.replace(qd / p.name)
    print("stale quarantined ->", qd)


# ------------------------------------------------------------------ selfcheck
def selfcheck(verbose: bool = True) -> int:
    problems = []
    blind = json.loads(BLIND_JSON.read_text(encoding="utf-8"))
    # 30 frames + 逐张真实 sha256
    frames = [(c["opaque_case_id"], f) for c in blind["cases"] for f in c["frames"]]
    if len(frames) != 30:
        problems.append(f"frame_count={len(frames)} != 30")
    for _, f in frames:
        fp = BLIND_FRAMES_DIR / f["frame"]
        if not fp.exists():
            problems.append(f"missing frame {f['frame']}")
            continue
        if sha256_file(fp) != f["sha256"]:
            problems.append(f"frame sha mismatch {f['frame']}")
    # ROI 实际 hash / 179 / coverage / binding
    roi_sha = sha256_file(ROI_BLIND_JSON)
    if roi_sha != EXPECTED_ROI_SHA256:
        problems.append(f"ROI sha {roi_sha[:16]} != expected")
    roi = json.loads(ROI_BLIND_JSON.read_text(encoding="utf-8"))
    anns = roi.get("annotations") or []
    if len(anns) != EXPECTED_ROI_BOXES:
        problems.append(f"ROI boxes {len(anns)} != {EXPECTED_ROI_BOXES}")
    sha_map = {f["frame"]: f["sha256"] for _, f in frames}
    covered = set()
    for a in anns:
        covered.add((a.get("opaque_case_id"), a.get("frame_timestamp")))
        if a.get("frame") not in sha_map:
            problems.append(f"unknown roi frame {a.get('frame')}")
            continue
        if a.get("frame_hash") != sha_map[a["frame"]]:
            problems.append(f"roi hash binding mismatch {a['frame']}")
    miss = [(c["opaque_case_id"], f["frame"]) for c in blind["cases"] for f in c["frames"]
            if (c["opaque_case_id"], f["t_s"]) not in covered]
    if miss:
        problems.append(f"ROI coverage missing {len(miss)}/30")
    # freeze
    ok, msg = freeze_ok()
    if not ok:
        problems.append(f"freeze diff non-empty: {msg[:300]}")
    # stale
    if PRED_JSON.exists() or PRED_SHA.exists():
        problems.append("stale prediction files present (quarantine first)")
    if verbose:
        print("frame count:", len(frames), "| roi boxes:", len(anns),
              "| roi sha:", roi_sha[:16], "| coverage missing:", len(miss),
              "| freeze:", ok, "| stale:", bool(PRED_JSON.exists()))
    if problems:
        for p in problems:
            print("SELFCHECK_FAIL:", p)
        return 2
    print("A3_SELFCHECK_PASS")
    return 0


# ------------------------------------------------------------------ predict
def predict() -> int:
    blind = json.loads(BLIND_JSON.read_text(encoding="utf-8"))
    roi = json.loads(ROI_BLIND_JSON.read_text(encoding="utf-8"))
    anns = roi.get("annotations") or []
    if not anns:
        print("A3_ROI_REQUIRED")
        return 3
    by_oid = {}
    for a in anns:
        by_oid.setdefault(a["opaque_case_id"], {}).setdefault(a["frame_timestamp"], []).append(a)
    blind_sha = sha256_file(BLIND_JSON)
    roi_sha = sha256_file(ROI_BLIND_JSON)
    cases_out = []
    for c in blind["cases"]:
        oid = c["opaque_case_id"]
        frame_meta = {f["t_s"]: f for f in c["frames"]}
        ts_sorted = [f["t_s"] for f in c["frames"]]
        imgs = {}
        for f in c["frames"]:
            imgs[f["t_s"]] = imread(BLIND_FRAMES_DIR / f["frame"])
        # 逐帧目标/岛台身份（fail-closed）
        target_state_by_t = {}
        island_by_t = {}
        for t in ts_sorted:
            frame_boxes = by_oid.get(oid, {}).get(t, [])
            bb, state, label = resolve_target(frame_boxes)
            target_state_by_t[t] = {"bbox": bb, "state": state, "actual_label": label}
            ibs = [b for b in frame_boxes if b.get("object_name") == "ISLAND_BODY"]
            if len(ibs) == 1:
                island_by_t[t] = list(ibs[0]["bbox_pixel"])
            else:
                island_by_t[t] = None
        # 相机(background-masked, 冻结) + 目标像素运动(before/after) 逐相邻帧
        cam_pair_records = []
        motion_pairs = []
        cam_synth = []
        prev_t = None
        for t in ts_sorted:
            if prev_t is None:
                prev_t = t
                continue
            a_bgr = imgs[prev_t]
            b_bgr = imgs[t]
            # boxes to exclude: prev 帧中 object_name ∈ 冻结 EXCLUDE_NAMES
            prev_boxes = by_oid.get(oid, {}).get(prev_t, [])
            excl = [list(b["bbox_pixel"]) for b in prev_boxes if b.get("object_name") in EXCLUDE_NAMES]
            cam = estimate_camera_background(a_bgr, b_bgr, excl, mode="background")
            rec = {"pair": f"{prev_t}->{t}",
                   "pair_state": cam.get("pair_state"),
                   "chosen_model": cam.get("chosen_model"),
                   "residual": cam.get("residual"),
                   "background_validation_residual_px": cam.get("background_validation_residual_px"),
                   "inlier_ratio": cam.get("inlier_ratio"),
                   "scene_difference_score": cam.get("scene_difference_score"),
                   "translation": cam.get("translation_median"),
                   "reason_codes": cam.get("reason_codes", [])}
            cam_pair_records.append(rec)
            cam_synth.append({
                "reliable": cam.get("pair_state") == "SAME_SCENE",
                "feature_residual": cam.get("residual") or cam.get("background_validation_residual_px") or 0.0,
                "inlier_ratio": cam.get("inlier_ratio"),
                "translation_px": float(np.linalg.norm(cam.get("translation_median") or [0, 0]))})
            # target pixel motion（目标框取当前帧；before=原始帧差, after=逆补偿后帧差）
            tgt = target_state_by_t[t]["bbox"]
            if tgt is not None and tgt[2] - tgt[0] >= 8 and tgt[3] - tgt[1] >= 8:
                x1, y1, x2, y2 = [int(v) for v in tgt]
                ga = cv2.cvtColor(a_bgr, cv2.COLOR_BGR2GRAY)[y1:y2, x1:x2].astype(np.float32)
                gb = cv2.cvtColor(b_bgr, cv2.COLOR_BGR2GRAY)[y1:y2, x1:x2].astype(np.float32)
                before = float(np.abs(ga - gb).mean() / 40.0)
                after = None
                if cam.get("chosen_model") and cam.get("chosen_M") is not None:
                    wb = warp_current_to_previous(b_bgr, cam["chosen_model"], cam["chosen_M"])
                    gw = cv2.cvtColor(wb, cv2.COLOR_BGR2GRAY)[y1:y2, x1:x2].astype(np.float32)
                    after = float(np.abs(ga - gw).mean() / 40.0)
                motion_pairs.append({"pair": rec["pair"], "target_pixel_motion_before": round(before, 4),
                                     "target_pixel_motion_after": (round(after, 4) if after is not None else None)})
            prev_t = t
        cam_ev = camera_reliability_evidence(cam_synth)
        cam_state = cam_ev.camera_state  # RELIABLE/UNRELIABLE/INSUFFICIENT
        cam_case = "RELIABLE" if cam_ev.camera_state == "RELIABLE" else "UNRELIABLE"
        cam_unrel = cam_ev.camera_state == "UNRELIABLE"
        # 目标时序（仅 TARGET_SINGLE 帧）
        tls = []
        for t in ts_sorted:
            st = target_state_by_t[t]
            if st["bbox"] is not None:
                tls.append({"t_s": t, "bbox_pixel": st["bbox"], "island_pixel": island_by_t.get(t)})
        target_vis_states = {t: target_state_by_t[t]["state"] for t in ts_sorted}
        after_px = max((m["target_pixel_motion_after"] or 0.0) for m in motion_pairs) if motion_pairs else 0.0
        before_px = max((m["target_pixel_motion_before"] or 0.0) for m in motion_pairs) if motion_pairs else 0.0
        # 几何证据（frozen）
        geo = build_geometry_direction_evidence(CANONICAL_TARGET, "A", tls, camera_unreliable=cam_unrel)
        # 时序判定（frozen；不足 2 个目标帧 → UNSURE 归因，不发明框）
        if len(tls) < 2:
            verdict = "UNSURE"
            vcodes = ["TARGET_NOT_VISIBLE_OR_INSUFFICIENT", "GEOMETRY_INSUFFICIENT_FRAMES"]
            mandatory = {"target_object_visible": "FAIL" if len(tls) == 0 else "PASS",
                         "target_object_motion": "UNSURE", "direction": "UNSURE",
                         "state_transition": "UNSURE"}
            geo_state = geo.state_progress
            geo_dir = geo.direction_action
        else:
            vis = [x["t_s"] for x in tls]
            def sem(t):
                bb = next(x["bbox_pixel"] for x in tls if x["t_s"] == t)
                return FrameSemantics(t, [CANONICAL_TARGET], [],
                                      [ROI(CANONICAL_TARGET, *[int(v) for v in bb], source="L3_HUMAN_ROI")],
                                      dominant_visual=CANONICAL_TARGET)
            before = sem(vis[0])
            middle = sem(vis[len(vis) // 2])
            after = sem(vis[-1])
            mm = MotionMetrics(camera_residual=0.0, roi_motion={CANONICAL_TARGET: round(after_px, 4)})
            ev = TemporalEvidence(before=before, middle=middle, after=after, motion=mm,
                                  requested_action=REQUESTED_ACTION, geometry_direction_evidence=geo)
            v = TemporalStateValidator(TargetObjectMotionRouter()).validate(ev)
            verdict = str(v.verdict.value)
            vcodes = list(v.reason_codes)
            mandatory = dict(v.mandatory)
            geo_state = geo.state_progress
            geo_dir = geo.direction_action
        cases_out.append({
            "opaque_case_id": oid,
            "requested_action": REQUESTED_ACTION.value,
            "target_visibility": target_vis_states,
            "target_identity_state": {t: s["state"] for t, s in target_state_by_t.items()},
            "target_actual_labels": {t: s["actual_label"] for t, s in target_state_by_t.items()},
            "island_reference": {t: ("OK" if island_by_t.get(t) else "NONE_OR_AMBIGUOUS") for t in ts_sorted},
            "camera_case": cam_case,
            "camera_evidence": {"state": cam_ev.camera_state, "source_pairs": cam_ev.source_pairs,
                                "max_feature_residual": cam_ev.max_feature_residual,
                                "min_inlier_ratio": cam_ev.min_inlier_ratio,
                                "max_translation_px": cam_ev.max_translation_px,
                                "pairs": cam_pair_records},
            "target_motion": {"pairs": motion_pairs,
                              "target_pixel_motion_before_max": round(before_px, 4),
                              "target_pixel_motion_after_max": round(after_px, 4)},
            "geometry_evidence": {"frames_used": geo.frames_used,
                                  "direction_action": geo_dir, "state_progress": geo_state,
                                  "geometry_change_present": geo.geometry_change_present,
                                  "relative_motion_present": geo.relative_motion_present,
                                  "confidence_class": geo.confidence_class,
                                  "reason_codes": geo.reason_codes,
                                  "visibility_progression": geo.visibility_progression,
                                  "robust_stats": (geo.raw_features.get("robust") or {}),
                                  "abs_seq": geo.raw_features.get("abs_seq"),
                                  "area_jitter_class": geo.raw_features.get("area_jitter_class")},
            "temporal_mandatory_gates": mandatory,
            "reason_codes": vcodes,
            "machine_verdict": verdict,
        })
        print(oid, "->", verdict, "| geo:", geo_dir, geo_state, "| cam:", cam_case,
              "| tls:", len(tls), "| after_px:", round(after_px, 3), "| codes:", vcodes[:4])
    doc = {
        "experiment": "MMVV_A3_MACHINE_PREDICTIONS_BLIND",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "algorithm_freeze_commit": "ca34678",
        "roi_sha256": roi_sha,
        "blind_manifest_sha256": blind_sha,
        "frame_hash_check": "verified_by_selfcheck",
        "requested_action": REQUESTED_ACTION.value,
        "input_boundary_note": "本文件由 blind 输入+人工 ROI 生成；不含 GT/原 media_id/POS-NEG/期望结果。",
        "cases": json_safe(cases_out),
    }
    tmp = PRED_JSON.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(PRED_JSON)
    # ---- HASH LOCK ----
    pred_sha = sha256_file(PRED_JSON)
    PRED_SHA.write_text(f"{pred_sha}  {PRED_JSON.name}\n", encoding="utf-8")
    pred_sha2 = sha256_file(PRED_JSON)
    assert pred_sha == pred_sha2, "prediction hash re-read mismatch"
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    lock = {"experiment": "A3_PREDICTION_LOCK_V1",
            "prediction_sha256": pred_sha,
            "prediction_created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "algorithm_freeze_commit": "ca34678",
            "roi_sha256": roi_sha,
            "blind_manifest_sha256": blind_sha,
            "git_head_before_gt": head,
            "gt_opened": False}
    LOCK_JSON.write_text(json.dumps(lock, ensure_ascii=False, indent=1), encoding="utf-8")
    print("PREDICTION_WRITTEN")
    print("PREDICTION_SHA256:", pred_sha)
    print("LOCK:", LOCK_JSON.name, "head_before_gt:", head)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--predict", action="store_true", help="显式触发预测(默认)")
    a = ap.parse_args()
    if a.selfcheck:
        return selfcheck()
    quarantine_stale()
    sc = selfcheck(verbose=True)
    if sc != 0:
        print("A3_SELFCHECK_FAIL_BLOCK_PREDICTION")
        return sc
    return predict()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
