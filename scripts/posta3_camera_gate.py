#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POST-A3 — CAM gate v1（优化版：单开视频+帧缓存；SPARSE vs BRIDGE_500/250；720 宽）。"""
import json
import sqlite3
import sys
import time
from pathlib import Path

import cv2
import numpy as np

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
sys.path.insert(0, str(REPO / "src"))
from treecut.services.mmv_camera_diag import estimate_camera_background  # noqa: E402
sys.stdout.reconfigure(encoding="utf-8")

ROOTS = {1: r"\\X1\素材盘01\已处理素材\卖点展示类素材",
         2: r"\\X1\素材盘01\已处理素材\效果展示类素材",
         3: r"\\X1\素材盘01\已处理素材\JianyingPro Presets",
         4: r"\\X1\素材盘01\未处理素材\【工厂】"}
BRIDGE = {"BRIDGE_500": 0.5, "BRIDGE_250": 0.25}
WMAX = 720


class Video:
    def __init__(self, path):
        self.path = path
        self.cap = cv2.VideoCapture(path)
        self.cache = {}
        self.ok = self.cap.isOpened()

    def frame(self, ts):
        key = round(ts, 3)
        if key in self.cache:
            return self.cache[key]
        if not self.cap.isOpened():
            return None
        self.cap.set(cv2.CAP_PROP_POS_MSEC, key * 1000.0)
        ok, fr = self.cap.read()
        fr = None if not ok else fr
        if fr is not None:
            h, w = fr.shape[:2]
            if w > WMAX:
                fr = cv2.resize(fr, (WMAX, int(h * WMAX / w)), interpolation=cv2.INTER_AREA)
        self.cache[key] = fr
        return fr

    def close(self):
        if self.cap:
            self.cap.release()


def est(a, b, excl):
    out = estimate_camera_background(a, b, excl, mode="background")
    return bool(out.get("chosen_model") and out.get("pair_state") == "SAME_SCENE"), out


def main():
    man = json.loads((OUT / "TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json").read_text(encoding="utf-8"))
    roi = json.loads((OUT / "TREECUT_POSTA3_HUMAN_ROI_V1.json").read_text(encoding="utf-8"))["annotations"]
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    out = {"experiment": "TREECUT_POSTA3_CAMERA_GATE_V1",
           "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "note": "前景排除=除 ISLAND_BODY 外全部人工框；bridge=逐段可建模率(compose 待下版)；宽<=720；125ms 后补",
           "cases": []}
    cnt = {m: [] for m in ["SPARSE_DIRECT", "BRIDGE_500", "BRIDGE_250"]}
    for c in man["cases"]:
        mid = c["media_id"]
        row = cur.execute("select source_id, relative_path from media_files where id=?", (mid,)).fetchone()
        src_path = ROOTS.get(row[0]) + "\\" + row[1]
        v = Video(src_path)
        ts = [f["t_s"] for f in c["frames"]]
        # 预取所有需要的时间点（语义帧 + bridge 中间帧）
        need = set(ts)
        for i in range(len(ts) - 1):
            for step in BRIDGE.values():
                need.update(np.arange(ts[i], ts[i + 1] + 1e-9, step).tolist())
        for t in sorted(need):
            v.frame(t)
        case_res = {"media_id": mid, "role": c["role"], "pairs": []}
        for i in range(len(ts) - 1):
            t0, t1 = ts[i], ts[i + 1]
            fa = v.frame(t0)
            fb = v.frame(t1)
            pair = {"pair": f"{t0}->{t1}"}
            if fa is None or fb is None:
                pair["error"] = "frame read fail"
                case_res["pairs"].append(pair)
                continue
            def excl_at(t):
                return [list(a["bbox_pixel"]) for a in roi
                        if a["media_id"] == mid and a["frame_timestamp"] == t
                        and a["object_name"] != "ISLAND_BODY"]
            ok0, d0 = est(fa, fb, excl_at(t0))
            pair["SPARSE_DIRECT"] = {"reliable": ok0, "pair_state": d0.get("pair_state"),
                                     "model": d0.get("chosen_model"), "residual": d0.get("residual"),
                                     "tracks": d0.get("tracked_count")}
            cnt["SPARSE_DIRECT"].append(1 if ok0 else 0)
            gap = t1 - t0
            for name, step in BRIDGE.items():
                if gap < step * 2:
                    pair[name] = {"skipped": True}
                    continue
                tt = np.arange(t0, t1 + 1e-9, step)
                allok = True
                nseg = 0
                for j in range(len(tt) - 1):
                    ga_ = v.frame(float(tt[j]))
                    gb_ = v.frame(float(tt[j + 1]))
                    okj, _ = est(ga_, gb_, excl_at(float(tt[j])))
                    nseg += 1
                    if not okj:
                        allok = False
                        break
                pair[name] = {"segments": nseg, "all_segments_ok": allok}
                if not pair[name].get("skipped"):
                    cnt[name].append(1 if allok else 0)
            case_res["pairs"].append(pair)
        v.close()
        out["cases"].append(case_res)
        s = {k: sum(vv) for k, vv in cnt.items()}
        print(mid, c["role"], "sparse", s["SPARSE_DIRECT"], "b500", s["BRIDGE_500"],
              "b250", s["BRIDGE_250"])
    rates = {k: round(sum(vv) / len(vv), 3) for k, vv in cnt.items() if vv}
    out["reliability_rates"] = rates
    out["gate_80pct"] = all(r >= 0.8 for r in rates.values() if r is not None)
    (OUT / "TREECUT_POSTA3_CAMERA_GATE_V1.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("RATES:", rates)
    print("gate>=80%:", out["gate_80pct"])
    con.close()


if __name__ == "__main__":
    main()
