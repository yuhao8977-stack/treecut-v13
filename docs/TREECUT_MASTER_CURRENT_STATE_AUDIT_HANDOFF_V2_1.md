# TREECUT MASTER CURRENT-STATE AUDIT & HANDOFF V2.1（EH02 D0 修正版）

- **性质**：READ-ONLY HANDOFF 修正包（supersedes V2 交接文件；**不改写 V2 历史文件**）
- **关联决策**：`docs/TREECUT_CAM01_EH02_NEG_POLICY_DECISION.md`（本 commit 冻结 NEG 政策，
  关闭 V2 P0）
- 基线 `c2bb7b6`（审计开始时 main/远端同步/工作树 clean）
- 机器对应：`TREECUT_MASTER_CURRENT_STATE_AUDIT_HANDOFF_V2_1.json`（全量）+
  `TREECUT_MASTER_CURRENT_STATE_EVIDENCE_INDEX_V2_1.json`（28 项）

## 0. V2 → V2.1 修正清单（对应架构师 10 项缺口）

1. evidence entry 数：V2 md 写 19 实为 18 → V2.1 以实际数组为准，**28 项**（md 与 JSON 一致）
2. tracked_size_mb：V2 JSON null → V2.1 写入真实值 **≈80.1 MB**（cat-file 重算）
3. git 状态拆分：`worktree_clean_at_start`(True) / `dirty_during_report_generation`(True,
   V2.1 文件生成中) / `final_clean` 仅在提交后最终回复报告
4. 风险表：md 与 JSON 同一 **6 项**完整表（P0×1 + P1×1 + P2×2 + P3×2，含 status_after_d0）
5. JSON 新增 `targeted_negative_candidates` 数组（**11 项**，recommendation only）
6. 候选仅记录推荐，不改变任何样本状态
7. `36_pair_table` 补齐：available_routes / transform provenance(ev family) / evidence_family /
   materialized / deterministic / local_agreement / selected_representative / visual_family /
   target_eligible / control_eligible
8. **视觉内容 family** 与**算法证据 family** 拆两字段两套定义（见 §4）
9. 8 个 STRONG 的 safe_emit / target_eligible / control_eligible 全量解释（见 §5）
10. 精度术语区分：matrix element max abs diff(<1e-3, artifact refit) vs grid disagreement
    (<1e-6, M1 deterministic) vs verdict/fingerprint equality(36/36 binary)
11. test_matrix：命令 + 类型（artifact-based, real_media=false）+ real-frame replay 如实标注
    **NOT_RERUN_IN_THIS_AUDIT**（M1 replay 真帧产物在 644c206）
12. evidence index 加入 router runner / 4 测试文件 / ROADMAP / HUMAN_REVIEW / ROUTER_FREEZE /
    NEG_POLICY_DECISION
13. eh01_to_eh02_changed → route_label_changed（本表字段；semantic/evidence 拆分见下注）
14. NEXT_BLOCKER = **TARGETED_NEGATIVE_REFERENCE_SET_DESIGN**（不执行）

（注：eh01→eh02 的 semantic_verdict_changed / evidence_changed 拆分需要逐 pair 的 R1 语义
verdict 与 evidence 变化源，超出本包 artifact 可直接证明范围 → 以 route_label_changed 为主，
semantic/evidence 变化以 V2 报告 §五 被纠正清单为准，不在此伪造逐 pair 归因。）

## 1. 政策冻结（详见 NEG_POLICY_DECISION.md，17 条）

核心：REFERENCE_STRONG ≠ POS 动作；router role-blind；NEG strong 允许；
**PRESENT = ≥1 NEG+target-valid+STRONG**（=2543，YES）；**ESTABLISHED = ≥3 不同
视觉内容 family** 且每样本 target-valid+STRONG+frame/ROI 人工复核（当前 NO，1 family）；
9697/21674 target-invalid 不得进 NEG control（target_eligible=false）；
≥3 family 不自动批准 GEOM。
`NEG_STRONG_POLICY_AUTHORITY = RESOLVED_BY_EH02_NEG_POLICY_DECISION`；
`SECTION_31_SOURCE_STATUS = NOT_FOUND`（不伪造）。

## 2. 8 个 REFERENCE_STRONG eligibility（全量）

