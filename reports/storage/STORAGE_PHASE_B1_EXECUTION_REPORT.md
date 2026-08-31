# Phase B1 执行报告 — 低风险 C 盘减压 + Storage Guard

- 日期：2026-08-31
- 状态：**执行完成；成功线 C_FREE>=70GB 未达（55.2GB）——按 §20 不乱删，报告缺口与下一步候选**
- 已批准约束遵守：未动 E 盘 runtime/DB/B007 Profile、未删旧模型副本、未碰 Downloads/Desktop、未迁 repo、未删 E 旧版、V0.2 保持暂停

---

## 1. 执行结果汇总

| 项 | 结果 |
|---|---|
| C free before | 42.47 GB |
| **C free after** | **55.18 GB（+12.71 实际释放）** |
| 成功线 | C_FREE >= 70GB —— **未达（缺口 14.8GB）** |
| Temp 清理 | ✅ 释放 **12.79 GB**（4331 个过期条目；占用/近期 4.69GB 正确跳过，未强杀程序） |
| HF 缓存 → G | ✅ 复制 13.63GB → `G:\AI\hf_cache`，`snapshot_download(local_files_only)` 从 G 加载验证通过；`HF_HOME/HF_HUB_CACHE` setx 指向 G |
| Ollama 模型 → G | ✅ 复制 5.56GB → `G:\AI\ollama_models`，`ollama list`（OLLAMA_MODELS=G）显示 qwen2.5vl:7b；setx 指向 G |
| dsh_models | ⏸ **SKIP_WITH_REASON**（Harness 自身 HF 缓存，消费方配置无法确认，不为 1.9GB 冒险） |
| StorageHealthGuard | ✅ 实现并接入面板启动：C<80 WARNING（当前 55.2 命中）、E<50 WARNING、Z 不可用→MEDIA_STORAGE_UNAVAILABLE、AI cache 回落 C→警告、E staging 上限 20GB |
| Z 媒体根 | ✅ 建 `Z:\TreeCut_Media\{B003,B007,B008,B010,UNASSIGNED_LEGACY}` + B007 五子目录（未动现有 14TB 素材池） |
| 启动脚本 | ✅ bat 重生成（GBK+CRLF）：HF_HOME/HF_HUB_CACHE/OLLAMA_MODELS 指向 G |

## 2. 迁移后验证（§18）

| 验证 | 结果 |
|---|---|
| B007 PublishedContent | **471 条完好** |
| B003 PublishedContent | **155 条完好** |
| DB integrity_check | **ok** |
| TreeCut 测试（browser 套件） | **51 通过** |
| HF 模型从 G 加载 | ✅ faster-whisper-small 解析到 `G:\AI\hf_cache\hub\...` |
| Ollama 从 G 列模型 | ✅ qwen2.5vl:7b |
| AI 缓存回落 C | ❌ 无（守卫 `ai_cache_on_system_drive=[]`） |
| B007 Profile | **未动**（本就在 E，登录态不受影响） |
| V0.2 | 暂停 |

## 3. 为什么 C 只回到 55.2GB（如实说明）

Phase B1 释放来源只有 **Temp 清理（+12.7GB）**。模型迁移本身**不释放 C**——按你的 §17 约束，旧 C 模型副本（HF 约 8-10GB 实占 + ollama 5.56GB）**保留**，待 **Cleanup Gate 批准后**才删。所以：
- 当前 55.2GB = 42.47 + 12.71（Temp）
- 距离 70GB 差 **14.8GB**

## 4. 下一步候选（需要你决策，我不自动执行）

| 候选 | 预计释放 | 门槛 |
|---|---|---|
| A. **Cleanup Gate**：删旧 C 模型副本（`C:\Users\admin\.cache\huggingface` 实占约 8-10 + `.ollama` 5.56） | **约 14-16GB → C 回 ~70GB** | 你确认 G 上模型已验证可用后批准删除 |
| B. **Phase B2**：Downloads/Desktop 只读分类 + 用户决定 | 最高 +28GB → 90GB+ | 你批准 B2 后才做 |

> 若批准 A：C 可达 **~70GB（达标线）**；A+B 可达 **90-100GB+**。

## 5. 产物

`reports/storage/`：`STORAGE_PHASE_B1_VALIDATION_V1.json`、`TEMP_CLEANUP_RESULT_V1.json`、
`HF_CACHE_MIGRATION_V1.json`、`OLLAMA_MODEL_MIGRATION_V1.json`、`DSH_MODEL_MIGRATION_V1.json`、
`STORAGE_HEALTH_GUARD_V1.json`；`src/treecut/browser/storage_guard.py`（新模块）；bat 更新。

## 6. 环境变更（setx，用户级持久）

- `HF_HOME=G:\AI\hf_cache`、`HF_HUB_CACHE=G:\AI\hf_cache\hub`
- `OLLAMA_MODELS=G:\AI\ollama_models`
- `MODELSCOPE_CACHE=G:\AI\modelscope_cache`

> 说明：setx 对新启动的进程生效；当前已运行的程序仍用旧路径（旧 C 副本保留故无影响）。
