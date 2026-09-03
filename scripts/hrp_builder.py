# -*- coding: utf-8 -*-
"""STAGE8 — ChatGPT 动态审核包打包器(PACKAGING ONLY): 每候选 = 前文0.7s+选中窗+后文0.7s,
drawtext(textfile) 顶部标签, 黑卡章节, concat; 输出 mp4 + json(human_result=null)。"""
import json, sqlite3, subprocess, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
FF = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
FFP = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffprobe.exe"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
PKG = OUT / "human_review_package"
PKG.mkdir(exist_ok=True)
WORK = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\hrp_work")
WORK.mkdir(exist_ok=True)
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
# font 复制到 WORK 供相对引用(避免滤镜串盘符冒号)
SRC = {1: r"\\X1\素材盘01\已处理素材\卖点展示类素材", 2: r"\\X1\素材盘01\已处理素材\效果展示类素材",
       4: r"\\X1\素材盘01\未处理素材\【工厂】"}
_FONT_LOCAL = WORK / "msyh.ttc"
if not _FONT_LOCAL.exists():
    import shutil
    shutil.copy(r"C:\Windows\Fonts\msyh.ttc", _FONT_LOCAL)
FONT = "msyh.ttc"
CTX = 0.7
_FF_CWD = WORK

_c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
_dur = {}
def path_for(mid):
    r = _c.execute("SELECT mf.source_id, mf.relative_path FROM media_files mf WHERE mf.id=?", (int(mid),)).fetchone()
    return str(Path(SRC.get(r[0], "")) / r[1]) if r and r[0] in SRC else None
def dur_of(p):
    if p not in _dur:
        r = subprocess.run([FFP, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                           capture_output=True, timeout=60, cwd=_FF_CWD)
        try:
            _dur[p] = float(r.stdout.decode().strip())
        except Exception:
            _dur[p] = 0.0
    return _dur[p]

def esc_path(p):
    return p.replace("\\", "/").replace(":", "\\:")

def write_textfile(lines, tag):
    f = WORK / f"{tag}.txt"
    f.write_text("\n".join(lines), encoding="utf-8")
    return f

def drawtext_f(tf, size=30, y=20):
    return (f"drawtext=fontfile={FONT}:textfile={tf.name}:fontsize={size}:"
            f"fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=12:x=16:y={y}")

def clip_segment(path, start, end, label_lines, out_mp4, ctx_tag=""):
    """编码 [start,end] 到统一 720x1280, 顶部烧标签。cwd=WORK 避免滤镜串盘符冒号。"""
    s = max(0.0, start); e = min(dur_of(path), end)
    if e - s < 0.2:
        return None
    tf = write_textfile(label_lines, f"lab_{out_mp4.stem}")
    vf = (f"scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2:black,"
          f"setsar=1,fps=30,{drawtext_f(tf)}")
    r = subprocess.run([FF, "-y", "-ss", f"{s:.2f}", "-t", f"{e-s:.2f}", "-i", str(path),
                        "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                        "-c:a", "aac", "-b:a", "96k", "-ar", "44100", "-ac", "1",
                        "-movflags", "+faststart", str(out_mp4)], capture_output=True, timeout=600,
                       cwd=_FF_CWD)
    return out_mp4 if r.returncode == 0 and out_mp4.exists() else None

def title_card(lines, out_mp4, d=1.6):
    """黑底标题卡(每行独立 textfile 逐行定位)。"""
    parts = []
    for i, ln in enumerate(lines):
        tf = write_textfile([ln], f"card_{out_mp4.stem}_{i}")
        parts.append(f"drawtext=fontfile={FONT}:textfile={tf.name}:fontsize=44:"
                     f"fontcolor=white:x=(w-text_w)/2:y={520 + i * 100}")
    vf = ",".join(parts)
    r = subprocess.run([FF, "-y", "-f", "lavfi", "-i", f"color=black:s=720x1280:r=30:d={d}",
                        "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                        "-an", str(out_mp4)], capture_output=True, timeout=300, cwd=_FF_CWD)
    return out_mp4 if r.returncode == 0 else None

def concat(pieces, final_mp4):
    lst = WORK / f"{final_mp4.stem}.txt"
    lst.write_text("\n".join(f"file '{p}'" for p in pieces), encoding="utf-8")
    r = subprocess.run([FF, "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-c", "copy", "-movflags", "+faststart", str(final_mp4)], capture_output=True, timeout=1800,
                       cwd=_FF_CWD)
    return r.returncode == 0 and final_mp4.exists()

def candidate_pieces(mid, s, e, top_label, base, ctx_labels=("CONTEXT BEFORE", "SELECTED WINDOW", "CONTEXT AFTER")):
    """前文/选中窗/后文 三段, 每段顶部持续 top_label+段标签。"""
    p = path_for(mid)
    if not p or not Path(p).exists():
        return []
    dur = dur_of(p)
    segs = [(max(0.0, s - CTX), s, f"{top_label} | {ctx_labels[0]}"),
            (s, min(e, dur), f"{top_label} | {ctx_labels[1]}"),
            (min(e, dur), min(dur, e + CTX), f"{top_label} | {ctx_labels[2]}")]
    out = []
    for i, (a, b, lab) in enumerate(segs):
        if b - a < 0.15:
            continue
        f = WORK / f"{base}_{i}.mp4"
        if clip_segment(p, a, b, [lab], f):
            out.append(f)
    return out
