# -*- coding: utf-8 -*-
"""G2 pass3: 追加 5 资产(煮茶器/对开门收纳空镜) ×3帧 → 丰富正/负/硬负。"""
import base64, json, subprocess, sys, time, urllib.request
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
FF = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
RES = OUT / "TREECUT_G2_TEMPORAL_EVIDENCE_V1.json"
SRC = {1: r"\\X1\素材盘01\已处理素材\卖点展示类素材", 2: r"\\X1\素材盘01\已处理素材\效果展示类素材"}
SPEC = [
    (2172, "POWER_USE", ["POWER_USE", "SOCKET_INSERT"], 1, "煮茶器空镜(无人操作→负/硬负)"),
    (418, "STORAGE_EMPTY", ["STORAGE_PUT_IN", "CABINET_OPEN"], 1, "收纳整体空镜"),
    (419, "STORAGE_EMPTY", ["STORAGE_PUT_IN", "CABINET_OPEN"], 1, "收纳整体空镜"),
    (866, "CABINET_EMPTY", ["CABINET_OPEN", "CABINET_CLOSE"], 1, "对开门空镜"),
    (867, "CABINET_EMPTY", ["CABINET_OPEN", "CABINET_CLOSE"], 1, "对开门空镜"),
]
PROMPTS = {
    "POWER_USE": ("这一帧: 是否有 煮茶器/电器 正在通电使用(烧水/亮灯/冒热气)或插头插入? state=NOT_PRESENT|OBJECT_PRESENT(可见未用)|ACTION_START|ACTION_IN_PROGRESS|ACTION_END; object=煮茶器/插座/其他; desc=一句话"),
    "STORAGE_EMPTY": ("这一帧: 是否有人正在把物品放入/取出收纳(抽屉/柜)? state=NOT_PRESENT|OBJECT_PRESENT(收纳可见,无人放物)|ACTION_START|ACTION_IN_PROGRESS|ACTION_END; object=抽屉/柜/物品; desc=一句话"),
    "CABINET_EMPTY": ("这一帧: 柜门是否正在被打开/关闭? state=NOT_PRESENT|OBJECT_PRESENT(柜门可见未开)|ACTION_START|ACTION_IN_PROGRESS|ACTION_END; object=柜门/抽屉/其他; desc=一句话"),
}
import sqlite3
c = sqlite3.connect("file:" + DB if False else "file:" + r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db".replace("\\", "/") + "?mode=ro", uri=True)

def ask(b64, p):
    body = json.dumps({"model": "qwen2.5vl:7b", "stream": False, "options": {"temperature": 0.0},
                       "messages": [{"role": "user", "content": p, "images": [b64]}]}).encode()
    req = urllib.request.Request("http://localhost:11434/api/chat", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.loads(r.read().decode("utf-8"))["message"]["content"]

data = json.loads(RES.read_text(encoding="utf-8"))
items = data["items"]
added = 0
for mid, grp, acts, sid, note in SPEC:
    rel = c.execute("SELECT relative_path FROM media_files WHERE id=?", (mid,)).fetchone()
    if not rel:
        continue
    full = str(Path(SRC[sid]) / rel[0])
    p = subprocess.run([r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffprobe.exe",
                        "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(full)],
                       capture_output=True, timeout=60)
    try:
        dur = float(p.stdout.decode().strip())
    except Exception:
        dur = 10.0
    prompt = PROMPTS[grp]
    for frac in (0.12, 0.50, 0.88):
        t = round(frac * dur, 2)
        png = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\g2_frames") / f"m{mid}_{frac}.jpg"
        subprocess.run([FF, "-y", "-ss", str(t), "-i", str(full), "-frames:v", "1", "-vf", "scale=480:-2", str(png)],
                       capture_output=True, timeout=90)
        if not png.exists() or png.stat().st_size <= 5000:
            continue
        try:
            txt = ask(base64.b64encode(png.read_bytes()).decode(), prompt)
        except Exception:
            continue
        items.append({"media_id": mid, "group": grp, "frame_idx": 97, "frac": frac, "t_s": t,
                      "qwen_l2_raw": txt, "level": "L2_VISUAL_CANDIDATE", "pass3": True,
                      "probe_actions": acts})
        added += 1
    print("mid", mid, "done", flush=True)
data["items"] = items
data["note"] = data.get("note", "") + " | pass3: 煮茶器/收纳/对开门空镜(含硬负) 3帧"
RES.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("pass3 added:", added, "total", len(items))
