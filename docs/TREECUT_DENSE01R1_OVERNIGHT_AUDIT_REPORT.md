# TREECUT DENSE01R1 OVERNIGHT — INDEPENDENT FORENSIC AUDIT REPORT

- 任务：CAM01 DENSE01R1 独立取证审计 + FULL REPLAY + 失败根因图 + 下一步路线证据
- 基线：main @ `08a6d28`（working tree 在审计产物前 clean；HEAD/branch/hash 见 BASELINE_AUDIT.json）
- 性质：**AUDIT / DIAGNOSTIC**。未修改 production（`scripts/posta3_cam01_dense01r1.py` 零改动）、
  未改动正式 DENSE01R1 JSON、未覆盖历史报告。全部结果为新文件名。
- role-blind：所有算法/诊断阶段不读 POS/NEG；role 透视仅在末尾且未改变结论。

## 0. 结论速览（§35 简版）
- **FINAL AUDIT CLASSIFICATION = A_DENSE01R1_VERIFIED_FAIL**（核心实现正确；full replay 复现；
  无会翻转 0/36 结论的 defect；但有 1 个 MEDIUM 实现缺陷记录 + 结构通道 NOT_IMPLEMENTED）
- 0/36 independently reproduced：**YES**
- determinism：**PASS**（seed42 vs 无 seed 零 mismatch、state 全等）
- PRIMARY 路线：**EVIDENCE_HIERARCHY_REDESIGN**；SECONDARY：**TEMPORAL_LEARNED_TRACKER**（TAPIR/SEA-RAFT 合规）

## 1. BASELINE（§1）
HEAD `08a6d28` · main · 审计启动时工作树 clean。文件 hash 全部记录于
`TREECUT_DENSE01R1_OVERNIGHT_BASELINE_AUDIT.json`。模型 checkpoint
`dinov2_vits14_reg4_pretrain.pth` sha256=`F433177089A681826F849F194ECE3BB48F4D63FB38D32FC837E3DC7A4E5641FB`。
注记：正式 `MODEL_PROVENANCE.json` 的 checkpoint/sha256 为空 → AUDIT_FINDING_04。

## 2. 指标独立重算（§2，不信任原报告，从 replay raw 重算）
| 指标 | production 报告 | overnight 独立重算 | 一致 |
|---|---|---|---|
| old MNN sufficient /36 | 36 | **36**（从 DENSE01 v1 MATRIX mnn_count） | YES |
| corrected (valid-domain) MNN /36 | 34 | **34** | YES |
| MNN 逐 pair 与 production 一致 | — | **36/36 零差异** | YES |
| LK attempted | 2571 | **2571** | YES |
| LK accepted（production 语义） | 1434 | **1434** | YES（round-2 对齐后逐 pair 零差异） |
| AFFINE/HOM validated | 0/0 | **0/0** | YES |
| MULTI/SINGLE/CONFLICT | 0/0/0 | **0/0/0** | YES |
| NO | 36 | **36** | YES |
| union | 0 | **0** | YES |
| case coverage /9 | 0 | **0** | YES |
| state counts | NO31/LOC3/INS2 | **NO31/LOC3/INS2** | YES |

**AUDIT_METRIC_MISMATCH：无。**

## 3. Defect 状态重审计（§3）
原 DEFECT_AUDIT 记 **8/8 fixed 不准确**：
- DENSE01_DEFECT_01..06（RGB/归一化/padding/MNN 域/温度/stride）：**VERIFIED_FIXED**
- DENSE01_DEFECT_07（真分歧实现）：**VERIFIED（实现存在；合成测试 §18 证明非 dead code：affine→MULTI、perspective→CONFLICT 均可达）**
- DENSE01_DEFECT_08（结构通道）：**NOT_IMPLEMENTED**（STRUCTURAL_VALIDATION.json rows 空占位，注明"后补"）
- 真实完成度：**6 VERIFIED_FIXED + 1 IMPL_PRESENT(07) + 1 NOT_IMPLEMENTED(08)** → 不是 8/8。

## 4. Preprocess / token-domain（§4/§5）
- 5 随机帧（seed11）pre/post channel stats：无灰度污染（三通道 std 区分明显）、
  post-norm mean 与 (RGB01-mean)/std 期望一致（float64 验证）、BGR→RGB 值保持无 swap、
  无双重归一化/0-255 直接减 mean。
