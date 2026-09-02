# -*- coding: utf-8 -*-
"""独立视觉 QA：qwen2.5vl 读成片关键帧 → 功能-画面匹配证据 + 水印/旧字幕排查。"""
import base64, json, subprocess, sys, urllib.request
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
import cv2, numpy as np

FF = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
D = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\pilot_v2")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
final = D / "B007_FIRST_REAL_PILOT_V2.mp4"

def qwen(img_b64, question):
    body = json.dumps({"model": "qwen2.5vl:7b", "stream": False,
                       "options": {"temperature": 0.1},
                       "messages": [{"role": "user", "content": question, "images": [img_b64]}]}).encode()
    req = urllib.request.Request("http://localhost:11434/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d.get("message", {}).get("content", "")

def frame_at(t):
    png = D / f"_vqa_{str(t).replace('.', '_')}.png"
    subprocess.run([FF, "-y", "-ss", str(t), "-i", str(final), "-frames:v", "1", str(png)],
                   capture_output=True, timeout=60)
    img = cv2.imdecode(np.fromfile(str(png), np.uint8), cv2.IMREAD_COLOR)
    png.unlink(missing_ok=True)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return base64.b64encode(buf.tobytes()).decode()

checks = [
    ("B1_HOOK", 1.0, "HOOK 开场画面应展示岛台/厨房场景。请描述画面：主体是什么？人在做什么？背景环境？"),
    ("B2_STORAGE", 6.8, "该镜头应对应「上层薄抽收纳」主张。请回答：画面中是否有人拉开/打开抽屉的动作？抽屉在上层还是下层？"),
    ("B3_POWER", 12.5, "该镜头应对应「轨道插座/插拔方便」主张。请回答：画面中是否出现插座（轨道插座/墙上插座）？是否有人插拔电器的动作？"),
    ("B4_FLEXIBLE", 17.5, "该镜头应对应「伸缩桌面」主张。请回答：画面中是否有人拉出/伸缩桌面的动作？"),
]
every = []
for i, (label, t, q) in enumerate(checks):
    try:
        txt = qwen(frame_at(t), q + " 另外：画面里有没有小红书/抖音等平台水印、@账号、或旧视频字幕残留？一并说明。")
        print(f"--- {label} t={t}s ---")
        print(txt[:600])
        every.append({"check": label, "t_s": t, "question": q, "qwen_desc": txt})
    except Exception as e:
        print(label, "ERROR", e)
        every.append({"check": label, "t_s": t, "error": str(e)[:200]})

(OUT / "B007_V2_VISION_QA_EVIDENCE_V1.json").write_text(
    json.dumps(every, ensure_ascii=False, indent=2), encoding="utf-8")
print("saved", OUT / "B007_V2_VISION_QA_EVIDENCE_V1.json")
