# TreeCut Review UI — Surgical Repair V1 Report

- **日期**：2026-08-28 ｜ 提交 `ded14a7`（main）｜ 备份 `src/treecut/services/phase3_review_ui.py.pre_ui_fix.bak`（SHA256 `ED2FE468...`）
- **性质**：最小范围外科修复（未修改数据库/已存标注/Schema V2.1/模型/采样队列/AnnotationService）

## 1. 修复内容

| # | 项 | 修复 |
|---|---|---|
| 1 | `_on_mandatory` 方法边界 | 精简为纯防呆（读 conf/status → 设按钮 state + 更新提示），**方法内零 Widget 创建** |
| 2 | body 构建代码归位 | `PanedWindow/左栏/右栏/_V21Form` 全部移回 `_build`（拆 `_build_toolbar` + `_build_body`），只构建一次 |
| 3 | Build Once Guard | `_ui_built` 标记，重复构建 `raise RuntimeError("Review UI must only be built once")` |
| 4 | Widget Leak Guard | 递归计数，首次构建后冻结基线；每次 `_load` 后 `after_idle` 核对，泄漏写 `UI_WIDGET_LEAK` ERROR 日志 |
| 5 | MouseWheel | 右侧表单 `Enter` 绑定 / `Leave` 解绑（含 Linux Button-4/5）；`<Destroy>` 清理；**鼠标离开右侧不再滚动**；不在每次 load 重复 bind |
| 6 | Geometry | 默认约 1280×820、最小约 980×640（按屏幕自适应）、`resizable(True,True)`、不强制最大化 |
| 7 | Layout 核对 | `winfo_parent` 确认 toolbar/body 同挂 root → **root 统一 grid**（toolbar row0 / body row1 + rowconfigure(1,weight=1)）；`_V21Form` 内部 grid + sequence editor pack 属不同父容器，合法保留 |

## 2. 验收实测（修复前 vs 修复后）

| 指标 | 修复前 | 修复后 |
|---|---|---|
| init widget | 257（已叠 3 套） | **95** |
| 切换 1 条 | 419（+162） | **95** |
| 切换 10 条 | 2039 | **95** |
| 切换 50 条 | 10139 | **95** |
| 切换 100 条 | — | **95（完全不增长）** |
| TPanedwindow（body） | 3 | **1** |
| 页面级 Canvas | 125 | **1** |
| `_V21Form` 实例 | 多份 | **1** |

## 3. 其余核对

- **MouseWheel 方案**：右侧 `VerticalScrollFrame` 模式（Enter/Leave 绑定解绑 + Destroy 清理），页面级绑定全局唯一
- **Canvas 宽度**：`canvas.itemconfigure(inner_id, width=canvas_width)`，内容不横向撑开
- **滚动唯一性**：Canvas=1、页面滚动条=1（Listbox 内部滚动条不计页面级）
- **已审核记录健康检查**：`saved=46, valid=46, invalid=0`（segment_id 唯一、dictionary_version=ANNOTATION_DICTIONARY_V2_1、human_confidence/review_status 非空、枚举值合法）
- **业务回调**：播放本段/播放完整/上一题/跳过/保存并下一题 均保留原实现（未改动）
- **pytest**：`tests/test_phase3_review_ui.py` 7 passed
- **进度保留**：UI 打开后显示真实 **46/60**，停留在下一题未审核记录，未自动保存

## 4. 待视觉验收

请截图：①默认状态 ②缩小至约 980×640 ③右侧滚到底。
三关通过后再继续剩余约 14 条审核。
