# -*- coding: utf-8 -*-
"""V0.2 — B007 捕获结果入库：用户人工浏览器捕获的笔记列表 JSON → 校验/归一化/幂等入库。

用法：
  python scripts/b007_ingest_capture.py <capture.json> [--data-root PATH]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from treecut.browser.creator_sync import (  # noqa: E402
    extract_cover_meta,
    normalize_publish_time,
    normalize_title,
)
from treecut.services.b007_creator_adapter import B007CreatorImportAdapterV1  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    parser = argparse.ArgumentParser(prog="b007-ingest-capture")
    parser.add_argument("capture_file", help="用户捕获的 JSON 文件（数组）")
    parser.add_argument("--data-root", default="",
                        help="数据根（默认取 TREECUT_DATA_ROOT/便携默认）")
    args = parser.parse_args(argv)

    raw = json.loads(Path(args.capture_file).read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "records" in raw:
        raw = raw["records"]
    if not isinstance(raw, list):
        print("ERROR: 输入必须是数组或 {records: [...]}")
        return 1

    data_root = Path(args.data_root) if args.data_root else None
    if data_root is None:
        from treecut.platform.paths import RuntimePaths
        data_root = RuntimePaths.discover().data_root
    adapter = B007CreatorImportAdapterV1(str(data_root / "database" / "materials.db"))

    committed, id_only, missing = 0, [], []
    for rec in raw:
        if not isinstance(rec, dict) or not rec.get("note_id"):
            missing.append(rec.get("title", "")[:40])
            continue
        title = normalize_title(rec.get("title") or rec.get("display_title"))
        publish_time = normalize_publish_time(rec.get("publish_time") or rec.get("time")
                                              or rec.get("lastUpdateTime"))
        media_type = str(rec.get("media_type") or rec.get("type") or "")
        duration = rec.get("duration")
        if duration is not None:
            try:
                duration = round(float(duration), 3)
            except (TypeError, ValueError):
                duration = None
        cover = extract_cover_meta(rec.get("cover") or rec.get("cover_safe"))
        if not (title or cover or duration is not None or publish_time or media_type):
            id_only.append(rec["note_id"])
            continue
        adapter.upsert_published_content({
            "account_id": "B007", "note_id": rec["note_id"],
            "note_url": f"https://www.xiaohongshu.com/explore/{rec['note_id']}",
            "title": title, "publish_time": publish_time,
            "content_type": media_type, "duration": duration,
            "source_refs": ["CAPTURE_MANUAL:" + rec.get("note_id", "")],
        })
        committed += 1

    print(f"committed={committed} id_only_skipped={len(id_only)} missing_note_id={len(missing)}")
    print(f"note_id={committed} title={sum(1 for r in raw if isinstance(r, dict) and (r.get('title') or r.get('display_title')))}")
    if id_only:
        print("id_only (无实质字段，跳过):", id_only[:10])
    return 0


if __name__ == "__main__":
    sys.exit(main())
