# TreeCut Review System Productization — 审核系统产品化报告

- **日期**：2026-08-28 16:18 ｜ 仓库 `f5aa944` ｜ 词典：ANNOTATION_DICTIONARY_V2_1
- **范围**：PART A 数据结算 + PART B 播放系统 + PART C 主程序接入 + PART D 响应式 + PART E/F 验收
- **纪律**：未自动学习、未改 AI 规则/权重/模型/CLIP；未创建 FRESH_HOLDOUT；未进入 Stage 2/Phase 4；未导入行业知识库

## PART A — 人工数据结算（详见 PHASE3_HUMAN_DATA_FINALIZATION_REPORT.md）

- **94 条冻结确认**：THIRD_ADJUDICATION_V1 = 34/34、TARGETED_REVIEW_BATCH_V1 = 60/60 全部落库
- V3 裁决：**33 resolved**（canonical truth_version 2，truth_source=THIRD_ADJUDICATION）+ **1 still_needs_review**（09f514b8…）
- Targeted：**60/60 CALIBRATION_ELIGIBLE**（truth_source=TARGETED_SINGLE_REVIEW，与原 300 零重叠）
- **CALIBRATION_CORPUS_V2 = 333 unique segment**（240 + 33 V3 + 60 Targeted）；needs_review 1、excluded 27
- COVERAGE_MATRIX_V3：GOOD 23 / MEDIUM 2 / LOW 16；**长尾改善有限（素材库先天偏科 工厂×岛台×岩板 98%+），诚实报告**
- 质量：两批仍全 MEDIUM/REVIEWED（如实报告，未自动修改）

## PART B — 播放系统

**1. 重复窗口真正根因**：修复前 `_on_mandatory` 方法边界错误导致 body 每次切题重建 → **多个"播放完整视频"按钮重叠** → 一次点击命中多个 handler → 打开 2/3/4 个播放器。修复后 body 唯一、按钮唯一（实测=1），此根因已消除。

**2. 修复前一次点击 launch 数量**：2/3/4（多按钮重叠，无防抖）
**3. 修复后一次点击 launch 数量**：**1**（实测；快速连点 600ms 内仍 1）
**4. PlaybackController 架构**：
```python
class PlaybackController:
    play_full(path)      → Single-Flight Debounce（同 path+mode 600ms 内只放行第一次）
    play_context(...)    → 同
    # UI 禁止直接 os.startfile/subprocess；统一经控制器
```
- 按钮点击后短暂 disabled（DEBOUNCE_MS+150ms 恢复）；不杀用户其他播放器进程
- 实测：单击=1、连点=1、800ms 后再点=2、load100 后单击=1 ✓

## PART C — 主程序接入

**5. TreeCut 主 UI**：`src/treecut/desktop.py` → `TreeCutDesktop(tk.Tk)`（单页向导式，无 Page Router/Sidebar）
**6. Review Center 架构**：`src/treecut/services/review_center.py`
- `ReviewCenterWindow(tk.Toplevel)`：任务列表（注册表 `TASKS` 可扩展，非硬编码）
- `ReviewTaskWindow(tk.Toplevel)`：审核页（复用 `_V21Form`/`validate_v21`/`PlaybackController`；未完成=审核模式，已完成=只读结果 Treeview）
- Main 顶部新增【人工审核中心】按钮（`TreeCutDesktop._open_review_center`）
**7. Review Detail 用 Toplevel 而非 Frame 的原因**：主程序是单页向导（无页面容器），C2 允许"现有架构不适合时用 Toplevel(main_root) 且由 Main 管理"——采用此方案，避免大改主程序
**8. 是否存在第二个 Tk root**：**否**——Center/Task 均为 `Toplevel(main)`，由 Main 持有唯一引用；CLI/debug 独立启动保留
**9. Main→Review→Back 生命周期**：循环 20 次实测——任务窗口单实例（重复打开 focus 不新建）、center/task 关闭后主窗口存活、X 关闭只关审核窗口不杀主程序

## PART D — Responsive

**10. Breakpoint**：
- 工具栏固定两行：第一行 返回/序号/进度；第二行 置信度*/状态*/保存/提示（**必选永远可见**）
- 快捷标签响应式 Grid：宽≥620 四列 / ≥460 三列 / 窄 两列（`_relayout_quick`，重排既有 widget 不重建）
- Paned：left weight 4 / right weight 6 + **right minsize 520**
**11. 980×640 实际结果**：1600×900 / 1280×820 / 1100×700 / 980×640 四尺寸 update 无异常、widget count 稳定、无横向滚动、左/右各一份

## PART E — 验收

- 生命周期 20 次循环：Toplevel 数不增长、单实例、主程序存活 ✓
- Playback 单击/双击/load100 ✓

## 12-16. 汇总

| # | 项 | 值 |
|---|---|---|
| 12 | 94 条健康状态 | 34/34 + 60/60 落库；V3 resolved 33、Targeted eligible 60 |
| 13 | 最新 Calibration unique | **333**（`CALIBRATION_CORPUS_V2_MANIFEST.json`） |
| 14 | 最新 Coverage | V3：GOOD 23 / MEDIUM 2 / LOW 16（`COVERAGE_MATRIX_V3.json`） |
| 15 | pytest | **121 passed**（新增：widget leak load100、mandatory trace 100、playback 3 项、生命周期 20 次、单实例、responsive 4 尺寸、任务统计） |
| 16 | git commit | `f5aa944`（main） |

## 交付物

- `PHASE3_HUMAN_DATA_FINALIZATION_REPORT.md`（桌面）
- `CALIBRATION_CORPUS_V2_MANIFEST.json`、`COVERAGE_MATRIX_V3.json`
- `src/treecut/services/review_center.py`（Review Center/Task）
- `src/treecut/desktop.py` 增加【人工审核中心】入口
- `src/treecut/services/phase3_review_ui.py`：PlaybackController + 快捷标签响应式
- `tests/test_review_productization.py`

> **停止条件已达成**：数据结算 + 播放稳定 + 主 UI 接入 + Responsive + 回归全过。等待架构监工最终验收；未进入 Stage 2/FRESH_HOLDOUT/Phase 4。
