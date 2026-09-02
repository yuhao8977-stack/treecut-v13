# -*- coding: utf-8 -*-
"""G2: 选择探测资产(每动作3-4条) + ffprobe 时长 + 生成 qwen 时序探测 manifest。"""
import json, sqlite3, subprocess, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
FFP = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffprobe.exe"
SRC = {1: r"\\X1\素材盘01\已处理素材\卖点展示类素材", 2: r"\\X1\素材盘01\已处理素材\效果展示类素材",
       4: r"\\X1\素材盘01\未处理素材\【工厂】"}
c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
inv = json.load(open(OUT / "_g2_inventory.json", encoding="utf-8"))

def pick(act, folder_part, n):
    out = []
    for it in inv.get(act, []):
        if folder_part in it["folder_hint"] and it["media_id"] not in {x["media_id"] for x in out}:
            out.append(it)
        if len(out) >= n:
            break
    return out

sel = []
def pick_rel(act, kw, n):
    used = {x[1]["media_id"] for x in sel}
    out = []
    for it in inv.get(act, []):
        if kw in it["rel"] and it["media_id"] not in used:
            out.append(it)
        if len(out) >= n:
            break
    return out

for it in pick_rel("EXTEND", "伸缩", 3):
    sel.append(("EXTEND_RETRACT", it))
for it in pick_rel("DRAWER_OPEN", "上层薄抽", 2):
    sel.append(("DRAWER", it))
for it in pick_rel("DRAWER_OPEN", "下层抽屉", 1):
    sel.append(("DRAWER", it))
for it in pick_rel("SOCKET_INSERT", "轨道插座", 3):
    sel.append(("SOCKET", it))
for it in pick_rel("CABINET_OPEN", "柜门", 2):
    sel.append(("CABINET", it))
for it in pick_rel("STORAGE_PUT_IN", "收纳", 2):
    sel.append(("STORAGE", it))
for it in pick_rel("CABINET_OPEN", "对开", 1):
    sel.append(("CABINET", it))
seen = set(); man = []
for grp, it in sel:
    if it["media_id"] in seen:
        continue
    seen.add(it["media_id"])
    man.append({"group": grp, "media_id": it["media_id"], "source_id": it["source_id"],
                "rel": it["rel"], "folder_hint": it["folder_hint"]})
print("selected assets:", len(man))
for m in man:
    full = Path(SRC[m["source_id"]]) / m["rel"]
    p = subprocess.run([FFP, "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(full)], capture_output=True, timeout=60)
    try:
        dur = float(p.stdout.decode().strip())
    except Exception:
        dur = None
    m["full_path"] = str(full)
    m["duration_s"] = round(dur, 3) if dur else None
    print(" ", m["group"], m["media_id"], "S" + str(m["source_id"]), "folder:", m["folder_hint"][:30],
          "dur:", m["duration_s"])
json.dump(man, open(OUT / "_g2_probe_manifest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("manifest saved", len(man))
