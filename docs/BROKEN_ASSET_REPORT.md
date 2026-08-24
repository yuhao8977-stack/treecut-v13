# 损坏资产报告（P2.7）

- **日期**：2026-08-24
- **说明**：13 个损坏素材已隔离到 `broken_assets` 表（未删除，仅标记，搜索时默认排除）

---

## 1. 损坏资产总览

| 指标 | 数值 |
|---|---|
| 损坏资产数 | **13** |
| 涉及任务数 | 130（每资产多阶段失败） |
| 失败阶段 | keyframe + asr（scene DONE 但后续失败） |
| 隔离状态 | `broken_assets` 表 resolved=0 |

## 2. 损坏原因

全部为**源文件无法解码**（`Invalid data found when processing input` / `无法打开视频`）：
- 文件损坏或格式异常（DJI 无人机 MP4 文件，部分在复制/传输中损坏）
- 网络盘（`\\X1\`）文件可能不完整

## 3. 损坏资产清单

| # | asset_id | 文件（截断） | 失败阶段 |
|---|---|---|---|
| 1 | 1f0d2c44a9e0 | 01_已发布产品视频…【170】2025.11.10…DJI_20251110103134 | keyframe+asr |
| 2 | 319c96d82eea | 【106】2025.7.21…上海…DJI_20250721144629 | keyframe+asr |
| 3 | 4f4dca4a7190 | 12.17…未处理…珠海…DJI_20251217142834 | keyframe+asr |
| 4 | 52b3fb3c273a | 小艺…12.22…DJI_20251222163004 | keyframe+asr |
| 5 | 5662233d8f46 | 20251221…DJI_20251221101049 | keyframe+asr |
| 6 | 692f748a61d7 | 20251124…视频未处理…DJI_20251124150947 | keyframe+asr |
| 7 | 74a287790ea3 | 【106】2025.7.21…DJI_20250721144759 | keyframe+asr |
| 8 | 7b1c13270695 | 【106】2025.7.21…DJI_20250721144650 | keyframe+asr |
| 9 | 8dec723c6474 | 【106】2025.7.21…DJI_20250721144739 | keyframe+asr |
| 10 | 93c2f0e585d7 | 【031】20250518…DJI_20250518144735 | keyframe+asr |
| 11 | b6fd32c3af80 | 【031】20250518…DJI_20250518100604 | keyframe+asr |
| 12 | ca5b705e7763 | 【106】2025.7.21…DJI_20250721144816 | keyframe+asr |
| 13 | f81230897ebc | 【106】2025.7.21…DJI_20250721144458 | keyframe+asr |

## 4. 处理策略

1. **已隔离**：全部记录在 `broken_assets` 表（asset_id/file_path/error_reason/failed_time/stage），**不删除原文件**
2. **搜索排除**：素材检索默认 `JOIN broken_assets b ON b.asset_id != a.asset_id AND b.resolved=0` 排除
3. **可恢复**：若未来源文件修复（重新下载/拷贝），置 `resolved=1` 后重跑分析

## 5. 影响评估

- 13/22,465 = **0.058%**，对素材库影响极小
- 均为单点文件损坏，无系统性风险

## 6. 后续动作

- 若需恢复：找到损坏文件的备份版本 → 替换网络盘文件 → `UPDATE broken_assets SET resolved=1` → 重跑 scene/keyframe/asr
- 否则：保持隔离，搜索自动排除
