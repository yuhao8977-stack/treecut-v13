# TREECUT MASTER CURRENT-STATE AUDIT & HANDOFF V2
# 树剪当前程序总审计与上下文交接报告

- 任务性质：**READ-ONLY AUDIT + HANDOFF**（为无法读取旧对话的新审查者重建完整技术上下文）
- 生成：2026-09-08 · 审计基线 HEAD `b757daf43f1c040c0020797f55edc3a51a55a28c`
- 边界：不修码/不优化/不重构/不改 router/不加样本/不进 GEOM/不推进阶段/不改 truth/
  不改历史报告/不自动采纳候选/不上传秘密与大型资产/不复制源码进报告
- 对应机器文件：`TREECUT_MASTER_CURRENT_STATE_AUDIT_HANDOFF_V2.json`（机器可读全量）+
  `TREECUT_MASTER_CURRENT_STATE_EVIDENCE_INDEX_V2.json`（证据索引）

---

## 一、审计基线（全部由当前 git/文件证据验证）

| 项 | 值 |
|---|---|
| repository | `treecut-v13`（GitHub: yuhao8977-stack/treecut-v13，remote 已脱敏） |
| 绝对路径 | `C:\Users\admin\github\treecut-v13` |
| branch | `main` |
| HEAD SHA | `b757daf43f1c040c0020797f55edc3a51a55a28c` |
| git status | clean（审计开始时 porcelain 0） |
| 领先/落后 origin | ahead 0 / behind 0 |
| tracked 文件 | **1596**（.py 640 / .json 511 / .md 225 / .jpg 75 / .html 33 / 其余见 evidence） |
| tracked 大小 | **≈80.1 MB**（cat-file 汇总；无 >2MB 视频/权重被跟踪） |
| 本地工作安装 | `E:\树剪整理\02_安装程序\TreeCut_v13`（runtime python 3.12.13） |
| torch 缓存 | `G:\TreeCut_AI\torch_cache`（DINOv2 checkpoint，非 git） |

**版本（当前实测）**
- runtime python `E:\...\TreeCut_v13\runtime\python.exe`：Python 3.12.13 · cv2 4.10.0 ·
  torch 2.6.0+cu124 · numpy 2.5.2 · CUDA 12.4（RTX 3050）
- system python `C:\Users\admin\AppData\Local\Programs\Python\Python312`：Python 3.12.10 ·
  cv2 4.13.0 · pytest 9.1.1
- ffmpeg 8.1.1-full_build（gyan.dev）
- FAISS / BGE-M3 / pyJianYingDraft：**runtime 内未 import 验证**（faiss/pyJianYingDraft import 未输出版本；
  见 §13 UNKNOWN 标注）；README 声称 Whisper/Chinese-CLIP/BGE-M3 "仍在建设/本地权重补齐决策"（stale 风险见 §13）

**v12 与 v13**：本地安装目录仅 `TreeCut_v13`（无 v12 安装副本）；README + `07_v12归档边界.md`
明确 v12 只作需求/算法参考，**不再作正式启动入口**，v12 文件保留不删（文档层面）。仓库无 v12 代码。

**生产基线**：正式主线 = **Stage0～Stage10**（`docs/TREECUT_ROADMAP_MASTER_V1.md`），当前
`STAGE8_PRODUCTION_QUALITY_HARDENING`；B007 第一条真实 Pilot V1 = HUMAN_REJECTED。
**CAM01 POST-A3 calibration / Evidence-Hierarchy（EH01→EH02）是 Stage8 下 G2 动作验证的
并行研究轨道，未改变 ROADMAP 主线状态。**

**提交链（本次任务相关）**
| commit | 职责 |
|---|---|
| `09e3b5b` | V23 feature bakeoff：METHOD_MATRIX/METHOD_CONFIG（GFTT 17/36 的 pair-state 真值来源） |
| `8cb7682` | DENSE01R1 overnight audit（0/36 复现，发现 FB gate 未实现） |
| `8f84735` | DENSE01R2：真 FB3 gate → 8/36 → endpoint route CLOSED |
| `f46701a` | EH01：6-source inventory + shadow router（semantics 有缺陷） |
| `4aec680` | EH01R1：reference/transform 语义修正 → EMITTABLE_STRONG 9/36 |
| `644c206` | EH01M1：V23 GFTT exact replay 17/17 + materialize + 独立 structural |
| `b757daf` | **EH02（当前 HEAD）**：router V2 freeze + M1 inlier-support correction |

**冲突入口/配置/数据库**：无证据显示多套冲突入口。安装内 `启动树剪v13.cmd` /
`启动树剪本地接口.cmd` / `启动远程管理端.cmd` 三个启动器指向同一 v13 安装。
数据库：`runtime_data\database\materials.db`（44.7MB / 88 表）为正式库；
CAM01 脚本另用 `runtime_data\temp\batch1\database\materials.db`（同一数据库文件的 temp 副本路径，
未发现 schema 分叉证据——标 UNKNOWN 未深验）。

