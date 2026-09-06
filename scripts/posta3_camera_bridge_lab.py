#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POST-A3 CAM01 — Camera bridge 实验（preliminary，无 L3 ROI 阶段：boxes=[] 全背景采样）。

对 calibration 候选（非 A3）的中段语义对 (t0=0.35d, t1=0.65d) 比较:
  SPARSE_DIRECT   : 关键帧→关键帧 直接背景 LK
  BRIDGE_500/250/125 : 每 500/250/125ms 一小段估计 translation/affine → 3x3 compose
  FULL_FRAME_DIRECT   : 全帧 RANSAC 阶梯（前景当 outlier）
只按对齐残差/FB/场景差/漂移评价（§8：不得用动作正确性评价 camera）。
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

import cv2
import numpy as np

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
REVIEW = OUT / "TREECUT_POSTA3_REVIEW_CANDIDATES_V1.json"
sys.path.insert(0, str(REPO / "src"))
from treecut.services.mmv_camera_diag import estimate_camera_background, warp_current_to_previous  # noqa: E402
sys.stdout.reconfigure(encoding="utf-8")

ROOTS = {1: r"\\X1\素材盘01\已处理素材\卖点展示类素材",
         2: r"\\X1\素材盘01\已处理素材\效果展示类素材",
         3: r"\\X1\素材盘01\已处理素材\JianyingPro Presets",
         4: r"\\X1\素材盘01\未处理素材\【工厂】"}
PREVIEW_IDS = {2163, 2543, 2552, 3571, 1019, 2208}
BRIDGE_STEPS = {"BRIDGE_500": 0.5, "BRIDGE_250": 0.25, "BRIDGE_125": 0.125}


def resolve_path(rel, src):
    r = ROOTS.get(src)
    if not r:
        return None
    p = Path(r + "\\" + rel)
    return str(p) if p.exists() else None


def imread_ts(path, ts):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000.0)
    ok, fr = cap.read()
    cap.release()
    return fr if ok else None


def to33(M):
    M = np.asarray(M, dtype=np.float64)
    if M.shape == (2, 3):
        H = np.vstack([M, [0, 0, 1]])
        return H
    if M.shape == (3, 3):
        return M
    return None


def est_translation_pair(a, b):
    """单小段估计：返回 (chosen_model, M33, scene_diff, ok)（boxes=[] 全背景）。"""
    out = estimate_camera_background(a, b, [], mode="background")
    if out.get("chosen_model") and out.get("chosen_M") is not None:
        M33 = to33(out["chosen_M"])
        wb = warp_current_to_previous(b, out["chosen_model"], out["chosen_M"])
        ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.float32)
        sd = float(np.abs(cv2.cvtColor(wb, cv2.COLOR_BGR2GRAY).astype(np.float32) - ga).mean() / 40.0)
        return out["chosen_model"], M33, sd, out
    return None, None, None, out


