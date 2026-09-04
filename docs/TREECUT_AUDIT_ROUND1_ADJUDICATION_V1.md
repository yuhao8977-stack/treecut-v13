# TreeCut 第二轮外部架构师独立裁决登记（Round-1 Adjudication）

> 层级：HUMAN L3（append-only，架构师裁决）
> 日期：2026-09-04
> 对象：docs/TREECUT_SYSTEM_MASTER_AUDIT_V1.md（Harness 第一轮内部审计）
> 裁决：**AUDIT_REPORT_PASS_WITH_MAJOR_CORRECTIONS**
> 边界声明（架构师）：当前为"报告+证据层"独立审计（MASTER AUDIT/Architect Guide/DB/测试/Git 证据可交叉核对）；**源码级逐文件独立审计 = PENDING DIRECT REPO ACCESS**（需 GitHub 连接授权后第二阶段执行）。

## 0. 认可的部分
- 报告未再犯"代码存在=功能可用"；明确承认：仅受控样例可产技术合格 MP4；不能自动产可发布视频；不能日常生产；非开发者不可独立使用；MMVV 不能 Enforcement。总判断认可。
- 关键架构发现被证实有值：两套 Production / 真 Pilot 绕过新主链 / 语义 QA 硬编码 / MMVV 无 caller / UI 只是审阅台 / DB schema 漂移 / script runner 泛滥 / 安全 token / 测试多但 E2E 内容验证缺失。

## 1. 主要修正（架构师裁决，正式口径变更）
| # | 修正 | 旧口径（Harness） | 新口径（架构师） |
| --- | --- | --- | --- |
| C1 | 最大系统问题定位 | 逐模块（MMVV ROI 等） | **"两个生产世界未真正合并"的架构断层**（Truth 底座成熟 + Stage8 智能层在建 + 旧渲染能力仍在 + monolithic Pilot 临时串联）；这解释了"模块测试 PASS 但成片没用它" |
| C2 | G5 拆分为三 | G5 = PROVISIONAL_PASS | **G5_TECHNICAL_QA=PASS/HUMAN_VALIDATED；G5_SEMANTIC_QA=BROKEN/NOT_VERIFIED；G5_OVERALL=BLOCKED_BY_SEMANTIC_QA** |
| C3 | "动作候选召回=0"术语错误 | ACTION RECALL = 0 | **VALIDATED ACTION PASS = 0**；RAW/BROAD RECALL = NON-ZERO（flexible 333 / drawer 888 / storage 1200 / socket 464）；HUMAN-POSITIVE ACTION SOURCE = EXISTS（≥ media52 DRAWER_OPEN）；MATERIAL GAP = NOT CONFIRMED |
| C4 | 不得直接"补拍 157" | Roadmap 写 157 人工核+定向补拍 | 先按动作分桶验证：157 排序 → ROI/target-motion 正确验证 → Cross-Segment → Human L3 → 按动作（EXTEND/RETRACT/DRAWER_OPEN/PUT_IN/SOCKET_INSERT）分别确认 → 仅某动作仍 0 才 MATERIAL_GAP_CONFIRMED → 再补拍 |
| C5 | MMVV A/B/C 拍板 | 待决策 | **选 A（GT ROI 校准，非最终生产方案）→ 证明后半段 → 再决定 B**；B 需 domain 检测器（COCO 无 EXTENSION_TABLETOP/UPPER_THIN_DRAWER/TRACK_SOCKET/SOCKET_MODULE），非通用 YOLO |
| C6 | DB 债权重上调 | P1 靠后 | **更早**：88 表/2.16M 行但迁移仅 0001–0009；b007_/spotlight_/stage2_ 不入迁移；b007_source_role_v1.asset_type 全 NULL；source_role=SOURCE_PRIOR confidence 0.5 → **G1 是"生产资格门"，不是"完整素材认知真值"**；他人不得见 PRODUCTION_CLEAN_RAW 即推断业务素材类型 |
| C7 | PipelineService 时机后移 | 较前 | 先定薄 **Production Contract**（ProductionSourceResult/CandidateResult/ActionValidationResult/ClaimMatchResult/TimelinePlan/QAResult）→ 等 G2/MMVV Known 通过 → 再统一 Orchestrator；"先稳定接口，再统一编排" |
| C8 | UI 判断 | 认可 | Workbench = 开发/审片工作台，非运营软件；兼容性未验证不得写 PASS；**不再开发新 UI** |
| C9 | Token | "以后处理" | **立即轮换/失效（今天做）**；仓库已公开 → 默认旧 token 已泄露，不判断有没有人看到 |
| C10 | 测试两问题 | 未强调 | ① test_claim_multiprocess rc=5/0 collected 必须修（测试基建问题）；② 逐文件绿 ≠ Integration；缺 G1→Discovery→G2→G3→Timeline→Render→Semantic QA 的自动 E2E 测试 |
| C11 | 仓库"报告仓库化"降噪 | P3 | reports ~40.5MB + assets ~22.7MB vs src ~1.7MB；大型 review PDF/图/HTML 应移 GitHub Release/evidence archive（P2/P3，不急） |
| C12 | 状态术语 | — | 动作按 EXTEND/RETRACT/DRAWER_OPEN/PUT_IN/SOCKET_INSERT **分别维护状态** |

