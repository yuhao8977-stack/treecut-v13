# -*- coding: utf-8 -*-
"""V0.2 — B007 Performance 提取（Route B 页面自有响应）+ PublishedContent Join。

数据源：schema_evidence 最新 run 的 notes_union.json（含 engagement）。
  - engagement: view_count/likes/comments_count/shared_count/collected_count
    （来源：creator note/user/posted 官方页面自有响应，非模拟 API）
  - 写入 performance_snapshot_v1（append-only，幂等：同 note+source+snapshot_time 跳过）
  - join 状态：EXACT_NOTE_ID_MATCH / UNMATCHED
  - 账号级 7d/30d：本会话未捕获（datacenter overview 未在页面观察范围）→ UNKNOWN，诚实记录
官方导出状态：EXPORT_LOCATOR_UNKNOWN（DOM 校准尝试未找到按钮，见报告 limitation）
输出：B007_V02_PERFORMANCE_V1.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.services.b007_creator_adapter import B007CreatorImportAdapterV1  # noqa: E402

DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
EVIDENCE_ROOT = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
                     r"\browser_profiles\B007\treecut_inbox\creator\raw\creator\schema_evidence")
SOURCE = "SRC-B007-POSTED-OBSERVED"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage\B007_V02_PERFORMANCE_V1.json")


def latest_run() -> Path:
    runs = sorted(EVIDENCE_ROOT.glob("*")) if EVIDENCE_ROOT.exists() else []
    return runs[-1] if runs else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="")
    args = ap.parse_args(argv)
    run_dir = (EVIDENCE_ROOT / args.run) if args.run else latest_run()
    notes = json.loads((run_dir / "notes_union.json").read_text(encoding="utf-8"))
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    run_name = run_dir.name
    print(f"evidence = {run_name}, notes = {len(notes)}")

    adapter = B007CreatorImportAdapterV1(DB)
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row

    snapshot_time = time.strftime("%Y-%m-%d %H:%M")
    inserted = 0
    skipped = 0
    joined = {"EXACT_NOTE_ID_MATCH": 0, "UNMATCHED": 0}
    eng_fields = ("view_count", "likes", "comments_count", "shared_count", "collected_count")
    eng_counts = {f: 0 for f in eng_fields}

    for nid, n in sorted(notes.items()):
        eng = n.get("engagement") or {}
        if not any(eng.get(f) is not None for f in eng_fields):
            continue
        for f in eng_fields:
            if eng.get(f) is not None:
                eng_counts[f] += 1
        pc_id = adapter.published_content_id("B007", nid)
        exists = conn.execute(
            "SELECT 1 FROM performance_snapshot_v1 WHERE published_content_id=? "
            "AND source=? AND snapshot_time=?",
            (pc_id, SOURCE, snapshot_time)).fetchone()
        if exists:
            skipped += 1
        else:
            conn.execute(
                "INSERT INTO performance_snapshot_v1(snapshot_id,published_content_id,"
                "snapshot_time,window,views,likes,favorites,comments,shares,"
                "private_messages,leads,forms,ad_spend,paid_impressions,paid_clicks,paid_leads,"
                "metric_type,source,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (f"SNAP-{nid[:8]}-{int(time.time())}", pc_id, snapshot_time, "UNKNOWN",
                 eng.get("view_count"), eng.get("likes"), eng.get("collected_count"),
                 eng.get("comments_count"), eng.get("shared_count"),
                 None, None, None, None, None, None, None,
                 "MIXED", SOURCE, time.time()))
            inserted += 1
        # join 状态
        pc_exists = conn.execute(
            "SELECT 1 FROM published_content_v1 WHERE published_content_id=?",
            (pc_id,)).fetchone()
        if pc_exists:
            joined["EXACT_NOTE_ID_MATCH"] += 1
            conn.execute(
                "INSERT OR IGNORE INTO content_join_status_v1(join_id,published_content_id,note_id,"
                "join_method,join_status,matched_title,evidence,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (f"JOIN-{nid[:8]}-{int(time.time())}", pc_id, nid, "NOTE_ID",
                 "EXACT_NOTE_ID_MATCH", n.get("title", "")[:80],
                 f"posted_capture:{run_name}", time.time()))
        else:
            joined["UNMATCHED"] += 1
    conn.commit()

    # 未在 evidence 的旧行 join 状态
    evidence_ids = set(notes.keys())
    legacy = conn.execute(
        "SELECT note_id FROM published_content_v1 WHERE account_id='B007'").fetchall()
    legacy_unmatched = 0
    for r in legacy:
        if r["note_id"] not in evidence_ids:
            legacy_unmatched += 1
    joined["UNMATCHED"] += legacy_unmatched

    # DB 汇总
    total_perf = conn.execute(
        "SELECT COUNT(*) FROM performance_snapshot_v1 WHERE source=?",
        (SOURCE,)).fetchone()[0]
    conn.close()

    result = {
        "run": run_name,
        "source": SOURCE,
        "source_note": "creator note/user/posted 页面自有响应（官方页面数据，非模拟 signed API）；"
                       "官方导出按钮定位在本会话未找到 → EXPORT_LOCATOR_UNKNOWN（limitation）",
        "snapshot_time": snapshot_time,
        "window": "UNKNOWN（列表为累计值，非 7d/30d 窗口）",
        "inserted": inserted,
        "skipped_idempotent": skipped,
        "engagement_field_coverage": eng_counts,
        "join": joined,
        "account_level_7d_30d": "UNKNOWN / SOURCE_NOT_PROVIDED（datacenter overview 未在本轮页面观察捕获；"
                                "账号级指标不分配给笔记）",
        "total_perf_rows_b007": total_perf,
        "export": {"status": "EXPORT_LOCATOR_UNKNOWN",
                   "attempts": ["note-manager 已发布 tab 语义文本扫描（导出/下载报表/下载数据/导出报表/下载）",
                                "datacenter /data/overview /data/note /data/content → 404",
                                "平台首页 数据看板 → 粉丝概览卡，无导出按钮"]},
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
