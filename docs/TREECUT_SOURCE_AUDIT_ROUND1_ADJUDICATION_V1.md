# TreeCut 源码级独立审计裁决登记（Source Audit Round-1 Adjudication）

> 层级：HUMAN L3（append-only）
> 日期：2026-09-04
> 方式：架构师直接读取 GitHub `yuhao8977-stack/treecut-v13` main@`661f2b4` 源码，独立核验
> 裁决：**TREECUT_SOURCE_AUDIT = NEEDS_MAJOR_CORRECTIONS**
> 关联：docs/TREECUT_AUDIT_ROUND1_ADJUDICATION_V1.md（报告层裁决）；docs/TREECUT_SYSTEM_MASTER_AUDIT_V1.md（Harness 主报告）

## 0. 认可
大方向仍成立："较成熟素材/Truth 底座 + 正在验证的 AI 生产决策层 + 已验证的技术渲染能力"；非完整生产软件。

## 1. 源码发现与裁决表（15 项）
| 级 | 源码发现 | 裁决 |
| --- | --- | --- |
| P0 | b007_v091_v2.py：语义 QA 四项（CLAIM_SUPPORTED/ACTION_VISUAL_MATCH/STORY_ENTITY_CONSISTENT/BEAT_VISUAL_SYNC）硬编码 True | 立即去掉 |
| P0 | 同脚本：CLEAN_SOURCE/OLD_SUBTITLE_ABSENT/PLATFORM_WATERMARK_ABSENT 也初始化为 True | Source QA 亦未真正闭环 |
| P0 | ClaimVisualMatcher：`if claim.required_object and cd.object_ and ...`——candidate 对象证据为空时放行 | 语义 False PASS 漏洞；required_object 有要求+candidate 无对象 → REQUIRED_OBJECT_UNPROVEN，不得 PASS |
| P0 | ClaimVisualMatcher 默认 `eligible_check or (True,{})` = fail-open | 无 G1 gate → FAIL（fail-closed）；测试用显式 Mock Gate |
| P1 | ActionSubclipService 构造收 eligible_check 但 find_action_subclips 未调用 | G2 可绕过 G1；服务层强制：每个 mid 进 build_windows 前 is_production_eligible |
| P1 | MMVV R2 camera compensation：estimateAffinePartial2D(pa,pb)=prev→curr，却 warpAffine(b,Ma) 用 forward 变换对齐 current | 方向可疑；应 current→previous（inverse）；translation 方向需 synthetic 验证；可能是 residual 高的原因之一 |
| P1 | test_mmvl_r2 存在假绿：`test_affine_camera_motion_not_product_motion: assert True`；字段存在≠行为验证 | 410+/412+ PASS 需继续降权 |
| P1 | Visual Understanding V2：代码+单测存在，但 sprintv2_v2int 未把它作为 runtime 调起 | `INTEGRATED` 表述过强 → IMPLEMENTED+AUTOMATED_TESTED+DESIGN_MAPPED，非 MAIN_CHAIN_INTEGRATED |
| P1 | Workbench：renderCands 中 `ev` 未定义（ReferenceError）；replace 只传 media_id+subclip 导致候选 actions/object/eligible/evidence/path/source_role 全丢；trim 无真实边界校验（start<end/duration/覆盖 action window）；resolve_local 无素材根白名单 | 当前不能叫"稳定审片台" |
| P2 | visual_beat：5 Beat 设计 vs 实现（is_sep and len<4 → 最多 4 beat，CTA 常并入末 beat） | 4~5 Beat = DESIGN；实现 = PARTIAL |
| P2 | services/__init__.py "统一 bootstrap" 仍注册旧世界（cognition/knowledge/…/visual_cognition），无 Stage8 主服务 | 两套 Production 世界源码级坐实（C1） |
| P2 | migrations 仅 0002–0009 而运行库 88 表 | schema debt 实锤 |
| P2 | .github/workflows/ci.yml 存在但 661f2b4 无 workflow run/status | CI_CONFIG_EXISTS ≠ CI_VALIDATED |
| P2 | test_claim_multiprocess.py 核心逻辑全在 `if __name__=="__main__"` → pytest 0 collected rc=5 | 测试基建债；包成真 test 函数 |
| P2 | ShadowGate 默认 SHADOW ✅ 但 ENFORCEMENT 无代码锁（无 approval/flag/config/known-case/blind gate） | "Enforcement 未批准"仅是流程纪律 → 加 MMVV_ENFORCEMENT_ALLOWED=false + known/blind/version 门 |

## 2. G5 状态再修正（架构师源码版）
G5_TECHNICAL_CORE = **PARTIALLY_VALIDATED**（技术 QA 规则在，但 runner 曾硬编码 source 项）
G5_SOURCE_QA = **NOT_FULLY_VERIFIED**
G5_SEMANTIC_QA = **BROKEN / NOT_VERIFIED**
G5_OVERALL = **NOT_READY**

## 3. MMVV Phase A 顺序修订（A0 前置）
A0 修 Camera Transform + 真 synthetic 测试 → A1 Human GT ROI → A2 Known6 → A3 20 难例 → A4 决定自动 ROI。
理由：人工 ROI 对但相机补偿错，会把错误归因给 Motion。

