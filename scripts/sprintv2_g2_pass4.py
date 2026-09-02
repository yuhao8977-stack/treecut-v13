# -*- coding: utf-8 -*-
"""G2 pass4: EXTEND 正例素材密集采样(3.5-8s @ ~0.5s, ~24帧) 提升动作窗证据强度。"""
import base64, json, subprocess, sys, urllib.request
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
FF = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
RES = OUT / "TREECUT_G2_TEMPORAL_EVIDENCE_V1.json"
man = {m["media_id"]: m for m in json.loads((OUT / "_g2_probe_manifest.json").read_text(encoding="utf-8"))}
PROMPT = ("这一帧中, 可伸缩桌面/岛台是否正在被拉出加宽或被收回? 一行 state=NOT_PRESENT|OBJECT_PRESENT|"
          "ACTION_START|ACTION_IN_PROGRESS|ACTION_END; 一行 object=桌面/轨道插座/其他; 一行 desc=一句话。")

def ask(b64):
    body = json.dumps({"model": "qwen2.5vl:7b", "stream": False, "options": {"temperature": 0.0},
                       "messages": [{"role": "user", "content": PROMPT, "images": [b64]}]}).encode()
    req = urllib.request.Request("http://localhost:11434/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.loads(r.read().decode("utf-8"))["message"]["content"]

data = json.loads(RES.read_text(encoding="utf-8"))
items = data["items"]
added = 0
FR = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\g2_frames")
for mid in (2482, 2483, 2484):
    m = man[mid]
    dur = m["duration_s"] or 12.0
    # 窗口粗估 4.0-7.5s(伸缩动作通常在中段), 0.5s 步长
    ts = [round(4.0 + 0.5 * i, 2) for i in range(8) if 4.0 + 0.5 * i < dur - 0.3]
    for t in ts:
        png = FR / f"dense_{mid}_{str(t).replace('.', '_')}.jpg"
        subprocess.run([FF, "-y", "-ss", str(t), "-i", str(m["full_path"]), "-frames:v", "1",
                        "-vf", "scale=480:-2", str(png)], capture_output=True, timeout=90)
        if not png.exists() or png.stat().st_size <= 5000:
            continue
        try:
            txt = ask(base64.b64encode(png.read_bytes()).decode())
        except Exception:
            continue
        items.append({"media_id": mid, "group": m["group"], "frame_idx": 96, "t_s": t,
                      "qwen_l2_raw": txt, "level": "L2_VISUAL_CANDIDATE", "pass4_dense": True})
        added += 1
    print("mid", mid, "dense done", flush=True)
data["items"] = items
data["note"] = data.get("note", "") + " | pass4: EXTEND 素材 4.0-7.5s 密集采样(0.5s)"
RES.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("pass4 added:", added, "total", len(items))
