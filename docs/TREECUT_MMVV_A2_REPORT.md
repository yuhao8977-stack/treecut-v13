# TreeCut MMVV A2 — 人工 ROI 动作验证实验报告（Machine vs Human GT）

> 阶段：MMVV A2（架构师批准 2026-09-04；基线 main@3bf8f9d）
> 性质：**验证实验**，不是调参/修算法任务。
> 输入（固定）：200 个 L3_HUMAN_ROI / 32 帧 / 7 evaluation slices。
> 方法（唯一允许链）：L3_HUMAN_ROI → canonical `compensate_pair` → 逐对象掩码运动（人工框排除 手/人/插座 区域）→ `TemporalStateValidator` → Direction。
> 约束遵守：未用 Qwen/heuristic/自动检测；未调阈值；未改 Human GT 与 A1 ROI；未开 Enforcement；机器结果与人工预期分开记录；**发现问题未自动修复**。

## 1. 结果总览
| slice | 机器结果 | 人工预期 | 一致? | 判读 |
| --- | --- | --- | --- | --- |
| 52_DRAWER_OPEN | **UNSURE** | PASS DRAWER_OPEN | ✗ | 抽屉运动信号强(1.058)，方向未证 |
| 109_ACTION_POSITIVE | **UNSURE** | PASS DRAWER_OPEN | ✗ | 抽屉运动强(1.163)+几何位移大(center_x 181→702)，方向未证 |
| 109_OPEN_STATE_NEGATIVE | **UNSURE** | FAIL DRAWER_OPEN | ✗ | 抽屉残余运动0.127 触"动了但方向未证"，未判"开着≠打开" |
| 89_EXTEND | **UNSURE** | FAIL EXTEND | ✗ | 桌板"运动"0.195(噪声级?) 方向未证；人运动0.476 |
| 51_EXTEND | **UNSURE** | FAIL EXTEND | ✗ | 桌板"运动"0.605(过高，见§4)；方向未证 |
| 1985_EXTEND | **UNSURE** | FAIL EXTEND | ✗ | 桌板0.595/插座0.919；相机残差25.4(补偿失败) |
| 1986_EXTEND | **UNSURE** | FAIL EXTEND | ✗ | 桌板0.586；相机残差25.4(补偿失败) |

- **一致数：0/7**；**False PASS：0**（安全方向正确，无一例假通过）；**False FAIL：0**；**UNSURE：7**。
- 即：**即使给了 100% 正确的人工 ROI，当前机器也无法产出任何动作判定（全部停在方向未证）**——问题**不只是自动找 ROI**，后半链（方向/状态）在本实验设置下不可判定，且相机残差使静态目标出现虚高运动。

## 2. 每 slice 原始证据要点（完整见 TREECUT_MMVV_A2_RESULTS_V1.json）
- 52：DRAWER 运动 1.058（显著>桌板0.376/人0.472）；目标几何 center_x 7.75→198 / 8.0→195 / 10.0→129.5（透视下外拉表现为框缩小+左移，非纯横向）；无方向证据 → UNSURE。
- 109 正例：DRAWER 1.163；center_x 0.0s=181.5 → 1.45s=702.5（位移极大）→ 机器"看到动了"，但 Direction 门无输入 → UNSURE。
- 109 负例：DRAWER 0.127（>判定"动"阈值? 仍给 TARGET_OBJECT_MOTION_BUT_DIRECTION_UNPROVEN）→ 未产出"OPEN_STATE 非 OPEN_ACTION"的 FAIL；**另发现：2.9s→4.35s 抽屉中心 707→112 跳变 = 每帧多抽屉框、轨迹取了第一个框 → 几何轨迹缺对象身份匹配（runner 局限，如实记录）**。
- 89：桌板(伸缩桌板)0.195、人0.476、手0.0（排除掩码生效，手被剔除）→ 人>桌板 分离方向对，但桌板自身 0.195 属噪声/相机残差级 → 无法给出 NO_TABLETOP_ACTION 的 FAIL。
- 51：桌板 0.605、手 0.716、人 0.53 —— 静态讲解案例桌板"运动"却达 0.6 → **采样帧间隔过大(0→2.5→5→7.5→10s)+相机/透视/光照残差**被算进框内（排除掩码只能剔除已标手/人，无法剔除未覆盖的运动像素）。
- 1985/1986：相机 feature_residual **25.35、reliable=False**（补偿基本失败，跨 0.625s 步进本应更稳，仍失败 → 这两条素材的相机运动/透视畸变超出 affine 能力）→ 所有框内运动虚高。

## 3. 问题层归属（规则式诊断，供定位；非自动修复）
| 层 | 现象 | 依据 |
| --- | --- | --- |
| Camera | 1985/1986 残差 25.4、51/89 残差 0.5–1.9 下的虚高运动 | pair_evidence.feature_residual |
| Target Motion | 正例抽屉运动信号强(1.06/1.16)但未转化为判定；静态桌板 0.2–0.6 虚高 | roi_motion |
| Geometry | 多抽屉帧轨迹跳变(109 neg 707→112)；透视下"外拉"缺有效位移特征(52 center_x 变化方向与直觉相反) | target_geometry_trajectory |
| Temporal State | 无状态通道（机器-only 未注入 states）→ 状态转移不可用 | mandatory/state_transition 空 |
| Direction | 全部 7/7 停在 TARGET_OBJECT_MOTION_BUT_DIRECTION_UNPROVEN | reason_codes |
| Fusion | 无假 PASS（安全）；但无法融合出最终判定 | verdict |

## 4. 结论（诚实）
1. **后半链"当前形态"不能判定动作**：7/7 UNSURE。即使 ROI 100% 正确，Direction/State 门依赖的输入（状态序列/方向探针/可靠的边缘位移通道）在纯机器设置下缺失 → 架构需要"运动→状态/方向"的显式推导，或喂方向探针/状态（非本实验允许）。
2. **相机补偿在稀疏采样与强运动素材上不足**（1985/86 残差 25.4）→ 静态/动态都虚高，当前 motion 通道无法支撑 NO_TABLETOP_ACTION 类 FAIL。
3. 排除掩码（人工框）方向有效：89 手运动 0.0（被剔除）、人 0.476 > 桌板 → 分离机制工作；但未覆盖运动像素仍会漏。
4. 数据本身给出了有用信号：正例抽屉运动 ≈1.06–1.16 vs 负例 0.127、桌板静态噪声 0.05–0.6 → 相对可分离，但绝对阈值/方向判定不成立。
5. **这不是"7/7 或 6/7"场景，也不是"全错"场景——是"全都无法判定(UNSURE)"场景**：机器不会撒谎 PASS（0 假 PASS 达成红线），但能力尚未成型。

## 5. 未做/下一步（等架构师裁决，不自动执行）
- 未做任何修复/调参/改判定。可选后续（需批准）：A2.1 方向证据实验（几何位移→direction 通道，含多框身份匹配）；A2.2 相机（对 1985/86 用稠密光流/homography 或缩小帧间隔）；A2.3 更密采样或辅助帧；均需架构师先看本报告裁决。
