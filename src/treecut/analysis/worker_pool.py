"""P2.5: WorkerPool — spawn N worker processes, each running Worker25.

多进程并发安全：
- 任务领取由 TaskStore.claim_task 的 BEGIN IMMEDIATE 原子事务保证，
  并发 Worker 不会双领同一任务
- 主进程 result_queue.get(timeout=...) 轮询 + process.is_alive() 检测，
  修复 P1 AnalysisPool 无超时阻塞 / 僵尸进程问题
- close() 对超时未退出进程 terminate()
"""
from __future__ import annotations

import logging
import multiprocessing
import time
from pathlib import Path

from treecut.platform.paths import RuntimePaths


def _pool_entry(worker_id: str, task_type: str, stages: list[str],
                db_path: str, log_path: str, limit: int | None,
                asr_device: str | None, cuda_dll_dir: str | None,
                cpu_threads: int | None,
                ready_queue, result_queue, stop_event) -> None:
    """spawn 子进程入口。模型常驻，循环领取任务直到无 pending 或达 limit。"""
    import os
    if cuda_dll_dir:
        cur = os.environ.get("PATH", "")
        if cuda_dll_dir not in cur:
            os.environ["PATH"] = cuda_dll_dir + os.pathsep + cur
    if cpu_threads and cpu_threads > 0:
        # 限制 onnxruntime/OpenMP 线程数，避免多进程争抢 CPU（OCR 场景）
        os.environ["OMP_NUM_THREADS"] = str(cpu_threads)
        os.environ["ORT_NUM_THREADS"] = str(cpu_threads)
    from treecut.analysis.worker_p25 import Worker25
    worker = Worker25(worker_id=worker_id, task_type=task_type, stages=stages,
                      db_path=db_path, log_path=log_path,
                      asr_device=asr_device)
    ready_queue.put(worker_id)
    try:
        counts = worker.run(limit=limit)
        result_queue.put(("done", counts))
    except Exception as error:
        result_queue.put(("error", f"{worker_id}: {type(error).__name__}: {error}"))
    finally:
        stop_event.set()


# 默认 Worker 分片（与设计文档一致）
DEFAULT_STAGES = {
    "vision": ["scene", "keyframe"],
    "asr": ["asr"],
    "ocr": ["ocr"],
}


