# STORAGE_PHASE_B1_CLEANUP_REPORT — Cleanup Gate A 执行 + Phase B2 只读审计

- 生成时间: 2026-08-31
- 状态: **Cleanup Gate A 完成（C free 55.3 → 74.0 GB，目标 ≥70GB 达成）**；Phase B2 只读审计完成（0 移动/删除）

---

## 1. Cleanup Gate A — 旧模型负载删除（用户已批准）

### 1.1 前置新进程验证（删除前，全通过）

| 项 | 结果 |
|---|---|
| HF fresh-process | `HF_HOME/HF_HUB_CACHE` 解析到 `G:\AI\hf_cache`（G 盘）；`faster-whisper-small` snapshot_download local_files_only → `G:\AI\hf_cache\hub\models--Systran--faster-whisper-small\snapshots\536b...` ✅ |
| Ollama fresh-process | 首次 smoke 输出 "OK" exit=0（后发现走的是旧 C 路径 server，见 §1.3）⚠️→ 修正后重验 ✅ |

### 1.2 删除执行（仅批准目录）

| 目标 | 大小 | 文件数 | 结果 |
|---|---|---|---|
| `C:\Users\admin\.cache\huggingface\hub` | 13.63 GB | 123 | DELETED ✅ |
| `C:\Users\admin\.ollama\models` | 5.56 GB | 7 | DELETED ✅ |

- 保留项完整：`.cache\huggingface\modules / xet / .agent_harnesses.json / .check_for_update_done`；`.ollama\cache / history / id_ed25519 / id_ed25519.pub`。`.cache\huggingface` 下无 token 文件（凭证不在此）。
- 清单：`HF_OLD_CACHE_DELETE_MANIFEST_V1.json`、`OLLAMA_OLD_MODEL_DELETE_MANIFEST_V1.json`（status=DELETED）
- 结果：`CLEANUP_GATE_A_RESULT_V1.json`；C free 55.3 → 74.5 GB（+19.2 GB）

### 1.3 发现并修复：Ollama server 环境未指向 G ⚠️

- **根因**：8/28 启动的旧 `ollama serve` 进程早于迁移，持有旧 C 路径环境；客户端 `ollama list/run` 只与本地 server 通信，**server 才决定模型路径**。因此迁移阶段的 ollama 验证实际走的是 C 旧副本（验证盲区，已诚实记录）。
- **修复**：杀掉旧进程 → 以 `OLLAMA_MODELS=G:\AI\ollama_models` 重启 serve → 验证通过。
- **托盘 App 陷阱**：实测 `ollama app`（托盘）拉起的 serve **不继承 OLLAMA_MODELS**（API 空），会回落到已清空的 C 路径 → 托盘显示无模型。**请勿用托盘 App 替代 serve 启动方式。**
- **提供**：`scripts\start_ollama_serve_g.cmd`（一键杀旧进程 + G 环境启动 + 验证列表）。

### 1.4 清理后验证（STORAGE_POST_CLEANUP_VALIDATION_V1.json → **all_pass=true**）

- 旧副本：C 上 HF hub 与 Ollama models blobs 均不存在；保留项全部完好
- HF：全新进程 local_files_only 从 G 加载 ✅
- Ollama：API tags 显示 `qwen2.5vl:7b` (5.6GB)；真实推理 stdout="OK" exit=0；C 无 blob、G 有 6 个 blob → 推理确定来自 G ✅
- DB：`published_content_v1` B007=471 / B003=155，`performance_snapshot_v1`=155，integrity=ok ✅
- G 负载：ollama blobs=6，HF faster-whisper-small 目录在 G ✅
- **C free = 74.0 GB，目标达成（≥70，未达理想 ≥80，缺口 6GB，不强制）**

---

## 2. Phase B2 — Downloads / Desktop 只读分类（0 动作）

模式：只读审计，未移动/删除/重命名任何用户文件。完整清单见 `DOWNLOADS_READONLY_AUDIT_V1.json`、`DESKTOP_READONLY_AUDIT_V1.json`；评审视图 `USER_C_DRIVE_CLEANUP_REVIEW_V1.md`。

### 2.1 Downloads（31,470 文件 / 21.33 GB）

| 类别 | 大小(GB) | 说明 |
|---|---|---|
| PROJECT_TO_E | 8.18 | 主要为 `cc-switch-main`（Rust/Tauri 项目，含 target 构建产物） |
| INSTALLER_DELETE | 8.42 | OllamaSetup.exe 1.3GB、ChatGPT-x64.msix 0.71GB、BaiduNetdisk、Feishu、DiskGenius 等 |
| DUPLICATE | 4.24 | 同名同大小重复（如 cc-switch 构建产物 deps 副本） |
| MEDIA_TO_Z | 0.29 | 视频/音频/图片 |
| ARCHIVE_REVIEW | 0.18 | 压缩包/镜像 |
| UNKNOWN_KEEP | 0.02 | 无法可靠分类 → 保留 |
| KEEP | 0.01 | 文档/配置 |

### 2.2 Desktop（360 文件 / 7.50 GB）

| 类别 | 大小(GB) | 说明 |
|---|---|---|
| MEDIA_TO_Z | 7.33 | 主要为「协助运营剪辑文件夹」（2025-12 各日期子目录 .mp4）、bgm、图片素材、证件照片等 —— **疑似活跃工作素材，迁移需谨慎评估** |
| KEEP | 0.13 | 文档/快捷方式 |
| INSTALLER_DELETE | 0.03 | DiskGenius 等 |
| ARCHIVE_REVIEW | <0.01 | — |

### 2.3 敏感提醒
- Desktop 存在 `证件文件\身份证*.png` 等个人敏感文件 → 归类 MEDIA_TO_Z 仅为建议；**此类文件默认不迁移、不删除**，如用户确认迁移需按机密处理。
- Desktop 含 `B003_6a8d75aa..._FULL_V4.mp4`（2026-08-30 生成，TreeCut B003 导出）→ 活跃产物，保留。

---

## 3. 未触碰清单（硬约束）
- TreeCut E 盘运行时/DB/B007 档案：不迁不改不重部署
- C 盘 treecut-v13 仓库（0.07GB）：保留
- E 盘旧版 TreeCut、dsh_models、Windows 系统目录：不动
- Downloads/Desktop 全部用户文件：只读分类，动作待用户逐项确认

## 4. 后续建议（待用户决策，本阶段不执行）
1. **Ollama 使用方式**：以后启动用 `scripts\start_ollama_serve_g.cmd`；托盘 App 的 serve 不读 G。
2. Downloads 候选（合计约 16.8GB）：cc-switch 项目（→E 或删除构建产物）、安装包（→删除）、重复项（→保留一份）。
3. Desktop 7.33GB 媒体：确认是否为活跃素材；若是，保持原地，不迁 Z。
4. V0.2 未自动恢复；用户确认后再继续。

## 5. 关联产物
- scripts: `storage_cleanup_gate_a.py`, `storage_post_cleanup_validation.py`, `storage_b2_readonly_audit.py`, `start_ollama_serve_g.cmd`
- reports/storage: `HF_OLD_CACHE_DELETE_MANIFEST_V1.json`, `OLLAMA_OLD_MODEL_DELETE_MANIFEST_V1.json`, `CLEANUP_GATE_A_RESULT_V1.json`, `STORAGE_POST_CLEANUP_VALIDATION_V1.json`, `DOWNLOADS_READONLY_AUDIT_V1.json`, `DESKTOP_READONLY_AUDIT_V1.json`, `USER_C_DRIVE_CLEANUP_REVIEW_V1.md`