## 二、系统使命与范围

**目标（README_小白版 + ROADMAP 冻结）**：素材发现/分析（画面/人物/产品/语音/场景）→ 卖点匹配
→ 配音/字幕/BGM/时间线 → 3 条候选成片 → 人工终审 → 剪映草稿或 MP4。

**范围（ROADMAP_MASTER_V1.md §5 冻结）**：
- 正式主线 Stage0–10；**当前 Stage8**（G1 PASS_FROZEN → G2 BLOCKED_BY_CANDIDATE_RECALL_VALIDATION）
- **B007/KUBON** = 当前正式内容范围（第一条真实 Pilot B007；Pilot2-5 规划中）
- **Stage9（Template Expansion）⏳ 冻结**：`STAGE9_FORBIDDEN_UNTIL_STAGE8_PASS`
- **AutoPublish 禁止**：ROADMAP §5 "禁止 AutoPublish 作为当前目标"
- 禁止（Stage8 PASS 前）：全面扩展模板 / 大规模扩账号 / 无关 UI 重构 / 大型模型替换
- 发布标准：**至少 4/5 Pilot 达 BASICALLY_PUBLISHABLE**（运营级人工微调即可，不需每次回改算法）
- 当前内容状态：**未达发布标准**（B007 V1 HUMAN_REJECTED、V2 HUMAN_NEEDS_REPAIR；
  Stage8_pass=NOT_PASSED_NEEDS_4OF5）

**范围改变的证据**：无（ROADMAP_MASTER 为冻结宪章，未见后续 commit 改变主线/范围；
CAM01/EH 系列为研究轨道，未声称改变 Stage 定义）。

## 三、完整架构地图（关键事实，非穷举）

**入口**：`src/treecut/main.py`（CLI 单入口：--status/--scan/--catalog-scan 等）、
`src/treecut/api.py`（本地 API）、`src/treecut/desktop.py`（桌面 UI）、
`src/treecut/browser/main.py`（XHS 工作浏览器）、`src/treecut/remote/hub*.py`（远程管理）、
安装内 3 个 `.cmd` 启动器、`tools/mmv_a1_annotate/server.py`（ROI 标注服务，port 8933）。

**层**（src/treecut/）：`application/`（jobs.py AnalysisWorker、production.py）、
`services/`（40+ 模块：mmvl_master_v1.py、mmv_camera_diag.py、production_source.py、
claim_visual.py、visual_beat.py、action_subclip.py、production_dedup.py、production_qa.py、
canonical_truth.py、business_cognition_v2.py、review_center.py…）、
`library/`（Catalog）、`media/`（discover_drives/ffprobe）、`analysis/`、`models/registry`、
`ui/` + 各 `*_ui.py`、`config/`、`remote/`、`workflow/`、`scanner/`、`search/`、`asr/`、`ocr/`、
`classify/`、`templates/`、`feedback_learning/`、`knowledge/`。

**数据流**（生产主链）：media discovery → Catalog/assets → analysis(ffprobe/keyframe/ASR/OCR/
scene) → segment → semantic annotation(L2/L3) → production(script/claim/visual beat/action
subclip → candidate) → QA/dedup → pilot/render。CAM01 轨道：semantic pair evidence → DENSE/GFTT/
V24 local transform → EH02 router（本报告核心）。

**身份规则（DB schema 实测）**：
- `media_files.id` = 文件身份 ✓
- `assets.asset_id` = 规范资产身份 ✓
- `segments.segment_id` = 镜头/最小单元身份 ✓
- **第四套 shot ID：NOT_FOUND**——`shot_usage` 用 `segment_id`+`beat_id`；`b007_segment_v1` 用
  `seg_id`（legacy）；`visual_clusters` 用 `cluster_id`。未发现与 segment 平行的第 4 套镜头 ID。
- 业务模块绕过 Service/Repository 直接 SQL：**未穷尽验证**（scripts/ 大量直接 sqlite 探针；
  服务层内规范与否需代码级审计，标 NOT_EXHAUSTIVELY_VERIFIED）。

**存储位置**：正式 DB `runtime_data\database\materials.db`（E: 安装内）；CAM01 用
`temp\batch1\database\materials.db`；模型缓存 `G:\TreeCut_AI\torch_cache`；报告
`reports/storage/*.json`（git 跟踪）；runtime secrets `runtime_data\config\api_token.txt` +
`master_key.txt`（本地、**未 git 跟踪**）；任务/队列在 DB `analysis_tasks`/`review_queue`/`jobs.db`。

**失败恢复**：README 声称"任务记录与中断恢复：意外退出后明确显示失败，可用原请求点击重试"
（未在本审计中实测）。

