# -*- coding: utf-8 -*-
"""G2: 最终探测 manifest(显式指定, 含真伸缩正例+插座伪伸缩硬负例)。"""
import json, sqlite3, subprocess, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
FFP = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffprobe.exe"
SRC = {1: r"\\X1\素材盘01\已处理素材\卖点展示类素材"}
c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
def rel(mid):
    r = c.execute("SELECT mf.source_id, mf.relative_path FROM media_files mf WHERE mf.id=?", (mid,)).fetchone()
    return r

# media_id -> (group, probe_actions, note)
SPEC = [
    (2482, "EXTEND_POS", ["EXTEND", "RETRACT"], "真伸缩文件夹【21】正例候选"),
    (2483, "EXTEND_POS", ["EXTEND", "RETRACT"], "真伸缩文件夹【21】正例候选"),
    (2484, "EXTEND_POS", ["EXTEND", "RETRACT"], "真伸缩文件夹【21】正例候选"),
    (1984, "EXTEND_HARDNEG", ["EXTEND", "RETRACT"], "文件夹含伸缩但实为轨道插座 → 硬负例"),
    (1985, "EXTEND_HARDNEG", ["EXTEND", "RETRACT"], "同上硬负例"),
    (1986, "EXTEND_HARDNEG", ["EXTEND", "RETRACT"], "同上硬负例"),
    (1, "DRAWER_POS", ["DRAWER_OPEN", "DRAWER_CLOSE"], "上层薄抽正例"),
    (37, "DRAWER_POS", ["DRAWER_OPEN", "DRAWER_CLOSE"], "上层薄抽正例"),
    (1590, "SOCKET_POS", ["SOCKET_INSERT", "SOCKET_MOVE"], "轨道插座正例"),
    (1591, "SOCKET_POS", ["SOCKET_INSERT", "SOCKET_MOVE"], "轨道插座正例"),
    (1592, "SOCKET_POS", ["SOCKET_INSERT", "SOCKET_MOVE"], "轨道插座正例"),
    (261, "CABINET_POS", ["CABINET_OPEN", "CABINET_CLOSE"], "柜门/对开候选"),
    (703, "CABINET_POS", ["CABINET_OPEN", "CABINET_CLOSE"], "下层抽屉区柜门候选"),
    (3, "STORAGE_POS", ["STORAGE_PUT_IN", "STORAGE_TAKE_OUT"], "收纳放物候选"),
    (4, "STORAGE_POS", ["STORAGE_PUT_IN", "STORAGE_TAKE_OUT"], "收纳放物候选"),
]
man = []
for mid, grp, acts, note in SPEC:
    r = rel(mid)
    if not r:
        print("missing media", mid); continue
    sid, relp = r
    full = str(Path(SRC[sid]) / relp)
    p = subprocess.run([FFP, "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(full)], capture_output=True, timeout=60)
    try:
        dur = float(p.stdout.decode().strip())
    except Exception:
        dur = None
    fracs = [0.12, 0.30, 0.50, 0.70, 0.88]
    frames = [{"frac": f, "t_s": round(f * dur, 2) if dur else None} for f in fracs]
    man.append({"media_id": mid, "group": grp, "probe_actions": acts, "note": note,
                "source_id": sid, "rel": relp[:120], "full_path": full,
                "duration_s": round(dur, 2) if dur else None, "frames": frames})
    print(grp, mid, "dur", round(dur, 2) if dur else None, relp[:70])
json.dump(man, open(OUT / "_g2_probe_manifest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("manifest:", len(man))
