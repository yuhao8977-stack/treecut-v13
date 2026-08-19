"""P1.1: Incremental scanner coordinating Catalog + Assets + ProcessingState.

目标（第二阶段 P1.1 §十一）：
- 第二次扫描同一目录：只检测 NEW / CHANGED / MOVED / MISSING / UNCHANGED
- UNCHANGED 快速跳过（不重新 probe / hash / AI 分析）
- MOVED（fingerprint 相同、路径不同）→ 复用 asset_id，不创建新 asset
- MISSING / OFFLINE → 标记不可用，不删除历史处理数据

本模块不重复实现 os.walk，而是包装 v13 Catalog.scan 的增量登记结果，
在其上增加「变更分类」与「asset 协调」。
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path

from treecut.library.assets import AssetsManager
from treecut.library.catalog import Catalog, ScanResult
from treecut.library.processing_state import ProcessingState


@dataclass(frozen=True)
class IncrementalScanResult:
    source: str
    total: int = 0
    new: int = 0            # 新增素材
    changed: int = 0        # 内容变化（size/mtime/指纹不同）
    moved: int = 0          # 同一内容新路径（fingerprint 相同）
    missing: int = 0        # 旧路径消失
    unchanged: int = 0      # 内容未变，跳过
    offline: int = 0        # 素材源离线
    seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class IncrementalScanner:
    """增量扫描：区分 NEW/CHANGED/MOVED/MISSING/UNCHANGED 并协调 asset 身份。"""

    def __init__(self, catalog: Catalog | None = None,
                 assets: AssetsManager | None = None,
                 state: ProcessingState | None = None):
        self.catalog = catalog or Catalog()
        self.assets = assets or AssetsManager(catalog=self.catalog)
        self.state = state or ProcessingState(assets=self.assets)

    def scan(self, source: str | Path, kind: str = "folder", label: str = "",
             max_files: int = 500_000) -> IncrementalScanResult:
        started = time.perf_counter()
        scan: ScanResult = self.catalog.scan(source, kind=kind, label=label, max_files=max_files)

        # 协调：为所有可用视频建 asset 行（含移动复用），并初始化 stage 状态
        self.assets.ensure_all_video_assets()
        self._init_stages()

        result = IncrementalScanResult(
            source=str(source),
            total=scan.total,
            new=scan.added,
            changed=scan.changed,
            missing=scan.missing,
            unchanged=scan.unchanged,
            offline=0 if scan.online else 1,
            seconds=round(time.perf_counter() - started, 3),
        )
        return result

    def _init_stages(self) -> int:
        """Ensure stage rows for all assets (NEW default)."""
        with self.state._connect() as connection:
            rows = connection.execute(
                "SELECT asset_id FROM assets a WHERE NOT EXISTS "
                "(SELECT 1 FROM asset_processing_state s WHERE s.asset_id=a.asset_id)"
            ).fetchall()
        now = time.time()
        from treecut.library.processing_state import STAGES
        with self.state._connect() as connection:
            for row in rows:
                for stage in STAGES:
                    connection.execute(
                        "INSERT OR IGNORE INTO asset_processing_state"
                        "(asset_id,stage,status,input_fingerprint,updated_at) VALUES(?,?,?,?,?)",
                        (row["asset_id"], stage, "NEW", "", now),
                    )
        return len(rows)

    def detect_moves(self) -> int:
        """Reconcile assets whose quick fingerprint now matches a different path.

        用于扫描后处理：若 catalog 产生了新 media 行且 fingerprint 与旧 asset 相同，
        说明文件移动/改名 → 复用 asset_id（由 ensure_all_video_assets 内联处理）。
        这里返回实际复用数（诊断用）。
        """
        moved = 0
        with self.assets._connect() as connection:
            # 找 fingerprint_quick 有多个 media 归属的 asset（同内容多位置）
            rows = connection.execute(
                "SELECT a.asset_id, a.fingerprint_quick, COUNT(DISTINCT m.id) n "
                "FROM assets a JOIN media_files m ON m.id=a.media_id "
                "GROUP BY a.asset_id HAVING n > 1"
            ).fetchall()
            moved = len(rows)
        return moved
