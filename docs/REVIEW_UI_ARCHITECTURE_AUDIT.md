# TreeCut Review UI Architecture Audit — 人工审核窗口架构审计

- **日期**：2026-08-28 15:30 ｜ 仓库 `104d4bb` ｜ 性质：**只读审计，未修改任何 UI/数据库/审核数据/模型**
- **审计方法**：代码静态审查 + **运行时实测**（widget 计数、逐次切换、构造器调用链跟踪）

## 0. 结论先行（一句话）

> **审核窗口存在系统性 UI 重建缺陷：`_on_mandatory` 方法体错误地包含了 `_build` 的整套 body 重建代码，
> 导致每次"置信度/审核状态"变化（包括每切一题 `reset()` 清空触发的 trace）都会重建整套界面，
> widget 数量随切换次数线性爆炸——这是截图"视频区/表单无限叠加、滚动条无限长"的确切代码根因。**

---

## 1. UI 入口文件

| 项 | 值 |
|---|---|
| 入口文件 | `src/treecut/services/phase3_review_ui.py`（695 行） |
| 主类 | `_ReviewBase(tk.Tk)`（基类）→ `AdjudicationV1App` / `TargetedReviewV1App` |
| 表单类 | `_V21Form(tk.Frame)`（右侧字段表单） |

**调用链**：
- 窗口首次打开：`__init__` → `_load_items()` → `_done_set()` → `_build()`（工具栏 + body + 左/右栏 + `_V21Form`）→ `_load(0)`（更新数据）
- 切换下一条（保存/跳过/上一题）：`_save()` / `_load(idx)` → 仅 `config/delete/insert/reset`（**设计意图是只更新值**）
- 刷新：无独立刷新函数

## 2. Widget Tree（运行时实测）

```
root (Tk)
 ├─ Frame (top 工具栏: 进度/置信度/状态/保存/提示/词典)
 ├─ TPanedwindow  ← 第 1 套 body
 ├─ TPanedwindow  ← 第 2 套 body（异常叠加！）
 ├─ TPanedwindow  ← 第 3 套 body（异常叠加！）
 └─ ...（随切换持续增加）
```

**实测证据**（`_load` 循环 50 次）：

| 阶段 | widget 总数 | TPanedwindow | Canvas | Listbox |
|---|---|---|---|---|
| 初始（init 后） | **257** | **3** | 3 | 18 |
| 切换 1 条 | **419** | 4 | 5 | 30 |
| 切换 10 条 | **2039** | 13 | 25 | 138 |
| 切换 50 条 | **10139** | 53 | 125 | 618 |

> 每切换一次：**+162 个 widget（+1 套完整 UI）**。初始就有 3 套——`_on_mandatory` 在构建期间被 trace 递归触发。

## 3. Widget 创建位置（代码证据）

**关键问题代码**：`phase3_review_ui.py` line 420-460

```python
def _on_mandatory(self, *_a):            # line 420 — 本应是"防呆按钮联动"短方法
    ok = bool(self.conf_var.get() ...)   # line 422
    self.save_btn.config(...)            # line 423
    if ok:
        self.mandatory_hint.config(...)  # line 425
    else:
        self.mandatory_hint.config(...)  # line 427
                                         # line 428 ← 方法体未结束！
    paned = ttk.PanedWindow(self, ...)   # line 429 — 以下全部是 _build 的代码！
    ...
    self.info = tk.Text(...)             # line 438
    self.form = _V21Form(...)            # line 458 — 每次 _on_mandatory 都新建整套表单！
```

**结论（确定）**：`_on_mandatory` 缺少缩进回退，`_build` 的后半段（body/左栏/右栏/表单创建）被并入 `_on_mandatory`。
后果：`conf_var`/`status_var` 的任何 `set()`（含 `reset()` 每题清空）触发 trace → `_on_mandatory` → **重建整套 body + 表单**；而 `_V21Form.__init__` 内又有 var 操作 → 递归触发 → 构建期间就叠加多套。

**`load_record/next/previous/refresh` 中创建 widget**：`_load` 本身**没有**直接创建（仅 config/delete/insert/reset），但 `reset()` 里 `conf_var.set("")` 经 trace 间接触发整套重建。

