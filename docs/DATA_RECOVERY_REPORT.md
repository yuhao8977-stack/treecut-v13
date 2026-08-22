# 数据恢复报告（P2.6）

- **日期**：2026-08-22
- **流程**：备份 → 暂停 → GPU 升级 → 恢复 → 一致性验证

---

## 1. 暂停前状态（Checkpoint，17:29:36）

**文件**：`<data_root>/P2_CHECKPOINT_BEFORE_GPU.json`

```json
{
  "batch": "batch1",
  "completed": {"scene": 12210, "asr": 12355, "keyframe": 12182, "ocr": 12130},
  "pending_assets": 10260,
  "total_assets": 22465,
  "analysis_tasks": {"pending": 28107, "completed": 4474, "processing": 2},
  "running_processes": ["PID 21316 (P2.5)", "PID 19152 (P2)"],
  "database_path": "...\\batch1\\database\\materials.db",
  "timestamp": "2026-08-22 17:29:36"
}
```

## 2. 备份（升级前）

| 项目 | 位置 | 大小 | 校验 |
|---|---|---|---|
| 数据库一致性备份 | `backup_before_gpu_upgrade/materials_20260822_172947.db` | 191.5 MB | integrity=ok |
| 配置备份 | `backup_before_gpu_upgrade/config/settings.json` | — | — |

## 3. 暂停执行

- P2.5 调度主进程 PID 21316 + 3 Worker（1092/18936/18616）优雅停止
- 旧 P2 进程 PID 19152 停止
- 2 个 processing 任务留在 analysis_tasks（由恢复时 `recover_all_processing` 回收为 pending，**不丢失**）

## 4. 恢复执行（17:48）

- 启动命令：`python -m treecut.main --p2.5-run --p2.5-workers 3 --p2.5-force --asr-device auto`
- `TREECUT_CUDA_DLL_DIR=<data_root>/cuda_dlls` 注入 cuBLAS
- 3 Worker 并行 + ASR Worker 走 GPU
- 遗留旧 P2 进程（PID 20700）已停止，避免双调度冲突

## 5. 恢复后状态（17:55）

| 指标 | 暂停前 | 恢复后 | 变化 |
|---|---|---|---|
| assets | 22,465 | 22,465 | 一致 |
| scene DONE | 12,210 | 12,272 | +62 |
| asr DONE | 12,355 | 12,494 | +139 |
| keyframe DONE | 12,182 | 12,243 | +61 |
| ocr DONE | 12,130 | 12,178 | +48 |
| 任务 completed | 4,474 | 5,206 | +732 |

## 6. 数据一致性检查（完整）

| 检查项 | 结果 |
|---|---|
| asset 数量 | ✅ 22,465 一致 |
| 各阶段 DONE | ✅ 只增不减（无丢失） |
| segments/keyframes/transcripts/ocr_text | ✅ 计数正常增长 |
| 数据库完整性 | ✅ `integrity_check = ok` |
| journal_mode | ✅ WAL |
| 重复分析 | ✅ 幂等护栏跳过已 DONE（验证：asr 已完任务被正确跳过） |

## 7. 结论

**升级全程数据零丢失、零重复**。所有阶段结果只增不减，数据库完整性保持 ok。恢复后 GPU 版并行分析正常运行，任务持续推进。
