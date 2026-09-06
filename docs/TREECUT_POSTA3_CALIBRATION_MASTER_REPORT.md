# POST-A3 Calibration Master Report（STOP POINT 达成）

- 日期：2026-09-06 · 状态：**候选发现+查重+中文评审页+CAM/GEOM infra 完成 → STOP**（未融合、未触碰 A3）
- A3 正式状态（不可变）：A3_EXPERIMENT_PROTOCOL = PASS；A3_CORE_GENERALIZATION = NOT_ESTABLISHED；
  HISTORICAL_BLIND_V1（prediction sha `78dc777c…`）

## 1. Calibration 候选（TREECUT_POSTA3_CALIBRATION_MANIFEST_V1.json → REVIEW 26）
- 池排除：A3_CANDIDATES.excluded_known_ids(240) ∪ A3 17 候选媒体 ∪ A3 家族文件夹（第二段）。
- 评审清单（26，均有 5 帧缩略）：EXTEND 7 · RETRACT 7（ASR"收回"路径 src 校正后全部存在）·
  INTERFERENCE_SOCKET 4 · INTERFERENCE_LEG 4 · STATIC 4。
- **A3 污染检查：NONE**（26 均 ∉ Known/A3；家族 ≠ A3 家族文件夹）。
- 缺失文件修复：DB available 行按 source 根解析（src1 卖点 / src2 效果 / src4 未处理【工厂】）。

## 2. 建议入选 calibration 12（待人工 ACTION GT 确认）
- EXTEND（拟选 4）：2163 · 2543 · 2552 · 2553
- RETRACT（拟选 2）：3571 · 12095（另备 11592/9697/25894/26023/27433）
- NO_ACTION 静态（拟选 3）：1019 · 1025 · 103
- 干扰运动（拟选 3）：2208(LEG) · 1600(SOCKET) · 1639(SOCKET)
- 若评审后某 bucket 不足 → 如实标记（RETRACT_DATA_INSUFFICIENT 允许）。

## 3. CAM01（见 CAM01_REPORT）
- A3：24 对中 20 不可用（稀疏关键帧直接 LK）。
- Preliminary rates：SPARSE 0.0 / FULL_FRAME 0.0 / BRIDGE_500 0.20 / 250 0.167 / 125 0.333
  → bridge>direct 有初步支持（3571 例），但远未达 80% 门 → **CAM01_NEEDS_REDESIGN**。
- 下步：人工 ROI 后带排除重跑 + 实现 compose 漂移。

## 4. GEOM01（见 GEOM01_REPORT）
- 合成证明：透视缩放下 OLD 面积法误判 EXTEND/RETRACT；RELATIVE_ANCHOR_V1 正确 STATIC（6/6 tests）。
- 状态：GEOM01_INFRA_READY_NEEDS_REAL_DATA（真实 gate 待人工 ROI）。

## 5. 人工评审页（下一人工门控）
- URL：**http://127.0.0.1:8933/postA3/review**（26 候选；EXTEND/RETRACT/NO_ACTION/UNCLEAR + 备注；
  保存到 TREECUT_POSTA3_HUMAN_REVIEW_V1.json）
- 第二轮人工门控：入选案例 ROI（按 TREECUT_EXTEND_ROI_SEMANTIC_CONTRACT_V1.md）

## 6. 纪律核对
- 未读 A3 GT/key 作开发输入；未对 H001–H006 写分支；未改 ca34678；未融合 Validator；未碰 G2/G3/Pilot/Stage9/Voice/BGM。
- 本轮 commit 见 git；全部输出带路径/测试证据。

## 产物
reports/storage/TREECUT_POSTA3_CALIBRATION_MANIFEST_V1.json · _REVIEW_CANDIDATES_V1.json ·
TREECUT_POSTA3_CAMERA_CALIBRATION_V1.json · TREECUT_POSTA3_GEOMETRY_CALIBRATION_V1.json
docs/TREECUT_EXTEND_ROI_SEMANTIC_CONTRACT_V1.md · TREECUT_POSTA3_CAM01_REPORT.md · TREECUT_POSTA3_GEOM01_REPORT.md · 本文件
scripts/posta3_calibration_discover.py · posta3_thumbs*.py · posta3_camera_bridge_lab.py · posta3_geometry_lab.py
tests/test_posta3_geometry_lab.py · tools/mmv_a1_annotate/posta3_review.html(+server 端点)
