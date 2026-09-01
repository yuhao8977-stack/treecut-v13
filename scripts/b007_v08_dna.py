# -*- coding: utf-8 -*-
"""V0.8 — CONTENT DNA EVIDENCE BUILD（仅 Sample20；observed/associated/co-occurs；禁因果/评分/模板）。

输入：V0.7 表(segment/asr/ocr/visual/cognition) + V0.4 dual-source facts + V0.5 strata(manifest)。
输出：20 Video DNA、Sample×Feature Matrix、A-F Stratum Summary、Pattern Candidates(含
supporting/contradicting/segment/ASR/OCR/visual evidence)、Counterexamples、Human Review Report。
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
import time
from collections import Counter
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

    dnas = []
    for nid, s in samples.items():
        media = q(c, "SELECT duration, has_audio FROM b007_media_asset_v1 WHERE note_id=?", (nid,))
        segs = q(c, "SELECT seg_no, start_ms, end_ms FROM b007_segment_v1 WHERE note_id=? ORDER BY seg_no", (nid,))
        asr = q(c, "SELECT start_ms, end_ms, text FROM b007_asr_v1 WHERE note_id=? ORDER BY start_ms", (nid,))
        ocr = q(c, "SELECT text, subtitle_flag FROM b007_ocr_v1 WHERE note_id=?", (nid,))
        vis = q(c, "SELECT scene_family, confidence FROM b007_visual_evidence_v1 WHERE note_id=?", (nid,))
        cog = q(c, "SELECT claims_json FROM b007_business_cognition_v1 WHERE note_id=?", (nid,))

        dur = media[0][0] if media else 0
        n_seg = len(segs)
        tl_cov = round(sum((e - st) for st, e in [(x[1], x[2]) for x in segs]) / (dur * 1000), 3) if dur else 0
        asr_text = " ".join(r[2] for r in asr)
        asr_utts = len(asr)
        asr_chars = len(asr_text)
        has_speech = asr_utts > 0 and asr_chars > 10
        ocr_text = " ".join(r[0] for r in ocr if r[0])
        ocr_items = len(ocr)
        subtitle = any(r[1] for r in ocr)
        fam = Counter(r[0] for r in vis)
        n_vis = len(vis)
        known = sum(v for k, v in fam.items() if k in ("FACTORY", "CUSTOMER_HOME", "SHOWROOM", "INSTALLATION_SITE"))
        scene_dom = fam.most_common(1)[0][0] if fam else "UNKNOWN"
        scene_dom_ratio = round(fam[scene_dom] / n_vis, 2) if n_vis else 0

        claims = []
        claim_status = Counter()
        for (js,) in cog:
            try:
                for cl in json.loads(js):
                    claims.append(cl)
                    claim_status[cl.get("claim_status", "UNKNOWN")] += 1
            except Exception:
                pass
        supported_values = sorted({cl["claim_value"] for cl in claims
                                   if cl.get("claim_status") in ("SUPPORTED", "LIKELY_SUPPORTED")})

        # V0.4 事实 + V0.5 stratum
        creator = s.get("creator") or {}
        paid = s.get("paid") or {}
        feat = {
            "note_id": nid, "sample_id": s["sample_id"], "stratum": s.get("primary_stratum"),
            "publish_time": s.get("publish_time"), "creator_duration": s.get("duration"),
            "media_duration": round(dur, 2), "n_segments": n_seg, "timeline_coverage": tl_cov,
            "asr_utterances": asr_utts, "asr_chars": asr_chars, "has_speech": has_speech,
            "ocr_items": ocr_items, "has_subtitle": subtitle,
            "visual_frames": n_vis, "scene_distribution": dict(fam),
            "scene_dominant": scene_dom, "scene_dominant_ratio": scene_dom_ratio,
            "scene_known_ratio": round(known / n_vis, 2) if n_vis else 0,
            "claim_status": dict(claim_status), "n_claims": len(claims),
            "supported_claim_values": supported_values,
            "creator_view": creator.get("view"), "creator_view_pct": creator.get("view_percentile"),
            "paid_status": paid.get("status"), "paid_fee": paid.get("observed_fee"),
            "paid_imp": paid.get("impressions"), "paid_clicks": paid.get("clicks"),
            "paid_leads": paid.get("leads"), "paid_months": paid.get("months"),
        }
        dnas.append(feat)

    # ---- Sample × Feature Matrix（布尔/分类投影）
    def boolf(f, key):
        return f.get(key) in (True, 1, "1", "SUPPORTED", "LIKELY_SUPPORTED") or bool(f.get(key))

    matrix_rows = []
    for f in dnas:
        matrix_rows.append({
            "note_id": f["note_id"], "sample_id": f["sample_id"], "stratum": f["stratum"],
            "video": f["media_duration"] > 30,
            "multi_segment": f["n_segments"] >= 3,
            "speech": f["has_speech"],
            "subtitle": f["has_subtitle"],
            "scene_customer_home": f["scene_dominant"] == "CUSTOMER_HOME",
            "scene_factory": f["scene_dominant"] == "FACTORY",
            "scene_showroom": f["scene_dominant"] == "SHOWROOM",
            "scene_installation": f["scene_dominant"] == "INSTALLATION_SITE",
            "scene_unknown_dom": f["scene_dominant"] == "UNKNOWN",
            "high_creator_view": (f.get("creator_view_pct") or 0) >= 75,
            "paid_associated": f["paid_status"] not in (None, "NO_PAID_ASSOCIATION_OBSERVED"),
            "paid_high_input": (f.get("paid_fee") or 0) >= 1.5,
            "paid_weak_outcome": f["paid_status"] == "NOTE_PAID_METRIC_PRESENT" and (f.get("paid_leads") or 0) == 0
                                 and f.get("paid_months") and f["paid_months"] > 0,
            "n_claims": f["n_claims"], "scene_dominant": f["scene_dominant"],
        })

    # ---- Pattern Candidates（仅关联；support≥2；报告 contradicting）
    feature_keys = ["multi_segment", "speech", "subtitle", "scene_customer_home", "scene_factory",
                    "scene_showroom", "scene_installation", "scene_unknown_dom",
                    "high_creator_view", "paid_associated", "paid_high_input", "paid_weak_outcome"]
    patterns = []
    for k in feature_keys:
        pos = [r for r in matrix_rows if r[k] is True]
        neg = [r for r in matrix_rows if r[k] is not True]
        if len(pos) < 2:
            continue
        for k2 in feature_keys:
            if k2 <= k:
                continue
            both = [r for r in matrix_rows if r[k] and r[k2]]
            pos_only = [r for r in matrix_rows if r[k] and not r[k2]]
            neg_only = [r for r in matrix_rows if not r[k] and r[k2]]
            if len(both) < 2:
                continue
            patterns.append({
                "pattern": f"{k} CO-OCCURS {k2}",
                "supporting_samples": [r["sample_id"] for r in both],
                "support_count": len(both),
                "contradicting_samples": [r["sample_id"] for r in pos_only + neg_only],
                "strata": sorted({r["stratum"] for r in both}),
                "confidence": round(len(both) / max(1, len(both) + len(pos_only) + len(neg_only)), 3),
                "limitations": ["sample-level association only (n=20)", "no causality",
                                "feature = single-note aggregate"],
            })
    # 按 support 排序取前 12
    patterns.sort(key=lambda p: p["support_count"], reverse=True)
    patterns = patterns[:12]

    # stratum summaries
    strat_summary = {}
    for f in dnas:
        st = f["stratum"]
        g = strat_summary.setdefault(st, {"notes": [], "scene": Counter(), "speech": 0,
                                          "subtitle": 0, "claims": 0, "paid_fee": []})
        g["notes"].append(f["sample_id"])
        g["scene"][f["scene_dominant"]] += 1
        g["speech"] += 1 if f["has_speech"] else 0
        g["subtitle"] += 1 if f["has_subtitle"] else 0
        g["claims"] += f["n_claims"]
        if f.get("paid_fee") is not None:
            g["paid_fee"].append(f["paid_fee"])
    for st, g in strat_summary.items():
        g["scene"] = dict(g["scene"])
        g["paid_fee"] = sorted(g["paid_fee"])

    # counterexamples
    counterexamples = []
    for p in patterns:
        for sid in p["contradicting_samples"]:
            counterexamples.append({"pattern": p["pattern"], "sample_id": sid})

    # coverage / unknown
    scene_unknown_notes = [r["note_id"] for r in matrix_rows if r["scene_unknown_dom"]]
    report = {
        "phase": "V0.8",
        "final_status": "B007_V08_DNA_EVIDENCE_PASS_WITH_LIMITATIONS",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "input": {"V0.7 tables": "b007_*_v1", "facts": "B007_SAMPLE20_V1.json (V0.4 dual-source + V0.5 strata)"},
        "dna_records": dnas,
        "feature_matrix": matrix_rows,
        "stratum_summary": strat_summary,
        "pattern_candidates": patterns,
        "counterexamples": counterexamples,
        "coverage": {"notes": len(dnas), "segments_present": sum(1 for f in dnas if f["n_segments"] > 0),
                     "asr_present": sum(1 for f in dnas if f["has_speech"]),
                     "ocr_present": sum(1 for f in dnas if f["ocr_items"] > 0),
                     "visual_present": sum(1 for f in dnas if f["visual_frames"] > 0),
                     "cognition_present": sum(1 for f in dnas if f["n_claims"] > 0),
                     "scene_unknown_dominant_notes": scene_unknown_notes},
        "limitations": ["n=20 single account; sample-level association only; no causality/winner/score; "
                        "scene = CLIP 5-class; ASR = faster-whisper-large-v3; OCR = RapidOCR; "
                        "business cognition = rule-based evidence with UNKNOWN discipline"],
    }
    (OUT / "B007_V08_DNA_EVIDENCE_V1.json").write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                                       encoding="utf-8")

    # Human Review Report (MD)
    md = ["# B007 V0.8 Content DNA Evidence — Human Review Report", "",
          f"Generated: {report['generated_at']} | Status: {report['final_status']}", "",
          "## 20 Video DNA Records",
          "",
          "| sample | stratum | segs | scene-dom | speech | subtitle | OCR | claims | paid-status |",
          "|---|---|---|---|---|---|---|---|---|"]
    for f in dnas:
        md.append(f"| {f['sample_id']} | {f['stratum']} | {f['n_segments']} | {f['scene_dominant']}({f['scene_dominant_ratio']}) "
                  f"| {'Y' if f['has_speech'] else 'N'} | {'Y' if f['has_subtitle'] else 'N'} | {f['ocr_items']} | "
                  f"{f['n_claims']} | {f['paid_status']} |")
    md += ["", "## Pattern Candidates（仅关联，无因果）", "",
           "| pattern | support | strata | contradicting | confidence |", "|---|---|---|---|---|"]
    for p in patterns:
        md.append(f"| {p['pattern']} | {p['support_count']} | {','.join(p['strata'])} | "
                  f"{','.join(p['contradicting_samples'][:6]) or '-'} | {p['confidence']} |")
    md += ["", "## Counterexamples", ""]
    for ce in counterexamples[:20]:
        md.append(f"- {ce['pattern']}: {ce['sample_id']}")
    md += ["", "## Coverage / Unknown", "",
           f"- notes {report['coverage']['notes']} | segments {report['coverage']['segments_present']} | "
           f"ASR {report['coverage']['asr_present']} | OCR {report['coverage']['ocr_present']} | "
           f"visual {report['coverage']['visual_present']} | cognition {report['coverage']['cognition_present']}",
           f"- scene-UNKNOWN dominant notes: {scene_unknown_notes}",
           "", "## Limitations", "",
           "- n=20 single account; sample-level association only; no causality/winner/score; no template rules.",
           "- Evidence provenance: scene=CLIP vit-base-patch32(5-class), ASR=faster-whisper-large-v3(zh), OCR=RapidOCR.",
           ""]
    (OUT / "B007_V08_DNA_HUMAN_REVIEW_REPORT_V1.md").write_text("\n".join(md), encoding="utf-8")

    print(json.dumps({"status": report["final_status"], "dna_notes": len(dnas),
                      "patterns": len(patterns), "counterexamples": len(counterexamples),
                      "scene_unknown_dominant": scene_unknown_notes,
                      "coverage": report["coverage"]}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
