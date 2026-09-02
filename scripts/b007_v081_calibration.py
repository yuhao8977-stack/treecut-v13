# -*- coding: utf-8 -*-
"""V0.8.1 — CALIBRATION40 选择：每条视频 2 段（OPENING + HIGH_INFORMATION），A-F 全覆盖。"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

DATA_ROOT = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = DATA_ROOT / "database" / "materials.db"
MANIFEST = Path(r"C:\Users\admin\github\treecut-v13\reports\storage\B007_SAMPLE20_V1.json")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")


def q(c, sql, args=()):
    return c.execute(sql, args).fetchall()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    samples = {s["note_id"]: s for s in manifest["samples"]}
    c = sqlite3.connect("file:" + str(DB).replace("\\", "/") + "?mode=ro", uri=True)

    # per-note data
    segs = {}
    for r in q(c, "SELECT note_id, seg_no, start_ms, end_ms, duration_ms FROM b007_segment_v1 ORDER BY note_id, seg_no"):
        segs.setdefault(r[0], []).append({"seg_no": r[1], "start_ms": r[2], "end_ms": r[3], "duration_ms": r[4]})
    asr = {}
    for r in q(c, "SELECT note_id, start_ms, end_ms, text FROM b007_asr_v1"):
        asr.setdefault(r[0], []).append({"start_ms": r[1], "end_ms": r[2], "text": r[3] or ""})
    ocr = {}
    for r in q(c, "SELECT note_id, frame_timestamp_ms, text, subtitle_flag FROM b007_ocr_v1"):
        ocr.setdefault(r[0], []).append({"ts": r[1], "text": r[2] or "", "sub": r[3]})
    cog = {}
    for r in q(c, "SELECT note_id, seg_no, claims_json FROM b007_business_cognition_v1"):
        try:
            claims = json.loads(r[2])
        except Exception:
            claims = []
        cog.setdefault(r[0], {})[r[1]] = claims
    vis = {}
    for r in q(c, "SELECT note_id, frame_timestamp_ms, scene_family FROM b007_visual_evidence_v1"):
        vis.setdefault(r[0], []).append({"ts": r[1], "fam": r[2]})
    c.close()

    def seg_asr_chars(nid, s):
        return sum(len(a["text"]) for a in asr.get(nid, []) if a["start_ms"] < s["end_ms"] and a["end_ms"] > s["start_ms"])

    def seg_ocr_count(nid, s):
        return sum(1 for o in ocr.get(nid, []) if s["start_ms"] <= o["ts"] < s["end_ms"])

    def seg_claims(nid, s):
        return len(cog.get(nid, {}).get(s["seg_no"], []))

    def seg_scene_known(nid, s):
        fams = [v["fam"] for v in vis.get(nid, []) if s["start_ms"] <= v["ts"] < s["end_ms"]]
        return sum(1 for f in fams if f in ("FACTORY", "CUSTOMER_HOME", "SHOWROOM", "INSTALLATION_SITE"))

    items = []
    for nid, sample in samples.items():
        ssegs = segs.get(nid, [])
        if not ssegs:
            continue
        # OPENING: 实际首段（覆盖 0~5s 优先）
        opening = min(ssegs, key=lambda s: s["start_ms"])
        opening_role = "OPENING_SEGMENT"
        opening_reason = f"first segment start={opening['start_ms']}ms (0~{opening['end_ms']}ms)"
        # HIGH_INFORMATION: 非 opening 中信息量最高（ASR 字符 + OCR 数×5 + claims + scene_known×3）
        def score(s):
            return (seg_asr_chars(nid, s) + seg_ocr_count(nid, s) * 5
                    + seg_claims(nid, s) * 3 + seg_scene_known(nid, s) * 3)
        candidates = [s for s in ssegs if s["seg_no"] != opening["seg_no"]]
        if not candidates:
            candidates = ssegs
        high = max(candidates, key=lambda s: (score(s), s["duration_ms"]))
        if high["seg_no"] == opening["seg_no"] and len(ssegs) > 1:
            high = sorted(candidates, key=lambda s: score(s), reverse=True)[0]
        high_role = "HIGH_INFORMATION_SEGMENT"
        high_reason = (f"ASR={seg_asr_chars(nid, high)}ch OCR={seg_ocr_count(nid, high)} "
                       f"claims={seg_claims(nid, high)} scene_known={seg_scene_known(nid, high)}")
        for s, role, reason in ((opening, opening_role, opening_reason), (high, high_role, high_reason)):
            items.append({
                "segment_id": f"b007:{nid}:{s['seg_no']}", "sample_id": sample["sample_id"],
                "note_id": nid, "stratum": sample.get("primary_stratum"),
                "seg_no": s["seg_no"], "start_ms": s["start_ms"], "end_ms": s["end_ms"],
                "duration_ms": s["duration_ms"], "selection_role": role, "selection_reason": reason,
            })

    # 校验：20 视频 × 2，A-F 全覆盖
    notes = set(i["note_id"] for i in items)
    strata = set(i["stratum"] for i in items)
    openings = sum(1 for i in items if i["selection_role"] == "OPENING_SEGMENT")
    highs = sum(1 for i in items if i["selection_role"] == "HIGH_INFORMATION_SEGMENT")
    cal = {"phase": "V0.8.1", "rule": "CALIBRATION40_RULE_V1 (2 per video: OPENING + HIGH_INFORMATION)",
           "generated_at": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
           "total": len(items), "videos_covered": len(notes), "strata_covered": sorted(strata),
           "opening_count": openings, "high_info_count": highs,
           "segments": items}
    (OUT / "B007_V081_CALIBRATION40_V1.json").write_text(
        json.dumps(cal, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"total": len(items), "videos": len(notes), "strata": sorted(strata),
                      "openings": openings, "highs": highs}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