- token：每 pair 记录 total 1369 / cvm / dyn / valid（见 TOKEN_DOMAIN_AUDIT.json）。
- softmax subtoken（§8）：全数据 shift median **0.71px**（对 patch 14px 是小量，非"大幅 refine"，
  如实记为 DINO_SUBTOKEN_COARSE_REFINE）。

## 5. Valid-domain MNN 独立 replay（§6）
audit 自研 valid_mnn（不复用 production helper），同 normalized features + 同 valid mask：
36 pair 逐项与 production `valid_mnn` **完全一致** → **MNN_IMPLEMENTATION_MISMATCH：无**。

## 6. LK audit（§9/§10/§11）
- **预审计缺陷证实**：production 声明 LK `FB≤3`（config fb_max=3.0、docstring）但 `lk_refine`
  仅单次 forward `calcOpticalFlowPyrLK`，**无 backward、无 FB 判定** → 
  **AUDIT_FINDING_LK_FB_GATE_NOT_IMPLEMENTED（MEDIUM，不翻转 0/36）**。
- audit 独立实现 forward+backward：**2571 attempted rejection taxonomy**：
  FWD_STATUS_FAIL 958 · DEST_OUTSIDE_ISLAND 129 · DEST_DYNAMIC_CONTAM 50 ·
  BWD_STATUS_FAIL 70 · ACCEPTED(FB 可算) 1364。
  production 语义 accepted=1434 = 1364+70（70 个 backward 失败点被 production 计入 accepted）。
- **FB gate 量化**：1434 accepted 中仅 **1003 FB≤3**（431 点 FB>3；pooled FB median 0.16px
  但 P90 45.7px / P95 100.6px / max 806.6px）。若真实施 FB 门 → accepted 降至 ~1003，
  union 仍 0（更严格）→ 不改变结论。
- LK quality：accepted 点 DINO-seed→LK correction magnitude（corr_px）pooled 见 LK_AUDIT.json；
  按 pair FB/correction 见 LK_QUALITY_MAP.json。
- synthetic test（§9）：已知 12px 位移，无 init LK 失败/大误差，OPTFLOW_USE_INITIAL_FLOW
  恢复正确点 → 确认 init flow 实现有效且必要。

## 7. 核心问题：1434 accepted → 0 validated（§12/§13/§14）
- **DINO_LK fold 级（144 fold）failure taxonomy**：
  MED_AND_P90_FAIL 50 · HOLDOUT_P90_FAIL_ONLY 24 · VALIDATED 10 ·
  NO_MODEL/REASON 20 · INSUFFICIENT 16 · LOW_INLIER 4。
- **关键证据**：7 个 pair 各有 **1 个 VALIDATED fold**（如 3571/2543/10000/25894 的 fold，
  median 0.98–2.7px、inlier 0.78–0.95——质量极佳），但 pair 级要求**双 fold 都过** →
  另一半支撑区 holdout 泛化失败。
- **P90 尾部是主杀手**：74/144 fold 因 P90>8px 失败（50 个同时 median>3px）。
- holdout global residual（DINO_LK，2496 点）：median **4.04px** · P90 37.3px · P95 60.5px。
- DINO_ONLY vs DINO_LK：LK 把 global median 从 **14.2px 降到 4.0px**（LK_HELPED 主导），
  但 P90 尾 37px 未消 → **LK 有效但不够**（不是 LK 失效，是支撑区不一致/局部非刚性）。
- 答案：**失败不在"找对应"，在"一个 2D 全局模型无法在另一半未见支撑上泛化"**
  ——局部非刚性/取景变化/部件位移造成的尾部残差，任何单一 rigid/planar 模型都过不了 3/8px 双 fold gate。

## 8. 结构诊断（§20，audit-only）
audit-only support-hull validator（正式结构通道 NOT_IMPLEMENTED）：31 pair 有 corr≥4。
ANISO（affine）pooled chamfer median **2.87px / P90 64.1px / P95 236px**；
ISO（homography）median 2.87 / P90 76.4 / P95 240.6。→ **几何残差差与真实结构错位同源**
（结构尾部同样巨大），confirming holdout 尾部不是数值 artifacts 而是真实几何不一致。

