# TREECUT B1R1 F0 — HISTORICAL FEATURE FORENSICS + PRODUCT CONTRACT FREEZE
- **性质**：只读 Git 全历史取证；产品代码零改动；未开始 B2/C0/N1/GEOM/CAM。
- **基线**：HEAD = origin/main = `6fc5e6fad5a36382277ecae3c46a7947923bae5e`（6fc5e6f，clean）；仓库 308 commits / 2 branches / 2 tags；
  关键 commit 11887df、02c1fc8、cec8040、ced26b6、0c95e5c、f378fda、HEAD 全部存在。
- **方法**：git log --all --full-history -S/-G 逐 token 取证 + HEAD grep + E 安装对照 + production import closure。

## 功能最终分类
| 功能 | 分类 | 核心证据 |
|---|---|---|
| 显示字幕去标点 (speech/display 分离) | **NEVER_IMPLEMENTED** | no display_text layer ever; build_srt/split_subtitle_cues write speech text verbatim (punctuation kept); publish_gates requires script punctuation and |
| 原字幕遮挡板 (drawbox/occlusion/plate) | **NEVER_IMPLEMENTED** | drawbox / 遮挡板 / inpaint never present in any src file (HEAD grep none; history none in src); the only 'occlusion' hits are the B1R1 status-note string |
| 原字幕检测/卫生 (old_subtitle/hygiene) | **IMPLEMENTED_BUT_DISCONNECTED** | services/production_qa.py (repo HEAD) historically touched OLD_SUBTITLE_ABSENT / 原字幕 semantics; its only consumer is desktop.py (QA center), NOT the c |
| 字幕安全区/字号行数 (safe zone/MarginV) | **NEVER_IMPLEMENTED** | only fixed style params in burn_subtitles (FontSize=19, MarginV=75, Alignment=2); no explicit 1080x1920 safe-zone/coordinate contract, no line-length/ |
| 干净生产源门 (source gate) | **IMPLEMENTED_BUT_DISCONNECTED** | services/production_source.py + test_g1_source_gate exist; zero callers in application/desktop/api; classic matching uses only the eligible flag; sour |
| Beat/Claim 拆解 | **IMPLEMENTED_BUT_DISCONNECTED** | services/visual_beat.py + claim_visual.py + tests (test_g2_action_subclip/test_g3_claim_visual) exist in repo research layer; absent from application/ |
| 人工反馈消费 (FeedbackStore) | **IMPLEMENTED_ACTIVE** | FeedbackStore.adjustments() consumed in production non-override branch (match ordering) plus desktop/api paths; limitation: no before/after ranking co |
| BGE/CLIP 语义选材 | **IMPLEMENTED_ACTIVE** | semantic_scores (BGE/CLIP) live in production import closure and run in the non-override branch; Chinese-CLIP defect OPEN ('BaseModelOutputWithPooling |
| CAM/MMVV/动作证据生产接线 | **IMPLEMENTED_BUT_DISCONNECTED** | services action/MMVL/visual modules (action_subclip, mmvl_master_v1, visual_understanding_v2, temporal_action_v2 ...) exist as shadow/research with te |
| plan_override 绕过智能选材 | **IMPLEMENTED_ACTIVE** | plan_override branch exists in production.py and was used by B1/B1R1 runners (media_id=32, source 0-25s, match_score/terms are test stubs; bge/clip=0) |

## 逐功能细节（详见 GIT_TIMELINE / CALL_GRAPH JSON）
1. **字幕显示去标点（speech/display 分离）→ NEVER_IMPLEMENTED**：任何历史与 HEAD 的 src 中都不存在 display_text 或去标点逻辑；
   build_srt/split_subtitle_cues 把带标点 speech 原样写入显示字幕；publish_gates 的 LAST_SUBTITLE_INCOMPLETE 甚至强制显示字幕带标点
   （本次 22 cue 中 21 条带逗号/句号，即系统性代码行为）。要求仅存在于报告/待办。
2. **原字幕遮挡板 → NEVER_IMPLEMENTED**：src 全历史与 HEAD 均无 drawbox/遮挡板/inpaint；production.py 中的 'occlusion' 仅是 B1R1
   状态 note 文本；burn_subtitles 仅 subtitles= 滤镜 + 固定 MarginV。
3. **原字幕检测/卫生 → IMPLEMENTED_BUT_DISCONNECTED**：services/production_qa.py 历史含 OLD_SUBTITLE_ABSENT/原字幕 语义，
   唯一消费者 desktop.py（QA 中心），经典渲染链不调用。
4. **字幕安全区 → NEVER_IMPLEMENTED**：仅 FontSize/MarginV/Alignment 固定参数，无显式 1080×1920 安全区契约、行长/两行门。
5. **干净源门 → IMPLEMENTED_BUT_DISCONNECTED**：services/production_source.py + test_g1_source_gate 在仓库研究层，
   application/desktop/api 零 caller；classic matching 仅用 eligible 标志。
6. **Beat/Claim → IMPLEMENTED_BUT_DISCONNECTED**：services/visual_beat.py、claim_visual.py + G2/G3 测试存在；
   production import closure（27 模块）不含任何 beat/claim。
7. **Feedback 消费 → IMPLEMENTED_ACTIVE（受限）**：FeedbackStore.adjustments 在 production 非 override 分支读入排序，
   无 before/after 反事实证据，仅软排序影响。
8. **BGE/CLIP 语义选材 → IMPLEMENTED_ACTIVE（未达标）**：semantic_scores 在生产闭包、非 override 分支运行；
   Chinese-CLIP `.norm` 缺陷 OPEN（clip_scored=0）；B1/B1R1 样本未运行本路径。
9. **CAM/MMVV/动作证据 → IMPLEMENTED_BUT_DISCONNECTED**：services action/MMVL/视觉 Shadow 模块 + 测试存在，
   无经典生产 caller。
10. **plan_override 绕过 → IMPLEMENTED_ACTIVE**：B1/B1R1 均复用 media_id=32、同源 0–25s、plan_override，
    match_score/terms 为测试桩；bge/clip=0 → **SELECTION_ROUTE_BYPASSED**，不得称智能选材复现。

## 结论（对“旧代码去哪了”的定案边界）
- 证据支持：字幕无标点/遮挡板/安全区 = **从未实现**（不是被删）；原字幕检测、源门、Beat/Claim、CAM/MMVV 能力 =
  **已实现但未接经典生产链**（Layer B / services / Shadow，production import closure 不含它们）。
- 同步文件（B0 后 221/221 E_CONTENT_EQ_HEAD）不等于接通调用关系；两套生产体系问题仍在。
- 未发现可证明“某实现被删除/覆盖”的 commit；若后续要精确到函数级 OVERWRITTEN/DELETED，需再按单文件全历史 blame 展开。

## 契约冻结（F0_PRODUCT_CONTRACT_FREEZE.json，后续唯一产品契约）
speech_text 保留标点 / display_text 默认无标点（保护小数/版本/百分比/型号/URL 内部符号，禁止朴素删点）；
DISPLAY_PUNCTUATION_FORBIDDEN/COUNT/EMPTY 硬闸；底部稳定原字幕 → 遮挡板（按区域定高+边距+高不透明）后重绘新字幕；
顶部/中部多区动态文字 REJECT_DIRTY_TEXT（fail-closed 换镜头）；水印 allowlist；SUBTITLE_HYGIENE_NOT_RUN 永不 PASS；
遮挡后抽帧复查（旧字不可读/新字存在/主体未被遮）；plan_override 运行一律 SELECTION_ROUTE_BYPASSED；
PUBLISH_READY=false 交付命名带 NOT_PUBLISHABLE/明确测试目的。

## 交付
- docs/TREECUT_B1R1_F0_HISTORICAL_FEATURE_FORENSICS.md（本文件）
- reports/storage/TREECUT_B1R1_F0_GIT_TIMELINE.json
- reports/storage/TREECUT_B1R1_F0_CALL_GRAPH.json（含 final classification + selection_route）
- reports/storage/TREECUT_B1R1_F0_PRODUCT_CONTRACT_FREEZE.json

只读取证完成；commit/push 审计产物后 STOP，等待架构师审核后批准 B2。