## 4. 最短修复顺序（源码版，SOURCE AUDIT CORRECTION WAVE 范围 = 1–5 + 工作台/测试基建）
1. **Hub Token 立即轮换**（公开仓库历史泄露假设；需架构师 hub 端执行）
2. Pilot V2/任何 Production Runner 删除 Source/Semantic hardcoded PASS；无证据=NOT_VERIFIED；Semantic 未验证不得 READY
3. ClaimVisualMatcher fail-open→fail-closed；required object UNKNOWN → 不得 PASS
4. ActionSubclipService 真正调用 ProductionSourceService（eligible_check 不得只挂不用）
5. MMVV Camera Compensation 修复 + 真 synthetic 测试（translation/affine/zoom/方向）；删 assert True
6. Human GT ROI Known6 + 20 难例（A1，Wave 后）
7. Known6 通过后按 EXTEND/RETRACT/DRAWER_OPEN/PUT_IN/SOCKET_INSERT 分桶收敛 G2/G3
8. G5 QA 输入从裸 bool → 带 evidence_id/producer/version/support_status 的 typed result（Wave 后）
9. 冻结 Production Contracts 再统一 Orchestrator（Wave 后）
10. 最后 Workbench 产品化 / Voice / BGM

## 5. 状态更新（覆盖前文）
- Visual Understanding V2：~~INTEGRATED~~ → IMPLEMENTED + AUTOMATED_TESTED + DESIGN_MAPPED（非主链 runtime）
- CI：~~已验证~~ → CI_CONFIG_EXISTS（无 run）
- test_claim_multiprocess rc=5 根因：无 test_ 函数（代码在 __main__）
- "两套 Production 世界"：报告推论 → **Source Code Confirmed**（bootstrap 未含 Stage8 服务）

## 6. 第二阶段独立审计状态
SOURCE_CODE_INDEPENDENT_AUDIT = **ROUND_1_COMPLETE**
Harness Master Audit = 大方向正确；Round-1 Adjudication = 多数修正正确；源码新增 P0/P1 见 §1。
后续动作：SOURCE AUDIT CORRECTION WAVE（本文件配套的代码修复轮）→ 完成后回到 MMVV Human ROI Calibration（A0 先）。

## 7. SOURCE AUDIT CORRECTION WAVE 执行记录（2026-09-04，Harness 执行）
| 项 | 修复 | 验证 |
| --- | --- | --- |
| 1 Pilot 语义 QA 硬编码 | b007_v091_v2.py：CLAIM_SUPPORTED/ACTION_VISUAL_MATCH/STORY_ENTITY_CONSISTENT/BEAT_VISUAL_SYNC → NOT_VERIFIED；新增语义门（未验证→B007_PILOT_V2_SEMANTIC_NOT_VERIFIED，不再 READY_WITH_LIMITATIONS） | py_compile OK（未实跑：需素材/qwen） |
| 2 Pilot Source QA 硬编码 | source_qa_from_db()：CLEAN_SOURCE/OLD_SUBTITLE_ABSENT/PLATFORM_WATERMARK_ABSENT 改查 b007_source_role_v1（role+APPROVED+5×ABSENT→True，否则 NOT_VERIFIED）；P0 门含 NOT_VERIFIED→NEEDS_REPAIR | py_compile OK |
| 3 ClaimVisualMatcher fail-open | claim_visual.py：默认无门→NO_ELIGIBILITY_GATE 拒绝（fail-closed）；required_object 有要求但对象证据缺失/UNKNOWN→REQUIRED_OBJECT_UNPROVEN 硬闸 | test_g3 11 passed（+2 回归）；stage8 组全绿 |
| 4 G2 强制 G1 | action_subclip.py：find_action_subclips 无门→RuntimeError(NO_ELIGIBILITY_GATE)；逐 media 调 eligible_check 拦截 | test_g2 11 passed（+2 回归） |
| 5 MMVV 相机方向 | sprintv2_mmv_r2.py：translation warp 用 (-dx,-dy)（synthetic sign check：+shift 残差 24.9→错、-shift 7.2→对）；affine 用 invertAffineTransform(Ma)（rotation: inv 3.1 vs fwd 12.2） | test_mmvl_r2 9 passed+4 xfail（+3 真 synthetic 相机测试，删 assert True/弱断言） |
| 6 Enforcement 代码锁 | mmvl_master_v1.py：MMVV_ENFORCEMENT_ALLOWED=False + env 显式放行；ENFORCEMENT 未批准→ValueError | test_mmvl_r2 锁测试通过 |
| 7 Workbench bug | index.html：renderCands 定义 ev（原 ReferenceError）；server.py：replace 合并保留候选元数据、trim 真边界(0<=start<end<=ffprobe 时长, 缺时长拒绝)、resolve_local 素材根白名单（目录穿越→404） | py_compile OK；冒烟 GET / 200、穿越被拦 |
| 8 claim_multiprocess rc=5 | 逻辑移入 _run_concurrent_claim()+真 test 函数 | 1 passed（pytest 可收集） |
| 9 全量回归 | 有界逐文件（ev_tests.json 覆盖） | **~420 passed / 4 xfailed(诚实 R2_KNOWN_UNMET) / 0 failed** |
| 10 CI | 发现 runs 全部 0s failure 无日志（CI_CONFIG_EXISTS+CI_RUNS_ALL_FAIL）→ 属账号/工作流层，不在代码轮内 | gh run list 证据 |
遗留（Wave 外，按架构师顺序后续）：Hub token 轮换（需 hub 端）；A0→A4 ROI 校准；G2/G3 per-action closure；G5 typed result；Production Contract；Orchestrator。
