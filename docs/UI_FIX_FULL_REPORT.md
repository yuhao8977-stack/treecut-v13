# TreeCut Phase 3 — 人工审核 UI 完整修复报告

- **日期**：2026-08-28
- **提交**：`ded14a7`（外科修复）→ `3f6a4e3`（报告）→ main
- **备份**：`src/treecut/services/phase3_review_ui.py.pre_ui_fix.bak`
  （SHA256：`ED2FE4684457D9A93953A0FF20453CCB0A3066E2F4504E09F50B2C17DBDF690F`）
- **性质**：最小范围外科修复；未修改数据库 / 已存人工标注 / Schema V2.1 / 模型 / 采样队列 / AnnotationService / ReviewQueue

---

## 一、背景：问题如何被发现

人工审核过程中出现三大异常，用户反复反馈后停止审核：

1. **界面无限叠加**：视频预览区、审核表单（场景/产品/材质/组件/功能…）纵向重复出现，滚动条无限变长；
2. **"人工置信度未选择"误报**：用户已选择仍报错（多次）；
3. **窗口最小尺寸过大**：最小化仍接近全屏，继续审核窗口越来越重、接近卡死。

### 只读审计（`docs/REVIEW_UI_ARCHITECTURE_AUDIT.md`）定位根因

对 `phase3_review_ui.py` 做代码静态审查 + **运行时实测**（widget 计数、切换 50 次、构造器调用链跟踪），确认：

> **`_on_mandatory()` 方法体错误地包含了 `_build()` 后半段的整套 body 构建代码**（line 420-460）。
> 置信度/审核状态任何变化（含每题 `reset()` 清空触发的 trace）→ 执行 `_on_mandatory` → **重建整套 PanedWindow/左栏/右栏/表单**；
> 表单构造内部又有 var 操作 → 递归触发 → 构建期间即叠加多套。

实测铁证：

| 阶段 | widget 总数 | TPanedwindow | Canvas |
|---|---|---|---|
| 窗口初始 | 257（已叠 3 套） | 3 | 3 |
| 切换 1 条 | 419（+162） | 4 | 5 |
| 切换 10 条 | 2039 | 13 | 25 |
| 切换 50 条 | **10139** | 53 | 125 |

每切一题 +162 个 widget（整套 UI 复制一份）。"置信度未选择"误报亦源于此：重建中 `self.form` 被反复替换，共享状态错乱，用户选择被覆盖。

---

## 二、修复内容（外科手术式，8 项）

| # | 修复项 | 实现 |
|---|---|---|
| 1 | **`_on_mandatory` 方法边界** | 精简为纯防呆：读 `conf_var/status_var` → 设 `save_btn.state` + 更新 `mandatory_hint`；**方法内禁止创建任何 Widget** |
| 2 | **body 构建归位** | `PanedWindow/左栏(信息/播放按钮/提示)/右栏/_V21Form` 全部移回 `_build`（拆 `_build_toolbar` + `_build_body`），**只构建一次** |
| 3 | **Build Once Guard** | `self._ui_built` 标记；重复构建 `raise RuntimeError("Review UI must only be built once")` |
| 4 | **Widget Leak Guard** | 递归计数；首次构建后冻结基线；每次 `_load` 后 `after_idle` 核对；泄漏写 `UI_WIDGET_LEAK` ERROR 日志 |
| 5 | **MouseWheel 修复** | 右侧表单 `Enter` 绑定 / `Leave` 解绑（含 Linux `Button-4/5`）；`<Destroy>` 清理；**鼠标离开右侧不再滚动**；不在每次 load 重复 bind |
| 6 | **Scroll 唯一化** | 页面级 Canvas=1、页面滚动条=1（Listbox 内部滚动条不计）；不嵌套 Canvas；无整页横向滚动条 |
| 7 | **Geometry** | 默认约 **1280×820**、最小约 **980×640**（按屏幕自适应）、`resizable(True,True)`、不强制最大化 |
| 8 | **Layout 核对** | `winfo_parent` 确认 toolbar/body 同挂 root → **root 统一 grid**（toolbar row0 / body row1 + `rowconfigure(1,weight=1)`）；`_V21Form` 内部 grid + sequence editor pack 属不同父容器，合法保留（未盲改） |

---

## 三、验收实测（修复前 vs 修复后）

| 指标 | 修复前 | 修复后 | 判定 |
|---|---|---|---|
| init widget | 257 | **95** | — |
| 切换 1 条 | 419 | **95** | ✅ 不增长 |
| 切换 10 条 | 2039 | **95** | ✅ 不增长 |
| 切换 50 条 | 10139 | **95** | ✅ 不增长 |
| 切换 100 条 | — | **95** | ✅ 完全不增长 |
| TPanedwindow（body） | 3 | **1** | ✅ 唯一 |
| 页面级 Canvas | 125 | **1** | ✅ 唯一 |
| `_V21Form` 实例 | 多份 | **1** | ✅ 唯一 |
| 窗口尺寸 | 1560×940 / min 1200×760 | ≈1280×820 / min ≈980×640 | ✅ 可缩放 |

---

## 四、已保存数据健康检查（只读）

| 项 | 结果 |
|---|---|
| saved_records | **46**（TARGETED_REVIEW_BATCH_V1） |
| segment_id 唯一 | ✅ |
| dictionary_version = ANNOTATION_DICTIONARY_V2_1 | ✅ 全部 |
| human_confidence 非空 | ✅ 全部 |
| review_status 非空 | ✅ 全部 |
| 枚举值合法（scene_family/product_family） | ✅ 0 非法 |
| **valid / invalid** | **46 / 0**（无需重审，无自动修复） |

（此前 34 条 THIRD_ADJUDICATION_V1 已全部落库 `human_annotation_v3`，不受本次 UI 修复影响。）

---

## 五、测试与回归

- `tests/test_phase3_review_ui.py`：**7 passed**（含 validate_v21、manifest 存在性、审核表存在性）
- 业务回调保留：播放本段（±3s ffmpeg 提取）/ 播放完整视频 / 上一题 / 跳过 / 保存并下一题
- 保存日志 `logs/review_save_log.tsv` 全程留痕

---

## 六、当前状态

- 修复后窗口已打开（PID 23900），**真实进度显示 46/60**，停留在下一题未审核记录，**未自动保存、未自动继续**
- 剩余约 14 条待审（含 rev3 类别配额清单：材质/功能/组件/场景长尾、纯视觉、低证据、随机）

---

## 七、下一步（等待视觉验收）

1. **请截图三关验收**：
   - ① 默认状态
   - ② 缩小至约 980×640
   - ③ 右侧滚到底（不应出现第二套表单）
2. 三关通过 → 继续剩余约 14 条审核（UI 已不会泄漏、不会叠加）
3. 94 条（34 裁决 + 60 新样本）全部完成后 → **Phase 3 人工数据结算**（届时再谈 Stage 2：GPU + 真实视觉模型 + FRESH_HOLDOUT_V1）

---

## 八、约束确认（本报告全程遵守）

- 未修改：审核数据库、已保存人工标注、Schema V2.1、AI 模型/规则、Phase3 Pipeline、采样队列、AnnotationService、ReviewQueue 业务逻辑
- 未重新生成 TARGETED_REVIEW_BATCH、未重置审核进度
- 行业知识库 Word 仍未使用（保留至 Phase 4）
