"""Run material analysis across multiple worker processes."""
from __future__ import annotations

import logging
import multiprocessing
from dataclasses import asdict, dataclass
from pathlib import Path

from treecut.platform.progress import ProgressCallback, no_progress


@dataclass(frozen=True)
class ParallelRun:
    workers: int
    claimed: int = 0
    succeeded: int = 0
    retried: int = 0
    failed: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    def merge(self, other: "ParallelRun") -> "ParallelRun":
        return ParallelRun(
            workers=self.workers,
            claimed=self.claimed + other.claimed,
            succeeded=self.succeeded + other.succeeded,
            retried=self.retried + other.retried,
            failed=self.failed + other.failed,
        )


def _worker_entry(db_path: str, limit: int, queue) -> None:
    """Run inside a spawned process; claims jobs from the shared SQLite DB."""
    try:
        from treecut.analysis.worker import AnalysisWorker
        from treecut.library import Catalog
        run = AnalysisWorker(catalog=Catalog(db_path)).run(limit=limit)
        queue.put(("run", run.to_dict()))
    except Exception as error:
        logging.getLogger("treecut").exception("并行分析子进程失败")
        queue.put(("error", f"{type(error).__name__}: {error}"))


def suggest_workers(requested: int, ram_gb: float) -> int:
    """Cap parallel workers by available RAM; each worker needs ~8 GB of headroom."""
    if not isinstance(requested, int) or requested < 1:
        return 1
    if ram_gb <= 0:
        return requested
    safe = max(1, int((ram_gb - 4) // 8))
    return max(1, min(requested, safe))


def run_parallel_analysis(db_path: str | Path, limit: int, workers: int = 2,
                          progress: ProgressCallback = no_progress) -> ParallelRun:
    """Analyze up to ``limit`` queued materials using ``workers`` processes."""
    if not isinstance(workers, int) or workers < 1:
        raise ValueError(f"并行数必须是正整数: {workers}")
    if limit < 1:
        return ParallelRun(workers=workers)
    per_worker = max(1, -(-limit // workers))
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    processes = []
    for _ in range(min(workers, limit)):
        process = context.Process(
            target=_worker_entry, args=(str(db_path), per_worker, queue),
        )
        process.start()
        processes.append(process)

    total = ParallelRun(workers=len(processes))
    finished = 0
    while finished < len(processes):
        kind, payload = queue.get()
        if kind == "run":
            total = total.merge(ParallelRun(
                workers=1, claimed=payload.get("claimed", 0),
                succeeded=payload.get("succeeded", 0),
                retried=payload.get("retried", 0), failed=payload.get("failed", 0),
            ))
            finished += 1
        elif kind == "error":
            progress(f"并行分析子进程出错：{payload}", None)
            finished += 1
        progress(
            f"并行分析进度：{total.succeeded + total.retried + total.failed}/{limit}",
            round((total.succeeded + total.retried + total.failed) / limit * 100, 1),
        )
    for process in processes:
        process.join(timeout=30)
    return total