## 四、权威来源与 Truth 层级

| 来源 | 路径 | commit | authoritative | derived | stale |
|---|---|---|---|---|---|
| V23 METHOD_MATRIX | reports/storage/TREECUT_CAM01_V23_METHOD_MATRIX.json | 09e3b5b / blob 98e74be9 | **YES(pair-state truth)** | no | no |
| V23 METHOD_CONFIG | 同目录 _V23_METHOD_CONFIG.json | 09e3b5b | YES(冻结参数) | no | no |
| CALIBRATION10 manifest | TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json | 136e466 | YES(36-pair universe) | no | no |
| HUMAN_ROI | TREECUT_POSTA3_HUMAN_ROI_V1.json | (git log 查得) | YES(L3 标注) | no | no |
| DB truth | materials.db(88 表) | 非 git | YES(运行时) | — | — |
| DENSE01R2 MATCH_MATRIX | TREECUT_CAM01_DENSE01R2_MATCH_MATRIX.json | 8f84735 | derived | YES | no |
| V24R1 consensus | TREECUT_CAM01_V24R1_TRUE_CLIQUE_CONSENSUS.json | e2bb0ae | derived | YES | no |
| GLOBAL camera V2 | TREECUT_POSTA3_CAMERA_PAIR_MATRIX_V2.json | f85b363 | derived(state only) | YES | no |
| M1 GFTT transforms | TREECUT_CAM01_EH01M1_GFTT_TRANSFORMS.json | 644c206 | derived(materialized) | YES | no |
| EH01M1 local agreement | TREECUT_CAM01_EH01M1_LOCAL_AGREEMENT.json | 644c206 | derived | YES | no |
| EH02 router freeze | TREECUT_CAM01_EH02_ROUTER_FREEZE.json | b757daf | derived(frozen) | YES | no |
| V23 REPORT.md | docs/TREECUT_CAM01_V23_FEATURE_BAKEOFF_REPORT.md | 09e3b5b 时代 | **NO** | YES | **YES(stale)** |
| V23_STALE_REPORT_NOTE | TREECUT_CAM01_EH01M1_V23_STALE_REPORT_NOTE.json | 644c206 | 记录 | YES | no |

**冲突取舍**：METHOD_MATRIX > derived JSON > REPORT.md 文字。V23 REPORT.md 困难案例文字
（"2543 GFTT 3/4"等）与 METHOD_MATRIX 不符（实际 1641 1/4、2543 1V+2P、10000 0V、21674 0V），
**REPORT.md 保持未修改**（stale note 已生成，不改历史 truth）。

**V23 关键约定**：36 pair universe = CALIBRATION10 的 9 个 island case ×4 adjacent pairs
（2212 LEG 无 island，不在 36）；fold = floor(x/40)+floor(y/40) mod 2（cell=40）；
pair-state fingerprint 36/36 与 fold fingerprint 全 match（M1 replay 验证，见 §六）。

## 五、CAM01 阶段历史（commit 证据）

| 里程碑 | 输入 | 目标/实际 | 结果 | commit | push | frozen | next |
|---|---|---|---|---|---|---|---|
| DENSE01R1 | 08a6d28 前 | DINO 语义锚点 | 0/36 forward-only | 08a6d28 | YES | YES | audit |
| Overnight audit | 08a6d28 | 独立复现 | 0/36 复现；FB gate 未实现；INTENDED_SPEC_INCONCLUSIVE | 8cb7682 | YES | YES | R2 |
| DENSE01R2 | 8cb7682 | 冻结规格闭合(真 FB3) | **8/36 union**；FAIL_DENSE；**route CLOSED** | 8f84735 | YES | YES | EH01 |
| EH01 | 8f84735 | 6-source join shadow | ROUTER_USABLE 19/36（语义缺陷）| f46701a | YES | YES | R1 |
| EH01R1 | f46701a | reference 语义修正 | EMITTABLE_STRONG 9/36；capability PARTIAL | 4aec680 | YES | YES | M1 |
| EH01M1 | 4aec680 | GFTT replay+materialize | 17/17 replay+materialize；fingerprint 36/36 | 644c206 | YES | YES | EH02 |
| **EH02(当前)** | 644c206 | router V2 + M1 correction | STRONG 8/36；NEG PRESENT；S1/S2/S3 frozen | b757daf | YES | YES | **TARGETED_NEGATIVE_REFERENCE_SET** |

**被纠正的结论**（每项都有 commit + correction artifact）：
1. GFTT↔V24 conflict 身份写错 → EH02 Stage0A 修正（真实 conflict=25894 3.112→4.07 med 4.245；
   12095 5.191→7.416 实为 AGREE 0.001）— `b757daf` / EH02_M1_CORRECTIONS.json