## 4. 重复 UI 风险（实测）

| 指标 | 值 | 判定 |
|---|---|---|
| baseline widget count | 257 | — |
| 切换 1 条后 | 419（+162） | **泄漏** |
| 切换 10 条后 | 2039（+1782） | **泄漏** |
| 切换 50 条后 | 10139（+9882） | **泄漏** |
| 增长 widget 类型 | TPanedwindow/TFrame/Frame/Text/Label/TButton/Canvas/TCombobox/Listbox/TScrollbar/Entry | 整套 UI 复制 |
| 增长父链 | `TPanedwindow <- Tk` | 新 body 直接挂 root |

**确定性：高**（运行时实测 + 代码行号双重证据）。

## 5. 视频播放区

- 代码中**设计上只有 1 个**：`_build` 左栏 `card`/`btn`（`_play_context`/`_play_full` 两个按钮）
- **实测**：由于 body 被多次重建，左栏（含"播放本段/播放完整视频"按钮）被复制多份 → 截图"多个播放按钮"由此而来
- `self.info`/`self.note` 引用被最后一次重建覆盖；旧副本成为孤儿 widget（仍挂在 root 下）

## 6. Scroll 架构

- 唯一滚动容器：`_V21Form._build` 内 `Canvas + Scrollbar + inner Frame`（设计 1 个）
- **实测**：Canvas 3 → 125（随 body 重建而复制）
- 滚轮：`canvas.bind_all("<MouseWheel>")` 在 `_V21Form._build` 中绑定（**无解绑**）；重建后多个 Canvas 各自 bind_all → 滚轮行为混乱、多个滚动区域抢事件
- `scrollregion`：每次重建的 Canvas 各自计算（实测 `0 0 949 1192` 重复出现）→ 不随切换扩大（因为每次是新 Canvas），但**多套 Canvas 叠加**造成"可以无限往下滚"的观感（实际是多层内容纵向堆叠）
- **无横向滚动条**（未发现 xscrollcommand）——用户截图"横向撑开"来自多套 body 并排堆积的视觉，不是独立横向滚动条

## 7. Geometry / 窗口尺寸

- `_ReviewBase.__init__`：`self.geometry("1560x940")`、`self.minsize(1200, 760)`
- **问题**：`1560x940` 偏大、`minsize(1200,760)` 过高；且**大量控件写死 width/height**（Text height=8、Listbox height=5、wraplength 等）累积出巨大 requested size
- **更严重**：body 被多套复制后，`pack` 的几何管理器把多套 PanedWindow 全部纳入布局 → 窗口被撑大、最小化仍接近全屏
- `resizable`：未设置（默认 True）✓

## 8. Layout Manager

- 工具栏：`pack`；body：`grid`（`rowconfigure/columnconfigure`）→ **同一父容器混用 pack/grid**（root 下 toolbar 用 pack 直接挂 root，body 用 grid 挂 root）→ Tk 内部冲突，加剧布局错乱
- `_V21Form`：`grid` 为主 + 内部 `pack`（seq 编辑器）→ 混合使用
- 多套 body 叠加后布局完全失控

## 9. 当前审核字段（Schema V2.1）

| 字段 | 控件 | 单选/多选 | 保存格式 |
|---|---|---|---|
| scene_family / scene_subtype | TCombobox（联动） | 单选 | 英文枚举 |
| product_family / product_variant | TCombobox（联动） | 单选 | 英文枚举 |
| material / component / function / shot_role | Listbox | **点击多选** | JSON array |
| action_group | TCombobox | 单选 | 英文枚举 |
| action_sequence | Listbox 有序编辑器 | 有序 | JSON array |
| shot_scale | TCombobox | 单选 | 英文枚举 |
| people_presence / product_visibility | TCombobox | 单选 | 英文枚举 |
| quality | Entry | 数字 | REAL |
| human_confidence / review_status | TCombobox（顶部固定） | 单选必选 | 英文枚举 |
| comment | Entry + 快捷标签 | 文本 | TEXT |

## 10. 数据流

