"""Persistent analysis worker pool: models stay loaded across batches."""
from __future__ import annotations

import multiprocessing
from pathlib import Path

from treecut.analysis.parallel import ParallelRun
from treecut.platform.progress import ProgressCallback, no_progress


def _pool_worker(command_queue, result_queue, db_path: str) -> None:
    """Run in a spawned process; loads models once and serves many batches."""
    from treecut.analysis.worker import AnalysisWorker
    from treecut.library import Catalog

    worker = AnalysisWorker(catalog=Catalog(db_path))
    while True:
        message = command_queue.get()
        if message == "stop":
            break
        limit = int(message)
        try:
            run = worker.run(limit=limit)
            result_queue.put(("run", run.to_dict()))
        except Exception as error:
            result_queue.put(("error", f"{type(error).__name__}: {error}"))


class AnalysisPool:
    def __init__(self, db_path: str | Path, workers: int = 1):
        if not isinstance(workers, int) or workers < 1:
            raise ValueError(f"并行数必须是正整数: {workers}")
        self.db_path = Path(db_path)
        self.workers = workers
        context = multiprocessing.get_context("spawn")
        self._command_queue = context.Queue()
        self._result_queue = context.Queue()
        self._processes = [
            context.Process(
                target=_pool_worker,
                args=(self._command_queue, self._result_queue, str(self.db_path)),
            )
            for _ in range(workers)
        ]
        for process in self._processes:
            process.start()

    def run_batch(self, limit: int, progress: ProgressCallback = no_progress) -> ParallelRun:
        if limit < 1:
            return ParallelRun(workers=self.workers)
        per_worker = max(1, -(-limit // self.workers))
        for _ in range(self.workers):
            self._command_queue.put(per_worker)
        total = ParallelRun(workers=self.workers)
        finished = 0
        while finished < self.workers:
            kind, payload = self._result_queue.get()
            if kind == "run":
                total = total.merge(ParallelRun(
                    workers=1,
                    claimed=payload.get("claimed", 0),
                    succeeded=payload.get("succeeded", 0),
                    retried=payload.get("retried", 0),
                    failed=payload.get("failed", 0),
                ))
                finished += 1
            elif kind == "error":
                progress(f"分析子进程出错：{payload}", None)
                finished += 1
        progress(
            f"本批分析完成：{total.succeeded + total.retried + total.failed}/{limit}",
            None,
        )
        return total

    def close(self) -> None:
        for _ in self._processes:
            self._command_queue.put("stop")
        for process in self._processes:
            process.join(timeout=30)