2. M1 structural hull 用全部 tracks（含 outlier）→ EH02 Stage0B 改 RANSAC inlier hull —
   `b757daf` / EH02_CORRECTION_M1_STRUCT_HULL_02
3. structural 7/10/0 → **7/9/1**（1641 2.642→3.434：DISAGREEMENT→UNKNOWN，inlier hull t1 边仅 1）
4. 2543 1.202→1.717 保持 CONSISTENT（sym P90 2.324）
5. 收回的 strong（EH01R1 9 → EH02 8）：25894 1.676→2.394、27433 10.352→13.458（corrected
   structural 真 veto）；3571 1.842/7.984 DENSE MULTI 但 R2 structural DISAGREEMENT → vetoed 未误升
6. 新增 strong：2543 1.202→1.717（GFTT S2，第一个 NEG strong target-valid）
7. EH01 post-hoc ">12→FEASIBLE" 阈值被删除（EH01R1 Defect 04）

## 六、EH01 M1 独立复核（本轮重算，不覆盖旧报告）

全部由当前 artifact + 独立代码重算：
- historical GFTT validated **17/36** · replay **17/36**（一致）
- pair-state fingerprint **36/36** · fold-state fingerprint **全 match**
- materialized **17/17** historical validated · deterministic rebuild **17/17**
- **独立 matrix 重建（affine RANSAC 3px on full FB3 corr）与 M1 matrix 差异 <1e-3：17/17**
- 7 个原 no-transform route（12095 2.225 / 1641 2.642 / 2543 1.202 / 25894 2.394 /
  9697 2.885/4.121/5.357）**全部 materialized（7/7）**
- transform provenance：全部 DERIVED_V23_GFTT_REFERENCE_TRANSFORM，affine RANSAC thr=3.0，
  source commit 644c206 + 09e3b5b 历史 config
- target-valid（M1 materialized 集）：POS 8 / NEG 2（1641 2.642 + 2543 1.202）
- structural（M1 全-hull 版）：7C/10D/0U；（EH02 inlier 版）：7C/9D/1U —— 差异已记录不改旧

## 七、EH02 Router 完整规则（来自代码 + ROUTER_CONFIG/ROUTER_FREEZE 冻结 artifact）

**frozen rules hash**（ROUTER_FREEZE.json）：`rules_hash` 记录 S1/S2/S3 + precedence +
tie-break 文本的 sha256 前 16 位。

- **confidence**：HIGH = V24R1 TRUE_MULTI_METHOD_CONSENSUS 或 DENSE_R2 MULTI_MODEL_CONSENSUS；
  MEDIUM = DENSE_R2 SINGLE_MODEL 或 GFTT_V23 VALIDATED materialized（GFTT bakeoff FAILED，
  不天然 STRONG）。
- **S1**：HIGH_CONF_LOCAL + 无 LOCAL_CONFLICT + structural ≠ DISAGREEMENT。structural UNKNOWN
  允许（= NO_STRUCTURAL_VETO_AVAILABLE），但不得写 STRUCTURAL_CONFIRMED。
- **S2**：MEDIUM_CONF_LOCAL + STRUCTURAL_CONSISTENT + GLOBAL reliable state + 无 LOCAL_CONFLICT。
- **S3**：MEDIUM_CONF_LOCAL + 与至少一个 **CROSS-FAMILY** materialized local source AGREE +
  structural ≠ DISAGREEMENT + 无 conflict。（V24↔GFTT 同 FEATURE_LOCAL family，不满足；
  DENSE↔GFTT、DENSE↔V24 可满足。）
- **conflict precedence**：LOCAL_CONFLICT > STRONG > PARTIAL > EVIDENCE_ONLY/NONE。
  两个已过各自历史 gate 的 materialized local source prediction disagreement >3px
  （ISLAND_BODY fixed raw grid median）即 CONFLICT → UNSURE_CONFLICT；global reliable /
  structural consistent 不得覆盖。
- **structural 语义**：CONSISTENT(per-pair 合并任一源) = supporting；DISAGREEMENT = strong veto
  （→ PARTIAL_VETOED，SAFE_EMIT=False）；UNKNOWN = neither support nor veto。
  边界 symmetric P90 ≤12 / >12（沿用，未调）。EH02 采用 **per-pair 合并**：GFTT inlier-hull +
  R2 DENSE symmetric 任一 DISAGREEMENT 即 veto。
- **representative selection / tie-break**：优先 cross-family agreement cluster；不矩阵平均；
  同级固定 DENSE_R2 > V24R1 > GFTT_M1；不用 action GT。
- **global 角色**：state-only（无 transform）→ 只能 SUPPORT STATE；不能 emit reference；
  不能做 transform agreement；global unreliable = NO_GLOBAL_SUPPORT（不作 veto）。
