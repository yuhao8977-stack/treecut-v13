# 任务调度系统设计（P2.5/P2.6）

- **版本**：v2.0（P2.6 增补 GPU ASR 透传）
- **关联**：docs/P2.5_ARCHITECTURE_DESIGN.md、docs/GPU_UPGRADE_REPORT.md

---

## 1. 架构总览

```
CLI: treecut.main --p2.5-run [--workers 3] [--asr-device auto] [--force]
        │
        ▼
TaskScheduler (analysis/scheduler.py)
  │  1) 迁移（analysis_tasks + schema_version，幂等）
  │  2) sync_from_state（扫描未完成阶段 → 批量生成任务，0.68s/3万）
  │  3) 旧进程互斥检查（默认不抢跑，--force 跳过）
  │  4) WorkerPool 并行执行
  ▼
WorkerPool (analysis/worker_pool.py)  ← spawn 多进程
  ├── worker_001 [vision] scene+keyframe
  ├── worker_002 [asr]    whisper（GPU/CPU 自动）★ P2.6
  └── worker_003 [ocr]    rapidocr
        │  每进程: TaskStore.claim_task() → Worker25.execute() → 回写
        ▼
materials.db（WAL）
  ├── analysis_tasks      ← 调度层任务表（新增，P2.5）
  ├── asset_processing_state  ← 阶段状态机（既有，兼容旧 UI）
  ├── schema_version      ← 版本表（新增，P2.5）
  └── segments/keyframes/transcripts/ocr_text  ← 结果表
```

## 2. 核心组件

### 2.1 TaskStore（`library/task_store.py`）
- `analysis_tasks` 表：task_id/asset_id/task_type/stages/status/worker_id/priority/retry_count/attempt/error/created_time/started_time/finished_time
- **原子领取**：`BEGIN IMMEDIATE` + `UPDATE ... WHERE status='pending'` + rowcount 校验 → 多 Worker 绝无双领（16 项单测 + 2 进程 200 任务并发验证）
- 状态机：pending → processing → completed | failed | skipped
- 失败重试 ≤3 次；失联任务 `recover_stale` 回收

### 2.2 WorkerPool（`analysis/worker_pool.py`）
- 默认 3 进程：vision/asr/ocr 各一（按阶段职责分片，模型内存隔离）
- 修复 P1 pool 缺陷：`queue.get(timeout)` + 存活轮询 + close 时 terminate
- **P2.6**：子进程透传 `asr_device` 与 `cuda_dll_dir`（spawn 子进程内 `os.add_dll_directory` 注入 cuBLAS）

### 2.3 Worker25（`analysis/worker_p25.py`）
- 复用 SceneDetector/KeyframeExtractor/WhisperEngine/OcrEngine
- 幂等护栏：`should_process()` 判定 → DONE/SKIPPED 跳过；PROCESSING 占用标记 occupied
- 每 Worker 独立日志（worker_id/asset_id/stage/耗时/结果）

### 2.4 ASR Device Manager（`asr/device_manager.py`）★ P2.6 新增
```
auto → detect_device(): ctranslate2 CUDA 设备数 + cuBLAS DLL 可加载 + 显存
       → cuda/float16 或 cpu/int8
```
- `TREECUT_CUDA_DLL_DIR` 环境变量注入 cuBLAS 目录
- 决策结果写入 WhisperEngine.device_decision（日志可查）

## 3. 任务生命周期

```
sync_from_state 扫描未完成阶段
      │  幂等（UNIQUE(asset_id, task_type)）
      ▼
pending ──claim_task──► processing ──complete_task──► completed
   ▲                        │
   │   fail_task(retryable) │ (超时 recover_stale)
   └────────────────────────┘
   │ retry_count > 3
   ▼
failed
```

## 4. 防重复分析（多 Worker + 旧任务共存）

| 场景 | 保护机制 |
|---|---|
| 多 Worker 抢同一任务 | `BEGIN IMMEDIATE` 原子领取 + rowcount 校验 |
| 任务已 DONE/SKIPPED | Worker25 幂等护栏 `should_process()` 跳过 |
| 旧进程正在处理某阶段 | 状态 PROCESSING → 标记 occupied 不抢 |
| 崩溃/中断恢复 | `recover_stale`/`recover_all_processing` 回收为 pending |

## 5. P2.6 关键增强

1. **GPU ASR**：`--asr-device auto` 自动选 GPU（float16），不可用回退 CPU（int8）
2. **性能**：实测 ASR 加速 9.2×（GPU 0.33s vs CPU 3.02s）
3. **兼容**：旧 `--p2-run`/`--p2.5-run` 参数全部保留；settings.json 新增 `asr_device` 配置
4. **可回滚**：删 `cuda_dlls/` 目录即回退 CPU 模式

## 6. 未来扩展（预留）

- `task_type` 自由扩展：segment/embedding/vision 直接接入同一调度
- `priority` 字段支持高优任务插队
- 3TB 素材：任务按 asset 粒度无限排队，断点恢复靠任务持久化
