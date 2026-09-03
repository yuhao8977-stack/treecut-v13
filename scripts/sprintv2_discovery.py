# -*- coding: utf-8 -*-
"""Candidate Discovery Recovery V1: 分层漏斗(非Top3)验证 Recall。
A 宽召回(已有) → B 廉价过滤(采样≤10/动作) → C 3帧运动代理(ffmpeg帧差) → D qwen(仅运动高/歧义≤4) →
E TVRC(动作门) → 逐动作指标。REVIEW_REQUIRED 定向恢复 + 跨段合并候选 单独落盘。
""" 
import base64, cv2, json, numpy as np, sqlite3, subprocess, sys, time, urllib.request
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
FR = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\disc_frames")
FR.mkdir(parents=True, exist_ok=True)
FF = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
FFP = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffprobe.exe"
SRC = {1: r"\\X1\素材盘01\已处理素材\卖点展示类素材", 2: r"\\X1\素材盘01\已处理素材\效果展示类素材",
       4: r"\\X1\素材盘01\未处理素材\【工厂】"}
SYS = r"C:\Users\admin\github\treecut-v13\src"
sys.path.insert(0, SYS)
from treecut.services.action_subclip import parse_qwen_state, build_windows, apply_action_gate, parse_direction, fit_duration

ELIG = ("r.source_role IN ('PRODUCTION_CLEAN_RAW','PRODUCTION_CLEAN_SEMI') AND r.review_status!='REJECTED' "
        "AND (r.review_status='APPROVED' OR (r.burned_subtitle_present='ABSENT' "
        "AND r.platform_watermark_present='ABSENT' AND r.unrelated_overlay_present='ABSENT' "
        "AND r.old_title_overlay_present='ABSENT' AND r.brand_overlay_present='ABSENT'))")
PLAN = {
    "EXTEND": {"path": ["伸缩", "变宽"], "state_q": "EXT", "dir_q": "EXTEND/RETRACT", "sample": 10, "qwen_n": 4},
    "RETRACT": {"path": ["伸缩"], "state_q": "EXT", "dir_q": "EXTEND/RETRACT", "sample": 10, "qwen_n": 4, "from_extend_pool": True},
    "DRAWER_OPEN": {"path": ["薄抽", "抽屉"], "state_q": "DRW", "dir_q": "DRAWER_OPEN/DRAWER_CLOSE", "sample": 10, "qwen_n": 4},
    "STORAGE_PUT_IN": {"path": ["收纳", "放置"], "state_q": "STO", "dir_q": "STORAGE_PUT_IN/STORAGE_TAKE_OUT", "sample": 10, "qwen_n": 4},
    "SOCKET_INSERT": {"path": ["轨道插座"], "state_q": "SKT", "dir_q": "SOCKET_INSERT/SOCKET_REMOVE", "sample": 10, "qwen_n": 4},
}
Q_STATE = {
    "EXT": "这一帧: 可伸缩桌面是否正在移动(拉出/收回)? state=NOT_PRESENT|OBJECT_PRESENT|ACTION_START|ACTION_IN_PROGRESS|ACTION_END; object=桌面/轨道插座/其他; desc=一句",
    "DRW": "这一帧: 抽屉是否正在被拉开或推回? state=NOT_PRESENT|OBJECT_PRESENT|ACTION_START|ACTION_IN_PROGRESS|ACTION_END; object=抽屉; desc=一句",
    "STO": "这一帧: 是否正在放/取物品入收纳? state=NOT_PRESENT|OBJECT_PRESENT|ACTION_START|ACTION_IN_PROGRESS|ACTION_END; object=抽屉/柜/物品; desc=一句",
    "SKT": "这一帧: 是否正在插拔/操作插座模块? state=NOT_PRESENT|OBJECT_PRESENT|ACTION_START|ACTION_IN_PROGRESS|ACTION_END; object=插座/插头; desc=一句",
}
Q_DIR = {
    "EXTEND/RETRACT": "direction=EXTEND(展开) / RETRACT(收回) / STATIC / UNCERTAIN?",
    "DRAWER_OPEN/DRAWER_CLOSE": "direction=DRAWER_OPEN(拉开) / DRAWER_CLOSE(推回) / STATIC / UNCERTAIN?",
    "STORAGE_PUT_IN/STORAGE_TAKE_OUT": "direction=STORAGE_PUT_IN(放入) / STORAGE_TAKE_OUT(取出) / STATIC / UNCERTAIN?",
    "SOCKET_INSERT/SOCKET_REMOVE": "direction=SOCKET_INSERT(插入) / SOCKET_REMOVE(拔出) / STATIC / UNCERTAIN?",
}
# 已探测(负例记忆+既有候选集)排除, 专注新召回
prob = {m["media_id"] for m in json.loads((OUT / "_g2_probe_manifest.json").read_text(encoding="utf-8"))}
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

