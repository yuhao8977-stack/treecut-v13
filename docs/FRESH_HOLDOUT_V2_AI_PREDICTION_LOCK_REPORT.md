# FRESH_HOLDOUT_V2 AI PREDICTION LOCK REPORT

> 状态：**Bundle V2 provenance 已修复 + V2 FIRST-PASS EXAM 完成（30/30 原子锁）**
> 日期：2026-08-29
> 纪律：未评分 / 未开始 Human Review / 未进 Phase4 / 未全量 41814

---

## STEP 0：Provenance Audit（Git 证据）

**结论：情况 B —— 旧 Lock provenance 错误，已重新生成。**

Git 证据：
- `c4ff7e5`（Stage3 MINI18 POST-REVIEW）：`people_analyzer_v2.py` 为**旧逻辑**（`if hits: → SigLIP fallback`），**不含** NORMAL_YOLO_NO 修复（`ran`/合法 NO 不存在）
- `813fc5a`（Stage3 FINAL CONSOLIDATION）：才包含 `ran`/`合法 NO` 修复（YOLO 正常运行无 person = 合法 NO，不 fallback SigLIP）

→ 旧 Lock 记录 `git_code_commit=c4ff7e5` 与实际 Inference 代码（813fc5a）不一致，**必须修正**。
旧 Lock（sha `01b7afa9…`）已标 **SUPERSEDED_PROVENANCE_LOCK** 保留（`VISION_MODEL_BUNDLE_V2_LOCK_SUPERSEDED_01b7afa9.json`）。

---

## STEP 1：最终 Bundle Identity ✅

| 项 | 值 |
|---|---|
| bundle_id | VISION_MODEL_BUNDLE_V2 |
| **inference_git_commit** | **`813fc5aa578dee55ba0cac8c61d5092859bd555a`** |
| packaging_commit | 813fc5a |
| stage3_dev_snapshot_sha256 | `59b6d52777a5ec7f37094953860b32f05bae2e3bb9f8a866a802d8c015932e29` |
| dictionary_version | ANNOTATION_DICTIONARY_V2_1 |
| people model | YOLOv8n (person=0)，**threshold 0.70** |
| component/function policy | V2（Top3+gap0.10+min0.02） |
| material/shot_role policy | V1（threshold 0.06） |
| semantic_action | SemanticActionRouterV2（per-action） |
| **bundle_lock_sha256** | **`a87d31246066bf8c6b0b1410d7e0b3598d626dfd2163274de5b1a77ef3871852`**（64 位，重算自洽） |

---

## STEP 2：Holdout V2 题目未变化 ✅

- **manifest_sha256 仍 = `27f751ed402f81e2c3477341ad562218f2b67cf1902c764d5735397767d9e64b`**（未重新挑题/未替换 segment）
- 30 unique segment / RANDOM 10 / HARD 10 / GAP 10

## STEP 3：污染检查 ✅

- Holdout V2 30 段 vs Cal333/Stage3/Mini18/HoldoutV1 Human Truth intersection = **0**
- `fresh_holdout_human_review_v1` 表对 V2 30 段：**0 rows / 0 truth**

---

## STEP 4-5：V2 FIRST-PASS EXAM（30/30 原子锁）✅

- 使用唯一 Bundle V2（lock sha `a87d3124…`），一次性完整推理，**未看前几题结果调整**
- 每段保存两层：`final_routed_prediction`（9 字段冻结 route）+ `raw_provider_evidence`（YOLO/SigLIP/ASR/OCR/Motion/SemanticAction V1/V2）
- 输出：`HOLDOUT_V2_AI_PREDICTIONS_V1.json`（含 bundle/manifest/inference identity）

## STEP 6：People 字段验证 ✅

- **30/30 全部 `provider=yolo`**；`fallback_used=FALSE` 全 30
- **NORMAL_NO_FALLBACK_VIOLATIONS = 0**（YOLO 正常运行无 person → NO，未 fallback）
- tech_fallback_count = 0（无技术失败）

## STEP 7：Semantic Action 纪律 ✅

