"""P6: FFmpeg 粗剪引擎 — 按模板 + 人工选镜生成粗剪与可追溯输出。

输出：
- rough_cut.mp4      可播放粗剪
- timeline.json      完整时间线（可追溯）
- cuts.csv           剪切表
- subtitles.srt      ASR 字幕草稿（可选）

每个片段可追溯：asset_id / segment_id / source_path / start_ms / end_ms
"""
from __future__ import annotations

import csv
import json
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from treecut.library.assets import AssetsManager
from treecut.library.segments import SegmentStore


@dataclass(frozen=True)
class RoughCutResult:
    output: str
    timeline: str
    cuts_csv: str
    srt: str
    clip_count: int = 0
    duration_sec: float = 0.0
    seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class RoughCutEngine:
    """按 project_segments 的 selected 顺序生成 FFmpeg 粗剪。"""

    def __init__(self, assets: AssetsManager | None = None):
        self.assets = assets or AssetsManager()
        self.store = SegmentStore(assets=self.assets)
        self.db_path = self.assets.db_path

    def _resolve_segment(self, segment_id: str) -> dict | None:
        """segment → (source_path, start_ms, end_ms)。"""
        with self.store._connect() as connection:
            row = connection.execute(
                "SELECT s.asset_id, s.start_ms, s.end_ms, a.media_id "
                "FROM segments s JOIN assets a ON a.asset_id=s.asset_id "
                "WHERE s.segment_id=?", (segment_id,)
            ).fetchone()
            if row is None:
                return None
            mrow = connection.execute(
                "SELECT m.relative_path, src.path source_path, m.available "
                "FROM media_files m JOIN sources src ON src.id=m.source_id "
                "WHERE m.id=?", (row["media_id"],)
            ).fetchone()
            if mrow is None or not mrow["available"]:
                return None
            return {
                "asset_id": row["asset_id"],
                "segment_id": segment_id,
                "start_ms": row["start_ms"],
                "end_ms": row["end_ms"],
                "source_path": str(Path(mrow["source_path"]) / mrow["relative_path"]),
            }

    def build(self, project_id: str, out_dir: str | Path,
              with_srt: bool = True) -> RoughCutResult:
        """按 project_segments(selected) 顺序粗剪。"""
        started = time.perf_counter()
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        rough_cut = out / f"rough_cut_{stamp}.mp4"
        timeline = out / f"timeline_{stamp}.json"
        cuts_csv = out / f"cuts_{stamp}.csv"
        srt = out / f"subtitles_{stamp}.srt"

        # 读取选镜（selected 优先，backup 兜底）
        with self.assets._connect() as connection:
            rows = connection.execute(
                "SELECT ps.slot_order, ps.segment_id, ps.selection_status, ps.score "
                "FROM project_segments ps WHERE ps.project_id=? AND ps.selection_status IN "
                "('selected','backup') ORDER BY ps.slot_order, ps.rank",
                (project_id,),
            ).fetchall()
        if not rows:
            raise RuntimeError(f"项目 {project_id} 无选镜")

        clips = []
        for r in rows:
            seg = self._resolve_segment(r["segment_id"])
            if seg is None:
                continue
            seg["slot_order"] = r["slot_order"]
            seg["selection_status"] = r["selection_status"]
            seg["score"] = r["score"]
            clips.append(seg)

        if not clips:
            raise RuntimeError(f"项目 {project_id} 无可用素材（文件可能离线）")

        # FFmpeg concat（逐段精确截取）
        concat_file = out / f"concat_{stamp}.txt"
        with open(concat_file, "w", encoding="utf-8") as f:
            for c in clips:
                start = c["start_ms"] / 1000.0
                dur = max(0.5, (c["end_ms"] - c["start_ms"]) / 1000.0)
                # 中文路径兼容：先用 ffmpeg 处理（ffmpeg CLI 支持 UTF-8 参数）
                f.write(f"file '{str(c['source_path']).replace(chr(39), chr(39)+chr(39)+chr(39))}'\n")
                f.write(f"inpoint {start:.3f}\n")
                f.write(f"outpoint {start + dur:.3f}\n")

        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
               "-c", "copy", str(rough_cut)]
        result = subprocess.run(cmd, capture_output=True, timeout=600)
        if result.returncode != 0:
            # concat demuxer 失败（如编码不一致）→ 用逐段重编码兜底
            cmd2 = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
                    "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", str(rough_cut)]
            result2 = subprocess.run(cmd2, capture_output=True, timeout=900)
            if result2.returncode != 0:
                raise RuntimeError(
                    f"粗剪失败: {result.stderr.decode('utf-8', errors='replace')[-300:]}")

        total_dur = sum((c["end_ms"] - c["start_ms"]) / 1000.0 for c in clips)
        # timeline.json
        timeline.write_text(json.dumps({
            "project": project_id,
            "generated_at": stamp,
            "clips": [{
                "asset_id": c["asset_id"], "segment_id": c["segment_id"],
                "source": c["source_path"], "start_ms": c["start_ms"],
                "end_ms": c["end_ms"], "slot_order": c["slot_order"],
                "selection_status": c["selection_status"], "score": c["score"],
            } for c in clips],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        # cuts.csv
        with open(cuts_csv, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["asset_id", "segment_id", "source_path",
                             "start_ms", "end_ms", "slot_order", "status"])
            for c in clips:
                writer.writerow([c["asset_id"], c["segment_id"], c["source_path"],
                                 c["start_ms"], c["end_ms"], c["slot_order"],
                                 c["selection_status"]])
        # SRT 字幕草稿（ASR 转写）
        if with_srt:
            self._write_srt(srt, clips)

        concat_file.unlink(missing_ok=True)
        return RoughCutResult(
            output=str(rough_cut), timeline=str(timeline), cuts_csv=str(cuts_csv),
            srt=str(srt) if with_srt else "",
            clip_count=len(clips), duration_sec=round(total_dur, 2),
            seconds=round(time.perf_counter() - started, 3),
        )

    def _write_srt(self, srt_path: Path, clips: list[dict]) -> None:
        """按 clips 顺序生成 SRT 草稿（无 ASR 时留空序号）。"""
        lines = []
        idx = 1
        cursor = 0.0
        for c in clips:
            dur = (c["end_ms"] - c["start_ms"]) / 1000.0
            start_hms = self._fmt_srt(cursor)
            end_hms = self._fmt_srt(cursor + dur)
            lines.append(str(idx))
            lines.append(f"{start_hms} --> {end_hms}")
            lines.append("")  # 字幕文本占位（ASR 校正后填充）
            lines.append("")
            cursor += dur
            idx += 1
        srt_path.write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _fmt_srt(sec: float) -> str:
        ms = int(round((sec % 1) * 1000))
        total = int(sec)
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
