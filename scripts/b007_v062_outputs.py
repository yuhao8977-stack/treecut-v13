# -*- coding: utf-8 -*-
"""V0.6.2 — 输出生成：从 checkpoint + manifest + registry DB 生成全部 V2 产物与最终判定。

产物:
  B007_SAMPLE20_MEDIA_RECOVERY_V2.json
  B007_SAMPLE20_MEDIA_TECH_METADATA_V2.json
  B007_SAMPLE20_MEDIA_DUPLICATES_V2.json
  B007_SAMPLE20_MEDIA_EXCEPTIONS_V2.json
  B007_SAMPLE20_MEDIA_RECOVERY_REVIEW_V2.md
  B007_V062_NAVIGATION_REPORT_V1.json
  docs/PHASE4_B007_V062_BATCH_MEDIA_RECOVERY_REPORT.md
最终判定: B007_V062_MEDIA_RECOVERY_PASS / _PASS_WITH_LIMITATIONS / _NEEDS_REPAIR
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
DOCS = REPO / "docs"
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
Z_MEDIA = Path(r"Z:\TreeCut_Media\B007\published_media")
CHECKPOINT = OUT / "B007_V062_CHECKPOINT_V1.json"
MANIFEST = OUT / "B007_SAMPLE20_V1.json"

EXACT = {"RECOVERED_EXACT", "ALREADY_RECOVERED_VALID"}


def load_db_rows() -> dict:
    rows = {}
    try:
        conn = sqlite3.connect(DB, timeout=30)
        cur = conn.execute(
            "SELECT note_id, sample_id, expected_note_id, actual_note_id, recovery_status, source_type, "
            "byte_size, sha256, duration, width, height, fps, video_codec, audio_codec, creator_duration, "
            "duration_match_status, final_path, validation_version, block_reason, attempts "
            "FROM b007_published_media_recovery_v1")
        for r in cur.fetchall():
            rows[r[0]] = {
                "note_id": r[0], "sample_id": r[1], "expected_note_id": r[2], "actual_note_id": r[3],
                "recovery_status": r[4], "source_type": r[5], "byte_size": r[6], "sha256": r[7],
                "duration": r[8], "width": r[9], "height": r[10], "fps": r[11], "video_codec": r[12],
                "audio_codec": r[13], "creator_duration": r[14], "duration_match_status": r[15],
                "final_path": r[16], "validation_version": r[17], "block_reason": r[18], "attempts": r[19]}
        conn.close()
    except Exception as e:
        print(f"db read error: {e}")
    return rows


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    samples = manifest["samples"]
    cp = json.loads(CHECKPOINT.read_text(encoding="utf-8")) if CHECKPOINT.exists() else {"notes": {}}
    cp_notes = cp.get("notes", {})
    db_rows = load_db_rows()

    records = []
    for s in samples:
        nid = s["note_id"]
        cp_entry = cp_notes.get(nid, {})
        db_row = db_rows.get(nid, {})
        status = cp_entry.get("status") or db_row.get("recovery_status") or "PENDING"
        tech = cp_entry.get("tech") or {}
        rec = {
            "sample_id": s["sample_id"],
            "primary_stratum": s.get("primary_stratum"),
            "selection_reason": s.get("reason"),
            "selection_rule_version": manifest.get("rule_version"),
            "note_id": nid,
            "title": s.get("title"),
            "publish_time": s.get("publish_time"),
            "creator_duration": s.get("duration"),
            "nav_mode": cp_entry.get("nav_mode") or ("PILOT1" if nid == "69f9a0ac000000003701d937" else None),
            "status": status,
            "attempts": cp_entry.get("attempts") or db_row.get("attempts"),
            "actual_note_id": db_row.get("actual_note_id") or cp_entry.get("actual_note_id"),
            "recovered_duration": tech.get("duration") or db_row.get("duration"),
            "resolution": f"{tech.get('width') or db_row.get('width')}x{tech.get('height') or db_row.get('height')}",
            "byte_size": tech.get("size") or db_row.get("byte_size"),
            "sha256": tech.get("sha256") or db_row.get("sha256"),
            "sha256_prefix": (tech.get("sha256") or db_row.get("sha256") or "")[:12],
            "fps": tech.get("fps") or db_row.get("fps"),
            "video_codec": tech.get("video_codec") or db_row.get("video_codec"),
            "audio_codec": tech.get("audio_codec") or db_row.get("audio_codec"),
            "full_decode_ok": tech.get("full_decode_ok"),
            "ffprobe_ok": tech.get("ffprobe_ok"),
            "duration_match_status": tech.get("duration_match_status") or db_row.get("duration_match_status"),
            "final_path": tech.get("final_path") or db_row.get("final_path"),
            "blob_mode": tech.get("blob_mode"),
            "canonical_note": tech.get("canonical_note"),
            "warning": None,
        }
        # warnings
        warns = []
        if status in EXACT:
            if rec["final_path"] is None:
                warns.append("exact but no final_path")
            if rec["sha256"] is None:
                warns.append("exact but no sha256")
            if rec["full_decode_ok"] is False:
                warns.append("full_decode not verified")
            if rec["final_path"] and not str(rec["final_path"]).startswith("Z:"):
                warns.append("final path not on Z")
            if rec["actual_note_id"] and rec["actual_note_id"] != nid:
                warns.append(f"actual_note_id mismatch {rec['actual_note_id']}")
            if rec["recovered_duration"] and rec["creator_duration"]:
                tol = max(5.0, rec["creator_duration"] * 0.15)
                if abs(float(rec["recovered_duration"]) - float(rec["creator_duration"])) > tol:
                    warns.append("duration crosscheck outside tolerance")
        if status == "PENDING":
            warns.append("no explicit status")
        rec["warning"] = "; ".join(warns) if warns else None
        records.append(rec)

    # ---- 汇总
    by_status = {}
    for r in records:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    recovered = [r for r in records if r["status"] in EXACT]
    exact_available = len(recovered)
    nav_auto = len([r for r in records if r["nav_mode"] == "AUTO" and r["status"] in EXACT])
    nav_human = len([r for r in records if r["nav_mode"] == "HUMAN" and r["status"] in EXACT])
    nav_human_attempted = len([r for r in records if r["nav_mode"] and "HUMAN" in str(r["nav_mode"])])
    nav_failed = len([r for r in records if r["status"] == "FAILED_NEEDS_HUMAN"])

    # ---- duplicates
    sha_groups = {}
    for r in recovered:
        if r["sha256"]:
            sha_groups.setdefault(r["sha256"], []).append(r["note_id"])
    dup_groups = {sha: nids for sha, nids in sha_groups.items() if len(nids) > 1}

    # ---- tech coverage（成功媒体）
    def cov(key, pred):
        base = [r for r in recovered if r.get(key) is not None and r.get(key) is not False]
        return {"numerator": len(base), "denominator": len(recovered),
                "coverage": round(len(base) / len(recovered), 3) if recovered else None}

    tech_coverage = {
        "sha256": cov("sha256", lambda x: bool(x)),
        "ffprobe": cov("ffprobe_ok", lambda x: bool(x)),
        "full_decode": cov("full_decode_ok", lambda x: bool(x)),
        "duration_crosscheck": {"numerator": len([r for r in recovered if r["duration_match_status"] == "MATCH_WITHIN_TOLERANCE"]),
                                "denominator": len(recovered),
                                "coverage": round(len([r for r in recovered if r["duration_match_status"] == "MATCH_WITHIN_TOLERANCE"]) / len(recovered), 3) if recovered else None},
        "resolution": cov("resolution", lambda x: "x" in str(x) and "None" not in str(x)),
        "codec": cov("video_codec", lambda x: bool(x)),
        "audio": {"numerator": len([r for r in recovered if r["audio_codec"]]),
                  "denominator": len(recovered),
                  "coverage": round(len([r for r in recovered if r["audio_codec"]]) / len(recovered), 3) if recovered else None},
    }

    # ---- validation (§58)
    unexpected = [r["note_id"] for r in records if r["note_id"] not in {s["note_id"] for s in samples}]
    no_replacements = len(records) == 20 and len({r["note_id"] for r in records}) == 20 and not unexpected
    validation = {
        "target": 20,
        "records": len(records),
        "unexpected_note_ids": unexpected,
        "no_replacements": no_replacements,
        "every_exact_gate": all(
            (r["actual_note_id"] in (None, r["note_id"])) and
            bool(r["sha256"]) and bool(r["ffprobe_ok"] is not False) and
            bool(r["full_decode_ok"] is not False) and
            bool(r["final_path"]) and str(r["final_path"]).startswith("Z:")
            for r in recovered),
    }

    # ---- final status
    non_terminal = [r for r in records if r["status"] == "PENDING"]
    all_terminal = not non_terminal
    all_exact = all_terminal and len(recovered) == 20
    some_exact = len(recovered) > 0
    any_invalid_recovered = any(r["warning"] for r in recovered)
    if all_terminal and all_exact and not any_invalid_recovered and no_replacements and validation["every_exact_gate"]:
        final_status = "B007_V062_MEDIA_RECOVERY_PASS"
    elif all_terminal and some_exact and not any_invalid_recovered and no_replacements and validation["every_exact_gate"]:
        final_status = "B007_V062_MEDIA_RECOVERY_PASS_WITH_LIMITATIONS"
    else:
        final_status = "B007_V062_MEDIA_RECOVERY_NEEDS_REPAIR"

    c_free_after = round(shutil.disk_usage("C:\\").free / 2**30, 1)

    # ---- outputs
    recovery_v2 = {
        "rule_version": "SAMPLE_SELECTION_RULE_V1 (frozen)",
        "phase": "V0.6.2-SAMPLE20-BATCH-EXACT-MEDIA-RECOVERY",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "final_status": final_status,
        "summary": {
            "target": 20, "already_recovered_valid": by_status.get("ALREADY_RECOVERED_VALID", 0),
            "newly_recovered_exact": by_status.get("RECOVERED_EXACT", 0),
            "total_exact_available": exact_available,
            "note_unavailable": by_status.get("NOTE_UNAVAILABLE", 0),
            "identity_mismatch": by_status.get("NOTE_IDENTITY_MISMATCH", 0),
            "media_not_observed": by_status.get("MEDIA_NOT_OBSERVED", 0),
            "validation_failed": by_status.get("MEDIA_VALIDATION_FAILED", 0),
            "failed_needs_human": by_status.get("FAILED_NEEDS_HUMAN", 0),
            "pending": len(non_terminal),
        },
        "by_status": by_status,
        "records": records,
        "validation": validation,
        "c_drive_guard": {"free_before_gb": cp.get("c_free_before_gb"), "free_after_gb": c_free_after,
                          "note": "媒体恢复不得造成 C 盘下降"},
    }
    (OUT / "B007_SAMPLE20_MEDIA_RECOVERY_V2.json").write_text(
        json.dumps(recovery_v2, ensure_ascii=False, indent=2), encoding="utf-8")

    tech_v2 = {r["note_id"]: {k: r[k] for k in
               ("sample_id", "status", "recovered_duration", "resolution", "fps", "video_codec",
                "audio_codec", "byte_size", "sha256", "full_decode_ok", "ffprobe_ok",
                "duration_match_status", "final_path", "blob_mode", "canonical_note")}
               for r in records if r["status"] in EXACT}
    (OUT / "B007_SAMPLE20_MEDIA_TECH_METADATA_V2.json").write_text(
        json.dumps({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "notes": tech_v2,
                    "tech_coverage": tech_coverage}, ensure_ascii=False, indent=2), encoding="utf-8")

    dups_v2 = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "recovered_note_count": len(recovered),
        "unique_sha256_count": len(sha_groups),
        "exact_duplicate_group_count": len(dup_groups),
        "groups": [{"sha256": sha, "note_ids": nids} for sha, nids in dup_groups.items()],
        "policy": "SHA256 EXACT only; no perceptual/visual/semantic dedup in this phase",
    }
    (OUT / "B007_SAMPLE20_MEDIA_DUPLICATES_V2.json").write_text(
        json.dumps(dups_v2, ensure_ascii=False, indent=2), encoding="utf-8")

    exceptions = [r for r in records if r["status"] not in EXACT]
    exceptions_v2 = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(exceptions),
        "policy": "禁止用其他笔记替换 Sample20; 每条必须明确状态; 不得静默遗留 PENDING",
        "items": [{k: r[k] for k in ("sample_id", "note_id", "title", "status", "attempts", "warning")}
                  for r in exceptions],
    }
    (OUT / "B007_SAMPLE20_MEDIA_EXCEPTIONS_V2.json").write_text(
        json.dumps(exceptions_v2, ensure_ascii=False, indent=2), encoding="utf-8")

    nav_report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "scope": "19 remaining (Pilot1 excluded, ALREADY_RECOVERED_VALID)",
        "auto_creator_navigation_success": nav_auto,
        "human_assisted_navigation": nav_human,
        "human_assisted_attempted_total": nav_human_attempted,
        "navigation_failed": nav_failed,
        "detail": [{"sample_id": r["sample_id"], "note_id": r["note_id"], "nav_mode": r["nav_mode"],
                    "status": r["status"]} for r in records if r["note_id"] != "69f9a0ac000000003701d937"],
        "conclusion": "决定后续是否仍需用户点击的量化依据",
    }
    (OUT / "B007_V062_NAVIGATION_REPORT_V1.json").write_text(
        json.dumps(nav_report, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- review MD
    lines = ["# B007 Sample20 Media Recovery Review — V2",
             "",
             f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}  |  Final: **{final_status}**",
             "",
             "| sample_id | stratum | note_id | title | nav | creator dur | rec dur | resolution | size | sha256 | status | final path | warning |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in records:
        title = (r["title"] or "").replace("|", "/")[:40]
        lines.append(
            f"| {r['sample_id']} | {r['primary_stratum']} | {r['note_id']} | {title} | "
            f"{r['nav_mode'] or '-'} | {r['creator_duration']} | {r['recovered_duration'] or '-'} | "
            f"{r['resolution'] or '-'} | {r['byte_size'] or '-'} | {r['sha256_prefix'] or '-'} | "
            f"{r['status']} | {r['final_path'] or '-'} | {r['warning'] or ''} |")
    lines += ["", f"Coverage: sha256 {tech_coverage['sha256']['coverage']} | "
                  f"ffprobe {tech_coverage['ffprobe']['coverage']} | "
                  f"full_decode {tech_coverage['full_decode']['coverage']} | "
                  f"duration_crosscheck {tech_coverage['duration_crosscheck']['coverage']} | "
                  f"resolution {tech_coverage['resolution']['coverage']} | "
                  f"codec {tech_coverage['codec']['coverage']} | audio {tech_coverage['audio']['coverage']}",
             "",
             f"Duplicates: unique sha256 = {len(sha_groups)} / recovered {len(recovered)}; "
             f"exact dup groups = {len(dup_groups)}",
             f"Validation: no_replacements={no_replacements}, unexpected_ids={len(unexpected)}, "
             f"every_exact_gate={validation['every_exact_gate']}",
             ""]
    (OUT / "B007_SAMPLE20_MEDIA_RECOVERY_REVIEW_V2.md").write_text("\n".join(lines), encoding="utf-8")

    # ---- docs report
    docs = [
        "# Phase 4 — B007 V0.6.2 Batch Exact Media Recovery Report",
        "",
        "## Status",
        "",
        f"**{final_status}**",
        "",
        "## Approval",
        "",
        "V0.6.1 (V06_ASSISTED_PILOT1_PASS) 验收通过后，架构批准 V0.6.2 处理 Sample20 剩余 19 条。",
        "默认 AUTO_CREATOR_NAVIGATION（搜索→定位→正常点击 Creator 卡片→平台生成合法 Frontend Detail），",
        "无法唯一定位时 HUMAN_ASSISTED_NAVIGATION（用户只需正常点击，不下载/不复制 URL/不看 Network）。",
        "",
        "## Method (locked disciplines)",
        "",
        "- 输入冻结：B007_SAMPLE20_V1（20 条，不增换选）；Pilot1 预检 ALREADY_RECOVERED_VALID 后禁止重下载。",
        "- 身份唯一：actual_note_id == expected_note_id 硬门；title 仅 NAVIGATION_HINT。",
        "- 媒体路径：Creator 卡片正常点击 → 平台自带合法 xsec 的前台详情 → 播放器真实请求视频（PAGE_OWNED_MEDIA_OBSERVATION）。",
        "- 媒体 URL 仅存内存生命周期内（临时签名 URL 不落 DB/JSON/MD/Log）。",
        "- 验证：ffprobe + 全量 ffmpeg decode + SHA256 + 统一 duration 容差（max(5.0, dur*0.15)）。",
        "- 存储：E staging(.part) → 验证通过后 shutil.move 至 Z（跨卷 os.replace 会 WinError 17）。",
        "- 重复：SHA256 EXACT 去重；已有 blob 只建 note→canonical reference，不重复保存。",
        "- 串行单 worker、逐条 checkpoint、可断点续跑；C-drive guard + Z gate。",
        "",
        "## Result",
        "",
        f"- target = 20",
        f"- already recovered valid = {by_status.get('ALREADY_RECOVERED_VALID', 0)}",
        f"- newly recovered exact = {by_status.get('RECOVERED_EXACT', 0)}",
        f"- total exact available = {exact_available}",
        f"- navigation auto success = {nav_auto} (of 19 remaining)",
        f"- human navigation required = {nav_human} (of 19 remaining)",
        f"- navigation failed = {nav_failed}",
        f"- note unavailable = {by_status.get('NOTE_UNAVAILABLE', 0)}",
        f"- identity mismatch = {by_status.get('NOTE_IDENTITY_MISMATCH', 0)}",
        f"- media not observed = {by_status.get('MEDIA_NOT_OBSERVED', 0)}",
        f"- validation failure = {by_status.get('MEDIA_VALIDATION_FAILED', 0)}",
        f"- failed needs human = {by_status.get('FAILED_NEEDS_HUMAN', 0)}",
        f"- pending = {len(non_terminal)}",
        "",
        "## Tech Coverage (recovered media)",
        "",
        f"- SHA256 coverage: {tech_coverage['sha256']['numerator']}/{tech_coverage['sha256']['denominator']}",
        f"- ffprobe coverage: {tech_coverage['ffprobe']['numerator']}/{tech_coverage['ffprobe']['denominator']}",
        f"- full decode coverage: {tech_coverage['full_decode']['numerator']}/{tech_coverage['full_decode']['denominator']}",
        f"- duration crosscheck: {tech_coverage['duration_crosscheck']['numerator']}/{tech_coverage['duration_crosscheck']['denominator']}",
        f"- resolution coverage: {tech_coverage['resolution']['numerator']}/{tech_coverage['resolution']['denominator']}",
        f"- codec coverage: {tech_coverage['codec']['numerator']}/{tech_coverage['codec']['denominator']}",
        f"- audio coverage: {tech_coverage['audio']['numerator']}/{tech_coverage['audio']['denominator']}",
        "",
        "## Duplicate Report",
        "",
        f"- recovered note count = {len(recovered)}",
        f"- unique SHA256 count = {len(sha_groups)}",
        f"- exact duplicate group count = {len(dup_groups)}",
        "",
        "## Honest Limitations",
        "",
        "- 媒体身份 = note_id + SHA256；不含视觉/语义去重（本轮只做 SHA256 EXACT）。",
        "- 恢复不代表业务归因；与投放/表现无因果关系（沿用 V0.4 纪律）。",
        "- 若存在 NOTE_UNAVAILABLE / FAILED_NEEDS_HUMAN，不虚构成功、不换样本。",
        "- 标题搜索仅导航提示；身份永远以 note_id 硬门为准。",
        "",
        "## C-Drive Guard",
        "",
        f"- C free before: {cp.get('c_free_before_gb')} GB",
        f"- C free after: {c_free_after} GB",
        "",
        "## STOP",
        "",
        "处理完整 Sample20 后 STOP。不自动进入 V0.7（Canonical Asset / Segment / ASR / OCR / Business Cognition）。",
        "",
    ]
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "PHASE4_B007_V062_BATCH_MEDIA_RECOVERY_REPORT.md").write_text("\n".join(docs), encoding="utf-8")

    print(json.dumps({"final_status": final_status, "summary": recovery_v2["summary"],
                      "validation": validation, "c_free_after_gb": c_free_after,
                      "nav_auto": nav_auto, "nav_human": nav_human, "nav_failed": nav_failed,
                      "dup_groups": len(dup_groups)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
