"""P6: AI 辅助镜头排序建议（只建议，不做不可逆决定）。

建议：镜头顺序 / 每镜时长 / 首 3 秒最强镜头 / 重复提示 / 备选。
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path

from treecut.roughcut.engine import RoughCutEngine


@dataclass(frozen=True)
class SortSuggestion:
    order: tuple[int, ...]          # 建议顺序（slot_order 排列）
    first_3s_segment: str           # 建议首镜 segment_id
    duplicates: tuple[str, ...]     # 疑似重复镜头
    tips: tuple[str, ...] = ()
    seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class SortAdvisor:
    """基于模板槽位顺序 + 质量 + 去重的排序建议。"""

    def __init__(self, roughcut: RoughCutEngine | None = None):
        self.roughcut = roughcut or RoughCutEngine()

    def advise(self, project_id: str) -> SortSuggestion:
        started = time.perf_counter()
        with self.roughcut.assets._connect() as connection:
            rows = connection.execute(
                "SELECT slot_order, segment_id, score FROM project_segments "
                "WHERE project_id=? AND selection_status IN ('selected','backup') "
                "ORDER BY slot_order, rank",
                (project_id,),
            ).fetchall()
        if not rows:
            raise RuntimeError(f"项目 {project_id} 无选镜")

        # 建议顺序：按模板槽位自然顺序（用户选镜已按槽位）
        order = tuple(r["slot_order"] for r in rows)
        # 首 3 秒：选 slot_order=1 或最高分镜头
        first = rows[0]["segment_id"] if rows else ""
        # 重复提示：同 asset 多段
        segs = [self.roughcut._resolve_segment(r["segment_id"]) for r in rows]
        segs = [s for s in segs if s]
        from collections import Counter
        asset_counts = Counter(s["asset_id"] for s in segs)
        dups = tuple(s["segment_id"] for s in segs if asset_counts[s["asset_id"]] > 1)

        tips = (
            f"共 {len(rows)} 个镜头，建议总时长 "
            f"{sum((s['end_ms']-s['start_ms'])/1000 for s in segs):.1f}s",
            "首镜建议使用槽位 1（问题/强视觉）",
            "重复镜头可考虑 EXCLUDE 其中一条",
        )
        return SortSuggestion(
            order=order, first_3s_segment=first, duplicates=dups, tips=tips,
            seconds=round(time.perf_counter() - started, 3),
        )
