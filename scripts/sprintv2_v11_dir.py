# -*- coding: utf-8 -*-
"""跨段合并候选方向探测(4条) → EXTEND/RETRACT 定向前候选。"""
import base64, json, sqlite3, subprocess, sys, urllib.request
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
FR = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\v11_frames")
FF = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
SRC = {1: r"\\X1\素材盘01\已处理素材\卖点展示类素材", 2: r"\\X1\素材盘01\已处理素材\效果展示类素材",
       4: r"\\X1\素材盘01\未处理素材\【工厂】"}
SYS = r"C:\Users\admin\github\treecut-v13\src"
sys.path.insert(0, SYS)
from treecut.services.action_subclip import parse_direction

def ask(b64, q):
    body = json.dumps({"model": "qwen2.5vl:7b", "stream": False, "options": {"temperature": 0.0},
                       "messages": [{"role": "user", "content": q, "images": [b64]}]}).encode()
    req = urllib.request.Request("http://localhost:11434/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.loads(r.read().decode("utf-8"))["message"]["content"]

c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
cs = json.loads((OUT / "_v11_branch_verify.json").read_text(encoding="utf-8"))["_crossseg_extend"]
DIRQ = "direction=EXTEND(正在展开/拉出变宽)/RETRACT(正在收回)/STATIC/UNCERTAIN? 一行 direction=.."
out = []
for item in cs:
    if item["verdict"] != "PASS":
        continue
    mid = item["media_id"]
    s, e = item["merged_window_s"]
    r = c.execute("SELECT source_id, relative_path FROM media_files WHERE id=?", (mid,)).fetchone()
    if not r:
        continue
    path = str(Path(SRC[r[0]]) / r[1])
    mid_t = (s + e) / 2
    png = FR / f"xsd_{mid}.jpg"
    subprocess.run([FF, "-y", "-ss", f"{mid_t:.2f}", "-i", path, "-frames:v", "1", "-vf", "scale=480:-2", str(png)],
                   capture_output=True, timeout=90)
    raw = ""
    if png.exists() and png.stat().st_size > 5000:
        raw = ask(base64.b64encode(png.read_bytes()).decode(), DIRQ)
        png.unlink(missing_ok=True)
    d = parse_direction(raw)
    out.append({"media_id": mid, "merged_window_s": [s, e], "direction": d,
                "rel": r[1][:90], "full_path": path})
    print(mid, "dir", d, r[1][:70], flush=True)
json.dump(out, open(OUT / "_v11_flexible_merged_direction.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("DONE", len(out))