class WorkerPool:
    """多进程 Worker 池。workers>3 时按 task_type 轮询扩展同阶段 Worker。"""

    def __init__(self, workers: int = 3, paths: RuntimePaths | None = None,
                 stages: dict[str, list[str]] | None = None,
                 limit: int | None = None, asr_device: str | None = None,
                 cuda_dll_dir: str | None = None,
                 cpu_threads: dict[str, int] | None = None):
        if not isinstance(workers, int) or workers < 1:
            raise ValueError(f"Worker 数必须是正整数: {workers}")
        self.workers = workers
        self.paths = paths or RuntimePaths.discover()
        self.limit = limit
        self.asr_device = asr_device or "auto"
        self.cuda_dll_dir = cuda_dll_dir
        # 各 task_type 的线程限制（如 {"ocr": 4} → OCR 每进程 4 线程）
        self.cpu_threads = cpu_threads or {}
        stage_map = dict(stages or DEFAULT_STAGES)
        if not stage_map:
            stage_map = dict(DEFAULT_STAGES)
        self._assignments = self._assign(workers, stage_map)

    def _assign(self, workers: int, stage_map: dict[str, list[str]]) -> list[dict]:
        """把 workers 个进程分配给 task_type。

        默认 3 类型（vision/asr/ocr）且 workers>3 时按瓶颈加权：
        - ocr 固定 1（最快）
        - asr 1~2（GPU 并发上限 2，显存 6GB / 模型 1.6GB）
        - 其余全部给 vision（scene+keyframe 是最慢瓶颈）
        否则按类型轮询（同阶段多 Worker 靠原子领取分片 asset）。
        """
        types = list(stage_map.keys())
        # 瓶颈加权（仅当默认 3 类型且 worker 数 > 类型数）
        if (len(types) == 3 and set(types) == {"vision", "asr", "ocr"}
                and workers > len(types)):
            ocr_n = 1
            asr_n = 1 if workers <= 4 else min(2, workers - 2)
            vision_n = workers - ocr_n - asr_n
            counts = {"vision": vision_n, "asr": asr_n, "ocr": ocr_n}
            assignments = []
            idx = 1
            for task_type in ("vision", "asr", "ocr"):
                for _ in range(counts[task_type]):
                    assignments.append({
                        "worker_id": f"worker_{idx:03d}",
                        "task_type": task_type,
                        "stages": stage_map[task_type],
                    })
                    idx += 1
            return assignments
        # 默认轮询
        assignments = []
        for i in range(workers):
            task_type = types[i % len(types)]
            assignments.append({
                "worker_id": f"worker_{i + 1:03d}",
                "task_type": task_type,
                "stages": stage_map[task_type],
            })
        return assignments

    # ------------------------------------------------------------------

    def run(self, batch_size: int | None = None) -> list[dict]:
        """启动全部 Worker 进程并等待完成。返回每个 Worker 的汇总。"""
        context = multiprocessing.get_context("spawn")
        db_path = str(self.paths.databases / "materials.db")
        log_dir = self.paths.logs
        log_dir.mkdir(parents=True, exist_ok=True)
        pool_log = log_dir / "worker_pool.log"
        logging.basicConfig(
            filename=str(pool_log), level=logging.INFO,
            format="[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        logger = logging.getLogger("treecut.workerpool")

        ready_queue = context.Queue()
        result_queue = context.Queue()
        stop_event = context.Event()
        processes = []
        for assignment in self.assignments():
            process = context.Process(
                target=_pool_entry,
                args=(assignment["worker_id"], assignment["task_type"],
                      assignment["stages"], db_path,
                      str(log_dir / f"worker_{assignment['worker_id']}.log"),
                      self.limit, self.asr_device, self.cuda_dll_dir,
                      self.cpu_threads.get(assignment["task_type"]),
                      ready_queue, result_queue, stop_event),
                daemon=True,
            )
            processes.append(process)
            process.start()

        # 等待全部就绪（每进程一个 ready 信号）
        ready_count = 0
        deadline = time.time() + 60
        while ready_count < len(processes) and time.time() < deadline:
            try:
                ready_queue.get(timeout=5)
                ready_count += 1
            except Exception:
                if all(not p.is_alive() for p in processes):
                    break
        if ready_count < len(processes):
            logger.warning("仅 %d/%d Worker 就绪（进程可能已崩溃）",
                           ready_count, len(processes))

        # 收集结果（带超时 + 存活检测，修复无超时阻塞缺陷）
        summaries: list[dict] = []
        finished = 0
        while finished < len(processes):
            try:
                kind, payload = result_queue.get(timeout=10)
                if kind == "done":
                    summaries.append(payload)
                else:
                    logger.error("Worker 出错: %s", payload)
                    summaries.append({"error": payload, "processed": 0})
                finished += 1
            except Exception:
                alive = [p for p in processes if p.is_alive()]
                if not alive:
                    # 全部死亡但没有发结果 → 记录为崩溃
                    for p in processes:
                        if p.exitcode is not None and p.exitcode != 0:
                            summaries.append({
                                "error": f"worker crashed exitcode={p.exitcode}",
                                "processed": 0,
                            })
                            finished += 1
                    if finished < len(processes):
                        # 仍有未收集的（正常结束但结果被并发读走）→ 补空
                        missing = len(processes) - finished
                        for _ in range(missing):
                            summaries.append({"processed": 0, "error": "no result"})
                            finished += 1
                else:
                    # 有进程存活但队列空：等待更多结果
                    if finished >= len(processes):
                        break
                    time.sleep(2)

        self._join(processes)
        logger.info("WorkerPool 完成: %d workers, %s", len(processes),
                    {s.get("worker_id", "?") + ":" + str(s.get("processed", 0))
                     for s in summaries})
        return summaries

    def assignments(self) -> list[dict]:
        return self._assignments

    def _join(self, processes: list) -> None:
        for process in processes:
            process.join(timeout=30)
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)

    def close(self) -> None:
        """兼容接口：run() 内部已 join/terminate。"""
