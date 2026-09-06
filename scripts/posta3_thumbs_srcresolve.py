#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POST-A3 — 按 source 根解析真实路径 + cv2 补抽（RETRACT/STATIC/EXTRA 缺失项）。"""
import json
import sqlite3
import sys
import time
from pathlib import Path

import cv2

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
REVIEW = OUT / "TREECUT_POSTA3_REVIEW_CANDIDATES_V1.json"
THUMBS = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\mmv_posta3_frames") / "thumbs"
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
sys.stdout.reconfigure(encoding="utf-8")
ROOTS = {1: r"\\X1\素材盘01\已处理素材\卖点展示类素材",
         2: r"\\X1\素材盘01\已处理素材\效果展示类素材",
         3: r"\\X1\素材盘01\已处理素材\JianyingPro Presets",
         4: r"\\X1\素材盘01\未处理素材\【工厂】"}
FR = [0.15, 0.35, 0.50, 0.65, 0.85]
WANT = {"11592": "RETRACT", "12095": "RETRACT", "3571": "RETRACT", "9697": "RETRACT",
        "25894": "RETRACT", "26023": "RETRACT", "27433": "RETRACT",
        "10000": "STATIC", "21674": "EXTEND"}


def resolve(rel, src):
    r = ROOTS.get(src)
    if not r:
        return None
    cands = [r + "\\" + rel]
    seg0 = rel.split("\\")[0]
    tail = ROOTS.get(src, "").split("\\")[-1]
    if seg0 == tail or seg0.startswith(tail) or tail.startswith(seg0):
        rest = rel[len(seg0):].lstrip("\\")
        cands.insert(0, r + "\\" + rest)
    for c in cands:
        if Path(c).exists():
            return c
    return None


def grab(path, ts):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000.0)
    ok, fr = cap.read()
    cap.release()
    return fr if ok else None


def main():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    doc = json.loads(REVIEW.read_text(encoding="utf-8"))
    have = {c["media_id"] for c in doc["candidates"]}
    added = []
    missing_rows = []
    for mid_s, bucket in WANT.items():
        if int(mid_s) in have:
            continue
        row = cur.execute("select source_id, relative_path from media_files where id=?",
                          (int(mid_s),)).fetchone()
        if not row:
            continue
        src, rel = row
        full = resolve(rel, src)
        if not full:
            missing_rows.append(int(mid_s))
            continue
        # 时长：cv2 frame count 探测；失败则 ffprobe 已证明不可用则跳过
        cap = cv2.VideoCapture(full)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        n = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        if not fps or not n:
            missing_rows.append(int(mid_s))
            continue
        dur = n / fps
        fam = rel.split("\\")[1] if "\\" in rel else rel
        frames = []
        for i, f in enumerate(FR):
            fr = grab(full, dur * f)
            if fr is None:
                continue
            h, w = fr.shape[:2]
            tw = 360
            th = int(h * tw / w)
            small = cv2.resize(fr, (tw, th), interpolation=cv2.INTER_AREA)
            name = f"pc{mid_s}_{i}.jpg"
            cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tofile(str(THUMBS / name))
            frames.append({"file": name, "ts": round(dur * f, 2)})
        if len(frames) >= 3:
            added.append({"bucket": bucket, "media_id": int(mid_s), "family": fam,
                          "path": rel, "duration_s": round(dur, 2), "frames": frames})
            print("added", mid_s, bucket, "dur", round(dur, 2), "thumbs", len(frames), "src", src)
    doc["candidates"].extend(added)
    doc["count"] = len(doc["candidates"])
    doc["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    doc["missing_files"] = missing_rows
    REVIEW.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print("total:", doc["count"], dict(Counter(c["bucket"] for c in doc["candidates"])))
    print("still missing:", missing_rows)
    con.close()


if __name__ == "__main__":
    main()