- **safe_emit**：仅 REFERENCE_STRONG = true。
- **六 route**：REFERENCE_STRONG / REFERENCE_PARTIAL / REFERENCE_PARTIAL_VETOED /
  UNSURE_CONFLICT / UNSURE_EVIDENCE_ONLY / UNSURE_NO_EVIDENCE。
- **abstain**：非 STRONG 全部 abstain（safe_emit false）。

## 八、NEG_REFERENCE_CONTROL 核心审计

- **POS/NEG 定义（本项目）**：CALIBRATION10 的 role 标注——POS = 有 EXTENSION 动作语义的
  case；NEG = 无动作 / 其它语义（2212 LEG / 1641 牛肉锅 / 10000 岩板炖锅 / 2543 餐边柜 /
  9697 小狮子 / 25894 岛台）。36 semantic pairs 中 16 POS / 20 NEG。strict target contract：
  EXTENSION_TABLETOP 唯一，否则 TABLETOP 唯一（用于 target-valid）。
- **NEG strong reference 目的**：为未来 EXTEND/STATIC 判别提供"负样本 reference"对照——
  判定"这个 pair 有可靠 camera/object reference 可用（不关心动作方向）"；避免仅凭漂亮单样本
  提前宣布成功。
- **过去是否"NEG_STRONG_REFERENCE 必须 = 0"**：是——EH01R1 报告 `NEG_STRONG_REFERENCE_TARGET_VALID=0`
  是**事实陈述**（当时 0 个），EH01M1 §22 明确"NEG materialized ≠ NEG strong；强度等 EH02"。
  它不是一条"禁止非零"的正式规则，而是阶段演进（materialized → strong 升级发生在 EH02 S2 规则下）。
- **是否正式修改**：无"修改规则"commit——升级路径由 EH02 的 **S2 规则** 授权（2543 满足
  MEDIUM+CONSISTENT+global reliable）。**原始 §31 指令（"NEG strong must remain 0" 等）在仓库
  无正式决策文件**：→ `SECTION_31_SOURCE_STATUS = NOT_FOUND`；
  `NEG_STRONG_POLICY_AUTHORITY = UNRESOLVED`（规则文本仅存在于对话指令 + EH02 报告/RESULT，
  无独立 commit 决策文档）。不得由报告反推 §31 要求。
- **2543 为何可 STRONG**：V23 GFTT 双 fold VALIDATED + transform materialized +
  structural CONSISTENT（sym P90 2.324）+ GLOBAL state RELIABLE + target t0/t1 有效 → **S2**。
- **2543 证据**：DENSE/GFTT/structural/global 各源见 §九表 + EVIDENCE_INDEX。
- **global RELIABLE 来源**：POSTA3_CAMERA_PAIR_MATRIX_V2 SPARSE_DIRECT state
  （commit f85b363）；2543 1.202→1.717 的 SPARSE_DIRECT = CAMERA_RELIABLE（fingerprint 见该
  artifact）。global **无 materialized transform**（GLOBAL_TRANSFORM_MATERIALIZED=NO）。
- **global 仅 state 为何可作 S2 support**：S2 要求的是"独立结构支持 + global state 支持"，
  2543 的 **transform 由 GFTT 提供**（materialized），global 只作 state support——
  架构师 §26 明确"GFTT 已提供 transform，global 只作 state support"；不要求 global 有矩阵。
- **运行时 router 是否可读 POS/NEG**：role-blind 设计——ROUTER_FREEZE.json 生成于读 role 前；
  TARGET_READINESS 在 freeze 后单独读 role。代码顺序有保证（freeze 先写，readiness 后算）。
- **label leakage**：未发现 router 逻辑按 role 分支；36-pair 表 role 仅用于事后 readiness。
- **pair ID 硬编码**：测试断言含具体 case id（12095/25894/2543/1641 等）用于验证已知 verdict，
  属测试级硬编码验证，非 router 逻辑硬编码（router 逻辑数据驱动自 agreement graph）。
- **≥3 unique visual families**：NEG strong target-valid 样本须覆盖 ≥3 个独立视觉 family
  （SEMANTIC_DENSE_LK / FEATURE_LOCAL_ENSEMBLE / FEATURE_LOCAL / GLOBAL_CAMERA…），
  且 FEATURE_LOCAL 系内 V24/GFTT 视为同链不重复计。当前 2543 属 FEATURE_LOCAL(GFTT)，
  仅 1 family → **ESTABLISHED 不满足**。
- **PRESENT vs ESTABLISHED**：PRESENT = ≥1 NEG strong target-valid（当前 YES, 1）；
  ESTABLISHED = ≥3 unique families AND target-valid AND STRONG（当前 NO）。
- **为何 PRESENT=YES / ESTABLISHED=NO**：只有 2543 一个 NEG strong target-valid，family 单一。

