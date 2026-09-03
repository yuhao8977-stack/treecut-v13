# -*- coding: utf-8 -*-
"""有界展开检索: 对 5 个高价值动作从 Eligible 池找未探测新素材, 3帧状态+必要时1方向帧, 产出新窗口。"""
import base64, json, sqlite3, subprocess, sys, urllib.request
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
FF = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
FFP = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffprobe.exe"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
FR = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\g2x_frames")
FR.mkdir(parents=True, exist_ok=True)
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
SRC = {1: r"\\X1\素材盘01\已处理素材\卖点展示类素材", 2: r"\\X1\素材盘01\已处理素材\效果展示类素材",
       4: r"\\X1\素材盘01\未处理素材\【工厂】"}
SYS = r"C:\Users\admin\github\treecut-v13\src"
sys.path.insert(0, SYS)
from treecut.services.action_subclip import parse_qwen_state, build_windows, apply_action_gate, parse_direction, fit_duration

ACT_PLAN = {
    "EXTEND": {"kw": ["伸缩桌面", "岛台伸缩", "伸缩60", "变宽"], "state_q": "EXTEND_STATE",
               "dir_q": "EXTEND/RETRACT"},
    "RETRACT": {"kw": ["伸缩桌面", "岛台伸缩"], "state_q": "EXTEND_STATE", "dir_q": "EXTEND/RETRACT"},
    "DRAWER_OPEN": {"kw": ["薄抽", "下层抽屉", "抽屉抽拉"], "state_q": "DRAWER_STATE", "dir_q": "DRAWER_OPEN/DRAWER_CLOSE"},
    "SOCKET_INSERT": {"kw": ["轨道插座", "插上", "插拔"], "state_q": "SOCKET_STATE", "dir_q": "SOCKET_INSERT/SOCKET_REMOVE"},
    "STORAGE_PUT_IN": {"kw": ["收纳", "放东西", "分区收纳"], "state_q": "STORAGE_STATE", "dir_q": "STORAGE_PUT_IN/STORAGE_TAKE_OUT"},
}
Q_STATE = {
    "EXTEND_STATE": ("这一帧中, 可伸缩桌面是否正在被拉出/收回移动? state=NOT_PRESENT|OBJECT_PRESENT|"
                     "ACTION_START|ACTION_IN_PROGRESS|ACTION_END; object=桌面/轨道插座/其他; desc=一句话"),
    "DRAWER_STATE": ("这一帧中, 抽屉是否正在被拉开或推回? state=NOT_PRESENT|OBJECT_PRESENT(可见未动)|"
                     "ACTION_START|ACTION_IN_PROGRESS|ACTION_END; object=抽屉; desc=一句话"),
    "SOCKET_STATE": ("这一帧中, 是否正在插拔/移动插座模块? state=NOT_PRESENT|OBJECT_PRESENT|"
                     "ACTION_START|ACTION_IN_PROGRESS|ACTION_END; object=插座/插头; desc=一句话"),
    "STORAGE_STATE": ("这一帧中, 是否正在把物品放入或取出收纳? state=NOT_PRESENT|OBJECT_PRESENT|"
                      "ACTION_START|ACTION_IN_PROGRESS|ACTION_END; object=抽屉/柜/物品; desc=一句话"),
}
Q_DIR = {
    "EXTEND/RETRACT": "此刻动作是 direction=EXTEND(正在展开) / RETRACT(正在收回) / STATIC / UNCERTAIN?",
    "DRAWER_OPEN/DRAWER_CLOSE": "此刻动作是 direction=DRAWER_OPEN(正在拉开) / DRAWER_CLOSE(正在推回) / STATIC / UNCERTAIN?",
    "SOCKET_INSERT/SOCKET_REMOVE": "此刻动作是 direction=SOCKET_INSERT(插入) / SOCKET_REMOVE(拔出) / STATIC / UNCERTAIN?",
    "STORAGE_PUT_IN/STORAGE_TAKE_OUT": "此刻动作是 direction=STORAGE_PUT_IN(放入) / STORAGE_TAKE_OUT(取出) / STATIC / UNCERTAIN?",
}
EVIDENCE = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db")
probed = {m["media_id"] for m in json.loads((OUT / "_g2_probe_manifest.json").read_text(encoding="utf-8"))}
extra = {}
p = OUT / "_g2_extra_inventory.json"
if p.exists():
    for v in json.loads(p.read_text(encoding="utf-8")).values():
        for it in v:
            extra[it["media_id"]] = it["rel"]

