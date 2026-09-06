#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POST-A3 — 兜底缩略图（ffprobe/ffmpeg）for DJI/容器文件 + 重建评审清单。"""
import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
REVIEW = OUT / "TREECUT_POSTA3_REVIEW_CANDIDATES_V1.json"
THUMBS = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\mmv_posta3_frames") / "thumbs"
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
FFMPEG = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
FFPROBE = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffprobe.exe"
BASE = r"\\X1\素材盘01\已处理素材\卖点展示类素材"
sys.stdout.reconfigure(encoding="utf-8")
FR = [0.15, 0.35, 0.50, 0.65, 0.85]
EXTRA = {  # id -> (bucket, family 覆盖)
    "21674": "EXTEND", "10000": "STATIC", "11592": "RETRACT",
    "12095": "RETRACT", "3571": "RETRACT", "9697": "RETRACT"}


def dur_of(path):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "json", path], capture_output=True)
    try:
        return float(json.loads(r.stdout)["format"]["duration"])
    except Exception:
        sys.stderr.write(f"ffprobe fail {path} :: {r.stderr.decode('utf-8','replace')[-300:]}\n")
        return 0.0


def main():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    doc = json.loads(REVIEW.read_text(encoding="utf-8"))
    existing = {c["media_id"] for c in doc["candidates"]}
    added = []
    for mid, bucket in EXTRA.items():
        row = cur.execute("select relative_path from media_files where id=?", (int(mid),)).fetchone()
        src = BASE + "\\" + row[0]
        d = dur_of(src)
        if d <= 1.0:
            print("too short skip", mid, round(d, 2))
            continue
        fam = row[0].split("\\")[1] if "\\" in row[0] else row[0]
        frames = []
        for i, f in enumerate(FR):
            ts = d * f
            out = THUMBS / f"pc{mid}_{i}.jpg"
            subprocess.run([FFMPEG, "-y", "-i", src, "-ss", f"{ts:.3f}", "-frames:v", "1",
                            "-vf", "scale=360:-2", "-q:v", "5", str(out)],
                           capture_output=True)
            if out.exists() and out.stat().st_size > 1000:
                frames.append({"file": out.name, "ts": round(ts, 2)})
        if len(frames) >= 3:
            added.append({"bucket": bucket, "media_id": int(mid), "family": fam,
                          "path": row[0], "duration_s": round(d, 2), "frames": frames})
            print("added", mid, bucket, "dur", round(d, 2), "thumbs", len(frames))
    doc["candidates"].extend(added)
    doc["count"] = len(doc["candidates"])
    doc["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    REVIEW.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print("total:", doc["count"], dict(Counter(c["bucket"] for c in doc["candidates"])))
    con.close()


if __name__ == "__main__":
    main()
