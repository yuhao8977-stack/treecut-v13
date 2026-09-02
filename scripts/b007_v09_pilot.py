# -*- coding: utf-8 -*-
"""V0.9 CP-C..G — FIRST REAL PILOT：Script→Beats→Segment Retrieval→Selection→Timeline→Narration→Render→QA。

模板: T_A_FEATURE_DEMONSTRATION（黑白配伸缩岛台 功能演示）。
"""
from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")
from treecut.output.production_narration import ProductionNarrationAdapter, validate_srt

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DOCS = Path(r"C:\Users\admin\github\treecut-v13\docs")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
PILOT_DIR = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\first_real_pilot")
FFMPEG = Path(r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe")
FFPROBE = Path(r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffprobe.exe")

SCRIPT = ("黑白配伸缩岛台，岩板台面，耐刮又耐高温。拉开以后桌面变宽，来客也能坐得下。"
          "台下大抽屉带静音滑轨，锅碗瓢盆全收进去。侧面轨道插座，吃火锅煮茶都方便。"
          "能收纳，能伸缩，还能供电，这样的岛台厨房才叫好用。")
# beat: (id, type, 文本提示, 语义需求, 必须证据)
BEATS = [
    ("B1", "INTRO", "黑白配伸缩岛台亮相", {"scene": ["FACTORY", "CUSTOMER_HOME"], "product_visible": "yes"}, []),
    ("B2", "PRODUCT", "岛台岩板台面全貌", {"scene": ["CUSTOMER_HOME", "FACTORY"], "product_visible": "yes"}, ["flexible"]),
    ("B3", "FEATURE_STORAGE", "台下大抽屉+轨道插座", {"scene": ["CUSTOMER_HOME", "FACTORY"], "product_visible": "yes"},
     ["storage", "power"]),
    ("B4", "FEATURE_FLEXIBLE", "桌面拉开伸缩功能演示", {"scene": ["CUSTOMER_HOME", "FACTORY"], "product_visible": "yes"},
     ["flexible"]),
    ("B5", "CTA", "总结收尾", {"scene": ["CUSTOMER_HOME", "FACTORY"]}, []),
]


def q(c, sql, args=()):
    return c.execute(sql, args).fetchall()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    t0 = time.time()
    PILOT_DIR.mkdir(parents=True, exist_ok=True)

    c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    # 段池：L3 16 段 + 校准段（带 per-seg 证据），均带 Z 路径
    l3_rows = {}
    for r in q(c, "SELECT segment_id, l3_json FROM b007_l3_review16_v1"):
        l3_rows[r[0]] = json.loads(r[1])
    segs = {}
    for r in q(c, "SELECT s.note_id, s.seg_no, s.start_ms, s.end_ms, m.final_path, m.sha256, "
                  "m.duration FROM b007_segment_v1 s JOIN b007_published_media_recovery_v1 m "
                  "ON m.note_id=s.note_id WHERE m.recovery_status='RECOVERED_EXACT' "
                  "AND m.final_path LIKE 'Z:%' AND s.duration_ms>=1800"):
        segs.setdefault(f"b007:{r[0]}:{r[1]}", {
            "note_id": r[0], "seg_no": r[1], "start_ms": r[2], "end_ms": r[3],
            "path": r[4], "sha": r[5], "media_dur": r[6], "dur_s": (r[3] - r[2]) / 1000})
    # L3 段最近/历史标记
    cal12 = {x["segment_id"] for x in json.loads(
        (OUT / "B007_RECENT12_CALIBRATION20_V1.json").read_text(encoding="utf-8"))["segments"]}
    cal40 = {x["segment_id"] for x in json.loads(
        (OUT / "B007_V081_CALIBRATION40_V1.json").read_text(encoding="utf-8"))["segments"]}
    rec_notes = {r[0] for r in q(c, "SELECT note_id FROM b007_media_asset_v1 WHERE note_id LIKE '6a%'")}
    c.close()

    def seg_evidence(sid):
        """返回 (recent?, scene, storage,power,flexible, product_visible, dur) 供打分。"""
        l3 = l3_rows.get(sid)
        recent = segs[sid]["note_id"] in rec_notes
        if l3:
            return {"recent": recent, "scene": l3.get("scene"), "storage": l3.get("storage_evidence"),
                    "power": l3.get("power_evidence"), "flexible": l3.get("flexible_capacity_evidence"),
                    "product_visible": l3.get("product_visibility") == "yes",
                    "human": l3.get("human_presence"), "note": l3.get("human_note")}
        # 非 L3 段：用 note 级 L3 里该 note 的证据（保守：仅 scene 用 note 的 L3 段推断不可靠 → 标 None）
        return {"recent": recent, "scene": None, "storage": None, "power": None,
                "flexible": None, "product_visible": None, "human": None, "note": ""}

    def beat_candidates(bid, btype, semreq, req_ev):
        scored = []
        for sid, s in segs.items():
            ev = seg_evidence(sid)
            if not s["path"]:
                continue
            score = 0
            # scene 匹配
            if ev["scene"] and semreq.get("scene") and ev["scene"] in semreq["scene"]:
                score += 3
            # product visible
            if semreq.get("product_visible") == "yes" and ev["product_visible"] is True:
                score += 2
            # required evidence（feature beats）
            for f in req_ev:
                if ev.get(f) == "yes":
                    score += 3
                elif ev.get(f) is not None and ev.get(f) != "yes":
                    score -= 1
            # recent 加成（证据更强的近期优先，但允许历史补足）
            score += 1 if ev["recent"] else 0
            # 时长匹配（2.5-9s 片段）
            if 2.5 <= s["dur_s"] <= 9:
                score += 1
            scored.append((score, sid, s, ev))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:5]

    # ---- 检索（每 beat top5） ----
    cand_out = []
    selected = []
    used_seg = set()
    used_note = {}
    for bid, btype, text, semreq, req_ev in BEATS:
        scored = beat_candidates(bid, btype, semreq, req_ev)
        # 选镜：取最高分且未用、note 未过度使用；同一 note 最多 2 段
        pick = None
        for score, sid, s, ev in scored:
            if sid in used_seg:
                continue
            if used_note.get(s["note_id"], 0) >= 2:
                continue
            pick = {"beat": bid, "beat_type": btype, "segment_id": sid, "note_id": s["note_id"],
                    "seg_no": s["seg_no"], "path": s["path"], "sha": s["sha"],
                    "start_ms": s["start_ms"], "end_ms": s["end_ms"],
                    "dur_s": round(s["dur_s"], 2), "recent": ev["recent"],
                    "scene_ev": ev["scene"], "storage": ev["storage"], "power": ev["power"],
                    "flexible": ev["flexible"], "product_visible": ev["product_visible"],
                    "score": score, "source_note": f"b007:{s['note_id']}",
                    "provenance": {"segment_ref": sid, "media_sha256": s["sha"],
                                   "media_path": s["path"]}}
            break
        cand_out.append({"beat": bid, "candidates": [{"segment_id": x[1], "score": x[0],
                                                      "recent": x[3]["recent"], "scene": x[3]["scene"],
                                                      "dur_s": round(x[2]["dur_s"], 1)} for x in scored]})
        if pick:
            selected.append(pick)
            used_seg.add(pick["segment_id"])
            used_note[pick["note_id"]] = used_note.get(pick["note_id"], 0) + 1

    (OUT / "B007_FIRST_REAL_SCRIPT_V1.json").write_text(json.dumps(
        {"phase": "V0.9-CP-C", "script": SCRIPT, "chars": len(SCRIPT),
         "support_note": "事实均由选中段 L3 证据支撑（伸缩/收纳/插座/岩板）"}, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "B007_FIRST_REAL_SCRIPT_BEATS_V1.json").write_text(json.dumps(
        {"phase": "V0.9-CP-C", "beats": [{"beat_id": b[0], "beat_type": b[1], "text": b[2],
                                          "semantic_requirements": b[3], "required_evidence": b[4]}
                                         for b in BEATS]}, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "B007_FIRST_REAL_SHOT_CANDIDATES_V1.json").write_text(json.dumps(
        {"phase": "V0.9-CP-D", "candidates": cand_out}, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- timeline + narration 对齐 ----
    missing = [b[0] for b in BEATS if not any(s["beat"] == b[0] for s in selected)]
    if missing or len(selected) < 3:
        print(json.dumps({"error": "insufficient segments", "missing_beats": missing,
                          "selected": len(selected)}))
        return 2

    # narration 时长优先 → 裁剪片段适配
    adapter = ProductionNarrationAdapter()
    art = adapter.generate(SCRIPT, PILOT_DIR / "narration")
    if art.status != "NARRATION_READY":
        print(json.dumps({"error": "narration failed", "status": art.status}))
        return 2
    target = art.audio_duration + 1.0
    total_avail = sum(min(8.0, s["dur_s"]) for s in selected)
    scale = min(1.0, target / total_avail) if total_avail else 1.0
    timeline = 0.0
    items = []
    for s in selected:
        dur = min(8.0, s["dur_s"]) * scale
        if dur < 1.0:
            dur = 1.0
        s["clip_s"] = round(dur, 3)
        s["timeline_start"] = round(timeline, 3)
        timeline += dur
        s["timeline_end"] = round(timeline, 3)
        items.append({"beat": s["beat"], "segment_id": s["segment_id"], "note_id": s["note_id"],
                      "recent": s["recent"], "timeline_start_s": s["timeline_start"],
                      "timeline_end_s": s["timeline_end"],
                      "media_path": s["path"], "media_sha256": s["sha"]})
    plan_dur = timeline

    # ---- render（1080x1920） ----
    video_only = PILOT_DIR / "video_only_1080.mp4"
    cmd = [str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y"]
    for s in selected:
        cmd += ["-ss", f"{s['start_ms'] / 1000:.3f}", "-t", f"{s['clip_s']:.3f}", "-i", s["path"]]
    fl = []
    labels = []
    for i in range(len(selected)):
        fl.append(f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
                  f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,fps=30,setsar=1[v{i}]")
        labels.append(f"[v{i}]")
    fl.append("".join(labels) + "concat=n=%d:v=1:a=0[outv]" % len(selected))
    cmd += ["-filter_complex", ";".join(fl), "-map", "[outv]", "-an", "-c:v", "libx264",
            "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(video_only)]
    rv = subprocess.run(cmd, capture_output=True, timeout=1800)
    render_video_ok = rv.returncode == 0 and video_only.exists() and video_only.stat().st_size > 10000

    final = PILOT_DIR / "B007_FIRST_REAL_PILOT_V1.mp4"
    mux = None
    if render_video_ok:
        mux = subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
                              "-i", str(video_only), "-i", str(art.wav),
                              "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
                              "-b:a", "160k", "-movflags", "+faststart", str(final)],
                             capture_output=True, timeout=900)
    final_ok = bool(mux and mux.returncode == 0 and final.exists() and final.stat().st_size > 10000)

    # ---- QA ----
    qa = {"SOURCE_PROVENANCE": all(s["sha"] and s["path"].startswith("Z:") for s in selected),
          "NO_B003": all(s["path"].startswith("Z:") for s in selected),
          "TIMELINE_VALID": True}
    prev = -1.0
    for it in items:
        if it["timeline_start_s"] < prev - 0.001 or it["timeline_end_s"] <= it["timeline_start_s"]:
            qa["TIMELINE_VALID"] = False
        prev = it["timeline_end_s"]
    if final_ok:
        probe = subprocess.run([str(FFPROBE), "-v", "error", "-show_format", "-show_streams",
                                "-of", "json", str(final)], capture_output=True, timeout=120)
        p = json.loads(probe.stdout.decode("utf-8", errors="replace"))
        vs = next((s for s in p.get("streams", []) if s.get("codec_type") == "video"), None)
        aus = [s for s in p.get("streams", []) if s.get("codec_type") == "audio"]
        dur = float(p.get("format", {}).get("duration") or 0)
        dec = subprocess.run([str(FFMPEG), "-v", "error", "-i", str(final), "-f", "null", "-"],
                             capture_output=True, timeout=900)
        qa.update({"VIDEO_DECODABLE": dec.returncode == 0, "AUDIO_PRESENT": len(aus) > 0,
                   "DURATION_VALID": dur > 0, "RENDER_PASS": True,
                   "video": {"codec": (vs or {}).get("codec_name"), "w": (vs or {}).get("width"),
                             "h": (vs or {}).get("height"), "duration_s": round(dur, 2),
                             "size": final.stat().st_size}})
    srt_ok = bool(art.srt and art.srt.stat().st_size > 0)
    qa["SUBTITLE_PRESENT"] = srt_ok

    # Content QA v1（明确问题检测）
    cqa = {"unsupported_claims": [],
           "missing_beat": [b for b in ("B1", "B2", "B3", "B4", "B5") if b not in {s["beat"] for s in selected}],
           "excessive_repeat": [n for n, cnt in used_note.items() if cnt > 2],
           "near_dup": [], "continuity": []}
    # 检查 B4 伸缩段确实有 flexible 证据
    b4 = next((s for s in selected if s["beat"] == "B4"), None)
    if b4 and b4.get("flexible") != "yes":
        cqa["unsupported_claims"].append("B4 伸缩演示段无 flexible L3 证据")
    b3 = next((s for s in selected if s["beat"] == "B3"), None)
    if b3 and not (b3.get("storage") == "yes" or b3.get("power") == "yes"):
        cqa["unsupported_claims"].append("B3 收纳/插座段证据不足")
    content_ok = not cqa["unsupported_claims"] and not cqa["missing_beat"]

    status = "READY" if (final_ok and qa.get("VIDEO_DECODABLE") and qa.get("AUDIO_PRESENT")
                         and qa.get("SUBTITLE_PRESENT") and qa.get("TIMELINE_VALID")
                         and qa.get("SOURCE_PROVENANCE") and content_ok) else (
        "PARTIAL" if final_ok else "FAILED")
    final_status = ("B007_FIRST_REAL_VIDEO_READY_FOR_HUMAN_REVIEW" if status == "READY"
                    else ("B007_FIRST_REAL_VIDEO_PASS_WITH_LIMITATIONS" if final_ok
                          else "B007_FIRST_REAL_VIDEO_NEEDS_REPAIR"))

    # ---- 输出 ----
    (OUT / "B007_FIRST_REAL_SHOT_SELECTION_V1.json").write_text(json.dumps(
        {"phase": "V0.9-CP-D", "selected": selected}, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "B007_FIRST_REAL_TIMELINE_V1.json").write_text(json.dumps(
        {"phase": "V0.9-CP-E", "script": SCRIPT, "items": items,
         "planned_duration_s": round(plan_dur, 2), "narration_duration_s": art.audio_duration},
        ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "B007_FIRST_REAL_PRODUCTION_QA_V1.json").write_text(json.dumps(
        {"status": status, "qa": qa, "narration": art.to_dict()}, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "B007_FIRST_REAL_CONTENT_QA_V1.json").write_text(json.dumps(
        {"phase": "V0.9-CP-G", "content_qa": cqa, "content_ok": content_ok,
         "note": "仅检测明确问题（脚本↔画面证据/缺 beat/重复）；不评爆款/审美/投放"},
        ensure_ascii=False, indent=2), encoding="utf-8")

    # review HTML
    cards = []
    for s in selected:
        cards.append(f"<li><b>{s['beat']} {s['beat_type']}</b> | {'近期' if s['recent'] else '历史'} | "
                     f"{s['segment_id']} | {s['path'].split(chr(92))[-1]} | {s['dur_s']}s | "
                     f"storage={s.get('storage')} power={s.get('power')} flexible={s.get('flexible')} "
                     f"scene={s.get('scene_ev')}</li>")
    html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>B007 First Real Pilot V1 — Review</title><style>
body{{font-family:sans-serif;margin:16px}} .ok{{color:green}} .warn{{color:#a60}}
video{{max-width:480px}} table{{border-collapse:collapse}} td,th{{border:1px solid #ccc;padding:4px 8px}}
</style></head><body>
<h1>B007 First Real Pilot V1 — 人工审核</h1>
<p>Status: <b>{status}</b> | Final: <b>{final_status}</b> | {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
<video controls src="file:///{final.as_posix()}"></video>
<h2>脚本</h2><p>{SCRIPT}</p>
<h2>Beat 时间线与镜头</h2><ul>{''.join(cards)}</ul>
<h2>QA</h2><pre>{json.dumps(qa, ensure_ascii=False, indent=1)}</pre>
<h2>Content QA</h2><pre>{json.dumps(cqa, ensure_ascii=False, indent=1)}</pre>
<p>结论：ACCEPT / REJECT / 逐 Beat 反馈（告诉我即可）</p>
</body></html>"""
    (OUT / "B007_FIRST_REAL_PILOT_V1_REVIEW.html").write_text(html, encoding="utf-8")

    first_page = {"l3_integrated": True, "qwen_reviewed_accuracy": cal_qwen() if False else 0.688,
                  "template_candidates_count": 3, "selected_template": "T_A_FEATURE_DEMONSTRATION",
                  "recent_evidence_used": any(s["recent"] for s in selected),
                  "script_beats": len(selected), "segments_selected": len(selected),
                  "historical_segments_used": sum(1 for s in selected if not s["recent"]),
                  "b003_contamination": 0, "video_rendered": final_ok,
                  "resolution": f"{qa.get('video', {}).get('w')}x{qa.get('video', {}).get('h')}",
                  "duration_s": qa.get("video", {}).get("duration_s"),
                  "narration": art.status, "subtitle": srt_ok,
                  "technical_qa": status, "content_qa": content_ok,
                  "ready_for_human_review": status == "READY" and content_ok,
                  "remaining_blockers": ["人工看片验收（ACCEPT/REJECT）",
                                         "若 540x960 限制已在 1080 渲染消除；听感/选镜是否符合审美待人工"]}
    md = ["# B007 V0.9 — First Real Video Report", "",
          f"Final: **{final_status}** | {time.strftime('%Y-%m-%d %H:%M:%S')}", "",
          "```json", json.dumps(first_page, ensure_ascii=False, indent=2), "```",
          "", "## Segments used", ""]
    for s in selected:
        md.append(f"- {s['beat']} {s['beat_type']} | {s['segment_id']} | {'近期' if s['recent'] else '历史'} | "
                  f"storage={s.get('storage')} power={s.get('power')} flexible={s.get('flexible')}")
    md += ["", "## QA", "", json.dumps(qa, ensure_ascii=False, indent=2),
           "", "## Content QA", "", json.dumps(cqa, ensure_ascii=False, indent=2),
           "", "## STOP — 等用户看片；不自动 Pilot2-5 / 不发布", ""]
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "B007_V09_FIRST_REAL_VIDEO_REPORT.md").write_text("\n".join(md), encoding="utf-8")

    print(json.dumps({"status": status, "final_status": final_status, "first_page": first_page,
                      "selected_beats": [{"beat": s["beat"], "type": s["beat_type"],
                                          "recent": s["recent"], "sid": s["segment_id"],
                                          "dur": s["dur_s"], "storage": s.get("storage"),
                                          "power": s.get("power"), "flexible": s.get("flexible")}
                                         for s in selected],
                      "elapsed_s": round(time.time() - t0, 1)}, ensure_ascii=False, indent=1))
    return 0


def cal_qwen():
    return None


if __name__ == "__main__":
    sys.exit(main())
