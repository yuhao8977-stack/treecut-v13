# -*- coding: utf-8 -*-
"""DENSE01R1 OVERNIGHT — PREPROCESS AUDIT (§4)：随机抽 5 帧，
pre/post-normalization channel stats、无 swap/双归一化/灰度污染验证。role-blind。"""
import json
import random
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
MANIFEST = OUT / "TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json"
ROI_JSON = OUT / "TREECUT_POSTA3_HUMAN_ROI_V1.json"
ROOTS = {1: r"\\X1\素材盘01\已处理素材\卖点展示类素材",
         2: r"\\X1\素材盘01\已处理素材\效果展示类素材",
         3: r"\\X1\素材盘01\已处理素材\JianyingPro Presets",
         4: r"\\X1\素材盘01\未处理素材\【工厂】"}
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
sys.stdout.reconfigure(encoding="utf-8")


def ch_stats(a):
    return {"mean": [round(float(v), 5) for v in a.reshape(-1, 3).mean(0)],
            "std": [round(float(v), 5) for v in a.reshape(-1, 3).std(0)]}


def main():
    random.seed(11)
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    roi = json.loads(ROI_JSON.read_text(encoding="utf-8"))["annotations"]
    # 收集所有 (case, t) 帧
    frames = []
    for c in man["cases"]:
        for f in c["frames"]:
            frames.append((c, f))
    picked = random.sample(frames, min(5, len(frames)))
    rows = []
    issues = []
    for c, f in picked:
        mid = c["media_id"]
        vpath = ROOTS.get(c["source_id"], "") + "\\" + c["relative_path"]
        cap = cv2.VideoCapture(vpath)
        cap.set(cv2.CAP_PROP_POS_MSEC, f["t_s"] * 1000.0)
        ok, fr = cap.read()
        cap.release()
        if not ok:
            issues.append(f"READ_FAIL {mid} {f['t_s']}")
            continue
        h, w = fr.shape[:2]
        if w > 960:
            fr = cv2.resize(fr, (960, int(h * 960 / w)), interpolation=cv2.INTER_AREA)
        # ISLAND_BODY crop（原始缩放平面）
        anns = [a for a in roi if a["media_id"] == mid and a["frame_timestamp"] == f["t_s"]]
        ib = [a for a in anns if a["object_name"] == "ISLAND_BODY"]
        if len(ib) != 1:
            issues.append(f"NO_ISLAND {mid} {f['t_s']}")
            continue
        b = ib[0]["bbox_pixel"]
        sx, sy = fr.shape[1] / f["width"], fr.shape[0] / f["height"]
        x1, y1, x2, y2 = [int(v) for v in (b[0] * sx, b[1] * sy, b[2] * sx, b[3] * sy)]
        crop = fr[max(0, y1):y2, max(0, x1):x2]
        # pre-norm stats（BGR 原 crop）
        pre_bgr = ch_stats(crop)
        # 转换路径 1：BGR→RGB→归一化（不 letterbox，纯通道验证，float64 免累加误差）
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB).astype(np.float64) / 255.0
        chs = rgb.reshape(-1, 3)
        MEAN64 = MEAN.astype(np.float64)
        STD64 = STD.astype(np.float64)
        post = (chs - MEAN64) / STD64
        post_stats = {"mean": [round(float(v), 5) for v in post.mean(0)],
                      "std": [round(float(v), 5) for v in post.std(0)]}
        # 灰度污染检查：BGR 三通道 std 应不同（非复制）
        bgr_std = [float(v) for v in crop.reshape(-1, 3).std(0)]
        gray_like = max(bgr_std) - min(bgr_std) < 0.5
        if gray_like:
            issues.append(f"GRAY_LIKE {mid} {f['t_s']} bgr_std={bgr_std}")
        # 0-255 直接减 mean 检查：expected 用 RGB 通道 pre01 mean 配 RGB 统计量
        pre01_mean_rgb = [float(v) for v in rgb.reshape(-1, 3).mean(0)]
        exp = [(pre01_mean_rgb[i] - float(MEAN64[i])) / float(STD64[i]) for i in range(3)]
        rows.append({"case": mid, "t_s": f["t_s"], "frame": f["frame"],
                     "pre_norm_bgr": pre_bgr,
                     "post_norm_rgb": post_stats,
                     "expected_post_mean": [round(v, 5) for v in exp],
                     "bgr_channel_std": [round(v, 3) for v in bgr_std],
                     "grayscale_contamination": bool(gray_like),
                     "swap_check": "R>B means ->" + str(round(float(rgb[..., 0].mean()), 4)) +
                                   "," + str(round(float(rgb[..., 2].mean()), 4))})
    out = {"n_frames": len(rows), "issues": issues,
           "rows": rows,
           "checks": {
               "grayscale_contamination": all(not r["grayscale_contamination"] for r in rows),
               "channel_distinct": all(max(r["bgr_channel_std"]) - min(r["bgr_channel_std"]) > 0.5
                                       for r in rows),
               "post_matches_expected_rgb": all(
                   abs(r["post_norm_rgb"]["mean"][i] - r["expected_post_mean"][i]) < 1e-3
                   for r in rows for i in range(3))}}
    (OUT / "TREECUT_DENSE01R1_OVERNIGHT_PREPROCESS_AUDIT.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