## 九、36 pair 完整判级表（本报告附录 A；机器 JSON 全量）

route 汇总：REFERENCE_STRONG **8** · REFERENCE_PARTIAL **1** · REFERENCE_PARTIAL_VETOED **11** ·
UNSURE_CONFLICT **2** · UNSURE_EVIDENCE_ONLY **0** · UNSURE_NO_EVIDENCE **14** · safe_emit **8** ·
case coverage **6/9**。

**8 个 REFERENCE_STRONG 明细**（POS strong 6，其中 target-valid 5；NEG strong 2，其中 target-valid 1）：
| case pair | role | rule | target-valid | global | structural | rep |
|---|---|---|---|---|---|---|
| 27433 7.246→10.352 | POS | S1 | ✓ | RELIABLE | (见表) | V24R1 |
| 12095 7.416→9.64 | POS | S1 | ✓ | RELIABLE | — | V24R1 |
| 12095 9.64→12.607 | POS | S1 | ✓ | RELIABLE | — | V24R1 |
| 3571 4.299→6.142 | POS | S1 | ✓ | UNRELIABLE | CONSISTENT | DENSE_R2 |
| 3571 6.142→7.984 | POS | S1 | ✓ | UNRELIABLE | CONSISTENT | DENSE_R2 |
| 21674 1.201→2.803 | POS | S1 | ✗ | UNRELIABLE | — | V24R1 |
| 9697 1.236→2.885 | NEG | S1 | ✗ | UNRELIABLE | — | V24R1 |
| 2543 1.202→1.717 | NEG | **S2** | ✓ | RELIABLE | CONSISTENT(2.324) | GFTT_M1 |

（注：27433 10.352→13.458 与 25894 1.676→2.394 是 EH01R1 strong、EH02 因 corrected structural
veto 收回——不在当前 8 内。精确 target_valid/role 见机器 JSON 的 36_pair_table。）

（§31 语义核对：**POS strong target-valid = 5**（27433 7.246、12095 7.416、12095 9.64、
3571 4.299、3571 6.142）；POS strong 非 target-valid 1（21674 1.201——target t0/t1 无效）；
**NEG strong target-valid = 1**（2543 1.202）；NEG strong 非 target-valid 1（9697 1.236）。
non-target-valid strong 不可用于 target 级后续；9697 虽 NEG 但 target 无效，不进入 NEG control。）

## 十、case coverage 与未覆盖

- 36 pairs 覆盖 9 case（岛台 present）；2212 无 island 不在 36。
- **case coverage 6/9**：有 strong 的 6 case = 2543/3571/9697/12095/21674/27433。
- 未覆盖 3 = **1641**（最强 pair 2.642→3.434 = PARTIAL）、**10000**（0.768→1.793 DENSE SINGLE
  但 R2 structural DISAGREEMENT → PARTIAL_VETOED）、**25894**（0.718/1.676/2.394 均 VETOED、
  3.112 CONFLICT）。
- 未覆盖处理：全部 abstain（非 STRONG → safe_emit false）；不统一强制 PASS。
- **ROUTER_RULESET_FROZEN=YES 的准确含义**：S1/S2/S3 + precedence + tie-break 的**规则文本**
  已冻结（rules hash 记录）；**不等于** calibration complete，更**不等于**可进 GEOM。
  证据充分性由 NEG_REFERENCE_CONTROL_ESTABLISHED / case coverage 等单独判定——当前
  ESTABLISHED=NO，GEOM 禁止。

## 十一、11 个 targeted NEG 候选（审计/推荐 only，不执行）

来源：POSTA3_HUMAN_REVIEW_V1.json `NO_ACTION` verdicts 中 **cal10 之外**的 11 个 media_id：
`1019 1025 103 1600 1638 1639 2163 2208 2211 2492 26023`（src1 卖点展示类为主 + 26023 src4 工厂）。

| id | 证据 | family(推断) | 人工审核 | 风险/备注 |
|---|---|---|---|---|
| 1019 | human NO_ACTION | 32运动者+实木升降台·内蒙古炖锅 | 见 POSTA3_HUMAN_REVIEW(media 级) | family 未在 cal10；需真实人工 frame 级复核 |
| 1025 | 同上 | 34可折叠水桶+实木桌·南京炖锅 | 同上 | 同上 |
| 103 | 同上 | 113欧式沙发+实木梳妆·山东炖锅 | 同上 | 同上 |
| 1600 | 同上 | 04壁挂水龙头+凉亭·内蒙古炖锅 | 同上 | 同上 |
| 1638 | 同上 | 1-4 55大理石+深黑实木 | 同上 | 同上 |
| 1639 | 同上 | 05烤牛肉串 | 同上 | 同上 |
| 2163 | 同上 | 85瓷白+深灰+黑白·岩板炖锅 | 同上 | 同上 |
| 2208 | 同上 | 48大理石+运动者+深灰拼花 | 同上 | 同上 |
| 2211 | 同上 | 32运动者+实木·内蒙古餐厅 | 同上 | 同上 |
| 2492 | 同上 | 岩板白·鱼尾锅·壁挂水龙头 | 同上 | 同上 |
| 26023 | 同上 | DJI 青岛·工厂(未处理 src4) | 同上 | src4 工厂类，与 2543 岛台展示不同源 |

