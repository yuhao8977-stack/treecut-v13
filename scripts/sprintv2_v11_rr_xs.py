# -*- coding: utf-8 -*-
"""V1.1 支线2/3: REVIEW_REQUIRED Top12/动作 verify→正规G1提升; 跨段边界漏斗(廉价先)→合并窗候选(qwen 小预算)。"""
import base64, cv2, json, numpy as np, sqlite3, subprocess, sys, time, urllib.request
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

def frame_diff(a_png, b_png):
    a = cv2.imdecode(np.fromfile(str(a_png), np.uint8), cv2.IMREAD_GRAYSCALE)
    b = cv2.imdecode(np.fromfile(str(b_png), np.uint8), cv2.IMREAD_GRAYSCALE)
    if a is None or b is None:
        return 0.0
    a = cv2.resize(a, (160, 240)); b = cv2.resize(b, (160, 240))
    return round(min(1.0, float(np.abs(a.astype(np.float32) - b.astype(np.float32)).mean()) / 40.0), 3)

c = sqlite3.connect(DB, timeout=60)
ACT_KW = {"EXTEND": ["伸缩", "变宽"], "RETRACT": ["伸缩"], "DRAWER_OPEN": ["薄抽", "抽屉"],
          "STORAGE_PUT_IN": ["收纳", "放置"], "SOCKET_INSERT": ["轨道插座", "插拔"]}
promoted_all = {}
for act, kws in ACT_KW.items():
    like = " OR ".join(["mf.relative_path LIKE ?"] * len(kws))
    rows = c.execute(
        f"""SELECT r.entity_id, mf.source_id, mf.relative_path, r.burned_subtitle_present,
                   r.platform_watermark_present
            FROM b007_source_role_v1 r JOIN media_files mf ON mf.id=r.entity_id
            WHERE r.entity_kind='media_file' AND r.review_status='REVIEW_REQUIRED'
              AND mf.source_id IN (1,2,4) AND ({like}) AND mf.extension='.mp4' LIMIT 120""",
        [f"%{k}%" for k in kws]).fetchall()
    pre = [r for r in rows if r[3] != "PRESENT" and r[4] != "PRESENT"][:12]
    done = []
    for eid, sid, rel, b, w in pre:
        ocr_p = c.execute(
            "SELECT count(*) FROM ocr_text o JOIN assets a ON a.asset_id=o.asset_id WHERE a.media_id=? "
            "AND (o.text LIKE '%小红书%' OR o.text LIKE '%关注%' OR o.text LIKE '%@%')", (int(eid),)).fetchone()[0]
        if ocr_p > 0:
            done.append({"media_id": eid, "result": "DIRTY_SIGNAL"})
            continue
        ev = json.loads(c.execute("SELECT contamination_evidence FROM b007_source_role_v1 "
                                  "WHERE entity_kind='media_file' AND entity_id=?", (str(eid),)).fetchone()[0] or "[]")
        ev.append({"recovery_v11": {"verify": "CLEAN", "at": time.strftime("%Y-%m-%d %H:%M:%S")}})
        c.execute("UPDATE b007_source_role_v1 SET review_status='APPROVED', contamination_evidence=?, "
                  "role_version=role_version+1, updated_at=? WHERE entity_kind='media_file' AND entity_id=?",
                  (json.dumps(ev, ensure_ascii=False), time.time(), str(eid)))
        done.append({"media_id": eid, "result": "PROMOTED_ELIGIBLE", "rel": rel[:80]})
        print("RR promote", act, eid, flush=True)
    c.commit()
    promoted_all[act] = done
json.dump(promoted_all, open(OUT / "_v11_rr_promote.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("RR promoted:", {a: sum(1 for x in v if x.get("result") == "PROMOTED_ELIGIBLE") for a, v in promoted_all.items()})

# ============ 支线3: 跨段边界漏斗(廉价先) ============
# 读取既有跨段结构候选 + 只保留 出现在动作家族关键词 rel 中的资产 以聚焦
xs = json.loads((OUT / "TREECUT_CROSS_SEGMENT_ACTION_RECOVERY_V1.json").read_text(encoding="utf-8"))["candidates"]
KW = ["伸缩", "薄抽", "抽屉", "轨道插座", "收纳", "插拔"]
relmap = {}
for cand in xs:
    relmap.setdefault(cand["media_id"], cand["rel"])
focus = [x for x in xs if any(k in (x.get("rel") or "") for k in KW)][:40]
print("crossseg focused:", len(focus))
# 边界帧差(连续性): segA 尾帧 vs segB 头帧 → 高差=切镜(排除), 低差含运动=合并候选
c2 = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
mid_src = {}
for r in c2.execute("SELECT mf.id, mf.source_id, mf.relative_path FROM media_files mf WHERE mf.extension='.mp4'"):
    mid_src[r[0]] = (r[1], r[2])
merged_scored = []
for cand in focus:
    mid = cand["media_id"]
    if mid not in mid_src:
        continue
    sid, rel = mid_src[mid]
    path = str(Path(SRC[sid]) / rel)
    if not Path(path).exists():
        continue
    a_end = (cand["seg_a_ms"][1] or 0) / 1000.0 - 0.1
    b_start = (cand["seg_b_ms"][0] or 0) / 1000.0 + 0.1
    tag = f"xs_{mid}"
    pa = frame_at(path, max(0.0, a_end), tag + "_a")
    pb = frame_at(path, b_start, tag + "_b")
    if pa is None or pb is None:
        if pa:
            pa.unlink(missing_ok=True)
        if pb:
            pb.unlink(missing_ok=True)
        continue
    d = frame_diff(pa, pb)
    pa.unlink(missing_ok=True); pb.unlink(missing_ok=True)
    merged_scored.append({"media_id": mid, "merged_window_ms": cand["merged_window_ms"],
                          "gap_ms": cand["gap_ms"], "boundary_diff": d,
                          "rel": rel[:90],
                          "continuity_proxy": "continuous" if d < 0.35 else "likely_cut"})
merged_scored.sort(key=lambda x: x["boundary_diff"])
json.dump({"focused_pairs": len(focus), "scored": merged_scored[:60]},
          open(OUT / "_v11_crossseg_scored.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("crossseg scored:", len(merged_scored), "| low-diff(合并候选优先):",
      sum(1 for x in merged_scored if x["continuity_proxy"] == "continuous"))
