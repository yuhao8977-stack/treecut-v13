# -*- coding: utf-8 -*-
"""V0.8.3 装配：Recent12 coverage / Hist20 vs Recent12 对比 / 时间模式 / L3 Review16 V2 / TTS 诊断 / 报告。"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DOCS = Path(r"C:\Users\admin\github\treecut-v13\docs")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
REC12 = OUT / "B007_RECENT12_V1.json"
HIST_DNA = OUT / "B007_V08_DNA_EVIDENCE_V1.json"
HIST_ENR = OUT / "B007_V081_DNA_ENRICHMENT_CANDIDATE_V1.json"
REC_CAL = OUT / "B007_RECENT12_CALIBRATION20_V1.json"
REC_QW = OUT / "B007_RECENT12_QWENVL_CANDIDATES_V1.json"


def q(c, sql, args=()):
    return c.execute(sql, args).fetchall()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    rec12 = json.loads(REC12.read_text(encoding="utf-8"))
    hist_dna = {r["note_id"]: r for r in json.loads(HIST_DNA.read_text(encoding="utf-8"))["dna_records"]}
    hist_enr = {r["note_id"]: r for r in json.loads(HIST_ENR.read_text(encoding="utf-8"))["records"]}
    rec_cal = json.loads(REC_CAL.read_text(encoding="utf-8"))
    rec_qw = {s["segment_id"]: s for s in json.loads(REC_QW.read_text(encoding="utf-8")).get("segments", [])}
    c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)

    rec_samples = [s for s in rec12["samples"]]
    # (rec_recovered 在 media 表加载后确定)

    # ---- Recent per-note DNA（从 V0.7 表） ----
    segs, asr, ocr, vis, cog, media = {}, {}, {}, {}, {}, {}
    for r in q(c, "SELECT note_id, seg_no, start_ms, end_ms FROM b007_segment_v1 ORDER BY note_id, seg_no"):
        segs.setdefault(r[0], []).append(r[1:])
    for r in q(c, "SELECT note_id, start_ms, end_ms, text FROM b007_asr_v1"):
        asr.setdefault(r[0], []).append(r[1:])
    for r in q(c, "SELECT note_id, frame_timestamp_ms, text, subtitle_flag FROM b007_ocr_v1"):
        ocr.setdefault(r[0], []).append(r[1:])
    for r in q(c, "SELECT note_id, frame_timestamp_ms, scene_family FROM b007_visual_evidence_v1"):
        vis.setdefault(r[0], []).append(r[1:])
    for r in q(c, "SELECT note_id, seg_no, claims_json FROM b007_business_cognition_v1"):
        try:
            cog.setdefault(r[0], {})[r[1]] = len(json.loads(r[2]))
        except Exception:
            cog.setdefault(r[0], {})[r[1]] = 0
    for r in q(c, "SELECT note_id, duration FROM b007_media_asset_v1"):
        media[r[0]] = r[1]
    c.close()

    rec_recovered = [s for s in rec_samples if s["note_id"] in media]   # 仅真实恢复（有 media asset）的
    rec_note_ids = [s["note_id"] for s in rec_recovered]

    rec_dna = {}
    for s in rec_recovered:
        nid = s["note_id"]
        ssegs = segs.get(nid, [])
        asr_t = asr.get(nid, [])
        ocr_t = ocr.get(nid, [])
        vis_t = vis.get(nid, [])
        asr_chars = sum(len(t[2]) for t in asr_t)
        fam = Counter(v[1] for v in vis_t)
        scene_dom = fam.most_common(1)[0][0] if fam else "UNKNOWN"
        n_claims = sum(cog.get(nid, {}).values())
        # 从 calibration/Qwen 取 opening/high 候选字段
        cal_segs = [x for x in rec_cal["segments"] if x["note_id"] == nid]
        opening = next((x for x in cal_segs if x["selection_role"] == "OPENING_SEGMENT"), None)
        high = next((x for x in cal_segs if x["selection_role"] == "HIGH_INFORMATION_SEGMENT"), None)
        def qf(x, k):
            if not x:
                return "UNKNOWN"
            f = rec_qw.get(x["segment_id"], {}).get("fields", {}).get(k, {})
            return f.get("value") if isinstance(f, dict) else "UNKNOWN"
        rec_dna[nid] = {
            "sample_id": s["sample_id"], "stratum": s.get("primary_stratum"),
            "media_duration": media.get(nid) or 0, "n_segments": len(ssegs),
            "avg_segment_s": round(sum((e - st) for st, e, _ in [x for x in ssegs]) / len(ssegs) / 1000, 1) if ssegs else 0,
            "has_speech": "yes" if asr_chars >= 10 else "no", "asr_chars": asr_chars,
            "has_subtitle": "yes" if any(t[2] for t in ocr_t) else "no", "ocr_items": len(ocr_t),
            "scene_dominant": scene_dom,
            "opening_product_visibility": qf(opening, "product_visibility"),
            "opening_human": qf(opening, "human_presence"),
            "opening_function_demo": qf(opening, "feature_demonstration"),
            "opening_scene": qf(opening, "scene"),
            "storage": qf(high, "storage_evidence"), "power": qf(high, "power_evidence"),
            "flexible": qf(high, "flexible_capacity_evidence"), "dining": qf(high, "dining_context_evidence"),
            "detail_shot": qf(high, "detail_shot"), "shot_function": qf(high, "shot_function_candidate"),
            "function": qf(high, "function"), "n_claims": n_claims,
        }

    # ---- Hist 侧汇总 ----
    def hist_dim(key, default="UNKNOWN"):
        vals = []
        for nid, r in hist_dna.items():
            en = hist_enr.get(nid, {})
            if key == "opening_product_visibility":
                vals.append((en.get("opening_candidate") or {}).get("product_visibility", "UNKNOWN"))
            elif key == "opening_human":
                vals.append((en.get("opening_candidate") or {}).get("human_presence", "UNKNOWN"))
            elif key == "opening_function_demo":
                vals.append((en.get("opening_candidate") or {}).get("feature_demonstration", "UNKNOWN"))
            elif key in ("storage", "power", "flexible", "dining"):
                vals.append((en.get("high_info_candidate") or {}).get(
                    {"storage": "storage_evidence", "power": "power_evidence",
                     "flexible": "flexible_capacity_evidence", "dining": "dining_context_evidence"}[key], "UNKNOWN"))
            elif key == "detail_shot":
                vals.append("UNKNOWN")  # 历史 enrichment 未含 detail_shot 高信息字段
            elif key == "scene_dominant":
                vals.append(r.get("scene_dominant", "UNKNOWN"))
            elif key == "has_subtitle":
                vals.append("yes" if r.get("has_subtitle") else "no")
            elif key == "has_speech":
                vals.append("yes" if r.get("has_speech") else "no")
            else:
                vals.append(default)
        return vals

    def yes_ratio(vals):
        return round(sum(1 for v in vals if v in ("yes", "Y")) / max(1, len(vals)), 3)

    def dom(vals):
        cc = Counter(vals)
        return cc.most_common(1)[0][0] if cc else "UNKNOWN"

    # ---- 维度对比 + 时间模式 ----
    dims = ["opening_product_visibility", "opening_human", "opening_function_demo",
            "storage", "power", "flexible", "dining", "has_subtitle", "has_speech",
            "scene_dominant"]
    comparison = {}
    patterns = []
    for d in dims:
        hv = hist_dim(d)
        rv = [rec_dna[nid].get(d, "UNKNOWN") for nid in rec_note_ids]
        if d == "scene_dominant":
            h_yes, r_yes = dom(hv), dom(rv)
            comparison[d] = {"historical": h_yes, "recent": r_yes, "type": "dominant"}
            cls = "STABLE_PATTERN_CANDIDATE" if h_yes == r_yes else "RECENT_PATTERN_CANDIDATE"
            patterns.append({"dim": d, "class": cls, "historical": h_yes, "recent": r_yes,
                             "note": f"historical dominant {h_yes} vs recent dominant {r_yes}"})
        else:
            hy, ry = yes_ratio(hv), yes_ratio(rv)
            comparison[d] = {"historical_yes_ratio": hy, "recent_yes_ratio": ry}
            diff = ry - hy
            if max(hy, ry) < 0.3:
                cls = "UNCERTAIN_PATTERN"
            elif abs(diff) <= 0.2:
                cls = "STABLE_PATTERN_CANDIDATE"
            elif diff > 0.2:
                cls = "RECENT_PATTERN_CANDIDATE"
            else:
                cls = "LEGACY_PATTERN_CANDIDATE"
            patterns.append({"dim": d, "class": cls, "historical_yes_ratio": hy,
                             "recent_yes_ratio": ry, "diff": round(diff, 3)})

    # duration / segments 汇总
    comparison["duration_avg_s"] = {"historical": round(sum(r.get("media_duration", 0) for r in hist_dna.values()) / 20, 1),
                                    "recent": round(sum(r.get("media_duration", 0) for r in rec_dna.values()) / len(rec_dna), 1)}
    comparison["segments_avg"] = {"historical": round(sum(r.get("n_segments", 0) for r in hist_dna.values()) / 20, 1),
                                  "recent": round(sum(r.get("n_segments", 0) for r in rec_dna.values()) / len(rec_dna), 1)}

    # ---- Review16 V2 ----
    def pick_hist(role, n):
        # 历史段：从 enrichment 中按 opening/high + 证据分值挑
        cands = []
        for nid, en in hist_enr.items():
            oc = en.get("opening_candidate") or {}
            hc = en.get("high_info_candidate") or {}
            base = oc if role == "OPENING" else hc
            score = sum(1 for k in ("product_visibility", "feature_demonstration", "human_presence")
                        if base.get(k) == "yes")
            seg_id = oc.get("segment_id") if role == "OPENING" else hc.get("segment_id")
            cands.append((score, nid, seg_id))
        cands.sort(key=lambda x: x[0], reverse=True)
        return [{"note_id": nid, "segment_id": sid or f"hist:{nid}", "sample_id": hist_dna[nid]["sample_id"],
                 "stratum": hist_dna[nid]["stratum"], "selection_role": role} for _, nid, sid in cands[:n]]

    def pick_rec(role, n):
        cands = []
        for x in rec_cal["segments"]:
            if x["selection_role"] != ("OPENING_SEGMENT" if role == "OPENING" else "HIGH_INFORMATION_SEGMENT"):
                continue
            f = rec_qw.get(x["segment_id"], {}).get("fields", {})
            score = sum(1 for k in ("storage_evidence", "power_evidence", "flexible_capacity_evidence",
                                    "dining_context_evidence", "detail_shot")
                        if isinstance(f.get(k), dict) and f[k].get("value") == "yes")
            cands.append((score, x))
        cands.sort(key=lambda x: x[0], reverse=True)
        return [{"note_id": x["note_id"], "segment_id": x["segment_id"], "sample_id": x["sample_id"],
                 "stratum": x["stratum"], "selection_role": role} for _, x in cands[:n]]

    review16 = {"structure": "Historical 4 opening + 4 high-info; Recent 4 opening + 4 high-info",
                "historical": pick_hist("OPENING", 4) + pick_hist("HIGH", 4),
                "recent": pick_rec("OPENING", 4) + pick_rec("HIGH", 4),
                "total": 16}
    (OUT / "B007_L3_REVIEW16_V2.json").write_text(json.dumps(review16, ensure_ascii=False, indent=2), encoding="utf-8")

    html = ["<!DOCTYPE html><html lang='zh'><head><meta charset='utf-8'><title>B007 L3 Review16 V2</title></head><body>",
            "<h1>B007 L3 Review16 V2</h1><p>Historical + Recent 平衡审核集（自动生成，未写 L3）</p>"]
    for part in ("historical", "recent"):
        html.append(f"<h2>{part.upper()}</h2><ul>")
        for r in review16[part]:
            html.append(f"<li>{r['sample_id']} | {r['stratum']} | {r['selection_role']} | {r['segment_id']}</li>")
        html.append("</ul>")
    html.append("</body></html>")
    (OUT / "B007_L3_REVIEW16_V2.html").write_text("\n".join(html), encoding="utf-8")

    # ---- 输出文件 ----
    cov = {"recovered_exact": [s["sample_id"] for s in rec_recovered],
           "unavailable": [s["sample_id"] for s in rec12["samples"]
                           if s["sample_id"] not in [x["sample_id"] for x in rec_recovered]],
           "asset": len(rec_note_ids), "segments": sum(len(segs.get(n, [])) for n in rec_note_ids),
           "asr_notes": sum(1 for n in rec_note_ids if len(asr.get(n, [])) > 0),
           "ocr_notes": sum(1 for n in rec_note_ids if len(ocr.get(n, [])) > 0),
           "visual_notes": sum(1 for n in rec_note_ids if len(vis.get(n, [])) > 0),
           "cognition_notes": sum(1 for n in rec_note_ids if cog.get(n)),
           "qwen_segments": len(rec_qw)}
    (OUT / "B007_RECENT12_ANALYSIS_COVERAGE_V1.json").write_text(
        json.dumps(cov, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "B007_HISTORICAL20_VS_RECENT12_V1.json").write_text(
        json.dumps({"comparison": comparison, "patterns": patterns,
                    "recent_dna": rec_dna}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "B007_TEMPORAL_PATTERN_CANDIDATES_V1.json").write_text(
        json.dumps({"patterns": patterns, "note": "observed/associated only; no causality"},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    tts = {"phase": "V0.8.3", "root_cause_identified": True,
           "conclusion": "narration.wav=2s 与 narration.srt=0 系 cognitive/production.produce() 的**设计占位**（anullsrc -t 2 静音 + 空 srt，代码注释'认知链路无 TTS/选曲时跳过'）；narration_script.txt 仅为结构提示（'结合素材内容口播'）。**真 TTS 链（copywriter.build_narration + models/tts_local.synthesize）存在于 desktop._generate_narration，但从未接入 produce()** → 集成缺口，非 TTS 引擎损坏。",
           "evidence": ["src/treecut/cognitive/production.py L338-352 (anullsrc 2s + 空 srt)",
                        "src/treecut/cognitive/production.py L379-384 (hints-only script)",
                        "desktop.py L411-414 (_generate_narration 未接 produce)",
                        "产物 narration.wav duration=2.000000 / srt bytes=0"],
           "repair_scope": "把 copywriter+tts_local 接入 produce()，输入真实口播文案（模板卖点+素材 hint），输出对齐时长 SRT"}
    (OUT / "TREECUT_TTS_SUBTITLE_DIAGNOSTIC_V1.json").write_text(json.dumps(tts, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- 报告 ----
    status = "B007_RECENT12_CORRECTION_COMPLETE_WITH_LIMITATIONS"
    report = {"phase": "V0.8.2+V0.8.3", "status": status,
              "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
              "recent12_selected": len(rec_samples), "recovered_exact": cov["recovered_exact"],
              "unavailable": cov["unavailable"], "gate_10of12": len(cov["recovered_exact"]) >= 10,
              "analysis_coverage": cov, "comparison": comparison, "patterns": patterns,
              "review16_v2": review16, "tts_diagnostic": tts}
    (OUT / "B007_RECENT12_CORRECTION_REPORT_V1.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    md = ["# Phase4 — B007 Recent12 Correction Report (V0.8.2 + V0.8.3)", "",
          f"Status: **{status}** | {report['generated_at']}", "",
          f"- Recent12 selected = {len(rec_samples)} (Latest6 2026-07~08, Earlier6 2026-04~06)",
          f"- Exact Media = {len(cov['recovered_exact'])}/12",
          f"- Unavailable = {cov['unavailable']}",
          f"- Gate 10/12 = {report['gate_10of12']}",
          f"- Recent Asset = {cov['asset']} | Segments = {cov['segments']} | ASR = {cov['asr_notes']} | "
          f"OCR = {cov['ocr_notes']} | Visual = {cov['visual_notes']} | Cognition = {cov['cognition_notes']} | "
          f"Qwen segs = {cov['qwen_segments']}",
          "", "## Historical20 vs Recent12", "",
          "| dim | historical | recent |", "|---|---|---|"]
    for k, v in comparison.items():
        md.append(f"| {k} | {json.dumps(v, ensure_ascii=False)} |")
    md += ["", "## Temporal Pattern Candidates", ""]
    for p in patterns:
        md.append(f"- **{p['class']}**: {p['dim']} ({json.dumps(p, ensure_ascii=False)})")
    md += ["", "## TTS/SRT Diagnostic", "", "- " + tts["conclusion"].replace("\n", " "),
           "", "## STOP", "", "Recent12 + analysis + comparison + Review16V2 + TTS diagnostic complete; "
           "NO L3 written; NO V0.9/Template/AutoCut/Production Render entered.", ""]
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "PHASE4_B007_RECENT12_CORRECTION_REPORT.md").write_text("\n".join(md), encoding="utf-8")

    print(json.dumps({"status": status, "recovered_exact": len(cov["recovered_exact"]),
                      "gate_10of12": report["gate_10of12"], "coverage": cov,
                      "patterns": [p["class"] + ":" + p["dim"] for p in patterns],
                      "tts_root_cause": tts["root_cause_identified"]},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
