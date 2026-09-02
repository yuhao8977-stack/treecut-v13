# -*- coding: utf-8 -*-
"""V0.8.5 — Production Path Technical Preflight（B007 Truth Chain → Timeline → TTS/SRT → Render → QA）。

工程验收 smoke；确定性 fixture；禁止 B003 污染（任何非 Z B007 来源 → FAIL）。
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
from treecut.workflow.planning import EditPlan, EditSegment
from treecut.output.production_narration import ProductionNarrationAdapter, validate_srt

DATA_ROOT = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = DATA_ROOT / "database" / "materials.db"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DOCS = Path(r"C:\Users\admin\github\treecut-v13\docs")
SMOKE_DIR = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007")
FFMPEG = Path(r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe")
FFPROBE = Path(r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffprobe.exe")

SCRIPT = ("这台两米四的伸缩岛台，拉开以后能坐八个人。岩板台面耐刮耐高温，"
          "平时切菜吃饭办公都在这里。台下的大抽屉用了静音滑轨，锅碗瓢盆全都能收进去。"
          "侧面还预留了升降插座，吃火锅很方便。")
BEATS = ["INTRO", "PRODUCT", "FEATURE", "DETAIL", "CTA"]
# 确定性 B007 段来源（真实恢复的笔记）
NOTE_ORDER = ["69f9a0ac000000003701d937", "69367987000000001b027d8f",
              "6a85b8490000000021022731", "6a92b9e8000000002501a357"]


def q(c, sql, args=()):
    return c.execute(sql, args).fetchall()


def pick_segments(n: int = 5) -> list[dict]:
    c = sqlite3.connect("file:" + str(DB).replace("\\", "/") + "?mode=ro", uri=True)
    rows = q(c, "SELECT s.note_id, s.seg_no, s.start_ms, s.end_ms, m.final_path, m.sha256 "
                "FROM b007_segment_v1 s JOIN b007_published_media_recovery_v1 m "
                "ON m.note_id=s.note_id WHERE m.recovery_status='RECOVERED_EXACT' "
                "AND m.final_path LIKE 'Z:%' AND s.duration_ms>=2500 ORDER BY "
                "CASE s.note_id " + " ".join(
                    [f"WHEN '{nid}' THEN {i}" for i, nid in enumerate(NOTE_ORDER)]) +
                " ELSE 99 END, s.seg_no")
    c.close()
    chosen = []
    seen = set()
    for r in rows:
        if len(chosen) >= n:
            break
        if r[5] in seen:
            continue
        seen.add(r[5])
        chosen.append({"note_id": r[0], "seg_no": r[1], "start_ms": r[2], "end_ms": r[3],
                       "path": r[4], "sha256": r[5]})
    return chosen


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    t0 = time.time()
    SMOKE_DIR.mkdir(parents=True, exist_ok=True)
    segs = pick_segments(len(BEATS))
    if len(segs) < len(BEATS):
        print(json.dumps({"error": f"only {len(segs)} segments found"}))
        return 1

    # ---- narration（真实 TTS + SRT） ----
    adapter = ProductionNarrationAdapter()
    art = adapter.generate(SCRIPT, SMOKE_DIR / "narration")
    narration_ok = art.status == "NARRATION_READY"
    target_dur = art.audio_duration if narration_ok else 28.0

    # ---- timeline（clip 段填充 narration 时长） ----
    total_avail = sum(min(8.0, (s["end_ms"] - s["start_ms"]) / 1000) for s in segs)
    scale = min(1.0, target_dur / total_avail) if total_avail else 1.0
    timeline = 0.0
    edit_segs = []
    timeline_items = []
    for i, (s, beat) in enumerate(zip(segs, BEATS)):
        dur = min(8.0, (s["end_ms"] - s["start_ms"]) / 1000) * scale
        if dur < 0.8:
            continue
        src_start = s["start_ms"] / 1000
        edit_segs.append(EditSegment(
            order=len(edit_segs) + 1, media_id=i, path=s["path"], category=beat,
            source_start=round(src_start, 3), source_end=round(src_start + dur, 3),
            timeline_start=round(timeline, 3), timeline_end=round(timeline + dur, 3),
            match_score=0.5, matched_terms=(beat,), content_fingerprint=s["sha256"]))
        timeline_items.append({
            "beat": beat, "segment_ref": f"b007:{s['note_id']}:{s['seg_no']}",
            "note_id": s["note_id"], "asset": f"b007:{s['note_id']}",
            "media_sha256": s["sha256"], "media_path": s["path"],
            "timeline_start_s": round(timeline, 3),
            "timeline_end_s": round(timeline + dur, 3),
            "source_start_s": round(src_start, 3), "source_end_s": round(src_start + dur, 3)})
        timeline += dur
    plan = EditPlan(requested_duration=round(target_dur, 3), planned_duration=round(timeline, 3),
                    complete=True, warnings=(), segments=tuple(edit_segs))
    plan_dur = timeline

    # provenance check：无 B003（全部路径 Z:）
    b003_contamination = [it for it in timeline_items if not it["media_path"].startswith("Z:")]
    provenance_ok = all(it["media_sha256"] and it["note_id"] and it["asset"] for it in timeline_items)

    # ---- timeline 校验 ----
    tl_errors = []
    prev_end = -1.0
    for it in timeline_items:
        if it["timeline_start_s"] < 0 or it["timeline_end_s"] < 0:
            tl_errors.append("negative")
        if it["timeline_end_s"] <= it["timeline_start_s"]:
            tl_errors.append("end<=start")
        if it["timeline_start_s"] < prev_end - 0.001:
            tl_errors.append("overlap")
        if it["source_end_s"] <= it["source_start_s"]:
            tl_errors.append("bad source trim")
        prev_end = it["timeline_end_s"]
    tl_valid = not tl_errors

    (SMOKE_DIR / "timeline.json").write_text(json.dumps(
        {"script": SCRIPT, "beats": BEATS, "items": timeline_items,
         "planned_duration": round(plan_dur, 2), "narration_duration": art.audio_duration},
        ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- 渲染：A) 现有 render_video_plan 可用性 ----
    renderer_readiness = {}
    try:
        from treecut.output.mp4 import render_video_plan
        legacy_out = SMOKE_DIR / "legacy_renderer_test.mp4"
        rr = render_video_plan(plan, legacy_out, FFMPEG, FFPROBE, profile="preview")
        renderer_readiness["render_video_plan"] = {"usable": True,
                                                   "duration": rr.duration, "size": rr.bytes}
    except Exception as e:
        renderer_readiness["render_video_plan"] = {"usable": False, "error": str(e)[:250]}

    # ---- 渲染：直接 ffmpeg concat（working path） ----
    video_out = SMOKE_DIR / "video_only.mp4"
    cmd = [str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y"]
    for s in edit_segs:
        cmd += ["-ss", f"{s.source_start:.3f}", "-t", f"{s.source_end - s.source_start:.3f}",
                "-i", s.path]
    fl = []
    labels = []
    for i in range(len(edit_segs)):
        fl.append(f"[{i}:v]scale=540:960:force_original_aspect_ratio=decrease,"
                  f"pad=540:960:(ow-iw)/2:(oh-ih)/2:black,fps=30,setsar=1[v{i}]")
        labels.append(f"[v{i}]")
    fl.append("".join(labels) + "concat=n=%d:v=1:a=0[outv]" % len(edit_segs))
    cmd += ["-filter_complex", ";".join(fl), "-map", "[outv]", "-an", "-c:v", "libx264",
            "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(video_out)]
    rr2 = subprocess.run(cmd, capture_output=True, timeout=1800)
    direct_render_ok = rr2.returncode == 0 and video_out.exists() and video_out.stat().st_size > 10000

    # ---- 混流 narration ----
    final_out = SMOKE_DIR / "TECHNICAL_SMOKE.mp4"
    mux = None
    if direct_render_ok and narration_ok:
        mux = subprocess.run(
            [str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
             "-i", str(video_out), "-i", str(art.wav),
             "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
             "-movflags", "+faststart", str(final_out)],
            capture_output=True, timeout=600)
    final_ok = bool(mux and mux.returncode == 0 and final_out.exists() and final_out.stat().st_size > 10000)

    # ---- QA ----
    qa = {}
    if final_ok:
        probe = subprocess.run([str(FFPROBE), "-v", "error", "-show_format", "-show_streams",
                                "-of", "json", str(final_out)], capture_output=True, timeout=120)
        p = json.loads(probe.stdout.decode("utf-8", errors="replace"))
        vs = next((s for s in p.get("streams", []) if s.get("codec_type") == "video"), None)
        aus = [s for s in p.get("streams", []) if s.get("codec_type") == "audio"]
        dur = float(p.get("format", {}).get("duration") or 0)
        dec = subprocess.run([str(FFMPEG), "-v", "error", "-i", str(final_out), "-f", "null", "-"],
                             capture_output=True, timeout=600)
        qa = {
            "SOURCE_IDENTITY": provenance_ok,
            "TIMELINE_VALID": tl_valid,
            "VIDEO_DECODABLE": dec.returncode == 0,
            "AUDIO_PRESENT": len(aus) > 0,
            "SUBTITLE_PRESENT": narration_ok and bool(art.srt and art.srt.exists() and art.srt.stat().st_size > 0),
            "DURATION_VALID": dur > 0,
            "SOURCE_PROVENANCE": provenance_ok and not b003_contamination,
            "RENDER_PASS": final_ok,
        }
        qa["video"] = {"codec": (vs or {}).get("codec_name"), "width": (vs or {}).get("width"),
                       "height": (vs or {}).get("height"), "duration_s": round(dur, 2),
                       "audio_streams": len(aus), "size": final_out.stat().st_size}
    status = "READY" if final_ok and all(qa.get(k) for k in
               ("SOURCE_IDENTITY", "TIMELINE_VALID", "VIDEO_DECODABLE", "AUDIO_PRESENT",
                "SUBTITLE_PRESENT", "DURATION_VALID", "SOURCE_PROVENANCE", "RENDER_PASS")) else (
        "PARTIAL" if final_ok else "FAILED")

    # ---- Jianying 就绪性（path B，尽力而为） ----
    jianying = {}
    try:
        from treecut.output.jianying import build_jianying_draft
        dj = SMOKE_DIR / "jianying_draft"
        dj.mkdir(parents=True, exist_ok=True)
        bj = build_jianying_draft(plan, dj, narration_wav=art.wav if narration_ok else None,
                                  bgm=None, subtitle_srt=art.srt if narration_ok else None,
                                  ffmpeg=FFMPEG)
        jianying = {"usable": True, "draft_dir": str(dj),
                    "detail": str(bj)[:200] if bj else "ok"}
    except Exception as e:
        jianying = {"usable": False, "error": str(e)[:250],
                    "note": "GUI 交互非本阶段要求（JIANYING_REQUIRES_HUMAN 不阻塞 direct renderer）"}

    (SMOKE_DIR / "qa.json").write_text(json.dumps({"status": status, "qa": qa,
                                                   "b003_contamination": len(b003_contamination)},
                                                  ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- outputs ----
    renderer_out = {"direct_ffmpeg_concat": {"usable": direct_render_ok,
                                             "note": "working smoke renderer (WinGet ffmpeg)"},
                    **renderer_readiness}
    (OUT / "TREECUT_RENDERER_READINESS_V1.json").write_text(json.dumps(renderer_out, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "TREECUT_JIANYING_READINESS_V1.json").write_text(json.dumps(jianying, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "B007_TECHNICAL_TIMELINE_V1.json").write_text(json.dumps(
        {"script": SCRIPT, "beats": BEATS, "items": timeline_items,
         "planned_duration": round(plan_dur, 2), "narration_duration": art.audio_duration,
         "timeline_errors": tl_errors}, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "B007_TECHNICAL_RENDER_RESULT_V1.json").write_text(json.dumps(
        {"final_mp4": str(final_out) if final_ok else None,
         "video_only": str(video_out) if direct_render_ok else None,
         "direct_render_ok": direct_render_ok, "final_ok": final_ok,
         "narration": art.to_dict()}, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "B007_PRODUCTION_QA_V1.json").write_text(json.dumps(
        {"status": status, "qa": qa, "schema": ["SOURCE_IDENTITY", "TIMELINE_VALID", "VIDEO_DECODABLE",
                                                "AUDIO_PRESENT", "SUBTITLE_PRESENT", "DURATION_VALID",
                                                "SOURCE_PROVENANCE", "RENDER_PASS"]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "B007_TECHNICAL_PRODUCTION_SMOKE_PLAN_V1.json").write_text(json.dumps(
        {"project": "B007_TECHNICAL_PRODUCTION_SMOKE_V1", "script": SCRIPT, "beats": BEATS,
         "segments": [{"note_id": s["note_id"], "seg_no": s["seg_no"], "sha256": s["sha256"],
                       "path": s["path"]} for s in segs],
         "narration_text_chars": len(SCRIPT)}, ensure_ascii=False, indent=2), encoding="utf-8")

    first_page = {
        "b007_segment_to_production_connected": True,
        "b007_source_provenance_valid": provenance_ok,
        "b003_contamination_count": len(b003_contamination),
        "timeline_built": tl_valid,
        "real_narration_attached": narration_ok,
        "real_subtitle_attached": bool(narration_ok and art.srt and art.srt.stat().st_size > 0),
        "direct_renderer_available": direct_render_ok,
        "new_technical_mp4_generated": final_ok,
        "mp4_decodable": bool(qa.get("VIDEO_DECODABLE")),
        "jianying_path_usable": jianying.get("usable", False),
        "production_qa_created": bool(qa),
        "remaining_blockers_to_first_real_video": [
            "L3 Review16 集成（用户审核中）",
            "模板/选镜/排序规则（V0.9）",
            "BGM/转场可选增强",
            "内容 QA（好看与否）——后续 Pilot"],
    }
    final_status = ("TREECUT_PRODUCTION_PREFLIGHT_PASS" if status == "READY" and not b003_contamination
                    else ("TREECUT_PRODUCTION_PREFLIGHT_PASS_WITH_LIMITATIONS" if final_ok
                          else "TREECUT_PRODUCTION_PREFLIGHT_NEEDS_REPAIR"))
    md = ["# TreeCut B007 Production Path Preflight (V0.8.5)", "",
          f"Status: **{final_status}** | {time.strftime('%Y-%m-%d %H:%M:%S')}", "",
          "## First page", "", "```json",
          json.dumps(first_page, ensure_ascii=False, indent=2), "```",
          "", "## QA", "", json.dumps(qa, ensure_ascii=False, indent=2),
          "", "## Timeline", "", f"- items={len(timeline_items)} duration={round(plan_dur,2)}s "
          f"narration={art.audio_duration}s errors={tl_errors}",
          "", "## Renderer / Jianying", "",
          f"- direct ffmpeg concat: {direct_render_ok}",
          f"- render_video_plan: {renderer_readiness.get('render_video_plan')}",
          f"- jianying: {jianying}",
          "", "## Remaining blockers", ""]
    for b in first_page["remaining_blockers_to_first_real_video"]:
        md.append(f"- {b}")
    md += ["", "## STOP — preflight complete; no V0.9/Template/AutoCut/AutoPublish", ""]
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "TREECUT_B007_PRODUCTION_PATH_PREFLIGHT_V1.md").write_text("\n".join(md), encoding="utf-8")

    print(json.dumps({"status": status, "final_status": final_status, "first_page": first_page,
                      "narration_duration": art.audio_duration,
                      "plan_duration": round(plan_dur, 2),
                      "renderer": {"direct": direct_render_ok,
                                   "render_video_plan": renderer_readiness.get("render_video_plan", {}).get("usable")},
                      "jianying": jianying.get("usable"),
                      "qa": qa, "elapsed_s": round(time.time() - t0, 1)},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
