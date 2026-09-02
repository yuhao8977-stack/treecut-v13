# -*- coding: utf-8 -*-
"""V0.9.1 Step1: 记录 V1 feedback + Clean Source 干净度审计（X1 原始素材池）。"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"

REJECT_REASONS = ["SOURCE_HAS_BURNED_CAPTIONS", "SOURCE_HAS_PLATFORM_WATERMARK",
                  "NEW_CAPTION_NOT_RENDERED", "AV_DURATION_MISMATCH", "VOICE_TOO_SYNTHETIC",
                  "NARRATION_TOO_SLOW", "BEAT_VISUAL_MISMATCH", "FUNCTION_ACTION_NOT_SHOWN",
                  "STORY_ENTITY_INCONSISTENCY", "SCENE_CONTINUITY_BREAK", "NO_BGM",
                  "CLAIM_EVIDENCE_TOO_COARSE"]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)

    # ---- V1 feedback ----
    fb = {"phase": "V0.9.1", "event_type": "feedback_event",
          "target": "B007_FIRST_REAL_PILOT_V1", "human_verdict": "REJECT",
          "reasons": REJECT_REASONS,
          "recorded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
          "lesson": "技术链可跑通 ≠ 内容可发布；Published media 只作 REFERENCE，不作默认生产源",
          "V1_known_issue": {"video_stream_s": 22.67, "audio_stream_s": 27.35, "delta_s": 4.68,
                             "qa_false_pass": "DURATION_VALID 用容器时长，未做 stream 级音画校验"}}
    (OUT / "B007_FIRST_REAL_PILOT_V1_FEEDBACK.json").write_text(
        json.dumps(fb, ensure_ascii=False, indent=2), encoding="utf-8")
    print("V1_FEEDBACK_WRITTEN")

    # ---- source roles ----
    roles = {"published_media_z": "PUBLISHED_REFERENCE",
             "X1_processed_sources": "PRODUCTION_CLEAN_CANDIDATE",
             "X1_unprocessed_factory": "PRODUCTION_CLEAN_CANDIDATE",
             "platform_reference_e": "PUBLISHED_REFERENCE"}
    (OUT / "B007_PRODUCTION_SOURCE_ROLE_V1.json").write_text(
        json.dumps({"roles": roles,
                    "note": "生产默认只允许 PRODUCTION_CLEAN；published 仅 REFERENCE"}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    # ---- clean audit：来源文件可达性 + OCR 字幕污染抽检 ----
    sources = {r[0]: r[1] for r in c.execute("SELECT id, path FROM sources")}
    pools = {
        "selling_point_raw": (1, 200),      # 卖点展示类素材（已处理）
        "effect_raw": (2, 200),             # 效果展示类素材
        "factory_raw": (4, 200),            # 工厂未处理
    }
    audit = {"reachability": {}, "ocr_contamination_sample": {}}
    for name, (sid, cap) in pools.items():
        base = sources.get(sid, "")
        rows = c.execute("SELECT id, relative_path FROM media_files WHERE source_id=? LIMIT ?",
                         (sid, cap)).fetchall()
        reach = 0
        sample = []
        for mid, rel in rows:
            p = Path(base) / rel
            if p.exists():
                reach += 1
                if len(sample) < 3:
                    sample.append(str(p))
        audit["reachability"][name] = {"files_scanned": len(rows), "reachable": reach,
                                       "sample_paths": sample}
        # OCR 污染：这些 media 是否有关联 keyframes/OCR subtitle 记录
        mids = [r[0] for r in rows]
        if mids:
            ph = ",".join("?" * min(len(mids), 500))
            sub = c.execute(f"SELECT COUNT(*) FROM ocr_text WHERE frame_id IN "
                            f"(SELECT frame_id FROM keyframes WHERE asset_id IN "
                            f"(SELECT asset_id FROM assets WHERE media_id IN ({ph}))) "
                            f"AND subtitle_flag=1", mids[:500]).fetchone()[0]
            audit["ocr_contamination_sample"][name] = {"burned_subtitle_hits": sub}
    c.close()
    (OUT / "B007_CLEAN_SOURCE_CANDIDATES_V1.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
