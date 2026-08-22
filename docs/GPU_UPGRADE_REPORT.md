# GPU 升级报告（P2.6）

- **日期**：2026-08-22
- **项目**：TreeCut v13.5.10 → P2.6（GPU 加速 + 多 Worker）
- **安全前提**：全程先备份、隔离测试、验证通过后才正式切换；生产数据库零修改

---

## 1. GPU 环境检测结果

| 项目 | 检测结果 |
|---|---|
| GPU 型号 | NVIDIA GeForce RTX 3050（6 GB，compute 8.6） |
| 驱动 | 591.86（支持 CUDA 13.1） |
| CUDA Toolkit | 未完整安装（无 nvcc / cudart） |
| cuDNN | ctranslate2 自带 `cudnn64_9.dll`（v9）✅ |
| **缺失项** | **cublas64_12.dll / cublasLt64_12.dll（CUDA 12 runtime）** ❌ |
| faster-whisper | 1.2.1 |
| ctranslate2 | 4.8.1（含 GPU 后端，`get_cuda_device_count()=1`） |
| torch | 2.6.0+cpu（TreeCut 能力检测因此报无 CUDA，但不影响 faster-whisper） |

**关键发现**：ctranslate2 的 GPU 后端**已随包分发**，模型能加载（1.0s），但推理失败——`cublas64_12.dll is not found`。只需补齐 cuBLAS 两个 DLL，无需完整 CUDA Toolkit。

## 2. 解决方案（轻量）

1. 从 PyPI 下载 `nvidia-cublas-cu12` wheel（527 MB），提取：
   - `cublas64_12.dll`（97.8 MB）
   - `cublasLt64_12.dll`（637.7 MB）
   - `nvblas64_12.dll`（0.3 MB）
2. 部署到生产数据根：`<data_root>/cuda_dlls/`（不修改 site-packages）
3. 通过环境变量 `TREECUT_CUDA_DLL_DIR` + `os.add_dll_directory` 注入加载路径

**未安装完整 CUDA Toolkit**（避免生产环境污染）；`cudart64_12.dll` 实际不需要（ctranslate2 已内置）。

## 3. 代码修改内容

| 文件 | 修改 |
|---|---|
| `src/treecut/asr/device_manager.py` | **新增**：ASR Device Manager（auto/cpu/cuda 自动检测，cuBLAS 可加载性探测，DLL 路径注入） |
| `src/treecut/asr/engine.py` | `WhisperEngine` 支持 `device="auto"`（默认），自动解析为 cuda/float16 或 cpu/int8 |
| `src/treecut/config/settings.py` | 新增 `asr_device: Literal["auto","cpu","cuda"]="auto"` 配置项 + 校验 |
| `src/treecut/analysis/worker_p25.py` | Worker25 接受 `asr_device` 参数透传给 WhisperEngine |
| `src/treecut/analysis/worker_pool.py` | WorkerPool 透传 `asr_device`/`cuda_dll_dir` 到子进程 |
| `src/treecut/analysis/scheduler.py` | `TaskScheduler.run()` 支持 `asr_device` 参数 |
| `src/treecut/main.py` | 新增 CLI 参数 `--asr-device auto/cpu/cuda` |

**ASR Device Manager 决策逻辑**：
```
auto → 检测 ctranslate2 CUDA 设备数 + cuBLAS DLL 可加载 + 显存 ≥3GB
       成功 → device=cuda, compute_type=float16
       失败 → device=cpu, compute_type=int8
cpu  → 强制 CPU (int8)
cuda → 强制 GPU (float16)，不可用则报错
```

## 4. 测试结果（隔离测试环境验证）

### 4.1 单素材 ASR 对比（5 个真实素材，30s 音频）

| 模式 | 平均耗时 | 实时率 |
|---|---|---|
| **GPU (float16)** | **0.33 s/素材** | ~90× |
| CPU (int8) | 3.02 s/素材 | ~10× |
| **加速比** | **9.2×** | |

### 4.2 全链路并行验证（WorkerPool + GPU ASR）

- 3 Worker 分片（vision/asr/ocr）各处理任务，全部 completed，0 失败，**无双领**
- 幂等护栏验证：已 DONE 的 asr 阶段被正确跳过（禁止重复分析生效）
- GPU ASR 实际推理成功（素材 `056668e1` 8.66s、`0566ce32` 0.88s）
- 生产恢复后 GPU 利用率 52%，显存 1.6 GB / 6 GB

## 5. 正式环境切换

1. 测试环境全部验证通过后，把 7 个修改文件复制到生产 git 仓库 `C:\Users\admin\github\treecut-v13\src`
2. cuBLAS DLL 部署到 `<data_root>/cuda_dlls/`
3. 重新启动 P2.5：`--p2.5-run --p2.5-workers 3 --p2.5-force --asr-device auto`

## 6. 数据安全验证

- 升级前 checkpoint + 数据库备份（`backup_before_gpu_upgrade/`，191.5 MB，integrity=ok）
- 升级后数据一致性检查全部通过（见 DATA_RECOVERY_REPORT.md / DATA_INTEGRITY_CHECK_REPORT.md）
- **生产数据库零修改**（只新增 analysis_tasks/schema_version 表）

## 7. 回滚方案

- 代码回滚：`git checkout` 至升级前提交（P2.6 修改已单独提交）
- DLL 回滚：删除 `<data_root>/cuda_dlls/`（ASR 自动回退 CPU int8）
- 数据库回滚：使用 `backup_before_gpu_upgrade/materials_*.db` 恢复（如需）
