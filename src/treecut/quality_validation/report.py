"""P2.7: 报告生成 — AI 分析准确率 / OCR 分析 / 抽检结果。

只读已有数据库，不修改任何分析结果。
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path


class ReportBuilder:
    """基于数据库统计生成质量报告（纯读取）。"""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            from treecut.platform.paths import RuntimePaths
            db_path = RuntimePaths.discover().databases / "materials.db"
        self.db_path = Path(db_path)

    def _connect(self):
        connection = sqlite3.connect("file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    # ------------------------------------------------------------------
    # 分析覆盖统计
    # ------------------------------------------------------------------

    def analysis_coverage(self) -> dict:
        """各阶段完成率统计。"""
        with closing(self._connect()) as connection:
            total = connection.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
            stages = {}
            for stage in ("scene", "keyframe", "asr", "ocr"):
                done = connection.execute(
                    "SELECT COUNT(*) FROM asset_processing_state WHERE stage=? AND status='DONE'",
                    (stage,)).fetchone()[0]
                skipped = connection.execute(
                    "SELECT COUNT(*) FROM asset_processing_state WHERE stage=? AND status='SKIPPED'",
                    (stage,)).fetchone()[0]
                failed = connection.execute(
                    "SELECT COUNT(*) FROM asset_processing_state WHERE stage=? AND status='FAILED'",
                    (stage,)).fetchone()[0]
                stages[stage] = {
                    "done": done, "skipped": skipped, "failed": failed,
                    "coverage_pct": round(done / total * 100, 1),
                }
            return {"total_assets": total, "stages": stages}

    # ------------------------------------------------------------------
    # OCR 跳过分析
    # ------------------------------------------------------------------

    def ocr_analysis(self) -> dict:
        """OCR 跳过原因分析（竞态检测）。"""
        with closing(self._connect()) as connection:
            total = connection.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
            ocr_states = {r["status"]: r["n"] for r in connection.execute(
                "SELECT status, COUNT(*) n FROM asset_processing_state WHERE stage='ocr' GROUP BY status")}
            # 竞态：OCR SKIPPED 但 keyframe 后完成
            race = connection.execute("""
                SELECT COUNT(*) FROM asset_processing_state s1
                JOIN asset_processing_state s2 ON s2.asset_id=s1.asset_id AND s2.stage='keyframe'
                WHERE s1.stage='ocr' AND s1.status='SKIPPED' AND s2.status='DONE'
                AND s2.completed_at > s1.completed_at
            """).fetchone()[0]
            no_kf = connection.execute("""
                SELECT COUNT(*) FROM asset_processing_state s1
                WHERE s1.stage='ocr' AND s1.status='SKIPPED'
                AND NOT EXISTS (SELECT 1 FROM keyframes kf WHERE kf.asset_id=s1.asset_id)
            """).fetchone()[0]
            ocr_done_assets = connection.execute(
                "SELECT COUNT(DISTINCT asset_id) FROM ocr_text").fetchone()[0]
            ocr_rows = connection.execute("SELECT COUNT(*) FROM ocr_text").fetchone()[0]
        return {
            "total_assets": total,
            "ocr_states": ocr_states,
            "race_skip": race,           # 竞态导致的误跳过（可修复）
            "no_keyframe_skip": no_kf,   # 真无关键帧跳过
            "ocr_done_assets": ocr_done_assets,
            "ocr_total_items": ocr_rows,
        }

    # ------------------------------------------------------------------
    # ASR 分析
    # ------------------------------------------------------------------

    def asr_analysis(self) -> dict:
        with closing(self._connect()) as connection:
            with_tr = connection.execute(
                "SELECT COUNT(DISTINCT asset_id) FROM transcripts").fetchone()[0]
            tr_rows = connection.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0]
            # 平均每资产转写段数
            avg = connection.execute(
                "SELECT AVG(c) FROM (SELECT COUNT(*) c FROM transcripts GROUP BY asset_id)").fetchone()[0]
        return {"assets_with_transcript": with_tr, "transcript_rows": tr_rows,
                "avg_segments_per_asset": round(avg or 0, 1)}

    # ------------------------------------------------------------------
    # 抽检报告
    # ------------------------------------------------------------------

    def sample_report(self, sample: list[dict]) -> dict:
        from collections import Counter
        cats = Counter(s["category"] for s in sample)
        return {"sample_size": len(sample), "by_category": dict(cats),
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")}

    # ------------------------------------------------------------------
    # Markdown 输出
    # ------------------------------------------------------------------

    def to_markdown(self, title: str, data: dict) -> str:
        lines = [f"# {title}", "", f"- 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}", ""]
        lines.append("```json")
        lines.append(json.dumps(data, ensure_ascii=False, indent=2))
        lines.append("```")
        return "\n".join(lines)
