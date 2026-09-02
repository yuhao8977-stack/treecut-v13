# -*- coding: utf-8 -*-
"""UI smoke: GET /  /api/project / Range 视频 / POST replace 持久化。"""
import json, sys, urllib.request
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8899"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
res = {}
try:
    r = urllib.request.urlopen(BASE + "/", timeout=15)
    res["open_workbench"] = {"status": r.status, "bytes": len(r.read())}
except Exception as e:
    res["open_workbench"] = {"error": str(e)[:120]}
try:
    r = urllib.request.urlopen(BASE + "/api/project", timeout=15)
    proj = json.loads(r.read().decode("utf-8"))
    res["load_project"] = {"status": r.status, "beats": len(proj.get("beats", []))}
except Exception as e:
    res["load_project"] = {"error": str(e)[:120]}
# Range 视频(用 X1 一段)
try:
    from urllib.parse import quote
    vid = r"\\X1\素材盘01\已处理素材\卖点展示类素材\【01】上层薄抽\    【62】【现代极简风岛台】广州赖小姐 【岛台上层薄抽收纳层】\    【62】【现代极简风岛台】广州赖小姐 【岛台上层薄抽收纳层】-1.mp4"
    req = urllib.request.Request(BASE + "/file?p=" + quote(vid), headers={"Range": "bytes=0-2047"})
    r = urllib.request.urlopen(req, timeout=30)
    chunk = r.read()
    res["video_range"] = {"status": r.status, "got_bytes": len(chunk), "content_range": r.headers.get("Content-Range")}
except Exception as e:
    res["video_range"] = {"error": str(e)[:160]}
# replace 持久化
try:
    body = json.dumps({"beat_id": "B1", "selection": {"media_id": 1,
                       "subclip": {"start_s": 1.82, "end_s": 4.37}}}).encode()
    req = urllib.request.Request(BASE + "/api/replace", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req, timeout=15)
    res["replace_save"] = json.loads(r.read().decode("utf-8"))
except Exception as e:
    res["replace_save"] = {"error": str(e)[:160]}
(OUT / "TREECUT_UI_SMOKE_V1.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False, indent=1))
