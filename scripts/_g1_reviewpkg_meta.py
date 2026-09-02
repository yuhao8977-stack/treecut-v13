# -*- coding: utf-8 -*-
"""G1: 45条 L3 审核包 — 元数据组装(机器角色行+L2候选+basename) + 时长探测(视频项)。"""
import json, sqlite3, subprocess, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
FFP = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffprobe.exe"
L3 = json.loads((OUT / "TREECUT_G1_L3_REVIEW_SUBSET_V1.json").read_text(encoding="utf-8"))["items"]
c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)

def role_row(eid):
    if eid is None:
        return {}
    r = c.execute("SELECT * FROM b007_source_role_v1 WHERE entity_kind='media_file' AND entity_id=?",
                  (str(eid),)).fetchone()
    if r is None:
        r = c.execute("SELECT * FROM b007_source_role_v1 WHERE entity_kind='b007_asset' AND entity_id=?",
                      (str(eid),)).fetchone()
    if r is None:
        return {}
    cols = [d[0] for d in c.execute("SELECT * FROM b007_source_role_v1 LIMIT 0").description]
    return dict(zip(cols, r))

def dur(path):
    if not path or not Path(path).exists():
        return None
    ext = Path(path).suffix.lower()
    if ext in (".jpg", ".jpeg", ".png", ".webp"):
        return "image"
    p = subprocess.run([FFP, "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, timeout=60)
    try:
        return float(p.stdout.decode().strip())
    except Exception:
        return None

meta = []
for it in L3:
    i = it["sample_idx"]
    rr = role_row(it["media_id"]) or role_row(it["asset_id"])
    path = it["full_path"]
    m = {"idx": i, "kind": it["kind"], "expectation": it["expectation"],
         "source_id": it["source_id"], "media_id": it["media_id"], "asset_id": it["asset_id"],
         "basename": Path(path).name if path else None,
         "source_role_candidate": rr.get("source_role") or it["initial_prior"],
         "machine": {"burned": rr.get("burned_subtitle_present"), "wm": rr.get("platform_watermark_present"),
                     "unrel": rr.get("unrelated_overlay_present"), "oldt": rr.get("old_title_overlay_present"),
                     "env": rr.get("environment_text_present"), "review": rr.get("review_status"),
                     "evidence": (rr.get("contamination_evidence") or "")[:160]},
         "qwen_l2": it.get("qwen_l2_candidate") or {},
         "why": it.get("why_in_subset"), "path": path}
    m["duration"] = dur(path)
    meta.append(m)

(OUT / "_g1_reviewpkg_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
imgs = sum(1 for m in meta if m["duration"] == "image")
vids = [m for m in meta if isinstance(m["duration"], float)]
print(f"meta: {len(meta)} items | images: {imgs} | videos with dur: {len(vids)} | no-dur: {sum(1 for m in meta if m['duration'] is None)}")
for m in meta[:3]:
    print(" ", m["idx"], m["kind"], m["basename"][:40], m["duration"], m["source_role_candidate"])