| case pair | role | rule | safe_emit | target_eligible | control_eligible | evidence_family | global |
|---|---|---|---|---|---|---|---|
| 27433 7.246→10.352 | POS | S1 | ✓ | ✓ | – | FEATURE_LOCAL_ENSEMBLE(V24) | RELIABLE |
| 12095 7.416→9.64 | POS | S1 | ✓ | ✓ | – | FEATURE_LOCAL_ENSEMBLE(V24) | RELIABLE |
| 12095 9.64→12.607 | POS | S1 | ✓ | ✓ | – | FEATURE_LOCAL_ENSEMBLE(V24) | RELIABLE |
| 3571 4.299→6.142 | POS | S1 | ✓ | ✓ | – | SEMANTIC_DENSE_LK(DENSE) | UNRELIABLE |
| 3571 6.142→7.984 | POS | S1 | ✓ | ✓ | – | SEMANTIC_DENSE_LK(DENSE) | UNRELIABLE |
| 21674 1.201→2.803 | POS | S1 | ✓ | **✗** | – | FEATURE_LOCAL_ENSEMBLE(V24) | UNRELIABLE |
| 2543 1.202→1.717 | NEG | **S2** | ✓ | ✓ | **✓(唯一)** | FEATURE_LOCAL(GFTT) | RELIABLE |
| 9697 1.236→2.885 | NEG | S1 | ✓ | **✗** | – | FEATURE_LOCAL_ENSEMBLE(V24) | UNRELIABLE |

- POS strong target-valid 5 · POS target-invalid 1(21674) · NEG target-valid 1(2543) ·
  NEG target-invalid 1(9697)。8/8 safe_emit=true；非 STRONG 全部 safe_emit=false（检查通过）。

## 3. 36 pair 表（机器 JSON 全量 36 行）

route 汇总：STRONG 8 · PARTIAL 1 · PARTIAL_VETOED 11 · CONFLICT 2 · NO_EVIDENCE 14 ·
safe_emit 8 · case coverage 6/9。每行含：case/pair/role/route/rule/reason_code/
available_routes/selected_representative/evidence_family/materialized/deterministic/
visual_family(UNKNOWN)/target_valid/target_eligible/control_eligible/structural/symP90/
global_state/local_agreement/r1_route/route_label_changed/safe_emit。
两个 conflict：12095 5.191→7.416（GFTT↔DENSE）、25894 3.112→4.07（GFTT↔V24 + GFTT↔DENSE）。

## 4. Family 双定义（本包核心修正）

- **visual_content_family（视觉内容 family）**：样本多样性——源视频/场景/物体构成/拍摄/
  动作干扰类型。**需人工标注**；本包 36 pair + 11 候选的 visual_family 全部 **UNKNOWN**（不伪造）。
  政策：3 种算法验证同一视觉样本 ≠ 3 个视觉 family。
- **algorithmic_evidence_family（算法证据 family）**：GFTT/FEATURE_LOCAL、V24/
  FEATURE_LOCAL_ENSEMBLE、DENSE/SEMANTIC_DENSE_LK、GLOBAL/GLOBAL_CAMERA。**自动判定**。
  政策：V24 与 GFTT 同 FEATURE_LOCAL 证据链，不重复计。

## 5. 11 个 targeted NEG 候选（recommendation only）

1019 / 1025 / 103 / 1600 / 1638 / 1639 / 2163 / 2208 / 2211 / 2492 / 26023 —— 完整字段
（media_id/source/human_media_verdict/frame_roi_review_depth=UNKNOWN/visual_family=UNKNOWN）
见机器 JSON `targeted_negative_candidates`。**不改变样本状态，不执行。**
视觉 family 需人工标注后才知道是否凑够 3 个独立 family（不能默认）。

## 6. 一致性自动检查结果（13 项全 PASS）

36 行唯一 ✓ · route 总和 36 ✓ · safe_emit iff STRONG ✓ · NEG PRESENT=1(2543) ✓ ·
ESTABLISHED=false ✓ · 2543 control_eligible ✓ · 9697 control_eligible=false ✓ ·
21674 target_eligible=false ✓ · candidate=11 ✓ · risk=6 ✓ · evidence=28(md=JSON) ✓ ·
sha256 格式 ✓ · tracked_size 非 null ✓ · git 状态拆分字段 ✓

## 7. 风险（6 项，P0 已关闭）

| 级别 | 风险 | 状态 |
|---|---|---|
| P0 | §31/政策权威缺失 | **CLOSED_BY_NEG_POLICY_DECISION**（本 commit） |
| P1 | NEG control 1/3 family | OPEN（NEXT_BLOCKER 设计任务，不执行） |
| P2 | V23 REPORT.md stale | OPEN（历史不动，加横幅待批） |
| P2 | global 仅 state | OPEN（upper bound 0） |
| P3 | 本地 _tmp_*.py | OPEN |
| P3 | README 路径 stale(G vs E) | OPEN |

## 8. 输出与边界

- 本 commit 只新增 **4 文件**：NEG_POLICY_DECISION.md + V2_1.md + V2_1.json +
  EVIDENCE_INDEX_V2_1.json（生成脚本为临时工具，未提交）。
- secret scan / large-file scan 已执行（见最终回复）。
- NEXT_BLOCKER = **TARGETED_NEGATIVE_REFERENCE_SET_DESIGN**（本任务不执行）。