- 是否真人工审核：POSTA3_HUMAN_REVIEW_V1 是 media 级 NO_ACTION verdict 记录（`at` 时间戳）；
  是否 frame/ROI 级人工复核未验证 → 需在补强任务前确认。
- 与 2543 同 family？：均为岛台/桌面产品展示类（src1）候选，视觉 family 可能重叠；
  26023(src4 工厂) 是潜在不同 family。**挑样偏差风险**：候选多来自"展示类"——需独立 family
  筛选 + target 两端可见才合格。
- label leakage：候选均非 A3、非 cal10 样本；加入前须经架构师批准 + frame 级人工 + ROI 契约，
  本轮不执行。

## 十二、测试与真实证据

**实际运行**（system python pytest，46 项，0.33s，全部数据驱动于冻结 artifact——非真实媒体）：
- `test_eh02_router.py`（16）：①M1 matrix rebuild exact ②inlier mask saved ③struct hull 用
  inliers ④agreement conflict 身份(25894 conflict / 12095 agree) ⑤conflict 非硬编码 ⑥same-family
  不满足 S3 ⑦cross-family 存在 ⑧struct DISAGREEMENT veto(3571 1.842/7.984) ⑨UNKNOWN≠CONSISTENT
  (1641 PARTIAL) ⑩global state 不 emit transform ⑪S2(2543) ⑫S1(DENSE multi) ⑬conflict precedence
  (12095 5.191→UNSURE_CONFLICT) ⑭only strong safe_emit ⑮freeze 先于 role read ⑯NEG established
  需 ≥3 families
- `test_eh01m1_gftt.py`（13）：config=V23 / FB3 / fold cell 40 / pair+fold fingerprint /
  partial 不 materialize / validated 可 materialize / affine 3px / deterministic / 不自动 strong /
  structural sym raw px / target 不 promotion / stale 非 truth / 7 route materialized
- `test_eh01r1_reference.py`（11）：pair thr / HOMOGRAPHY / 禁固定 4px / GFTT null 不 emit /
  global-only 不 emit / partial 触发 global check / conflict 不被 global 覆盖 / UNKNOWN≠CONSISTENT /
  post-hoc 阈值已删 / provenance 无 -era / target 只计真 reference
- `test_eh01_inventory.py`（6）：symmetric 修正 R2 / agreement verdicts / router counts /
  raw union≠usable / structural counts / target role-blind

分类：**unit/integration(data-driven)** = 46；**replay test** = M1 独立复核（§六，17/17）；
**real-media** = CAM01 各 runner 属真实视频复现（DENSE R2/EH01M1/EH02 重跑均跑真帧）；manual =
POSTA3 HUMAN_REVIEW。覆盖 pairs：1641/2543/12095/25894/3571/27433 均在断言中出现。

## 十三、完整度与真实性审计（模块状态）

- **文档声称完成但代码未完成**：README"Whisper/Chinese-CLIP/BGE-M3 本地权重补齐或正式替代决策"
  标仍在建设；`VISION_MODEL_BUNDLE_V2.md` 为设计非实装证据 → 这些标 **PARTIAL/UNKNOWN**。
- **代码存在未接入主流程**：`src/treecut/feedback_learning`、`learning/`、`cognitive/` 部分 UI
  与宣传模块——README 自己强调"不能只建立空模块"，需逐模块审计，本报告标 **NOT_VERIFIED**。
- **只有测试无生产入口**：未穷尽；`tests/` 有大量单元（本次 46 + 历史更多），入口多为 scripts/
  runner 而非 src 服务。
- **只有报告数字无法复现**：PROJECT_STATE 历史快照（09-03）中 G2/G3 等数字属当时状态；
  当前 CAM01 各实验均有 runner+JSON 可复现（本次已复现 M1）。
- **缺真实媒体验证**：EH router 的 36 pairs 全为真实 CALIBRATION10 帧（有真媒体验证）；
  M1 replay 用真视频帧跑出（fingerprint 36/36 即真帧复现证据）。
- **能跑链路**：CLI(main.py) / catalog-scan / analysis worker / CAM01 runners /
  ROI annotator server(8933)。
- **不能跑/未验证链路**：完整 Stage8 render→QA→pilot 端到端（Pilot V2 HUMAN_NEEDS_REPAIR）；
  远程管理端、自动学习回流。
