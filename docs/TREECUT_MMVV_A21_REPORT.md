# TreeCut MMVV A2.1 — Target Identity + Geometry Direction/State 实验报告

> 阶段：MMVV A2.1（架构师批准；基线 main@3b55370→e218c1b 后）
> 输入（冻结）：200 个 L3_HUMAN_ROI / 32 帧 / 7 slices；52/109 抽屉实例人工绑定（TREECUT_MMVV_A21_TARGET_BINDING.json）
> 方法：绑定实例 ROI → GeometryDirectionEvidence（岛台相对优先、绝对回退、分数化变化率）→ TemporalStateValidator（几何优先；与 model_action 分离）
> 约束：未调阈值（几何容差为文档化 provisional 常量）；未升级 Camera；未加帧/模型；未改 Human GT/ROI；机器结果与人工预期分开。

## 1. 结果总览（机器 vs Human GT）
| slice | 机器 | 人工 | 一致 | 几何方向 | 状态进程 | 像素运动(证据) | 判定代码 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 52_DRAWER_OPEN | **PASS** | PASS | ✅ | DRAWER_OPEN | PROGRESSION_UP | 1.064 | GEOMETRY_PROGRESSION_SUPPORTED |
| 109_ACTION_POSITIVE | **PASS** | PASS | ✅ | DRAWER_OPEN | PROGRESSION_UP | 1.570 | GEOMETRY_PROGRESSION_SUPPORTED |
| 109_OPEN_STATE_NEGATIVE | UNSURE | FAIL | ❌ | UNKNOWN | UNKNOWN | 0.124 | 方向未证（几何非单调） |
| 89_EXTEND | **FAIL** | FAIL | ✅ | STATIC | STABLE | 0.188 | NO_TARGET_GEOMETRY_CHANGE |
| 51_EXTEND | UNSURE | FAIL | ❌ | UNKNOWN | UNKNOWN | 0.550 | 方向未证（几何非单调） |
| 1985_EXTEND | UNSURE | FAIL | ⚠️允许 | STATIC | STABLE | 0.735 | CAMERA_UNRELIABLE_GEOMETRY_UNSTABLE |
| 1986_EXTEND | UNSURE | FAIL | ⚠️允许 | STATIC | STABLE | 0.752 | CAMERA_UNRELIABLE_GEOMETRY_UNSTABLE |

- **一致 3/7**（52、109前段、89）；**False PASS 0 / False FAIL 0**（没有任何假通过/假拒绝）；UNSURE 4。
- 核心 5（52 / 109前 / 109后 / 89 / 51）：**3/5 与 GT 一致**（< 架构师 §15 的 4/5 门槛）。

## 2. 关键信号与根因
1. **几何方向通道对"真动作"有效**：52 与 109 前段在人工 ROI + 绑定后，机器几何检测到单调外拉（52 面积 17,496→18,774→31,313；109 前 16,632→41,528），几何优先路径给出 **PASS**——A2 里"方向未接线→全 UNSURE"的问题已修复一大半。
2. **0 假 PASS / 0 假 FAIL**：没有任何 slice 被硬判成错的 PASS/FAIL——安全机制保持。
3. **静态负例 109后段 与 51 未达 FAIL**：目标框面积在 ±10–16% 抖动（109后：41,302→37,541→43,665；51：407,416→397,792→430,122…），几何被判"非单调 UNKNOWN"而非 STATIC → 诚实 UNSURE（不假 PASS，但也没给出 NO_OPENING/NO_GEOMETRY_CHANGE 的 FAIL）。这是**标注框抖动超出静态容差(6%)** 导致的 Geometry 层噪声问题。
4. **1985/1986**：几何其实判 STATIC（相对岛台 0.98–1.02 稳定），但按规格相机不可靠时保持 **UNSURE(CAMERA_UNRELIABLE_GEOMETRY_UNSTABLE)**（允许结果）。
5. 岛台相对参考跨帧不稳定（52 rel 0.88→0.67→0.89 vs abs 单调↑）→ builder 回退绝对序列（代码内已标注 ISLAND_REFERENCE_UNSTABLE_FALLBACK_ABSOLUTE）——这是标注参考系问题，非算法可消除。

## 3. 问题层归属（规则式诊断，未修）
| 层 | 状态 | 依据 |
| --- | --- | --- |
| 方向/状态通道 | **PARTIAL PASS** | 52/109前 PASS；109后/51 UNSURE |
| Geometry 噪声 | 主要残留 | 109后/51 面积抖动→非单调；静态容差 6% 偏紧(provisional) |
| 岛台参考 | 不稳定 | 相对序列被岛台框跨帧范围变化污染 |
| 像素运动 | 证据可用 | px 真动作 1.06–1.57 vs 静态 0.12–0.19 可分离 |
| Camera | 1985/86 阻塞（允许） | feature residual 25.4 → UNSURE |
| 安全 | **PASS** | 0 假 PASS/0 假 FAIL |

## 4. 结论（诚实）
A2.1 证明：**人工 ROI + 实例绑定 + 机器几何方向推导，能让"真抽屉打开"(52/109前) PASS、让"桌板几何静止"(89) FAIL，且零假 PASS/零假 FAIL**——方向/状态通道从 A2 的"全 UNSURE(NOT WIRED)"推进到"对干净几何变化可用"。残留：① 负例静态判 FAIL 需要几何"静止"判定更稳（标注抖动 vs 容差）；② 1985/86 仍被 Camera 阻塞。按架构师 §15：核心 5 一致 3/5（未达 4/5）→ **GEOMETRY_DIRECTION_CHANNEL = PARTIAL_PASS / PROMISING_WITH_RESIDUAL**（不是 FULL，也不是失败）。

## 5. 未做/下一步（等架构师裁决）
- 未自动修任何失败项。候选后续（需批准）：A2.1b 负例噪声处理（同实例框稳定化/时序平滑，属 Geometry 层；明确非阈值调参）；A2.2 仅 1985/1986 Camera；另补真实 EXTEND 正例（现无正例，不能宣称 EXTEND 正识别 PASS）。
- 产出：`reports/storage/TREECUT_MMVV_A21_RESULTS_V1.json`（本报告原始证据）