- Router 保护生效：**OPEN_CABINET / RETRACT（NO_CLAIM）未出现在任何 routed prediction**；OPERATE_SOCKET / OPEN_SINK_COVER（INSUFFICIENT）未输出
- 输出动作限于：OTHER / CLOSE_CABINET（V2 exp）/ OPEN_DRAWER（V1）/ CLOSE_DRAWER（V2 exp）/ PULL_OUT（V1）

## STEP 8-10：原子锁 ✅

- staging 30/30 成功，schema/identity/bundle/manifest 校验全过
- **FRESH_HOLDOUT_V2_PREDICTION_LOCK.json**：AI_PREDICTION_COUNT=30 · PREDICTION_LOCKED=TRUE · DO_NOT_REPREDICT=TRUE · DO_NOT_TRAIN=TRUE · DO_NOT_CALIBRATE=TRUE · HUMAN_REVIEW_STARTED=FALSE
- **prediction_sha256 = `4b53b0c0f46c9ee2560e100fe2e275cbe6ba82ed30a5354b4a8d1286cfb68f66`**（64 位）

## STEP 12-13：Blind Review 准备 ✅

- Review Center 新增 **FRESH_HOLDOUT_V2**（Bundle V2 未见样本盲审 30 条，blind=True）
- 显示：题号 / RANDOM-HARD-GAP / 视频 / segment 事实 / 完整 V2.1 表单 / confidence / status / comment
- 隐藏：一切 AI prediction / provider / score / YOLO / SigLIP / semantic action / evidence / routing / bundle output
- **Blind UI 泄漏测试 PASS**（2 项：术语 + 具体答案值零泄漏）

---

## 16 问答复

1. **最终 Inference commit？** → `813fc5aa578dee55ba0cac8c61d5092859bd555a`
2. **为什么旧 Lock 记录 c4ff7e5？** → Final Consolidation 脚本初版误用了 Mini18 提交；Git 审计确认 c4ff7e5 无 People 修复
3. **是否重新生成 Bundle Lock？** → **是**（旧 `01b7afa9…` 标 SUPERSEDED_PROVENANCE_LOCK，保留未删）
4. **最终 bundle_lock_sha256？** → **`a87d31246066bf8c6b0b1410d7e0b3598d626dfd2163274de5b1a77ef3871852`**
5. **Holdout V2 manifest hash？** → **仍 `27f751ed…`**（题目未变化）
6. **Human Truth 在 AI 考试前严格为 0？** → **是**（0 rows / 0 truth）
7. **Prediction 30/30？** → **是**
8. **失败/重试？** → 首次运行 schema 校验失败（脚本漏 people_presence 键，30/30 推理本身成功），修复后重跑一次 30/30 通过 —— **推理无失败，仅脚本字段 bug 修正**
9. **prediction_sha256？** → **`4b53b0c0f46c9ee2560e100fe2e275cbe6ba82ed30a5354b4a8d1286cfb68f66`**
10. **People NORMAL_NO_FALLBACK_VIOLATIONS？** → **0**（30/30 YOLO，无违规）
11. **30 条是否相同 Bundle/Prompt/Policy/Threshold/Route？** → **是**（唯一 Bundle V2 lock `a87d3124…` 全程）
12. **PREDICTION_LOCKED？** → **TRUE**
13. **DO_NOT_REPREDICT？** → **TRUE**
14. **Human Review 仍 0/30？** → **是**
15. **Blind UI 零 AI 泄漏？** → **是**（术语 + 答案值测试 PASS）
16. **是否可以让用户开始盲审？** → **是**（等待用户放行后开 FRESH_HOLDOUT_V2 30 条）

---

## 产物

- `VISION_MODEL_BUNDLE_V2_LOCK.json`（新，sha `a87d3124…`）+ `VISION_MODEL_BUNDLE_V2_LOCK_SUPERSEDED_01b7afa9.json`（旧保留）
- `STAGE3_FINAL_DEV_SNAPSHOT.json`（sha `59b6d527…`）
- `HOLDOUT_V2_AI_PREDICTIONS_V1.json`（30 条双层）
- `FRESH_HOLDOUT_V2_PREDICTION_LOCK.json`（sha `4b53b0c0…`）
- `FRESH_HOLDOUT_V2_MANIFEST_LOCK.json`（未变，`27f751ed…`）
- Review Center 接入 FRESH_HOLDOUT_V2 盲审任务
- 测试：consolidation 12 + blind_ui 2 全过
