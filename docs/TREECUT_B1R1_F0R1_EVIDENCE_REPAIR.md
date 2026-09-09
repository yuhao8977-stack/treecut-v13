# TREECUT B1R1 F0R1 — CALL GRAPH + FULL-HISTORY EVIDENCE REPAIR
- **性质**：只修审计证据（只读，产品代码零改动）；保留原 F0 文件，F0R1 为新增交付。
- **基线**：HEAD = origin/main = `89c1d393b83b896964f80e96834f2e9e77d97b97`（clean）。
- 未开始 B2/C0/N1/GEOM/CAM。

## 修复的证据缺陷
1. **路径归一化**：`src/treecut/x.py -> treecut/x.py`；包 `__init__` re-export 解析
   （`from treecut.output import X` → 解析到 `output/narration.py` 等），不再出现 `treecut/treecut`。
   production import closure = **35 个 canonical 模块**；验证：
   - application/production.py / output/narration.py / output/mix.py /
     quality/publish_gates.py / quality/duration_contract.py /
     models/semantic_matching.py **import_reachable=true**（不再全 false）。
2. **全历史实跑**：每功能每个 token 实际执行并记录 `-S` 与 `-G` 与 `--name-status`
   （history.S/G 均有 ran=true 记录）；`src/tests/scripts/docs/reports/other` 分桶统计；
   内容 token 与**文件名/路径双搜索**（source_gate/CAM/old_subtitle 通过文件名
   production_source.py / mmvl_master_v1.py / production_qa.py 发现，不依赖内容 token）；
   记录 A/M/D/R。
3. **NEVER_IMPLEMENTED 措辞**：仅当 capability tokens 在可达历史 src 中
   **NOT_FOUND_IN_REACHABLE_GIT_HISTORY**（记录 refs=all、commit 数、路径范围、token）
   才派生；未把"未发现"表述为绝对证明。
4. **分类由证据生成**：rule_id + machine_inputs + derived_classification；
   人工裁决存于独立 `manual_adjudication/adjudication_reason` 字段，不覆盖机器结果；
   `import_reachable`（可 import）、`direct_callers`（文本调用方）、
   `runtime_executed`（本次运行是否执行）三者分开。

## 十项最终分类（机器派生 + 分离的人工裁决）
| id | derived_classification | 关键依据 |
|---|---|---|
| caption_display_punctuation | NEVER_IMPLEMENTED | display_text/caption_policy/strip_punctuation 在 src 可达历史 NOT_FOUND；build_srt 现把带标点 speech 原样写入（人工裁决补充：旧标点 token 仅在注释/文档） |
| subtitle_occlusion_plate | NEVER_IMPLEMENTED | drawbox/遮挡板/inpaint NOT_FOUND in src 可达历史；'occlusion' 仅注释/报告 |
| old_subtitle_detection | IMPLEMENTED_BUT_DISCONNECTED | production_qa.py（文件名发现）不在 production closure |
| caption_safe_zone | NEVER_IMPLEMENTED | safe zone/安全区 NOT_FOUND；仅固定 MarginV/Alignment |
| source_gate | IMPLEMENTED_BUT_DISCONNECTED | production_source.py 存在但不在 closure、零生产 caller |
| beat_claim | IMPLEMENTED_BUT_DISCONNECTED | visual_beat/claim_visual services，不在 closure |
| feedback_loop | IMPLEMENTED_ACTIVE | adjustments 在 production 非 override 分支；B1/B1R1 未执行（人工裁决：代码态 active） |
| semantic_selection | IMPLEMENTED_ACTIVE | semantic_scores 在 closure 非 override 调用；CLIP 缺陷 OPEN；样本未执行 |
| cam_mmvv_action | IMPLEMENTED_BUT_DISCONNECTED | mmvl/action services 文件名发现，不在 closure |
| plan_override_bypass | IMPLEMENTED_ACTIVE | plan_override 分支存在且被 B1/B1R1 使用 |

## SELECTION_ROUTE_BYPASSED（机器一致）
- B1/B1R1 均 media_id=32、0–25s、`plan_override=plan`（source_start=0/source_end=25，runner 代码证据）；
- B1R1 json `semantic_models bge_scored=0 / clip_scored=0`；B1 json 无该字段，
  依 runner plan_override + production override 分支（bge=clip={}）推导（已注明证据来源）；
- → B1/B1R1 是 SELECTION_ROUTE_BYPASSED，**不是智能选材复现**；Feedback/BGE/CLIP 仅反映
  非 override 分支的代码状态，不构成"样本实际执行过"。

## 最终字段
- F0_SUBSTANTIVE_FINDINGS = **ACCEPTED**
- F0_EVIDENCE_CLOSURE = **YES**
- SELECTION_ROUTE_BYPASSED = **YES**
- OLD_FEATURES_DELETED_PROVEN = **NO**
- B2_READY = **YES**（仅当 F0_EVIDENCE_CLOSURE=YES）
- NEXT_BLOCKER = **B2_CAPTION_SPEECH_DISPLAY_SPLIT_AND_OCCLUSION**

## 测试
tests/test_audit_treecut_b1r1_f0r1.py **9/9 PASS**（10 项唯一完整 / closure 非全 false /
四已知生产文件可达 / 文件名发现独立于内容 token / -S 与 -G 均有执行记录 /
分类非固定字典覆盖 / bypass 与 B1/B1R1 JSON 一致 / index sha 校验）。

## 交付
- docs/TREECUT_B1R1_F0R1_EVIDENCE_REPAIR.md（本文件）
- reports/storage/TREECUT_B1R1_F0R1_CALL_GRAPH.json
- reports/storage/TREECUT_B1R1_F0R1_GIT_HISTORY.json
- reports/storage/TREECUT_B1R1_F0R1_RESULT.json
- reports/storage/TREECUT_B1R1_F0R1_EVIDENCE_INDEX.json
- scripts/audit_treecut_b1r1_f0r1_forensics.py + tests/test_audit_treecut_b1r1_f0r1.py

commit/push/clean 后 STOP，等待架构师审核；通过后 B2 自动转 YES（范围：speech/display
分离去标点 + 原字幕检测 + 底部遮挡板 + 安全区 + 顶部/中部脏字拒绝 + 渲染后抽帧复验 +
保留 B1 三轨时长/响度回归）。
