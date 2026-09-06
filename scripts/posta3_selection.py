#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POST-A3 — 依人工 ACTION GT 生成 calibration 入选组合（12，家族独立）。"""
import json
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
sys.stdout.reconfigure(encoding="utf-8")


def main():
    cand = {c["media_id"]: c for c in
            json.loads((OUT / "TREECUT_POSTA3_REVIEW_CANDIDATES_V1.json").read_text(encoding="utf-8"))["candidates"]}
    gt = json.loads((OUT / "TREECUT_POSTA3_HUMAN_REVIEW_V1.json").read_text(encoding="utf-8"))["verdicts"]
    pos = [int(m) for m, x in gt.items() if x["label"] == "EXTEND"]
    neg = [int(m) for m, x in gt.items() if x["label"] == "NO_ACTION"]
    print("pos", len(pos), "neg", len(neg))
    # 家族去重选择：pos 取 4、neg 取 4（neg 覆盖 static/socket/leg/extend-bucket-但无动作 多样）
    def pick(ids, want):
        seen, out = set(), []
        for m in sorted(ids, key=lambda i: -(cand[i]["duration_s"] or 0)):
            f = cand[m]["family"]
            if f in seen:
                continue
            seen.add(f)
            out.append(m)
            if len(out) >= want:
                break
        return out
    pos4 = pick(pos, 4)
    # neg: 尽量含 LEG/SOCKET/STATIC/EXTEND-无动作 各一
    neg_pool = sorted(neg, key=lambda i: cand[i]["bucket"])
    neg4 = []
    want_buckets = ["INTERFERENCE_LEG", "INTERFERENCE_SOCKET", "STATIC", "EXTEND"]
    used = set()
    for b in want_buckets:
        for m in neg_pool:
            if cand[m]["bucket"] == b and cand[m]["family"] not in used and m not in used:
                neg4.append(m)
                used.add(cand[m]["family"])
                used.add(m)
                break
    for m in neg_pool:
        if len(neg4) >= 4:
            break
        if cand[m]["family"] not in used and m not in used:
            neg4.append(m)
            used.add(cand[m]["family"])
    selected = pos4 + neg4
    doc = {"experiment": "TREECUT_POSTA3_CALIBRATION_SELECTION_V1",
           "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "note": "由人工 ACTION GT 派生；RETRACT_DATA_INSUFFICIENT(无素材被判 RETRACT)已记录",
           "gt_summary": {"EXTEND": len(pos), "NO_ACTION": len(neg), "RETRACT": 0},
           "selected_EXTEND": pos4, "selected_NO_ACTION": neg4,
           "cases": [{"media_id": m, "role": ("POS" if m in pos4 else "NEG"),
                      "bucket": cand[m]["bucket"], "family": cand[m]["family"],
                      "duration_s": cand[m]["duration_s"]} for m in selected]}
    (OUT / "TREECUT_POSTA3_CALIBRATION_SELECTION_V1.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    for c in doc["cases"]:
        print(f"  {c['media_id']} {c['role']:3s} {c['bucket']:20s} {c['family'][:40]}")
    print("total selected:", len(selected))


if __name__ == "__main__":
    main()
