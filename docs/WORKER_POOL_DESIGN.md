# Worker Pool 设计（P2.6 GPU 版）

- **版本**：v2.0（P2.6 增补 GPU ASR Worker）
- **关联**：docs/P2.5_ARCHITECTURE_DESIGN.md、docs/GPU_UPGRADE_REPORT.md

---

## 1. 硬件基线（当前电脑）

| 资源 | 配置 | P2.6 分配 |
|---|---|---|
| CPU | 6 核 12 线程 | 3 Worker × 2-4 线程 |
| 内存 | 32 GB | 3 模型常驻 ≈ 3-5 GB |
| **GPU** | **RTX 3050 6GB** | **ASR Worker 使用 GPU（float16）** ★ |

## 2. Worker 分片（默认 3）

```
WorkerPool（1 调度主进程）
 ├── worker_001 [vision] scene + keyframe（CPU，cv2/scenedetect）
 ├── worker_002 [asr]    whisper（★ GPU float16，RTX 3050）
 └── worker_003 [ocr]    rapidocr（CPU，onnxruntime）
```

**为何 ASR 用 GPU**：
- whisper small float16 显存 ~1.6GB（6GB 卡无压力）
- 实测 9.2× 加速（GPU 0.33s vs CPU 3.02s/素材）
- 视觉/OCR 保持 CPU（无 GPU 模型或收益低），避免显存竞争

## 3. 进程模型

```python
def _pool_entry(worker_id, task_type, stages, db_path, log_path,
                limit, asr_device, cuda_dll_dir, ready_queue, result_queue, stop_event):
    if cuda_dll_dir:
        os.add_dll_directory(cuda_dll_dir)   # ★ spawn 子进程内注入 cuBLAS
    worker = Worker25(..., asr_device=asr_device)
    while True:
        task = store.claim_task(worker_id, task_type, stages)
        if task is None: break
        worker.execute(task)                  # 幂等护栏 + 结果回写
```

**关键**：`os.add_dll_directory` 必须在**子进程内**调用（不继承父进程），故 cuda_dll_dir 经进程参数传入。

## 4. GPU ASR Worker 详细设计

### 4.1 设备决策（WhisperEngine）
```
启动时 detect_device("auto"):
  ctranslate2.get_cuda_device_count() > 0
  AND cuBLAS DLL 可加载（cublas64_12.dll + cublasLt64_12.dll）
  AND 显存 ≥ 3GB
  → device=cuda, compute_type=float16
  否则 → device=cpu, compute_type=int8
```

### 4.2 显存管理
- whisper small float16：~1.6GB（6GB 卡，余量充足）
- 模型常驻 Worker 进程（不重复加载）
- 决策记录 `device_decision`（reason 含 vram/cublas 状态），可查日志

### 4.3 失败降级
- GPU 加载/推理异常 → Worker25 捕获 → `fail_task(retryable=True)` → 重试
- 若持续失败（如显存不足），可用 `--asr-device cpu` 强制 CPU

## 5. 并发安全

| 机制 | 说明 |
|---|---|
| 原子领取 | `BEGIN IMMEDIATE` + rowcount，Worker 间无双领（验证：200 任务 2 进程 0 重复） |
| 幂等护栏 | `should_process()` 跳过已 DONE/SKIPPED |
| 占用互斥 | PROCESSING 状态 → occupied 不抢（与旧进程共存） |
| 崩溃恢复 | `recover_stale`（30min 超时回收）+ 启动兜底回收 |

## 6. 实测数据（隔离测试环境）

| 测试 | 结果 |
|---|---|
| 3 Worker 并行（vision/asr/ocr） | 9 任务全 completed，0 失败，无双领 |
| GPU ASR 推理 | 8.66s（长素材）/ 0.88s（短视频） |
| GPU 利用率 | 52%（推理峰值） |
| 显存 | 1.6 GB / 6 GB |
| ASR 加速比 | 9.2×（vs CPU int8） |

## 7. 启动/停止

```bash
# 默认：3 Worker + GPU ASR 自动检测
python -m treecut.main --p2.5-run --p2.5-workers 3 --asr-device auto

# 强制 GPU / 强制 CPU
python -m treecut.main --p2.5-run --asr-device cuda
python -m treecut.main --p2.5-run --asr-device cpu
```

停止：Ctrl+C → stop_event → Worker 完成当前任务后退出；未完成任务由 recover_stale 兜底。

## 8. 回滚

- 删除 `<data_root>/cuda_dlls/` → ASR 自动回退 CPU（无需改代码）
- 或 `--asr-device cpu` 显式指定
