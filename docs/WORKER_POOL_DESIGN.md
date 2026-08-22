# P2.5 Worker Pool 设计

- **版本**：v1.0
- **关联**：docs/P2.5_ARCHITECTURE_DESIGN.md §2.4、docs/P2.5_UPGRADE_AUDIT.md §5
- **日期**：2026-08-22

---

## 1. 设计目标

- 默认 3 Worker，按阶段职责分片，互不抢任务
- 模型常驻（不重复加载），内存隔离
- 任何 Worker 崩溃不影响其他 Worker 与已提交数据
- 多进程并发领取同一任务**绝无双领**（数据库原子领取）
- 与运行中旧 P2 进程（PID 19152）互斥共存（默认不抢跑）

---

## 2. 硬件基线（当前电脑）

| 资源 | 配置 | P2.5 分配 |
|---|---|---|
| CPU | 6 核 12 线程（实测 12 逻辑核） | 3 Worker × 2-4 线程 ≈ 6-9 核 |
| 内存 | 32 GB | 3 模型常驻 ≈ 3-5 GB（余量充足） |
| GPU | RTX 3050 6GB（当前闲置） | 默认 CPU；预留 `--device cuda` |

---

## 3. Worker 角色分片（默认拓扑）

```
WorkerPool (1 个调度主进程)
 │
 ├── worker_001  [task_type=vision]  stages: scene, keyframe
 │     └── 加载: SceneDetector + KeyframeExtractor (+ cv2)
 ├── worker_002  [task_type=asr]     stages: asr
 │     └── 加载: WhisperEngine (faster-whisper small, CPU int8)
 └── worker_003  [task_type=ocr]     stages: ocr
       └── 加载: OcrEngine (RapidOCR onnxruntime CPU)
```

**为何这样分**：
1. **模型互斥**：whisper（~1-2GB 内存）与 RapidOCR（onnx 模型）与 cv2 抽帧互不干扰；视觉 Worker 不需 whisper → 显存/内存峰值低
2. **依赖链**：scene→keyframe 同进程串行（keyframe 依赖 scene 的 segments），asr/ocr 独立可并行
3. **弹性**：`--workers 5` 时按 `task_type` 轮询分配额外 Worker（如同阶段多 Worker），同阶段 Worker 靠原子领取自然分片 asset

---

## 4. 进程模型

```python
# worker_pool.py
def _pool_entry(worker_id, task_type, stages, db_path, log_path, limit, ready_queue, stop_event):
    """spawn 子进程：每进程一个 Worker25，循环领取任务直到无 pending 或达 limit。"""
    from treecut.library.task_store import TaskStore
    from treecut.analysis.worker_p25 import Worker25
    store = TaskStore(db_path)
    worker = Worker25(worker_id=worker_id, stages=stages, task_type=task_type,
                      db_path=db_path, log_path=log_path)
    ready_queue.put(worker_id)          # 通知主进程本 Worker 已就绪
    processed = 0
    while not stop_event.is_set():
        if limit is not None and processed >= limit:
            break
        task = store.claim_task(worker_id=worker_id, task_type=task_type, stages=stages)
        if task is None:
            break                        # 无 pending → 退出
        worker.execute(task)             # 内含幂等护栏 + 完成/失败回写
        processed += 1
    return processed


class WorkerPool:
    def __init__(self, workers: int, paths: RuntimePaths,
                 stages: dict[str, list[str]] | None = None, limit: int | None = None): ...
    def run(self) -> list[WorkerSummary]:
        # spawn N 进程；等待全部结束；汇总 {worker_id, processed, failed, seconds}
    def close(self) -> None:
        # stop_event.set(); 对超时未退出进程 terminate()
```

**崩溃恢复（修复 P1 pool 缺陷）**：
- 主进程 `result_queue.get(timeout=5)` 循环 + 轮询 `process.is_alive()`
- 子进程异常死亡 → 主进程记录该 Worker 失败并继续等待其余 Worker
- 子进程退出前把未完成任务交还：不主动交还，由 `TaskStore.recover_stale()`（processing 超时 30 分钟 → pending）兜底

---

## 5. 领取协议（防双领核心）