```
TARGETED/ADJUDICATION manifest (json)
 → __init__ 载入 → queue（未审段）
 → _load(idx) → _seg_info(DB 只读) → 更新 Text/重置表单
 → 用户填写 → _save() → form.collect()（中文→英文映射）→ validate_v21
 → _persist() → INSERT OR REPLACE → targeted_human_review_v1 / human_annotation_v3
 → 保存日志 → logs/review_save_log.tsv
```

**切换下一条**：设计为"只更新值"（`_load` → `reset`），**实际因 bug 变成"重建 UI"**。

## 11. 相关文件

| 文件 | 职责 | 行数 | 核心 |
|---|---|---|---|
| `src/treecut/services/phase3_review_ui.py` | 审核 UI（本审计主体） | 695 | `_ReviewBase`/`_V21Form`/`AdjudicationV1App`/`TargetedReviewV1App`/`validate_v21` |
| `src/treecut/services/schema_v2.py` | V2.1 枚举/中文标签/映射 | ~330 | `LABELS`/`cn`/`en`/`MULTI_OPTIONS` |
| `migrations/0008_phase3_human_review.sql` | v3/新审核表 | 66 | `human_annotation_v3`/`targeted_human_review_v1` |
| `tests/test_phase3_review_ui.py` | UI 校验测试 | ~100 | `validate_v21` 等 |
| `scripts/phase3_rebuild_remaining.py` | 采样清单重建 | ~200 | 类别配额采样 |

## 12. 问题清单

| # | 问题 | 代码证据 | 严重度 | 确定 | 建议修复方向 |
|---|---|---|---|---|---|
| 1 | **每切一题重建整套 UI（widget 泄漏 +162/次）** | line 420-460：`_on_mandatory` 方法体包含 `_build` 的 body 重建代码；trace 递归触发 | **致命** | ✅ 确定（实测+行号） | 恢复方法边界：`_on_mandatory` 在 line 428 结束；`paned=...` 起所有代码回归 `_build`；构建只执行一次 |
| 2 | 视频区/播放按钮重复 | 同 #1（body 复制） | 严重 | ✅ | 同 #1 |
| 3 | 表单纵向叠加、滚动条超长 | 同 #1（多套 Canvas 叠加） | 严重 | ✅ | 同 #1 |
| 4 | 窗口最小尺寸接近全屏 | `geometry("1560x940")`+`minsize(1200,760)`+多套 body | 中等 | ✅ | 改约 1280×820 / min 980×640；删除冗余固定尺寸 |
| 5 | 滚轮行为异常 | `bind_all("<MouseWheel>")` 无解绑 + 多 Canvas 抢事件 | 中等 | ✅ | 改为 Enter/Leave 绑定解绑（参考 `VerticalScrollFrame` 模式） |
| 6 | 横向撑开观感 | 多套 body 并排堆积（非独立横向滚动条） | 中等 | ✅ | 同 #1 后消失 |
| 7 | 混用 pack/grid | root 下 toolbar pack + body grid | 低 | ✅ | 统一布局管理器 |
| 8 | 保存日志已就位 | `logs/review_save_log.tsv` | 无 | ✅ | 保留（已证明有效：定位了"未选择"误报） |

## 13. 与"人工置信度未选择"误报的关系

保存日志（`logs/review_save_log.tsv`）显示失败时 `conf='' status=''` 同时为空——原因是 #1 重建 bug 导致 `self.form` 被反复替换，顶部 `conf_var` 与表单的共享状态在重建中错乱，用户的选择可能被新重建的表单/var 覆盖。**#1 修复后此误报也随之消除**（配合顶部必选防呆）。

## 14. 审计结论

1. **根本缺陷是单点**（`_on_mandatory` 方法边界错误），不是布局/滚动/尺寸的多个独立问题——修复 #1 后 #2/#3/#5/#6 一并消失
2. 建议重构方向（**本次未执行**）：`build_ui_once()` 单次构建 + `load_record()` 仅更新值 + widget count 回归守卫（参考用户提供的 `treecut_review_ui_layout_v2.py` 的 `_build_ui_once`/`assert_widget_count_stable` 模式）
3. 按指令：**本报告只读审计，未修改任何代码/数据；报告生成后停止，等待外部 UI 验收**