def frame(path, t, tag):
    png = FR / f"{tag}.jpg"
    subprocess.run([FF, "-y", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1", "-vf", "scale=320:-2", str(png)],
                   capture_output=True, timeout=90)
    return png if png.exists() and png.stat().st_size > 2000 else None

def motion_proxy(path, dur):
    """3帧帧差均值 → 运动代理(0~1)。"""
    ts = [0.25 * dur, 0.5 * dur, 0.75 * dur]
    ims = []
    for i, t in enumerate(ts):
        png = frame(path, t, f"mp_{abs(hash(path))%10**8}_{i}")
        if png is None:
            continue
        im = cv2.imdecode(np.fromfile(str(png), np.uint8), cv2.IMREAD_GRAYSCALE)
        if im is not None:
            ims.append(cv2.resize(im, (160, 240)))
        png.unlink(missing_ok=True)
    if len(ims) < 2:
        return 0.0
    d = sum(float(np.abs(ims[i] - ims[i + 1]).mean()) for i in range(len(ims) - 1)) / (len(ims) - 1)
    return round(min(1.0, d / 40.0), 3)

c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
summary_all = {}
cands_all = []
for act, plan in PLAN.items():
    like = " OR ".join(["mf.relative_path LIKE ?"] * len(plan["path"]))
    rows = c.execute(
        f"SELECT DISTINCT mf.id, mf.source_id, mf.relative_path FROM media_files mf "
        f"WHERE mf.source_id IN (1,2,4) AND mf.extension='.mp4' AND ({like}) AND "
        f"mf.id IN (SELECT r.entity_id FROM b007_source_role_v1 r WHERE r.entity_kind='media_file' AND {ELIG}) "
        f"ORDER BY mf.id LIMIT 400", [f"%{k}%" for k in plan["path"]]).fetchall()
    cands = [r for r in rows if r[0] not in prob]
    # B: 廉价过滤(非Top3): 全量计数 + 随机种子采样(验证"库里是否有")
    broad = len(cands)
    import random
    random.seed(20260903 + hash(act) % 1000)
    sample = random.sample(cands, min(plan["sample"], len(cands)))
    # C: 运动代理
    scored = []
    for mid, sid, rel in sample:
        full = str(Path(SRC[sid]) / rel)
        dur = 0.0
        try:
            dur = float(subprocess.run([FFP, "-v", "error", "-show_entries", "format=duration",
                                        "-of", "csv=p=0", full], capture_output=True, timeout=60).stdout.decode().strip())
        except Exception:
            continue
        mp = motion_proxy(full, dur)
        scored.append({"media_id": mid, "sid": sid, "rel": rel[:90], "dur": round(dur, 1),
                       "motion_proxy": mp})
    scored.sort(key=lambda x: -x["motion_proxy"])
    # D: qwen 仅 motion 高 top_n
    qwen_top = scored[: plan["qwen_n"]]
    valid = []
    for sc in qwen_top:
        full = str(Path(SRC[sc["sid"]]) / sc["rel"])
        dur = sc["dur"]
        st_ev = []
        for frac in (0.2, 0.5, 0.8):
            png = frame(full, frac * dur, f"q_{act}_{sc['media_id']}_{frac}")
            if png is None:
                continue
            raw = ask(base64.b64encode(png.read_bytes()).decode(), Q_STATE[plan["state_q"]])
            png.unlink(missing_ok=True)
            st_ev.append({"t_s": round(frac * dur, 2), "state": parse_qwen_state(raw),
                          "qwen_l2_raw": raw, "media_id": sc["media_id"]})
        actn = [e for e in st_ev if e["state"] in ("ACTION_START", "ACTION_IN_PROGRESS", "ACTION_END")]
        if len(actn) < 2:
            sc["qwen_verdict"] = "NO_ACTION_STATE"
            continue
        mid_t = sorted(e["t_s"] for e in actn)[len(actn) // 2]
        png = frame(full, mid_t, f"qd_{act}_{sc['media_id']}")
        rawdir = ask(base64.b64encode(png.read_bytes()).decode(), Q_DIR[plan["dir_q"]]) if png else ""
        if png:
            png.unlink(missing_ok=True)
        ev_full = st_ev + ([{"t_s": mid_t, "qwen_l2_raw": rawdir, "direction_probe": True,
                             "media_id": sc["media_id"]}] if rawdir else [])
        wins = apply_action_gate(build_windows(st_ev, dur, act, media_id=sc["media_id"], asset_path=full), ev_full)
        wins = [fit_duration(w, 3.0, "action") for w in wins]
        sc["direction"] = parse_direction(rawdir)
        sc["windows"] = [w.to_dict() for w in wins]
        sc["tvrc"] = "PASS" if wins else "FAIL"
        if wins:
            valid.append(sc)
        print(act, "mid", sc["media_id"], "mp", sc["motion_proxy"], "dir", sc["direction"],
              "tvrc", sc["tvrc"], flush=True)
    summary_all[act] = {"broad_eligible_union": broad, "cheap_sample": len(scored),
                        "motion_high_shortlist": len(qwen_top), "qwen_reviewed": len(qwen_top),
                        "tvrc_pass": len(valid), "tvrc_fail": sum(1 for s in qwen_top if s.get("tvrc") == "FAIL"),
                        "note": "样本非穷举; broad 池仍数百, 若样本有命中则证明 Recall 存在"}
    cands_all.extend([{"action": act, **{k: v for k, v in s.items() if k != "windows"},
                       "windows": s.get("windows", [])} for s in scored])
    json.dump({"metrics": summary_all, "candidates": cands_all},
              open(OUT / "_g2_discovery_progress.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump({"metrics": summary_all, "candidates": cands_all},
          open(OUT / "_g2_discovery_progress.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("DISCOVERY DONE")
print(json.dumps(summary_all, ensure_ascii=False, indent=1))