每个 Worker 循环：
```
task = store.claim_task(worker_id, task_type, stages)
```
`claim_task` 内部（`library/task_store.py`）：
```
BEGIN IMMEDIATE
  SELECT ... FROM analysis_tasks WHERE status='pending' AND retry_count<=3
         AND task_type=:t ORDER BY priority DESC, created_at LIMIT 1
  -- 命中:
  UPDATE analysis_tasks SET status='processing', worker_id=:w,
         started_time=:now, attempt=attempt+1 WHERE task_id=:id AND status='pending'
  -- rowcount==1 → 领取成功；否则循环重试
COMMIT
```
- `BEGIN IMMEDIATE` 使写事务串行化：并发 Worker 的 UPDATE 不会同时成功
- 条件 `AND status='pending'` 双保险（即使事务隔离异常也不双领）
- `busy_timeout=30000` 处理 `SQLITE_BUSY` 竞争

---

## 6. Worker 执行协议（幂等护栏）

`Worker25.execute(task)`：
```
1. 护栏检查 ps.should_process(asset_id, stage, pipeline_version):
   - SKIP_ALREADY_DONE → store.complete_task(skip=True); return
   - 状态 PROCESSING（旧进程持有）→ store.fail_task(retryable=False, 'occupied'); return
2. 按 stage 分派执行（scene/keyframe/asr/ocr），复用现有引擎
3. 成功 → store.save_*(...) 写结果表
         → ps.mark_done(...)（同步状态，兼容旧 UI/统计）
         → store.complete_task()
4. 失败 → ps.mark_failed(...) → store.fail_task(retryable=True)  # 重试≤3次
```

**写结果与状态的一致性**：结果表（segments/keyframes/transcripts/ocr_text）先写，`asset_processing_state` 后写，`analysis_tasks` 最后置 completed——任务完成标志是最外层提交，任何一步崩溃都会由 recover_stale 重跑（重跑幂等：结果表 UPSERT）。

---

## 7. Worker 日志（第八阶段）

每个 Worker 独立日志文件 `<data_root>/logs/worker_{id}.log`：
```
[2026-08-22 16:00:01.123] worker_001 | task=p25_ab12 | asset=000599b6 | stage=scene | result=success | 耗时=3.24s
[2026-08-22 16:00:05.401] worker_001 | task=p25_ab12 | asset=000599b6 | stage=keyframe | result=success | 耗时=2.10s
[2026-08-22 16:00:08.112] worker_002 | task=p25_cd34 | asset=0007e437 | stage=asr | result=success | 耗时=28.9s
[2026-08-22 16:00:09.000] worker_003 | task=p25_ef56 | asset=000805ca | stage=ocr | result=success | 耗时=1.02s
```
汇总日志 `worker_pool.log`：每轮批次 {workers, pending, completed, failed, seconds}。

---

## 8. 启动/停止

```bash
# 默认 3 Worker 全阶段
python -m treecut.main --p2.5-run

# 指定并行数与阶段
python -m treecut.main --p2.5-run --workers 3 --stages scene,keyframe,asr,ocr --limit 1000

# 仅状态查看
python -m treecut.main --p2.5-status
```

停止：Ctrl+C → stop_event → 各 Worker 完成当前任务后退出；未完成任务由 recover_stale 兜底（重启后继续）。

---

## 9. 验收（对应第九阶段 benchmark）

| 测试 | 方法 | 通过标准 |
|---|---|---|
| 防双领 | 2 进程同时 `--p2.5-run --workers 2` 指向同库 | 无同一 (asset_id,stage) 双跑；任务状态机无异常 |
| 吞吐 | 1000 素材，3 Worker vs 单 Worker（旧 P2） | ≥2× 吞吐（预计 2.5-3×，受 whisper 单素材串行瓶颈约束） |
| 断点恢复 | 中途 kill Worker，重启 `--p2.5-run` | 被 kill 任务 recover_stale 后重新完成，无重复结果 |
| 兼容 | 运行中 PID 19152 期间不启动 P2.5（默认策略） | 旧进程正常跑完，结果无损坏 |

---

## 10. 风险与缓解

| 风险 | 缓解 |
|---|---|
| whisper CPU 是瓶颈，3 Worker 提升有限 | 视觉/OCR Worker 先行，ASR 保持 1 Worker；后续 GPU 化 ASR |
| 多进程同时写 sqlite WAL | 已启用 WAL + busy_timeout；领取与写入均为短事务；结果表 UPSERT 幂等 |
| 内存峰值（whisper+onnx+cv2 同驻） | 每进程只加载自己阶段的模型，天然隔离；32GB 余量充足 |
| 旧进程与新 Worker 抢同一 asset | 默认不并存（检测 PROCESSING 等待）；强制并行时靠状态断言跳过 |
