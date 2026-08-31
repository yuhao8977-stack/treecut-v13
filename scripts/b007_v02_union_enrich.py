# -*- coding: utf-8 -*-
"""V0.2 — B007 published union + enrichment（幂等，字段级 provenance）。

从最新 schema_evidence run 读取 notes_union.json（posted 全分页富字段），
与 DB published_content_v1 按 account+note_id union：
  - 不存在 → INSERT（source_refs=[POSTED_CAPTURE:<run>]）
  - 存在且字段空 → 填充（enrichment，来源=POSTED_CAPTURE）
  - 存在且字段冲突（非空且不同）→ 按 precedence POSTED_CAPTURE > 旧 OBSERVATION 覆盖，
    并计数 REVIEW_REQUIRED（报告统计，§16）
cover metadata 存入新增列 cover_url_safe/cover_origin/cover_path（非阻塞，§17）。
输出：B007_V02_ENRICHMENT_V1.json
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.services.b007_creator_adapter import B007CreatorImportAdapterV1  # noqa: E402

DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
EVIDENCE_ROOT = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
                     r"\browser_profiles\B007\treecut_inbox\creator\raw\creator\schema_evidence")

FIELDS = {
    "title": "title",
    "publish_time": "publish_time",
    "media_type": "content_type",
    "duration": "duration",
}


def ensure_cover_columns(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(published_content_v1)")}
    for c in ("cover_url_safe", "cover_origin", "cover_path"):
        if c not in cols:
            conn.execute(f"ALTER TABLE published_content_v1 ADD COLUMN {c} TEXT")
    conn.commit()


def latest_evidence_run() -> Path:
    runs = sorted(EVIDENCE_ROOT.glob("*")) if EVIDENCE_ROOT.exists() else []
    if not runs:
        raise SystemExit("no evidence runs found")
    return runs[-1]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="", help="evidence run dir name (default: latest)")
    args = ap.parse_args(argv)

    run_dir = Path(args.run) if args.run else latest_evidence_run()
    notes = json.loads((run_dir / "notes_union.json").read_text(encoding="utf-8"))
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    run_name = run_dir.name
    ref = f"POSTED_CAPTURE:{run_name}"
    print(f"evidence run = {run_name}, notes = {len(notes)}, pages = {summary['pages_in_order']}")

    adapter = B007CreatorImportAdapterV1(DB)
    conn = sqlite3.connect(DB, timeout=30)
    ensure_cover_columns(conn)
    conn.row_factory = sqlite3.Row

    existing = {r["note_id"]: dict(r) for r in conn.execute(
        "SELECT * FROM published_content_v1 WHERE account_id='B007'")}
    print(f"existing B007 rows = {len(existing)}")

    stats = {"new": 0, "updated": 0, "conflicts": {}, "cover_filled": 0,
             "notes_in_evidence": len(notes)}
    conflicts = []

    def norm(v):
        return "" if v is None else str(v).strip()

    def upsert(rec):
        """单连接幂等 upsert（与 adapter 同语义）。"""
        pc_id = adapter.published_content_id(rec["account_id"], rec["note_id"])
        old_row = conn.execute(
            "SELECT source_refs FROM published_content_v1 WHERE published_content_id=?",
            (pc_id,)).fetchone()
        now = time.time()
        if old_row:
            refs = set(json.loads(old_row[0] or "[]"))
            refs.update(rec.get("source_refs", []))
            conn.execute(
                "UPDATE published_content_v1 SET title=?, publish_time=?, content_type=?,"
                "duration=?, note_url=?, source_refs=?, updated_at=? "
                "WHERE published_content_id=?",
                (rec.get("title", ""), rec.get("publish_time", ""),
                 rec.get("content_type", ""), rec.get("duration"),
                 rec.get("note_url", ""), json.dumps(sorted(refs), ensure_ascii=False),
                 now, pc_id))
        else:
            conn.execute(
                "INSERT INTO published_content_v1(published_content_id,platform,account_id,"
                "note_id,note_url,title,publish_time,content_type,duration,"
                "asset_id,asset_mapping_method,asset_mapping_confidence,"
                "source_refs,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (pc_id, adapter.PLATFORM, rec["account_id"], rec["note_id"],
                 rec.get("note_url", ""), rec.get("title", ""),
                 rec.get("publish_time", ""), rec.get("content_type", ""),
                 rec.get("duration"), rec.get("asset_id"),
                 rec.get("asset_mapping_method", "UNKNOWN"),
                 rec.get("asset_mapping_confidence", "UNKNOWN"),
                 json.dumps(rec.get("source_refs", []), ensure_ascii=False),
                 now, now))
        return pc_id

    for nid, n in sorted(notes.items()):
        rec = {
            "account_id": "B007",
            "note_id": nid,
            "note_url": f"https://www.xiaohongshu.com/explore/{nid}",
            "title": norm(n.get("title")),
            "publish_time": norm(n.get("publish_time")),
            "content_type": norm(n.get("media_type")).lower(),
            "duration": n.get("duration"),
            "source_refs": [ref],
        }
        cover = n.get("cover") or {}
        old = existing.get(nid)
        if old is None:
            upsert(rec)
            if cover:
                conn.execute(
                    "UPDATE published_content_v1 SET cover_url_safe=?,cover_origin=?,cover_path=? "
                    "WHERE published_content_id=?",
                    (cover.get("cover_url_safe"), cover.get("cover_origin"),
                     cover.get("cover_path"),
                     adapter.published_content_id("B007", nid)))
            stats["new"] += 1
            if cover:
                stats["cover_filled"] += 1
            continue

        # enrichment: 空则填；冲突则 precedence 覆盖 + 计数
        pc_id = old["published_content_id"]
        updates = {}
        for src_field, db_field in FIELDS.items():
            newv = rec[db_field] if db_field != "title" else rec["title"]
            if db_field == "duration":
                newv = rec["duration"]
            oldv = old[db_field]
            if db_field == "duration":
                oldv = old["duration"]
            if db_field == "content_type":
                oldv = norm(oldv).lower()
            newv_n = norm(newv) if db_field != "duration" else newv
            oldv_n = norm(oldv) if db_field != "duration" else oldv
            if newv_n in ("", None):
                continue
            if oldv_n in ("", None):
                updates[db_field] = newv
            elif db_field == "duration":
                # 数值相等（int/float 表示差异）不算冲突
                try:
                    if abs(float(newv_n) - float(oldv_n)) > 1e-6:
                        updates[db_field] = newv
                        stats["conflicts"][db_field] = stats["conflicts"].get(db_field, 0) + 1
                        conflicts.append({"note_id": nid, "field": db_field,
                                          "old": oldv, "new": newv, "source": ref})
                except (TypeError, ValueError):
                    updates[db_field] = newv
            elif str(newv_n) != str(oldv_n):
                # 冲突：POSTED_CAPTURE precedence
                updates[db_field] = newv
                stats["conflicts"][db_field] = stats["conflicts"].get(db_field, 0) + 1
                conflicts.append({"note_id": nid, "field": db_field,
                                  "old": oldv, "new": newv, "source": ref})
        cover_changed = False
        if cover and not norm(old.get("cover_url_safe")):
            updates["cover_url_safe"] = cover.get("cover_url_safe")
            updates["cover_origin"] = cover.get("cover_origin")
            updates["cover_path"] = cover.get("cover_path")
            cover_changed = True
        if updates or cover_changed:
            # 合并 source_refs（保留旧来源）
            refs = set(json.loads(old["source_refs"] or "[]"))
            refs.add(ref)
            updates["source_refs"] = json.dumps(sorted(refs), ensure_ascii=False)
            updates["updated_at"] = time.time()
            cols = ", ".join(f"{k}=?" for k in updates)
            conn.execute(
                f"UPDATE published_content_v1 SET {cols} WHERE published_content_id=?",
                (*updates.values(), pc_id))
            stats["updated"] += 1
            if cover_changed:
                stats["cover_filled"] += 1

    conn.commit()

    # 覆盖率（enrichment 后）
    cov = {}
    for col in ("note_id", "title", "publish_time", "content_type", "duration",
                "cover_url_safe"):
        n = conn.execute(
            f"SELECT COUNT(*) FROM published_content_v1 WHERE account_id='B007'"
            f" AND {col} IS NOT NULL AND {col} != ''").fetchone()[0]
        cov[col] = n
    total = conn.execute(
        "SELECT COUNT(*) FROM published_content_v1 WHERE account_id='B007'").fetchone()[0]
    cov["total"] = total
    conn.close()

    result = {
        "run": run_name,
        "source_ref": ref,
        "precedence": "POSTED_CAPTURE > old OBSERVATION(DOM/SSR)",
        "stats": stats,
        "conflicts_sample": conflicts[:50],
        "conflict_count": len(conflicts),
        "coverage_after": {k: {"count": v, "pct": round(v / total * 100, 1) if total else 0}
                           for k, v in cov.items()},
    }
    out = Path(r"C:\Users\admin\github\treecut-v13\reports\storage\B007_V02_ENRICHMENT_V1.json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