## 9. Temporal gap（§21）
分桶（36 pair）：<1s n12（med 2.11/P90 16.0）、1–2s n14（med 0.83/**P90 7.82**）、
2–3s n6（med 2.52/P90 11.7）、>3s n4（med 4.34/P90 19.4）。
1–2s 桶 P90 最低（7.8px 接近 8px 门）——**端到端失败随 gap 增长而变差，但即便最短 gap
（<1s, P90 16px）也不达标** → 不是单纯"gap 太长"，是语义帧本身含非刚性运动。
（未用动作 GT。）

## 10. Determinism（§25）
replay1（无显式 seed）vs replay2（numpy/torch/cv2 seed=42）：36 pair MNN count、LK
attempted/accepted、pair state **全等，零 mismatch** → **NONDETERMINISM_FOUND：无（PASS）**。

## 11. Performance（§26）
total 41.2s/36 pair · DINO feat 0.5s（6.9ms/frame，GPU 极快）· match 289ms/pair ·
LK 281ms/pair · VRAM peak 0.13GB。瓶颈在 MNN 矩阵乘与 LK(CPU) 而非 DINO。

## 12. 最终分类（§29）
**A_DENSE01R1_VERIFIED_FAIL**：
- 核心实现正确（预处理/MNN/LK/fold/RANSAC 独立复现一致）；
- full replay 复现核心数字（0/36、union 0、state 全等）；
- 无会翻转 0/36 结论的 defect。发现缺陷仅记录/量化：FB 门未实现（若实施只会更严格）、
  结构通道 NOT_IMPLEMENTED（原报告已注明后补）、coverage gate 用全量 MNN（本数据无翻转）、
  provenance 不完整。

## 13. 路线推荐（§30，仅推荐不开发）
- **PRIMARY：EVIDENCE_HIERARCHY_REDESIGN（LOCAL/GLOBAL/UNSURE）**——
  audit 显示 7 pair 单 fold 极准、DINO 语义召回 34/36；问题在"单一全局模型泛化"而非"无证据"。
  hierarchy 可用现有真实能力（GFTT 17/36、V24 consensus 12/36、global camera、DINO semantic）
  分层表决 + 显式 UNSURE，fail-closed，无需新模型（草案见 EVIDENCE_HIERARCHY_PROPOSAL_V1.md）。
- **SECONDARY：TEMPORAL_LEARNED_TRACKER**——中间帧约束直接针对 1–4s 大 gap 的非刚性；
  合规候选见下。

## 14. Tracker 许可调研（§27，禁安装，官方证据）
| 候选 | 官方 repo | code/model license | 商用 | 状态 |
|---|---|---|---|---|
| CoTracker3 | facebookresearch/co-tracker | **CC-BY-NC**（README + HF license: cc-by-nc-4.0） | NO | **REFERENCE_ONLY_NONCOMMERCIAL** |
| TAPIR | google-deepmind/tapnet | **Apache-2.0**（GitHub API + LICENSE 文本） | YES | COMMERCIAL_OK（首选） |
| PIPs/PIPs++ | aharley/pips, pips2 | **MIT** | YES | COMMERCIAL_OK |
| LocoTrack | cvlab-kaist/locotrack | **Apache-2.0** | YES | COMMERCIAL_OK |
| RAFT / SEA-RAFT | princeton-vl/RAFT, sea-raft | **BSD-3-Clause**（稠密光流） | YES | COMMERCIAL_OK（dense flow 替代） |

全部基于 GitHub API license + 官方 LICENSE/README 直读；未安装/未运行任何 tracker。

## 15. 主要产物
reports/storage/：BASELINE_AUDIT · DEFECT_STATUS · PREPROCESS_AUDIT · TOKEN_DOMAIN_AUDIT ·
MATCH_QUALITY · METRICS_RECOMPUTED · MNN_REPLAY(隐含于 REPLAY raw 的 mnn_matches_prod) ·
SOFTMAX_AUDIT · LK_AUDIT · LK_QUALITY_MAP · LK_SEED_SAMPLE · FAILURE_MAP · FAILURE_CAUSES ·
DINO_LK_FOLD_CAUSES · HOLDOUT_ANALYSIS · DINO_VS_LK · RANSAC_STRIDE · FOLD_INDEPENDENCE ·
SPATIAL_COVERAGE · TRUE_POOLED · STRUCTURAL_DIAGNOSTIC · TEMPORAL_GAP · CAMERA_VIEW ·
DETERMINISM · PERFORMANCE · TRACKER_LICENSE_RESEARCH · RESULT ·
REPLAY_replay1.json / REPLAY_replay2.json（raw pair records）。
docs/：本报告 + EVIDENCE_HIERARCHY_PROPOSAL_V1.md。
scripts/：audit_dense01r1_overnight.py（replay runner）· _analyze.py · _diag.py ·
_preprocess.py · _structural.py · _result.py。tests/test_dense01r1_overnight_audit.py（6 测试）。
