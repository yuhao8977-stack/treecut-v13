# -*- coding: utf-8 -*-
"""V0.6.1 — 验证并提升 quarantine 中的已下载媒体（ffprobe 解析修复后）。"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
QUARANTINE = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\quarantine")
Z_MEDIA = Path(r"Z:\TreeCut_Media\B007\published_media")
TARGET = "69f9a0ac000000003701d937"
CREATOR_DUR = 21.0
FFPROBE = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffprobe.exe"
FFMPEG = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"


def main() -> int:
    part = QUARANTINE / f"{TARGET}.part"
    if not part.exists():
        print("no part file in quarantine")
        return 1
    tech = {"file": str(part), "size": part.stat().st_size}
    out = subprocess.run([FFPROBE, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(part)],
                         capture_output=True, timeout=120)
    probe = json.loads(out.stdout.decode("utf-8", errors="replace"))
    fmt = probe.get("format", {})
    streams = probe.get("streams", [])
    vs = next((s for s in streams if s.get("codec_type") == "video"), None)
    au = next((s for s in streams if s.get("codec_type") == "audio"), None)
    dur = float(fmt.get("duration") or (vs or {}).get("duration") or 0)
    tech.update({"ffprobe_ok": bool(vs and dur > 0), "duration": dur,
                 "video_codec": (vs or {}).get("codec_name"),
                 "width": (vs or {}).get("width"), "height": (vs or {}).get("height"),
                 "fps": eval_r((vs or {}).get("avg_frame_rate")),
                 "audio_codec": (au or {}).get("codec_name") if au else None})
    print("TECH =", json.dumps(tech, ensure_ascii=False))

    dec = subprocess.run([FFMPEG, "-v", "error", "-i", str(part), "-f", "null", "-"],
                         capture_output=True, timeout=600)
    tech["full_decode_ok"] = dec.returncode == 0
    if dec.stderr:
        tech["decode_stderr_tail"] = dec.stderr.decode("utf-8", errors="replace")[-200:]

    h = hashlib.sha256()
    with open(part, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    sha = h.hexdigest()
    tech["sha256"] = sha

    tol = max(5.0, CREATOR_DUR * 0.15)
    match = abs(dur - CREATOR_DUR) <= tol
    tech["duration_crosscheck"] = {"creator": CREATOR_DUR, "ffprobe": round(dur, 2),
                                   "tolerance": round(tol, 2), "pass": match}
    print("MATCH =", match, "| FULL_DECODE =", tech["full_decode_ok"])

    ok = tech.get("ffprobe_ok") and tech.get("full_decode_ok") and sha and match
    (OUT / "B007_V061_MEDIA_TECH_METADATA.json").write_text(
        json.dumps(tech, ensure_ascii=False, indent=2), encoding="utf-8")

    if not ok:
        print("VALIDATION_FAILED -> stays quarantined")
        return 1
    Z_MEDIA.mkdir(parents=True, exist_ok=True)
    final = Z_MEDIA / f"{TARGET}__{sha[:12]}.mp4"
    import shutil
    shutil.move(str(part), str(final))  # 跨卷移动（E->Z）
    tech["final_path"] = str(final)
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("DELETE FROM b007_published_media_recovery_v1 WHERE note_id=?", (TARGET,))
    conn.execute(
        "INSERT INTO b007_published_media_recovery_v1(note_id,sample_id,expected_note_id,actual_note_id,"
        "recovery_status,source_type,container,byte_size,sha256,duration,width,height,fps,video_codec,"
        "audio_codec,creator_duration,duration_match_status,final_path,recovered_at,validation_version,"
        "block_reason,attempts,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (TARGET, "PILOT1", TARGET, TARGET, "RECOVERED_EXACT", "USER_ASSISTED_CREATOR_DETAIL", "mp4",
         tech["size"], sha, dur, tech.get("width"), tech.get("height"), tech.get("fps"),
         tech.get("video_codec"), tech.get("audio_codec"), CREATOR_DUR,
         "MATCH_WITHIN_TOLERANCE" if match else "MISMATCH", str(final),
         time.strftime("%Y-%m-%d %H:%M:%S"), "V0.6.1-PILOT1", None, 1, time.time()))
    conn.commit()
    conn.close()
    print("PROMOTED =", final)
    print("STATUS = V06_ASSISTED_PILOT1_PASS")
    return 0


def eval_r(v):
    try:
        a, b = str(v).split("/")
        return round(float(a) / float(b), 3)
    except Exception:
        return None


if __name__ == "__main__":
    sys.exit(main())