def run_pair(path, t0, t1):
    """返回 {method: {...}}"""
    res = {}
    a = imread_ts(path, t0)
    b = imread_ts(path, t1)
    if a is None or b is None:
        return {"error": "frame read fail"}
    gap = t1 - t0
    # SPARSE_DIRECT
    m0, H0, sd0, out0 = est_translation_pair(a, b)
    res["SPARSE_DIRECT"] = {"model": m0, "scene_diff": (round(sd0, 3) if sd0 is not None else None),
                            "pair_state": out0.get("pair_state"), "residual": out0.get("residual"),
                            "tracks": out0.get("tracked_count"),
                            "reliable": bool(m0 and sd0 is not None and sd0 < 1.6 and out0.get("pair_state") == "SAME_SCENE"),
                            "detail": out0}
    # FULL_FRAME_DIRECT
    ff = estimate_camera_background(a, b, [], mode="full_frame")
    res["FULL_FRAME_DIRECT"] = {"model": ff.get("chosen_model"), "pair_state": ff.get("pair_state"),
                                "residual": ff.get("residual"), "scene_diff": ff.get("scene_difference_score"),
                                "tracks": ff.get("tracked_count"),
                                "reliable": bool(ff.get("chosen_model") and ff.get("pair_state") in ("SAME_SCENE",))}
    # BRIDGE_*
    for name, step in BRIDGE_STEPS.items():
        if gap < step * 2:
            res[name] = {"skipped": "gap_too_small"}
            continue
        ts = np.arange(t0, t1 + 1e-9, step)
        if len(ts) < 2:
            res[name] = {"skipped": "no_steps"}
            continue
        chain = []
        ok_all = True
        for i in range(len(ts) - 1):
            fa = imread_ts(path, float(ts[i]))
            fb = imread_ts(path, float(ts[i + 1]))
            if fa is None or fb is None:
                ok_all = False
                break
            md, M33, sd, d = est_translation_pair(fa, fb)
            if M33 is None:
                ok_all = False
                chain.append({"seg": f"{ts[i]:.2f}->{ts[i+1]:.2f}", "model": md, "ok": False,
                              "pair_state": d.get("pair_state")})
                break
            chain.append({"seg": f"{ts[i]:.2f}->{ts[i+1]:.2f}", "model": md, "ok": True})
        comp = None
        if ok_all and chain and all(c["ok"] for c in chain):
            comp = np.eye(3)
            for c in chain:
                pass  # 需要 M33 per seg → 简化：此处仅统计；组合下一版实现
        res[name] = {"step": step, "segments": len(chain), "all_segments_ok": bool(ok_all and chain and all(c["ok"] for c in chain)),
                     "chain": chain[:6], "composition_supported": False}
    return res


def main():
    doc = json.loads(REVIEW.read_text(encoding="utf-8"))
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    out = {"experiment": "TREECUT_POSTA3_CAMERA_CALIBRATION_V1",
           "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "phase": "PRELIMINARY_NO_ROI",
           "note": "boxes=[]（无 L3 ROI 阶段，全背景采样）；仅对齐质量指标；bridge 组合(compose) 下版实现；不评价动作",
           "pairs": []}
    stats = {}
    for c in doc["candidates"]:
        if c["media_id"] not in PREVIEW_IDS:
            continue
        row = cur.execute("select source_id, relative_path from media_files where id=?",
                          (c["media_id"],)).fetchone()
        full = resolve_path(row[1], row[0]) if row else None
        if not full:
            print("missing file", c["media_id"])
            continue
        d = c["duration_s"]
        t0, t1 = 0.35 * d, 0.65 * d
        pair = run_pair(full, t0, t1)
        pair["media_id"] = c["media_id"]
        pair["bucket"] = c["bucket"]
        pair["semantic_pair"] = [round(t0, 2), round(t1, 2)]
        out["pairs"].append(pair)
        for k, v in pair.items():
            if isinstance(v, dict) and "reliable" in v:
                stats.setdefault(k, []).append(1 if v["reliable"] else 0)
            elif isinstance(v, dict) and "all_segments_ok" in v:
                stats.setdefault(k, []).append(1 if v["all_segments_ok"] else 0)
        print(c["media_id"], c["bucket"], "SPARSE:", pair["SPARSE_DIRECT"].get("reliable"),
              "| BRIDGE_500:", pair["BRIDGE_500"].get("all_segments_ok"),
              "| BRIDGE_250:", pair["BRIDGE_250"].get("all_segments_ok"),
              "| FULL_FRAME:", pair["FULL_FRAME_DIRECT"].get("reliable"))
    rates = {k: (round(sum(v) / len(v), 3) if v else None) for k, v in stats.items()}
    out["reliability_rates"] = rates
    (OUT / "TREECUT_POSTA3_CAMERA_CALIBRATION_V1.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("RATES:", rates)
    con.close()


if __name__ == "__main__":
    main()