- **持久性**：DB(SQLite, E:) 与日志在进程关闭后保留；CAM01 结果全落 JSON(git)；模型缓存 G:。
- **团队域名/共享访问**：未见落地证据（X1 素材盘 \\X1\ 为本地共享；远程管理 hub 存在但状态
  UNKNOWN）。

## 十四、安全与 Git 边界

- **secret scan（本审计独立执行，tracked 文本 1100+ 文件正则）**：**0 命中**（当前 tracked）。
- 历史 `ev_git_secrets.json`（REVIEW 结论）列出的 xsec_token/authorization 命中均为
  **URL 结构样例 / 测试占位符 / 工具说明**，无真实凭据值。
- **large-file scan**：>2MB tracked 仅 5 个——PDF 16.8MB(G1 review) / OTF 16.4MB(字体) /
  release_manifest 3.1MB / HTML gallery 2.3MB / PNG 2.2MB。**无视频/模型权重/数据库被 git 跟踪**。
- tracked jpg 75 个 = G1 L3 review 缩略图（小额）。
- 本地未跟踪敏感：`runtime_data\config\api_token.txt` / `master_key.txt`（E: 安装内，**未进 git**）。
- 结论：GitHub 仓库只含代码/知识/合规报告/小额证据资产；不应进 GitHub 的大型本地资产
  （视频/模型/DB/素材）均未跟踪。本报告 3 个输出文件已做 secret/large-file 检查。

## 十五、风险与下一步

| 级别 | 风险 | 证据 | 影响 | 已发生 | 阻塞 | 最小修复 | 需用户决策 |
|---|---|---|---|---|---|---|---|
| **P0** | §31/政策权威缺失 | EH02 §31 原指令不在仓库；NEG≥3-family 规则仅对话+报告 | 无法从 repo 独立证明政策来源 | 否 | 是 | 补决策文档(commit) | **是** |
| **P1** | NEG control 仅 1/3 family | NEG strong tv=1(2543) | ESTABLISHED=NO；GEOM 禁 | 否 | 是 | targeted NEG set(11 候选) | **是** |
| **P2** | V23 REPORT.md stale | matrix vs report 不一致 | 读者误读 | 是 | 否 | 加 stale 横幅 | 否 |
| **P2** | global 仅 state | GLOBAL_TRANSFORM_MATERIALIZED=NO | 未来 fallback 无矩阵 | 否 | 否 | 视 EH02 后需决定 | 否 |
| **P3** | 本地 _tmp_*.py 60+ | E:\TreeCut_v13 根目录 | 本地杂乱 | 是 | 否 | 清理 | 否 |
| **P3** | README 路径陈述 stale | README"G 盘运行环境" vs 实装 E: | 误导 | 是 | 否 | 更新 README | 否 |

**推荐 NEXT_BLOCKER（唯一，不执行）**：`TARGETED_NEGATIVE_REFERENCE_SET`
（补 ≥3 unique visual family 的 NEG strong control；11 候选清单见 §11 + RESULT.json；
须架构师批准 + 人工 frame 级复核后才执行）。

## 十六、输出文件

1. `docs/TREECUT_MASTER_CURRENT_STATE_AUDIT_HANDOFF_V2.md`（本文件）
2. `reports/storage/TREECUT_MASTER_CURRENT_STATE_AUDIT_HANDOFF_V2.json`（机器可读全量：
   repository state / architecture / authoritative registry / timeline / 36-pair table /
   router rules / test matrix / risks / unresolved / next blocker）
3. `reports/storage/TREECUT_MASTER_CURRENT_STATE_EVIDENCE_INDEX_V2.json`（19 项 evidence：
   path / type / commit-blob / sha256 / status / supported conclusion）

## 附 A：36-pair 判级表（精简；全量含 target_valid/symP90/global/change 见机器 JSON）

（机器 JSON `36_pair_table` 每行含 case/pair/role/route/rule/reason/safe_emit/rep/
struct_corrected/symP90_corr/struct_old/symP90_old/global/r1_route/eh01_to_eh02_changed/
target_valid —— 36 行全量，此处不逐行复制。）

## 附 B：关键 UNKNOWN 清单（不补写推测）

- SECTION_31_SOURCE_STATUS = **NOT_FOUND**
- NEG_STRONG_POLICY_AUTHORITY = **UNRESOLVED**
- faiss / pyJianYingDraft / BGE-M3 运行时版本 = UNKNOWN（未验证 import）
- 服务层 SQL 绕过 = NOT_EXHAUSTIVELY_VERIFIED
- 11 个 NEG 候选的 frame/ROI 级人工审核深度 = UNKNOWN
- 远程管理端 / 自动学习回流 / 团队共享落地 = UNKNOWN
- README 与实装盘符差异（G vs E）= STALE（记录不改）