## 2. TD02 重命名（裁决）
`TD02 "动作候选召回=0"` → **`TD02 VALIDATED ACTION SOURCE SHORTAGE`**（搜得到候选，缺的是"可靠证明候选动作是什么"的能力）。

## 3. MMVV Phase A 实验规格（裁决，冻结）
- 人工框 Known6 + ~20 高价值动作片段（TABLETOP/DRAWER/TRACK_SOCKET/PERSON），完全绕开 ROI semantic uncertainty；
- 测：正确 ROI → Camera Motion → Target Motion → Temporal State → Action Direction；
- 期望：89→EXTEND FAIL；52→DRAWER_OPEN PASS/strong；109→OPEN FAIL；51/1985/1986→EXTEND FAIL；
- 判定：若通过 ⇒ MMVV 后半段架构成立 → 再解决自动 ROI；若不通过 ⇒ 问题在 motion/temporal 逻辑本身，与 Qwen bbox 无关。
- 长期路线：Human ROI Calibration → 50–200 框 → 证明 target-motion pipeline → 再定 domain detector / Qwen region proposal+tracker / interactive fallback。

## 4. 修订后优先级（架构师版，取代 Harness Roadmap 顺序）
- **P0（现在）**：① Hub token 立即轮换（公开泄露假设）；② 语义 QA 去硬编码（TRUE→NOT_VERIFIED，matcher 接入前不允许 semantic PASS）；③ 修状态术语（VALIDATED_ACTION_PASS=0 + 按动作分桶）。
- **P1-A（先证明视觉链）**：④ 人工 ROI Calibration（Known6+20 难例）；⑤ Known6 达期望（89/52/109/51/1985/1986）。
- **P1-B（修真正生产链）**：⑥ G2/G3 per-action closure（不再用"动作素材缺失"大桶）；⑦ G5 Semantic QA 接真实结果（ClaimMatchResult/ActionValidationResult/StoryConsistencyResult/BeatAlignmentResult 全带 evidence ID）；⑧ G1 成为唯一 Production source gate（pick_clean 类仅 LEGACY）。
- **P1-C（再统一工程）**：⑨ DB migration baseline（88 表）；⑩ Runner 超时/孤儿/进度；⑪ 定义 Production Contracts；⑫ PipelineService。
- **P2**：Voice / BGM / RenderService 统一 / Workbench Production UI / Legacy archive / L3 表收敛（Voice/BGM 仍非 Critical Path）。

## 5. TreeCut 一句话重新定位（架构师版，取代 Harness 表述）
> TreeCut 现在是"**成熟度较高的素材/Truth 底座 + 正在验证中的 AI 视频生产决策层 + 已验证的技术渲染能力**"，还不是完整生产软件。

## 6. 第二阶段（源码级独立审计）待查清单
production_source.py / action_subclip.py / claim_visual.py / visual_beat.py / visual_understanding_v2.py / mmvl_master_v1.py / production_qa.py / b007_v091_v2.py / sprintv2_v11_* / production_workbench/server.py / production_narration.py / migrations / CI/tests。
输出：Harness 哪些结论=代码事实、哪些夸大、哪些遗漏，以及最终如何收敛为 TreeCut V1。

## 7. Git/可见性事实（2026-09-04 核验）
- 账号 `yuhao8977-stack`：public_repos=5，total_private_repos=0 → **5/5 仓库已全部公开**（treecut-v13 / treecut / xiaohongshu-note-reader / dsh-tools / dsh-desktop），无需再改可见性。
- 推论：未轮换 hub token 已在 GitHub 公开历史中 → 轮换为最高优先（P0，公开泄露假设）。
