# TreeCut 存储架构报告 V1

- 日期：2026-08-31
- 阶段：Phase A — 存储审计 + 迁移规划（**只读，未执行任何移动/删除**）
- 优先级：P0（C 盘 42.7GB 可用，CRITICAL）

---

## 1. 磁盘现状

| 盘 | 可用 GB | 总 GB | 角色建议 |
|---|-------:|-----:|----------|
| C | 42.7 | 449.2 | 系统 / 配置 / 必要小文件 |
| D | 140.3 | 481.2 | 普通软件 / 备用 |
| E | 155.7 | 500.0 | **TreeCut 程序 + 运行数据** |
| G | 167.1 | 431.5 | **AI 模型 / 大型缓存** |
| Z | 12172.5 | 14902.0 | **大型媒体**（素材盘） |

## 2. C:\Users\admin 占用分布

| 目录 | 大小 GB | 分类 |
|------|-------:|------|
| Downloads | 21.33 | 用户文件——需人工审查 |
| AppData\Local\Temp | 17.48 | 临时——审查后清理 |
| .cache | 14.93 | HF 模型缓存（含硬链接，实占约 8-10GB）——可迁 G |
| Desktop | 7.50 | 用户文件——需人工审查 |
| .ollama | 5.56 | 模型——可迁 G |
| dsh_models | 1.89 | 模型——可迁 G |
| deepseek-harness | 1.07 | Harness 程序数据 |
| .dsh | 0.81 | Harness 数据 |
| github | 0.07 | **开发仓库（唯一 git 仓库）** |
| 其余 | <0.1 | — |

**关键结论**：TreeCut 本身在 C 盘仅 ~0.07GB；其运行数据（DB/Profile/快照）已在 E 盘。
C 盘压力来自用户文件、Temp、AI 模型缓存——不是 TreeCut。

## 3. 目标架构（四层，冻结）

```
C   系统 + 用户配置 + 必要小文件
E   E:\TreeCut\
      repo\treecut-v13          （唯一 canonical 仓库）
      runtime\db                （SQLite/索引）
      runtime\browser_profiles  （B007 等，登录持久化关键）
      runtime\checkpoints\inbox\processed\quarantine\logs\temp\staging
G   G:\AI\
      models / huggingface_cache / modelscope_cache / ollama / dsh_models
Z   Z:\TreeCut_Media\
      B003 / B007 / B008 / B010 / UNASSIGNED_LEGACY
      B007: covers / published_media / creator_exports / raw_media / archive
```

纪律：
- Z 只放媒体；**不放** SQLite / Browser Profile / LevelDB / Git working tree（网络盘 IO 延迟风险）。
- 媒体先写 `E:\TreeCut\runtime\staging\*.part` → size/ffprobe/decode/SHA256 PASS → 原子移 Z；FAIL → quarantine。
- **MEDIA_ROOT 不可用 → MEDIA_STORAGE_UNAVAILABLE → STOP MEDIA TASK，绝不 fallback 到 C 盘**。
- 磁盘守卫：C free <80GB → WARNING；<50GB → CRITICAL（禁媒体/缓存写 C）。
- 日志单文件 ≤100MB、保留 5-10 份 rotate。

## 4. 仓库与版本审计

| 位置 | 类型 | 判定 |
|------|------|------|
| C:\Users\admin\github\treecut-v13 | git（HEAD e5c4f65，clean，pushed） | **CURRENT_CANONICAL（唯一）** |
| E:\树剪整理\01_主程序源码 | 无 git 旧源码转储 | LEGACY_SOURCE_DUMP / NEEDS_REVIEW |
| E:\树剪整理\02_安装程序\TreeCut_v13 | 安装产物（含运行数据） | INSTALLED_PRODUCT / MUST_PRESERVE |

迁移策略：以 C 为源在 `E:\TreeCut\repo\treecut-v13` 建 canonical（同 commit），C 保留备份，
E 旧版本不覆盖合并，验证后再分类清理。

## 5. 模型缓存（可迁 G）

| 缓存 | 大小 GB | 重定向方式 |
|------|-------:|------------|
| .cache/huggingface | 14.93（实占约 8-10） | `HF_HOME=G:\AI\huggingface_cache` + 迁移 hub 内容 |
| .ollama | 5.56 | `OLLAMA_MODELS=G:\AI\ollama` |
| dsh_models | 1.89 | `G:\AI\dsh_models`（确认消费方后） |
| .modelscope | ≈0 | `MODELSCOPE_CACHE=G:\AI\modelscope_cache` |

禁止直接剪切未知目录；须经支持的重定向并验证。

## 6. 预计 C 盘释放（不含用户文件审查项）

Temp 10-15 + HF 8-10 + ollama 5.5 + dsh 1.9 ≈ **26-33GB → C 回 70-80GB**；
含 Downloads/Desktop 审查处理可达 **100GB+**（用户决定）。

## 7. 迁移顺序（Phase B，用户批准后）

建目录 → 模型缓存迁 G → **B007 Profile 迁 E（高风险管理，须重验三站登录）** →
Runtime 数据迁 E（DB integrity 一致）→ Repo canonical 迁 E → 媒体根指向 Z →
Harness/脚本切换 → 最后才 C 盘清理（独立阶段 + 备份 + 批准）。

## 8. 暂停事项

V0.2 Creator Sync 扩展暂停；现有 471 条 B007 PublishedContent、B003 155 条、
Browser Profile 登录态全部保留；迁移完成后续跑，无需重来。

---

*本报告仅基于 Phase A 只读审计；未删除、未移动任何文件。详细数据见 `reports/storage/`。*
