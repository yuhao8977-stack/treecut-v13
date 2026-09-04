# TreeCut MMVV A1 — Human Ground-Truth ROI Calibration（数据准备）报告

> 阶段：MMVV A1（baseline main@3be032e）；前置：SOURCE_AUDIT_CORRECTION_WAVE = FULL_PASS
> 日期：2026-09-04
> 状态：**MMVV_A1_GT_ROI_PACKAGE_READY_FOR_HUMAN_ANNOTATION**（不是 MMVV PASS）
> 原则：只 6 案例；冻结人审窗口；不加 Qwen/不加 heuristic；不调阈值；人工框选后 STOP。

## 1. 目的
消除 ROI semantic uncertainty：用 **L3_HUMAN_ROI** 回答"对象位置 100% 给对时，Camera→Motion→Temporal→Direction 后半视觉链是否成立"。本任务只做标注数据准备（A1），不评价动作（A2 才评价）。

## 2. 冻结案例与窗口（沿用 R2 人审窗口，不重搜）
| media | requested | 冻结窗口 [s,e] | 人工已知事实（独立字段 human_facts） |
| --- | --- | --- | --- |
| 89 | EXTEND | [0.0, 7.12] | 人动，桌板基本不动（PERSON_MOTION_NOT_TABLETOP_MOTION） |
| 52 | DRAWER_OPEN | [0.0, 10.0] | 抽屉真实向外打开 OUTWARD（正例校准） |
| 109 | DRAWER_OPEN | [0.0, 5.8] | 抽屉已打开但无打开动作（OPEN_STATE ≠ OPEN_ACTION） |
| 51 | EXTEND | [0.0, 10.0] | 静态产品讲解（NO_TARGET_OBJECT_MOTION） |
| 1985 | EXTEND | [1.9, 4.4] | 插座在动、桌板不动（SOCKET_ADJUST ≠ EXTEND） |
| 1986 | EXTEND | [1.9, 4.4] | 同类插座操作（SOCKET_ADJUST） |

## 3. 产出物
- `reports/storage/TREECUT_MMVV_A1_FRAME_MANIFEST.json` —— 6 案例 ×5 帧（F0–F4），ts=s+i*(e-s)/4，sha256/宽高/源路径/源时长/human_facts（帧文件在 E:\...\runtime\production_smoke\B007\mmv_a1_frames，810 宽，不入 git）
- `reports/storage/TREECUT_MMVV_HUMAN_GT_ROI_A1.json` —— annotation_source=**L3_HUMAN_ROI**（与 L2_QWEN/HEURISTIC 分离）；当前 annotations=[]（待人工）
- `reports/storage/TREECUT_MMVV_A1_ANNOTATION_STATE.json` —— 6 案例逐帧标注状态（当前 0 整例完成）
- `reports/storage/TREECUT_MMVV_A1_GEOMETRY_TRAJECTORY.json` —— 几何轨迹证据（由 build_geometry.py 从 human ROI 计算，evidence-only；当前 0 框）
- `reports/storage/TREECUT_MMVV_A1_HUMAN_GT_ROI_REVIEW.html` —— 人工核验页（§19，标注后重跑 gen_review.py）
- `tools/mmv_a1_annotate/` —— 最小本地标注台（server.py+index.html+build_geometry.py+gen_review.py+README）

## 4. 人工标注指引
启动 `python tools\mmv_a1_annotate\server.py --port 8933` → http://127.0.0.1:8933
每帧 1–3 个关键框：目标对象（TABLETOP/EXTENSION_TABLETOP 或 DRAWER/UPPER_THIN_DRAWER）、PERSON、必要时 TRACK_SOCKET/SOCKET_MODULE/ISLAND_BODY。30 帧 ≈ 人工 15–30 分钟。

## 5. 已知记录（tech-debt 落实）
- Camera 字段分离：A1 工具不引入 camera_residual 误填；CameraMotion 以 translation_px/inlier_ratio/residual/reliable 分字段（test_mmvv_a1 覆盖）。
- Pilot(LEGACY) 的 SOURCE_PRODUCTION_ELIGIBLE 不进 P0_KEYS：不再演进该文件。

## 6. 测试（tests/test_mmvv_a1.py，8/8 通过）
human_roi 与 L2 分离 / frame_hash 绑定 / per-frame 非静态 / 坐标边界 / 必需对象契约 / reload 确定性 / camera 字段分离 / A1 无 qwen。4 个 R2_KNOWN_UNMET xfail 保留未转绿。

## 7. A1 READY 判定（§18；2026-09-04 复查更新）
1985/1986 补框（伸缩桌板 5/5 + 岛台主体 5/5）后重跑 post_annotation_validate：**issues=0 / missing=0 / A1_READY=True**。
- 30/30 帧 hash 与磁盘一致；坐标全部合法；182 框 annotation_source 全部 L3_HUMAN_ROI（无 Qwen/heuristic）；6/6 案例全帧标注；Review HTML 正常（中文标签）。
- 状态：**MMVV_A1_GT_ROI_READY**（不等于 MMVV/G2/G3/Stage8 PASS）。
- 架构师审核开放项：52 的「抽屉」框仅出现在 t=10.0（2 个），F0–F3 为伸缩桌板/插座模块/人手/岛台主体——请在 Review HTML 复核 52 中"移动抽屉"区域是否被正确框住（若打开动作发生在窗口后段，A2 可能需窗口内加辅助帧）。由架构师最终确认后再批准 A2（不得自动进入 A2）。
