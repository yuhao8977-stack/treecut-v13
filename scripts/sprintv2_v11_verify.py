# -*- coding: utf-8 -*-
"""V1.1 收尾验证: RR提升后 Top(EXTEND/SOCKET) + 跨段连续合并(EXTEND族) 有界 qwen 动作验证。"""
import base64, json, sqlite3, subprocess, sys, time, urllib.request
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
FR = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\v11_frames")
FF = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
FFP = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffprobe.exe"
SRC = {1: r"\\X1\素材盘01\已处理素材\卖点展示类素材", 2: r"\\X1\素材盘01\已处理素材\效果展示类素材",
       4: r"\\X1\素材盘01\未处理素材\【工厂】"}
SYS = r"C:\Users\admin\github\treecut-v13\src"
sys.path.insert(0, SYS)
from treecut.services.action_subclip import parse_qwen_state, build_windows, apply_action_gate, parse_direction, fit_duration

def ask(b64, q):
    body = json.dumps({"model": "qwen2.5vl:7b", "stream": False, "options": {"temperature": 0.0},
                       "messages": [{"role": "user", "content": q, "images": [b64]}]}).encode()
    req = urllib.request.Request("http://localhost:11434/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.loads(r.read().decode("utf-8"))["message"]["content"]

def frame_at(path, t, tag):
    png = FR / f"{tag}.jpg"
    subprocess.run([FF, "-y", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1", "-vf", "scale=320:-2", str(png)],
                   capture_output=True, timeout=90)
    return png if png.exists() and png.stat().st_size > 2000 else None

def dur_of(path):
    try:
        return float(subprocess.run([FFP, "-v", "error", "-show_entries", "format=duration",
                                     "-of", "csv=p=0", str(path)], capture_output=True, timeout=60).stdout.decode().strip())
    except Exception:
        return 0.0

c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
def path_of(mid):
    r = c.execute("SELECT source_id, relative_path FROM media_files WHERE id=?", (int(mid),)).fetchone()
    return str(Path(SRC[r[0]]) / r[1]) if r else None

def verify(path, dur, act, fam, tag):
    Q = {"flexible": "这一帧: 可伸缩桌面是否在移动(拉出/收回)? state=NOT_PRESENT|OBJECT_PRESENT|ACTION_START|ACTION_IN_PROGRESS|ACTION_END; object; desc",
         "socket": "这一帧: 是否正在插拔/操作插座模块? state=NOT_PRESENT|OBJECT_PRESENT|ACTION_START|ACTION_IN_PROGRESS|ACTION_END; object; desc"}
    D = {"flexible": "direction=EXTEND(展开)/RETRACT(收回)/STATIC/UNCERTAIN?",
         "socket": "direction=SOCKET_INSERT(插入)/SOCKET_REMOVE(拔出)/STATIC/UNCERTAIN?"}
    st = []
    for frac in (0.2, 0.5, 0.8):
        png = frame_at(path, frac * dur, f"fv_{tag}_{frac}")
        if png is None:
            continue
        raw = ask(base64.b64encode(png.read_bytes()).decode(), Q[fam])
        png.unlink(missing_ok=True)
        st.append({"t_s": round(frac * dur, 2), "state": parse_qwen_state(raw), "qwen_l2_raw": raw})
    actn = [e for e in st if e["state"] in ("ACTION_START", "ACTION_IN_PROGRESS", "ACTION_END")]
    if len(actn) < 2:
        return {"verdict": "NO_ACTION_STATE"}
    mid_t = sorted(e["t_s"] for e in actn)[len(actn) // 2]
    png = frame_at(path, mid_t, f"d_{tag}")
    rawdir = ask(base64.b64encode(png.read_bytes()).decode(), D[fam]) if png else ""
    if png:
        png.unlink(missing_ok=True)
    ev = st + ([{"t_s": mid_t, "qwen_l2_raw": rawdir, "direction_probe": True}] if rawdir else [])
    wins = apply_action_gate(build_windows(st, dur, act), ev)
    return {"verdict": "PASS" if wins else "FAIL", "direction": parse_direction(rawdir),
            "windows": [fit_duration(w, 3.0, "action").to_dict() for w in wins]}

rr = json.loads((OUT / "_v11_rr_promote.json").read_text(encoding="utf-8"))
out = {}
for act, fam, n in (("EXTEND", "flexible", 3), ("SOCKET_INSERT", "socket", 3)):
    mids = [x["media_id"] for x in rr.get(act, []) if x.get("result") == "PROMOTED_ELIGIBLE"][:n]
    res = []
    for mid in mids:
        p = path_of(mid)
        if not p:
            continue
        d = dur_of(p)
        r = verify(p, d, act, fam, f"rr_{act}_{mid}")
        r["media_id"] = mid
        res.append(r)
        print("RR-verify", act, mid, r["verdict"], r.get("direction"), flush=True)
    out[act] = res

# 跨段合并(EXTEND/flexible 族): 取 4 条 low-diff, 用合并窗内 3 帧验证
xs = json.loads((OUT / "_v11_crossseg_scored.json").read_text(encoding="utf-8"))["scored"]
xs_cont = [x for x in xs if x["continuity_proxy"] == "continuous"][:4]
cs_res = []
for x in xs_cont:
    mid = x["media_id"]
    p = path_of(mid)
    if not p:
        continue
    s, e = (x["merged_window_ms"][0] / 1000.0), (x["merged_window_ms"][1] / 1000.0)
    if e - s < 2.0:
        continue
    # 合并窗内 3 采样(t = s+0.3, mid, e-0.3)
    st = []
    for frac in (0.2, 0.5, 0.8):
        t = s + frac * (e - s)
        png = frame_at(p, t, f"cs_{mid}_{frac}")
        if png is None:
            continue
        raw = ask(base64.b64encode(png.read_bytes()).decode(),
                  "这一帧: 可伸缩桌面是否在移动(拉出/收回)? state=NOT_PRESENT|OBJECT_PRESENT|ACTION_START|ACTION_IN_PROGRESS|ACTION_END; object; desc")
        png.unlink(missing_ok=True)
        st.append({"t_s": round(t, 2), "state": parse_qwen_state(raw), "qwen_l2_raw": raw})
    actn = [e for e in st if e["state"] in ("ACTION_START", "ACTION_IN_PROGRESS", "ACTION_END")]
    verdict = "PASS" if len(actn) >= 2 else "NO_ACTION_STATE"
    cs_res.append({"media_id": mid, "merged_window_s": [round(s, 2), round(e, 2)],
                   "verdict": verdict, "action_states": len(actn)})
    print("crossseg verify", mid, verdict, flush=True)
out["_crossseg_extend"] = cs_res
json.dump(out, open(OUT / "_v11_branch_verify.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("DONE", json.dumps(out, ensure_ascii=False)[:400])
