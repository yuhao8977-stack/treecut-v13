# -*- coding: utf-8 -*-
"""G2 二次采样: 伸缩组素材 +2 帧(0.42/0.58) 定位动作(有界补充, §15)。"""
import base64, json, subprocess, sys, time, urllib.request
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
FF = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
RES = OUT / "TREECUT_G2_TEMPORAL_EVIDENCE_V1.json"
data = json.loads(RES.read_text(encoding="utf-8"))
items = data["items"]
man = json.loads((OUT / "_g2_probe_manifest.json").read_text(encoding="utf-8"))
prompt = ("这一帧中, 可伸缩桌面/岛台是否正在被拉出加宽或被收回? 回答一行 state=NOT_PRESENT|OBJECT_PRESENT|"
          "ACTION_START|ACTION_IN_PROGRESS|ACTION_END; 一行 object=桌面/轨道插座/其他; 一行 desc=一句话。")

def ask(b64):
    body = json.dumps({"model": "qwen2.5vl:7b", "stream": False, "options": {"temperature": 0.0},
                       "messages": [{"role": "user", "content": prompt, "images": [b64]}]}).encode()
    req = urllib.request.Request("http://localhost:11434/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.loads(r.read().decode("utf-8"))["message"]["content"]

extend_assets = [m for m in man if m["group"] in ("EXTEND_POS", "EXTEND_HARDNEG")]
added = 0
for m in extend_assets:
    dur = m["duration_s"] or 12.0
    for frac, tag in ((0.42, "x"), (0.58, "y")):
        t = round(frac * dur, 2)
        png = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\g2_frames") / f"m{m['media_id']}_{tag}.jpg"
        subprocess.run([FF, "-y", "-ss", str(t), "-i", str(m["full_path"]), "-frames:v", "1",
                        "-vf", "scale=480:-2", str(png)], capture_output=True, timeout=90)
        if not png.exists() or png.stat().st_size <= 5000:
            continue
        try:
            txt = ask(base64.b64encode(png.read_bytes()).decode())
        except Exception:
            continue
        items.append({"media_id": m["media_id"], "group": m["group"], "frame_idx": 99,
                      "frac": frac, "t_s": t, "qwen_l2_raw": txt, "level": "L2_VISUAL_CANDIDATE",
                      "pass2": True})
        added += 1
    print("mid", m["media_id"], "pass2 done", flush=True)
data["items"] = items
data["note"] = data.get("note", "") + " | pass2: extend 素材 0.42/0.58 有界补充帧"
RES.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("added", added, "frames; total", len(items))
