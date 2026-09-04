# MMVV A1 — Human Ground-Truth ROI 标注工具（最小本地工具，非 Workbench）

只服务 A1（6 案例 89/52/109/51/1985/1986，30 帧，冻结窗口）。只存 **L3_HUMAN_ROI**；不调用/不显示 Qwen 或 heuristic ROI。

## 启动
```bat
python tools\mmv_a1_annotate\server.py --port 8933
```
浏览器打开 `http://127.0.0.1:8933`

## 标注步骤（人工）
1. 左栏选案例（media id / requested / 窗口）；顶部选帧 F0–F4（带框数角标）。
2. 点「开始画框」→ 在画面上拖出矩形；框默认用下拉框所选标签（10 类：TABLETOP / EXTENSION_TABLETOP / DRAWER / UPPER_THIN_DRAWER / TRACK_SOCKET / SOCKET_MODULE / PERSON / HAND / ISLAND_BODY / OTHER_MOVING_PART）。
3. 点已有框=选中 → 可拖动；「删除选中框」「清空本帧」。
4. 每帧标完点「保存本帧」（后端校验坐标边界，写 `TREECUT_MMVV_HUMAN_GT_ROI_A1.json`）。

建议每帧框 1–3 个关键对象（目标对象 + PERSON + 必要时 ISLAND_BODY/SOCKET）。

## 数据流
- 帧：`E:\...\runtime\production_smoke\B007\mmv_a1_frames\m<mid>_<i>.jpg`（810 宽，不入 git）
- 清单：`reports/storage/TREECUT_MMVV_A1_FRAME_MANIFEST.json`（含 sha256/时间戳/人工事实）
- ROI：`reports/storage/TREECUT_MMVV_HUMAN_GT_ROI_A1.json`（annotation_source=L3_HUMAN_ROI）
- 状态：`reports/storage/TREECUT_MMVV_A1_ANNOTATION_STATE.json`（/api/state 自动刷新）

## 标注后
```bat
python tools\mmv_a1_annotate\build_geometry.py   # 几何轨迹证据（evidence-only）
python tools\mmv_a1_annotate\gen_review.py       # 人工核验 HTML
```
人工确认框后再批准 A2（不得自动进入 A2）。
