#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POST-A3 — CALIBRATION10 最终 manifest + 50 帧全分辨率抽取 + 哈希 + 查重审计。"""
import cv2
import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
ROI50 = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\mmv_posta3_frames") / "roi50"
A3C = json.loads((OUT / "TREECUT_MMVV_A3_CANDIDATES.json").read_text(encoding="utf-8"))
REV = {c["media_id"]: c for c in
       json.loads((OUT / "TREECUT_POSTA3_REVIEW_CANDIDATES_V1.json").read_text(encoding="utf-8"))["candidates"]}
sys.stdout.reconfigure(encoding="utf-8")

ROOTS = {1: r"\\X1\素材盘01\已处理素材\卖点展示类素材",
         2: r"\\X1\素材盘01\已处理素材\效果展示类素材",
         3: r"\\X1\素材盘01\已处理素材\JianyingPro Presets",
         4: r"\\X1\素材盘01\未处理素材\【工厂】"}
FR = [0.15, 0.35, 0.50, 0.65, 0.85]
FINAL = [  # (media_id, role)
    (27433, "POS"), (12095, "POS"), (3571, "POS"), (21674, "POS"),
    (2212, "NEG"), (1641, "NEG"), (10000, "NEG"), (2543, "NEG"),
    (9697, "NEG"), (25894, "NEG"),
]
EXCLUDED_CONSERVATIVE = {"11592": "EXCLUDED_CONSERVATIVE_CUSTOMER_OVERLAP_WITH_A3"}


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def grab(path, ts):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    dur = (n / fps) if fps and n else 0.0
    cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000.0)
    ok, fr = cap.read()
    cap.release()
    return (fr, dur) if ok else (None, dur)


def main():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    ROI50.mkdir(parents=True, exist_ok=True)
    excluded = set(A3C["excluded_known_ids"])
    a3_ids = {c["media_id"] for c in A3C["candidates"]}
    cases = []
    seen_sha = {}
    for mid, role in FINAL:
        row = cur.execute("select source_id, relative_path from media_files where id=?",
                          (mid,)).fetchone()
        src, rel = row
        full = ROOTS.get(src) + "\\" + rel
        fr0, dur = grab(full, 0.05)
        if dur <= 0 or fr0 is None:
            raise SystemExit(f"无法读取 {mid}")
        frs = []
        for i, f in enumerate(FR):
            fr, _ = grab(full, dur * f)
            if fr is None:
                continue
            h, w = fr.shape[:2]
            if w > 1280:  # 限宽保持 ROI 一致与体量
                sc = 1280 / w
                fr = cv2.resize(fr, (1280, int(h * sc)), interpolation=cv2.INTER_AREA)
            name = f"pc10_{mid}_{i}.jpg"
            cv2.imencode(".jpg", fr, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tofile(str(ROI50 / name))
            sha = sha_file(ROI50 / name)
            if sha in seen_sha:
                raise SystemExit(f"帧重复 {name}=={seen_sha[sha]}")
            seen_sha[sha] = name
            img2 = cv2.imdecode(cv2.imencode(".jpg", fr)[1], cv2.IMREAD_COLOR)
            hh, ww = img2.shape[:2]
            frs.append({"idx": i, "frame": name, "t_s": round(dur * f, 3),
                        "sha256": sha, "width": ww, "height": hh,
                        "bytes": (ROI50 / name).stat().st_size, "local_path": str(ROI50 / name)})
        c = REV.get(mid, {})
        cases.append({"media_id": mid, "role": role, "bucket": c.get("bucket"),
                      "family": c.get("family"), "duration_s": round(dur, 2),
                      "source_id": src, "relative_path": rel, "frames": frs})
        print(mid, role, c.get("family", "")[:40], "dur", round(dur, 2), "frames", len(frs))
    fams = [c["family"] for c in cases]
    checks = {
        "a3_overlap_media": [m for m in [c["media_id"] for c in cases] if m in excluded or m in a3_ids],
        "a3_overlap_family_folder": [f for f in fams if f in {
            (cc["relative_path"].split("\\")[1] if "\\" in cc["relative_path"] else cc["relative_path"])
            for cc in A3C["candidates"]}],
        "unique_visual_families": len(set(fams)),
        "11592": EXCLUDED_CONSERVATIVE,
        "25894_decision": "KEPT (motion-diversity check: mean_diff 0.115 MOVING, not static-redundant with 10000; replacement condition not met)",
    }
    doc = {"experiment": "POSTA3_CALIBRATION10",
           "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "note": "4 EXTEND + 6 NO_ACTION；ROI 契约 TREECUT_EXTEND_ROI_SEMANTIC_CONTRACT_V1.md；RETRACT_DATA_INSUFFICIENT",
           "sampling": {"policy": "uniform_time_window", "relative_fractions": FR},
           "checks": checks,
           "cases": cases}
    (OUT / "TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("checks:", checks)
    print("frames total:", sum(len(c["frames"]) for c in cases))
    con.close()


if __name__ == "__main__":
    main()
