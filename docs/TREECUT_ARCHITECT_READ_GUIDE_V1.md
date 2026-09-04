# TreeCut 外部架构师读码指南 V1

> 配套文档：`docs/TREECUT_SYSTEM_MASTER_AUDIT_V1.md`（主审计，中文）
> 目的：让只凭 GitHub 源码 + 主审计报告的外部架构师，能最快建立正确心智模型，**不被历史文档/遗留代码误导**。

## 0. 三分钟结论
TreeCut = "素材 Truth + 半自动生产"系统，当前唯一业务 = B007 岛台（KUBON）。代码里有**两套都叫 production 的世界**：
- **Layer A（classic，历史桌面产品线）**：`src/treecut/application|cognitive|output|roughcut|ui|desktop.py` —— v12 时代延续，近期无真实成片证据。
- **Layer B（B007/STAGE8，当前主线）**：`src/treecut/services/{production_source,action_subclip,claim_visual,visual_beat,visual_understanding_v2,mmvl_master_v1,production_dedup,production_qa}.py` + `scripts/sprintv2_*.py` + `tools/production_workbench/` —— 全部由一次性脚本驱动，**没有统一编排器**。
真实成片（B007_FIRST_REAL_PILOT_V2.mp4）由 `scripts/b007_v091_v2.py`（monolithic、硬编码、**未走 G1/MMVV**）产出。

## 1. 按顺序读这些文件（先读主链再读细节）
1. `docs/TREECUT_SYSTEM_MASTER_AUDIT_V1.md`（本审计，先读 §00 第一屏 + §03 状态 + §05 架构）。
2. `docs/TREECUT_ROADMAP_MASTER_V1.md`（唯一主进度宪章：Stage0-10、G1-G6、PASS 标准）。
3. `src/treecut/services/production_source.py`（G1：生产源资格门；对比 `scripts/b007_v091_v2.py` 的 pick_clean —— 看"门没被所有取材路径用"）。
4. `src/treecut/services/action_subclip.py` → `claim_visual.py` → `visual_beat.py`（G2/G3 主链）。
5. `src/treecut/services/mmvl_master_v1.py`（MMVV，默认 SHADOW；看 `MMVVMode`/`ShadowGate`）。
6. `src/treecut/services/production_qa.py`（G5 15 项 check + P0 门禁）。
7. `src/treecut/output/production_narration.py` + `scripts/b007_v091_v2.py`（真实 TTS→SRT→ASS→ffmpeg→QA 的**唯一真实成片链**）。
8. `tools/production_workbench/server.py` + `index.html`（当前 UI：审阅 JSON 项目，非生产控制台）。
9. `src/treecut/services/canonical_truth.py`? 注意：真正的 L3 在 DB 表 `canonical_human_truth`（版本化 truth_version/is_current/supersedes）；别把 service 与表名混淆。
10. `configs/`、`src/treecut/config/production.py`（默认参数：TopK3/durations/caption 66/LUFS -14..-16/TP≤-1）。

## 2. 数据库（只读理解用）
- 单库 `materials.db`（WAL，88 表，2.16M 行）。
- **必看**：`b007_source_role_v1`（G1 主表：source_role/contamination 5 字段/review_status；注意 asset_type 全 NULL、role_confidence 0.5=路径先验）。
- 核心 L1：media_files / assets / segments / keyframes / ocr_text / transcripts。
- L3：canonical_human_truth(+history)、b007_l3_review16_v1。
- 空表群（设计未接）：production_plans/shot_usage/review_queue/duplicate_groups/visual_clusters…
- 迁移只到 0009；b007/spotlight/stage2 表**不在迁移历史**（schema 债）。
- 证据文件：`reports/storage/audit_evidence/_db_counts.json`、`ev_db_dist*.json`。

## 3. 测试怎么跑（避免踩坑）
- runtime python：`E:\树剪整理\02_安装程序\TreeCut_v13\runtime\python.exe`；设 `PYTHONPATH=src`。
- `-m pytest tests -q`：单次全量可能 >15min 卡（TD08）；建议逐文件跑或加超时。
- 真实媒体级测试只有 test_mmvl_real_media.py(13)/mmvl_r2(6+4xfail)；**410+ passed ≠ 生产可用**。
- xfail 集中在 mmvl_r2（R2_KNOWN_UNMET：语义 ROI 未解决）——是诚实外化的 blocker，不是"绿"。

## 4. 不要误判成主链的东西（重点防坑清单）
| 文件/目录 | 真实身份 |
| --- | --- |
| docs/01-36 升级任务、PHASE*/BRAIN/FRESH_HOLDOUT/UI_FIX 等 | 历史存档（v12→v13 迁移+早期阶段），非当前状态 |
| src/treecut/application|cognitive/production.py | Layer A 旧生产（近期无产物） |
| src/treecut/output/jianying.py + "支持剪映"表述 | pyJianYingDraft **可导入但审计期无真实草稿产物**；主链不用剪映 |
| src/treecut/services/{visual_cognition, static_vision_v2, semantic_action_v1/v2, temporal_action_v2, people_analyzer_v2} | 历史视觉代，被 visual_understanding_v2 / mmvl_master_v1 方向取代 |
| src/treecut/services/business_cognition_service/v2/v2_1 | 三代并存，最新 v2_1 |
| scripts/ 296 个 | 绝大多数一次性 runner；当前活动组 = sprintv2_*（Discovery/G2/G3/MMVV 证据流） |
| reports/storage/TREECUT_PROJECT_STATE_V1.json | **混合新旧，勿当唯一状态源**（以 MASTER AUDIT §03 为准） |
| reports/storage/*.mp4 | 已 gitignore（不入 GitHub）；看片需本地 |

## 5. 回答"它到底能不能"的核验路径
- 问"能用吗" → 追六层：代码存在 → import（ev_layerA_imports.json）→ 主链接通（grep caller）→ 测试（ev_tests.json）→ 真实数据（DB/帧/成片产物）→ 人工（L3/裁决 JSON）。
- 问"谁调用谁" → 在 `reports/storage/audit_evidence/ev_*` + §05.2 连接矩阵基础上自己再 grep。
- 问"MMVV/Discovery 到底行不行" → 读 sprintv2_mmv_r2.py 与 mmvl_master_v1.py 的 ShadowGate；看 Known6 六案例（TREECUT_MMV_KNOWN6_R2_V1.json）→ **全 UNSURE/FAIL，无 PASS，Enforcement 未批**。

## 6. 已知 P0（架构师复核优先级）
1. `配置子机连接.cmd` 曾含真实 hub token → **需在 hub 端轮换**（工作树已清）。
2. 语义 QA 在 b007_v091_v2.py L223-226 硬编码 True → 假 PASS 风险。
3. 动作候选召回 = 0 → G2/G3/成片无有效输入（素材缺口）。
4. MMVV ROI 方案 A/B/C 未决 → 不 Enforcement、不 Blind50。