def ask(b64, q):
    body = json.dumps({"model": "qwen2.5vl:7b", "stream": False, "options": {"temperature": 0.0},
                       "messages": [{"role": "user", "content": q, "images": [b64]}]}).encode()
    req = urllib.request.Request("http://localhost:11434/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.loads(r.read().decode("utf-8"))["message"]["content"]

def _probe_one(act, plan, mid, sid, rel):
    """探测单个资产: 3 状态帧 + 1 方向帧 → 门过滤 → 窗口列表。"""
    full = str(Path(SRC[sid]) / rel)
    dur = float(subprocess.run([FFP, "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", full], capture_output=True, timeout=60).stdout.decode().strip())
    st_ev = []
    for frac in (0.15, 0.50, 0.85):
        t = round(frac * dur, 2)
        png = FR / f"x_{act}_{mid}_{frac}.jpg"
        subprocess.run([FF, "-y", "-ss", str(t), "-i", full, "-frames:v", "1", "-vf", "scale=480:-2", str(png)],
                       capture_output=True, timeout=90)
        if not png.exists() or png.stat().st_size <= 5000:
            continue
        raw = ask(base64.b64encode(png.read_bytes()).decode(), Q_STATE[plan["state_q"]])
        st_ev.append({"t_s": t, "state": parse_qwen_state(raw), "qwen_l2_raw": raw, "media_id": mid})
    actn = [e for e in st_ev if e["state"] in ("ACTION_START", "ACTION_IN_PROGRESS", "ACTION_END")]
    if len(actn) < 2:
        return []
    mid_t = sorted(e["t_s"] for e in actn)[len(actn) // 2]
    png = FR / f"xd_{act}_{mid}.jpg"
    subprocess.run([FF, "-y", "-ss", str(mid_t), "-i", full, "-frames:v", "1", "-vf", "scale=480:-2", str(png)],
                   capture_output=True, timeout=90)
    rawdir = ""
    if png.exists() and png.stat().st_size > 5000:
        rawdir = ask(base64.b64encode(png.read_bytes()).decode(), Q_DIR[plan["dir_q"]])
    direction = parse_direction(rawdir)
    for e in st_ev:
        e["state"] = parse_qwen_state(e.get("qwen_l2_raw") or "")
    ev_full = st_ev + ([] if not rawdir else
                       [{"t_s": mid_t, "qwen_l2_raw": rawdir, "direction_probe": True, "media_id": mid}])
    wins = apply_action_gate(build_windows(st_ev, dur, act, media_id=mid, asset_path=full), ev_full)
    out = []
    for w in wins:
        w = fit_duration(w, 3.0, "action")
        wd = w.to_dict()
        wd["media_id"] = mid
        wd["rel"] = rel[:100]
        wd["group"] = f"EXPAND_{act}"
        wd["expand_source"] = True
        out.append(wd)
    return out


c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
new_win = []
summary = {}
for act, plan in ACT_PLAN.items():
    like = " OR ".join(["mf.relative_path LIKE ?"] * len(plan["kw"]))
    rows = c.execute(
        f"""SELECT DISTINCT mf.id, mf.source_id, mf.relative_path FROM media_files mf
            WHERE mf.source_id IN (1,2,4) AND mf.extension='.mp4' AND ({like})
            AND mf.id IN (SELECT r.entity_id FROM b007_source_role_v1 r WHERE r.entity_kind='media_file'
              AND r.source_role IN ('PRODUCTION_CLEAN_RAW','PRODUCTION_CLEAN_SEMI')
              AND r.review_status!='REJECTED'
              AND (r.review_status='APPROVED' OR (r.burned_subtitle_present='ABSENT'
                AND r.platform_watermark_present='ABSENT' AND r.unrelated_overlay_present='ABSENT'
                AND r.old_title_overlay_present='ABSENT' AND r.brand_overlay_present='ABSENT')))
            LIMIT 8""", [f"%{k}%" for k in plan["kw"]]).fetchall()
    picked = [r for r in rows if r[0] not in probed][:3]
    found = 0
    for mid, sid, rel in picked:
        try:
            res = _probe_one(act, plan, mid, sid, rel)
        except Exception as ex:
            import traceback
            print(act, mid, "ERR", str(ex)[:150], flush=True)
            traceback.print_exc()
            continue
        new_win.extend(res)
        found += len(res)
        json.dump({"windows": new_win, "summary": summary},
                  open(OUT / "_g2_expand_results.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(act, "mid", mid, "kept", len(res), flush=True)
    summary[act] = {"searched": len(picked), "found_windows": found}
print("expand summary:", json.dumps(summary, ensure_ascii=False))
json.dump({"windows": new_win, "summary": summary},
          open(OUT / "_g2_expand_results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("expand total windows:", len(new_win))
