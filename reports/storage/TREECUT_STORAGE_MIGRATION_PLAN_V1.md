# TreeCut 存储迁移计划 V1（Phase B 待批准）

- 日期：2026-08-31
- 前置：Phase A 审计完成（`reports/storage/`）
- 状态：**PENDING_USER_APPROVAL —— 本计划未执行任何移动/删除**

---

## 1. 现状结论（Phase A 审计要点）

| 项 | 结果 |
|---|---|
| C 盘可用 | **42.7 GB / 449 GB（CRITICAL，<50GB）** |
| E 盘可用 | 155.7 GB |
| G 盘可用 | 167.1 GB |
| Z 盘可用 | 12172 GB（11.9 TB） |
| TreeCut 在 C 盘的占用 | **仅 ~0.07 GB**（github 仓库）；运行数据（DB/profile/快照）**实际已在 E 盘**（`E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1`） |
| C 盘压力主源 | Downloads 21.3GB、AppData\Local\Temp 17.5GB、.cache 15GB（HF 模型）、Desktop 7.5GB、.ollama 5.6GB、dsh_models 1.9GB |
| 唯一 git 仓库 | `C:\Users\admin\github\treecut-v13`（HEAD e5c4f65，干净，已 push） |
| E 旧源码 | `E:\树剪整理\01_主程序源码` = 无 git 的旧源码转储（LEGACY/NEEDS_REVIEW） |
| E 安装版 | `E:\树剪整理\02_安装程序\TreeCut_v13` = 安装产物（含当前运行数据，MUST_PRESERVE） |

## 2. 目标架构（四层）

```
C  系统/配置/必要小文件
E  E:\TreeCut\            TreeCut repo + runtime（DB/profile/checkpoint/inbox/logs/temp/staging）
G  G:\AI\                 AI 模型 + 大型缓存（huggingface/modelscope/ollama/dsh_models）
Z  Z:\TreeCut_Media\      视频/图片/cover/导出/归档（B003/B007/B008/B010/UNASSIGNED_LEGACY）
```

纪律：Z 只放 media（不放 SQLite/Profile/LevelDB/Git）；媒体先写 E staging `*.part` → 验证 → 原子移 Z；
MEDIA_ROOT 不可用 → MEDIA_STORAGE_UNAVAILABLE，STOP，绝不 fallback C。

## 3. 迁移步骤（Phase B，按序执行，每步验证）

| # | 步骤 | 验证 | 风险 |
|---|------|------|------|
| 1 | 建目录 `E:\TreeCut\{repo,runtime\db,runtime\browser_profiles,runtime\checkpoints,runtime\inbox,runtime\processed,runtime\quarantine,runtime\logs,runtime\temp,runtime\staging}`、`G:\AI\...`、`Z:\TreeCut_Media\B007\{covers,published_media,creator_exports,raw_media,archive}` | 可写 | 低 |
| 2 | **模型缓存迁 G**：设 `HF_HOME=G:\AI\huggingface_cache`（+迁移现有 hub 内容）、`OLLAMA_MODELS=G:\AI\ollama`、dsh_models→G | 模型可加载（ASR/embedding/florence 冒烟） | 中：须支持重定向，禁止剪切未知目录 |
| 3 | **B007 Browser Profile 迁 E**：Work Browser 完全关闭 → 复制 `runtime_data\temp\batch1\browser_profiles\B007` → `E:\TreeCut\runtime\browser_profiles\B007` → 切换 ProfileRoot → 重启验证**三站登录持久化** | Creator/Spotlight/Frontend 免登录 | 高：任一丢 Session → PROFILE_MIGRATION_FAIL，保留原 profile 回滚 |
| 4 | **Runtime 数据迁 E**（DB/checkpoints/inbox/logs/temp 到 `E:\TreeCut\runtime\`）：TreeCut 停止写入时复制 → integrity_check/行数一致 → 切换 DATA_ROOT | sqlite integrity_check、155 B003 + 471 B007 行数一致、checkpoint 存在 | 中 |
| 5 | **Repo canonical 迁 E**：`git clone`/复制 C 仓库 → `E:\TreeCut\repo\treecut-v13`，checkout 同 commit（e5c4f65）→ HEAD identical + status clean + 测试跑通 | `git rev-parse HEAD` 相同、pytest 通过 | 低 |
| 6 | **媒体根指向 Z**：现有 cover 等媒体 → `Z:\TreeCut_Media\<account>\`；不能确定账号 → `UNASSIGNED_LEGACY`（**不靠文件夹名猜账号**） | 读写验证 | 低 |
| 7 | Harness/启动脚本切换：workspace/launcher/脚本 path → E canonical | 面板可启动、同步可用 | 低 |
| 8 | **C 盘清理（独立最后阶段，用户批准后）**：Temp 审查清理、已迁移并验证的 HF/.ollama/dsh 缓存清理、C 仓库保留备份一段后清理 | 见 Cleanup Plan | 用户文件项（Downloads/Desktop）一律人工审查 |

## 4. 预计 C 盘释放

| 项 | 预计释放 |
|---|---|
| Temp 清理（审查后） | 10-15 GB |
| HF 缓存迁 G 后清（硬链接实占） | 8-10 GB |
| .ollama → G 后清 | 5.5 GB |
| dsh_models → G 后清 | 1.9 GB |
| 小计（不含用户文件） | **约 26-33 GB → C 回 ~70-80GB** |
| 用户文件审查（Downloads/Desktop 37GB 内可处理部分） | 视用户决定 → 可达 **100GB+** |

## 5. 必须保留（MUST_PRESERVE）

- B007 三站登录（Browser Profile）——迁移后必须重验
- B007 471 条真实 PublishedContent + B003 155 条（DB）
- Raw Snapshots / Creator binding / checkpoints
- 未迁移前 C 仓库作为备份保留

## 6. 明确不做（本轮）

- 不删除任何文件（DELETE 仅在全部验证 PASS + 用户批准后独立执行）
- 不剪切未知 AI 目录（.ollama 等须经配置重定向）
- 不动 Windows 系统目录；Temp 清理仅限明确可清项
- 不继续 V0.2 Creator Sync 扩展（待迁移完成后续跑，471 条数据保留续用）

## 7. 请用户批准

确认本计划后进入 Phase B（COPY → VERIFY → SWITCH，按步骤执行并每步回报验证结果）。
