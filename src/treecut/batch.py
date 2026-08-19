"""Batch production input loader (TSV: 卖点\t配音\t时长秒)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BatchRow:
    selling_points: str
    narration: str
    target_duration: float = 30.0


def load_batch_file(path: str | Path) -> list[BatchRow]:
    rows: list[BatchRow] = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        separator = "\t" if "\t" in stripped else "|"
        parts = [part.strip() for part in stripped.split(separator)]
        if len(parts) < 2:
            raise ValueError(f"第 {line_number} 行格式错误：需要 卖点|配音|时长")
        selling_points, narration = parts[0], parts[1]
        duration = float(parts[2]) if len(parts) >= 3 and parts[2] else 30.0
        if not selling_points or not narration:
            raise ValueError(f"第 {line_number} 行卖点或配音为空")
        if not 5 <= duration <= 300:
            raise ValueError(f"第 {line_number} 行时长必须在 5–300 秒")
        rows.append(BatchRow(selling_points, narration, duration))
    if not rows:
        raise ValueError("批量文件里没有有效任务")
    return rows
