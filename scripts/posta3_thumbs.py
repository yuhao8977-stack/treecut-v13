#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POST-A3 — 评审缩略图抽取（21 候选 × 5 均匀时间点，宽~360 缩略）。"""
import json
import sys
import time
from pathlib import Path

import cv2

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
MAN = OUT / "TREECUT_POSTA3_CALIBRATION_MANIFEST_V1.json"
THUMBS = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\mmv_posta3_frames") / "thumbs"
sys.stdout.reconfigure(encoding="utf-8")
FRACTIONS = [0.15, 0.35, 0.50, 0.65, 0.85]
BASE = r"\\X1\素材盘01\已处理素材\卖点展示类素材"


def grab(path, ts):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None, 0.0
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    dur = (n / fps) if fps and n else 0.0
    cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000.0)
    ok, fr = cap.read()
    cap.release()
    return (fr if ok else None), dur


def main():
    man = json.loads(MAN.read_text(encoding="utf-8"))
    THUMBS.mkdir(parents=True, exist_ok=True)
    n_ok = 0
    items = []
    for bucket, rows in man["proposals"].items():
        for r in rows:
            src = BASE + "\\" + r["path"]
            fr0, dur = grab(src, 0.05)
            if dur <= 0 or fr0 is None:
                print("SKIP(no dur)", r["media_id"], r["path"][:60])
                continue
            frames = []
            for i, f in enumerate(FRACTIONS):
                ts = dur * f
                fr, _ = grab(src, ts)
                if fr is None:
                    continue
                h, w = fr.shape[:2]
                tw = 360
                th = int(h * tw / w)
                small = cv2.resize(fr, (tw, th), interpolation=cv2.INTER_AREA)
                name = f"pc{r['media_id']}_{i}.jpg"
                cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tofile(str(THUMBS / name))
                frames.append({"file": name, "ts": round(ts, 2)})
            if len(frames) >= 3:
                items.append({"bucket": bucket, "media_id": r["media_id"], "family": r["family"],
                              "path": r["path"], "duration_s": round(dur, 2), "frames": frames})
                n_ok += 1
            print(r["media_id"], bucket, "dur", round(dur, 2), "thumbs", len(frames))
    doc = {"experiment": "POSTA3_REVIEW_CANDIDATES", "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "thumbs_dir": str(THUMBS), "count": n_ok, "candidates": items}
    (OUT / "TREECUT_POSTA3_REVIEW_CANDIDATES_V1.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("review candidates with thumbs:", n_ok)


if __name__ == "__main__":
    main()
