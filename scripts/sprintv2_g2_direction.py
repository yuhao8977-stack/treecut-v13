# -*- coding: utf-8 -*-
"""G2 方向细化: 对已检出 EXTEND/RETRACT 窗口的素材, 在动作帧处做 EXTEND-vs-RETRACT 独立有界复核。"""
import base64, json, subprocess, sys, time, urllib.request
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
FF = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
RES = OUT / "TREECUT_G2_TEMPORAL_EVIDENCE_V1.json"
data = json.loads(RES.read_text(encoding="utf-8"))
items = data["items"]
# 找含 EXTEND/RETRACT 窗的素材与动作时刻
wins = json.loads((OUT / "TREECUT_G2_SUBCLIP_WINDOWS_V1.json").read_text(encoding="utf-8"))["windows"]
targets = {}
for w in wins:
    if w["action"] in ("EXTEND", "RETRACT") and w["action_start_s"] is not None:
        targets.setdefault(w["media_id"], set()).add(w["action_start_s"])
man = {m["media_id"]: m for m in json.loads((OUT / "_g2_probe_manifest.json").read_text(encoding="utf-8"))}

DIRQ = ("这一帧的桌面上，此刻正在发生的动作是：1) 桌面/台面正在被【拉出/加宽】(伸缩展开)？"
        "2) 还是正在被【收回/收起】(缩回去变窄)？还是 3) 静止没动？"
        "只回答一行：direction=EXTEND(正在展开) / RETRACT(正在收回) / STATIC(静止) / UNCERTAIN")

def ask(b64):
    body = json.dumps({"model": "qwen2.5vl:7b", "stream": False, "options": {"temperature": 0.0},
                       "messages": [{"role": "user", "content": DIRQ, "images": [b64]}]}).encode()
    req = urllib.request.Request("http://localhost:11434/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.loads(r.read().decode("utf-8"))["message"]["content"]

added = 0
for mid, ts_set in targets.items():
    m = man.get(mid)
    if not m:
        continue
    for t in sorted(ts_set)[:2]:
        png = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\g2_frames") / f"dir_{mid}_{str(t).replace('.', '_')}.jpg"
        subprocess.run([FF, "-y", "-ss", str(t), "-i", str(m["full_path"]), "-frames:v", "1",
                        "-vf", "scale=480:-2", str(png)], capture_output=True, timeout=90)
        if not png.exists() or png.stat().st_size <= 5000:
            continue
        try:
            txt = ask(base64.b64encode(png.read_bytes()).decode())
        except Exception as e:
            print(mid, t, "err", str(e)[:80]); continue
        items.append({"media_id": mid, "group": m["group"], "frame_idx": 98, "t_s": t,
                      "qwen_l2_raw": txt, "level": "L2_VISUAL_CANDIDATE", "direction_probe": True})
        added += 1
        print("mid", mid, "t", t, "->", txt[:90].replace("\n", " | "), flush=True)
data["items"] = items
data["note"] = data.get("note", "") + " | direction probe: EXTEND vs RETRACT 独立复核"
RES.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("added direction frames:", added, "total", len(items))
