# -*- coding: utf-8 -*-
"""V1.1 探测: Eligible top60→(帧差)24→短名单12→qwen6→TVRC;
REVIEW_REQUIRED top12 verify→正规G1提升; 跨段合并候选(边界运动)→短名单 qwen。"""
import base64, cv2, json, numpy as np, sqlite3, subprocess, sys, time, urllib.request
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
FR = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\v11_frames")
FR.mkdir(parents=True, exist_ok=True)
FF = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
FFP = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffprobe.exe"
SRC = {1: r"\\X1\素材盘01\已处理素材\卖点展示类素材", 2: r"\\X1\素材盘01\已处理素材\效果展示类素材",
       4: r"\\X1\素材盘01\未处理素材\【工厂】"}
SYS = r"C:\Users\admin\github\treecut-v13\src"
sys.path.insert(0, SYS)
from treecut.services.action_subclip import parse_qwen_state, build_windows, apply_action_gate, parse_direction, fit_duration

ranked = json.loads((OUT / "_v11_ranked.json").read_text(encoding="utf-8"))
DIRQ = {"flexible": "direction=EXTEND(展开)/RETRACT(收回)/STATIC/UNCERTAIN?",
        "drawer": "direction=DRAWER_OPEN(拉开)/DRAWER_CLOSE(推回)/STATIC/UNCERTAIN?",
        "storage": "direction=STORAGE_PUT_IN(放入)/STORAGE_TAKE_OUT(取出)/STATIC/UNCERTAIN?",
        "socket": "direction=SOCKET_INSERT(插入)/SOCKET_REMOVE(拔出)/STATIC/UNCERTAIN?"}
FAM_ACT = {"EXTEND": "flexible", "RETRACT": "flexible", "DRAWER_OPEN": "drawer",
           "STORAGE_PUT_IN": "storage", "SOCKET_INSERT": "socket"}
Q_OBJ = {"flexible": "可伸缩桌面是否在移动(拉出/收回)?", "drawer": "抽屉是否正被拉开/推回?",
         "storage": "是否正把物品放入/取出收纳?", "socket": "是否正在插拔/操作插座?"}

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

def motion_proxy(path, fracs):
    ims = []
    for i, f_ in enumerate(fracs):
        png = frame_at(path, f_ * dur_of(path), f"mp_{abs(hash(path))%10**8}_{i}")
        if png is None:
            continue
        im = cv2.imdecode(np.fromfile(str(png), np.uint8), cv2.IMREAD_GRAYSCALE)
        if im is not None:
            ims.append(cv2.resize(im, (160, 240)))
        png.unlink(missing_ok=True)
    if len(ims) < 2:
        return 0.0
    return round(min(1.0, sum(float(np.abs(ims[i] - ims[i + 1]).mean()) for i in range(len(ims) - 1)) / (len(ims) - 1) / 40.0), 3)

def full_path(sid, rel):
    return str(Path(SRC[sid]) / rel)

def qwen_verify(path, dur, act, fam, tag):
    st = []
    for frac in (0.2, 0.5, 0.8):
        png = frame_at(path, frac * dur, f"{tag}_{frac}")
        if png is None:
            continue
        raw = ask(base64.b64encode(png.read_bytes()).decode(),
                  f"这一帧: {Q_OBJ[fam]} state=NOT_PRESENT|OBJECT_PRESENT|ACTION_START|ACTION_IN_PROGRESS|ACTION_END; object; desc")
        png.unlink(missing_ok=True)
        st.append({"t_s": round(frac * dur, 2), "state": parse_qwen_state(raw), "qwen_l2_raw": raw})
    actn = [e for e in st if e["state"] in ("ACTION_START", "ACTION_IN_PROGRESS", "ACTION_END")]
    if len(actn) < 2:
        return {"verdict": "NO_ACTION_STATE", "windows": []}
    mid_t = sorted(e["t_s"] for e in actn)[len(actn) // 2]
    png = frame_at(path, mid_t, f"d_{tag}")
    rawdir = ask(base64.b64encode(png.read_bytes()).decode(), DIRQ[fam]) if png else ""
    if png:
        png.unlink(missing_ok=True)
    ev = st + ([{"t_s": mid_t, "qwen_l2_raw": rawdir, "direction_probe": True}] if rawdir else [])
    wins = apply_action_gate(build_windows(st, dur, act), ev)
    return {"verdict": "PASS" if wins else "FAIL", "direction": parse_direction(rawdir),
            "windows": [fit_duration(w, 3.0, "action").to_dict() for w in wins]}

summary = {}
final = {}
for act in ranked:
    fam = FAM_ACT[act]
    top24 = ranked[act][:24]
    # 帧差运动代理(整段 5 时间点)
    scored = []
    for cand in top24:
        p = full_path(cand["sid"], cand["rel"])
        dur = dur_of(p)
        if dur < 3.0:
            continue
        mp = motion_proxy(p, (0.1, 0.3, 0.5, 0.7, 0.9))
        scored.append({**cand, "dur": round(dur, 1), "motion_proxy": mp})
    scored.sort(key=lambda x: (-x["motion_proxy"], -x["score"]))
    short12 = scored[:12]
    # qwen top6 短名单
    qwen_res = []
    for cand in short12[:6]:
        p = full_path(cand["sid"], cand["rel"])
        r = qwen_verify(p, cand["dur"], act, fam, f"q_{act}_{cand['media_id']}")
        cand.update(r)
        qwen_res.append(cand)
    passes = [c for c in qwen_res if c["verdict"] == "PASS"]
    summary[act] = {"ranked": len(ranked[act]), "probed_motion": len(scored),
                    "shortlist": len(short12), "qwen": len(qwen_res),
                    "tvrc_pass": len(passes), "final_top": [{"media_id": c["media_id"],
                                                              "subclip": [c["windows"][0]["subclip_start_s"],
                                                                          c["windows"][0]["subclip_end_s"]],
                                                              "dir": c.get("direction")} for c in passes]}
    final[act] = {"top3": [{"media_id": c["media_id"],
                            "window": [c["windows"][0]["subclip_start_s"], c["windows"][0]["subclip_end_s"]],
                            "score": c["score"], "motion_proxy": c["motion_proxy"],
                            "direction": c.get("direction"),
                            "rel": c["rel"][:100]} for c in passes[:3]],
                  "count": min(3, len(passes))}
    print(act, "pass", len(passes), flush=True)

json.dump({"summary": summary, "final_top3": final},
          open(OUT / "_v11_results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("V1.1 eligible done")
print(json.dumps({a: {"pass": s["tvrc_pass"], "top": s["final_top"]} for a, s in summary.items()}, ensure_ascii=False, indent=1))
