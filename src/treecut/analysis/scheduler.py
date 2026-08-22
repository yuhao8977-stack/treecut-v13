"""P2.5: TaskScheduler — 生成 analysis_tasks 并编排 WorkerPool。

任务来源（唯一入口）：扫描 asset_processing_state 中阶段未完成（NOT IN
DONE/SKIPPED）的 asset → 幂等写入 analysis_tasks。已完成/处理中由状态过滤，
失败任务通过 retry_count 机制重试。运行中旧 P2 进程（PID 19152）不受影响：
本模块只新增表与任务，不修改旧代码路径。
"""
from __future__ import annotations

import time
from pathlib import Path

from treecut.analysis.worker_pool import WorkerPool, DEFAULT_STAGES
from treecut.library.processing_state import ProcessingState, STAGES
from treecut.library.task_store import TaskStore
from treecut.platform.paths import RuntimePaths


class SchedulerResult:
    def __init__(self, created: int = 0, completed: int = 0, failed: int = 0,
                 skipped: int = 0, occupied: int = 0, remaining: int = 0,
                 workers: int = 0, seconds: float = 0.0,
                 worker_summaries: list[dict] | None = None):
        self.created = created
        self.completed = completed
        self.failed = failed
        self.skipped = skipped
        self.occupied = occupied
        self.remaining = remaining
        self.workers = workers
        self.seconds = seconds
        self.worker_summaries = worker_summaries or []

    def to_dict(self) -> dict:
        return {
            "created_tasks": self.created,
            "completed": self.completed,
            "failed": self.failed,
            "skipped": self.skipped,
            "occupied": self.occupied,
            "remaining_pending": self.remaining,
            "workers": self.workers,
            "seconds": round(self.seconds, 2),
            "workers_detail": self.worker_summaries,
        }


class TaskScheduler:
    """任务生成 + WorkerPool 编排。"""

    # 需要分析的阶段（P2.5 覆盖 P2 的四阶段）
    DEFAULT_P2_STAGES = ["scene", "keyframe", "asr", "ocr"]

    def __init__(self, paths: RuntimePaths | None = None):
        self.paths = paths or RuntimePaths.discover()
        self.db_path = self.paths.databases / "materials.db"
        self.store = TaskStore(self.db_path)
        self.ps = ProcessingState()

    # ------------------------------------------------------------------
    # 任务生成
    # ------------------------------------------------------------------

    def sync_from_state(self, stages: list[str] | None = None) -> dict:
        """扫描未完成阶段，幂等写入 analysis_tasks。

        按阶段职责映射 task_type：scene/keyframe→vision，asr→asr，ocr→ocr。
        返回 {created, total_pending, by_type}。
        """
        stages = stages or self.DEFAULT_P2_STAGES
        self.store.migrate_if_needed()

        # 找出各阶段未完成的 asset（一次查询按 asset 聚合）
        placeholders = ",".join("?" * len(stages))
        with self.ps._connect() as connection:
            rows = connection.execute(
                f"SELECT asset_id, stage FROM asset_processing_state "
                f"WHERE stage IN ({placeholders}) AND status NOT IN ('DONE','SKIPPED')",
                stages,
            ).fetchall()

        # 按 asset 聚合未完成阶段
        pending_by_asset: dict[str, set[str]] = {}
        for row in rows:
            pending_by_asset.setdefault(row["asset_id"], set()).add(row["stage"])

        # 按 task_type 分桶创建
        created = 0
        by_type: dict[str, int] = {}
        for asset_id, asset_stages in pending_by_asset.items():
            vision = [s for s in ("scene", "keyframe") if s in asset_stages]
            asr = "asr" in asset_stages
            ocr = "ocr" in asset_stages
            if vision:
                created += self.store.create_task(
                    asset_id, "vision", stages=",".join(vision))
                by_type["vision"] = by_type.get("vision", 0) + 1
            if asr:
                created += self.store.create_task(asset_id, "asr", stages="asr")
                by_type["asr"] = by_type.get("asr", 0) + 1
            if ocr:
                created += self.store.create_task(asset_id, "ocr", stages="ocr")
                by_type["ocr"] = by_type.get("ocr", 0) + 1

        return {
            "created": created,
            "by_type": by_type,
            "total_pending": self.store.pending_count(),
        }

    # ------------------------------------------------------------------
    # 编排
    # ------------------------------------------------------------------

    def run(self, workers: int = 3, limit: int | None = None,
            stages: list[str] | None = None,
            force: bool = False) -> SchedulerResult:
        """完整流程：迁移 → 同步任务 → 检查旧进程 → WorkerPool 并行执行。"""
        started = time.perf_counter()
        stages = stages or self.DEFAULT_P2_STAGES

        # 1) 迁移 + 生成任务
        sync = self.sync_from_state(stages)
        if sync["created"] == 0 and self.store.pending_count() == 0:
            return SchedulerResult(created=0, remaining=0, workers=workers,
                                   seconds=round(time.perf_counter() - started, 2))

        # 2) 旧进程互斥检查（默认不抢跑）
        if not force:
            occupied = self._count_processing_assets(stages)
            if occupied > 0:
                return SchedulerResult(
                    created=sync["created"], remaining=self.store.pending_count(),
                    workers=workers,
                    seconds=round(time.perf_counter() - started, 2),
                    worker_summaries=[{
                        "warning": (f"检测到 {occupied} 个阶段正在被旧 P2 进程处理，"
                                    f"默认不并行抢跑。等待其完成或使用 --force 强制并行"),
                    }],
                )

        # 3) 启动 WorkerPool
        pool = WorkerPool(workers=workers, paths=self.paths, limit=limit)
        summaries = pool.run(batch_size=limit)

        # 4) 汇总
        completed = sum(s.get("completed", 0) for s in summaries)
        failed = sum(s.get("failed", 0) for s in summaries)
        skipped = sum(s.get("skipped", 0) for s in summaries)
        occupied_n = sum(s.get("occupied", 0) for s in summaries)
        remaining = self.store.pending_count()

        return SchedulerResult(
            created=sync["created"], completed=completed, failed=failed,
            skipped=skipped, occupied=occupied_n, remaining=remaining,
            workers=workers, seconds=round(time.perf_counter() - started, 2),
            worker_summaries=summaries,
        )

    def _count_processing_assets(self, stages: list[str]) -> int:
        placeholders = ",".join("?" * len(stages))
        with self.ps._connect() as connection:
            row = connection.execute(
                f"SELECT COUNT(DISTINCT asset_id) n FROM asset_processing_state "
                f"WHERE stage IN ({placeholders}) AND status='PROCESSING'",
                stages,
            ).fetchone()
        return int(row["n"]) if row else 0

    # ------------------------------------------------------------------
    # 状态
    # ------------------------------------------------------------------

    def status(self) -> dict:
        self.store.ensure_schema()
        task_stats = self.store.stats()
        stage_stats = self.ps.stage_stats()
        p2 = {k: stage_stats.get(k, {}) for k in
              ("scene", "keyframe", "asr", "ocr")}
        return {
            "task_store": task_stats,
            "schema_versions": self.store.schema_status(),
            "p2_stages": p2,
        }
