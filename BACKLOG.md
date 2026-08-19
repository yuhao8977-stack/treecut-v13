# BACKLOG.md — TreeCut 全局规则与后续阶段需求登记

> 用途：记录「当前阶段不做、但已确认的新需求」与全局命名规则。
> 开发纪律：**一个阶段 = 一个明确目标 + 一套代码结构 + 一套验收标准 + 一条停止线。**
> 不得因为本阶段发现其他有趣功能而扩大任务范围；新需求写入本文件，本阶段不实施。

---

## 全局命名规则（2026-08-19 用户确认，所有阶段强制）

```text
B001/B002/.../B010  = 仅表示 account_id（账号编号）
TC_CONTENT_TAGS     = 内容运营标签体系（禁止出现任何账号编号）
CT01–CT12           = 内容模板（Content Template，替代旧 T01–T12 命名）
PRJ-xxxx            = 视频项目编号
asset_id            = 素材唯一身份
segment_id          = 镜头唯一身份
account_id          = 账号（素材默认 account_id=NULL，允许多账号复用）
```

架构解耦硬约束：
```text
Asset ≠ Account ≠ Template ≠ Project
一条素材允许被多个账号、多个模板、多个项目复用。
账号只在 projects 表出现（发布目标），绝不出现在标签/模型/模板/搜索命名中。
```

---

## 后续阶段需求（不在 P1.1 实施）

### P2 场景切分 + 关键帧 + ASR + OCR
- [ ] `src/treecut/scenes/` detector/segmenter/config
- [ ] `src/treecut/keyframes/` extractor/quality/selector
- [ ] `src/treecut/asr/` engine/faster_whisper_engine/transcript_store
- [ ] `src/treecut/ocr/` engine/subtitle_detector/text_store
- [ ] `segments` 表（segment_id, asset_id, scene_no, start_ms, end_ms, duration_ms, quality_score）
- [ ] `keyframes` 表（frame_id, segment_id, timestamp_ms, image_path, sharpness, brightness, selected）
- [ ] 关键帧策略：首/中/尾 + 清晰度最高 + 差异度最大，每 segment 2–5 张
- [ ] ASR：先 faster-whisper small，真实中文岛台口播 Benchmark 不足再 medium；raw + corrected 分离
- [ ] OCR：PaddleOCR/现有可靠中文 OCR，只对关键帧+必要抽样，禁止逐帧
- [ ] 所有 worker 必须接入 P1.1 should_process + processing_state，禁止绕过

### P3 成片/原片 + 重复识别 + TC_CONTENT_TAGS
- [ ] 成片/原片/半成品分类：字幕覆盖+切镜+BGM+口播+时长+片头尾，规则打分，不单独依赖 VLM
- [ ] 重复检测三级：exact hash → pHash → embedding similarity；禁止自动删除
- [ ] TC_CONTENT_TAGS 首批 40–60 个标签，分类：SCENE/STATE/FEATURE/ACTION/SHOT/PERSON/CRAFT/STYLE/USE_CASE
- [ ] `labels` 表：category/label/confidence/source(rule|model|human)/human_override；人工标签模型不得覆盖
- [ ] 动作标签必须结合多帧，不能单帧判断
- [ ] 100–200 条人工标注评估集

### P4 检索
- [ ] 混合检索：Metadata Filter → FTS5 → FAISS → Tag Rerank → Quality → Duplicate Penalty
- [ ] 复用已验证 BGE-M3 + FAISS，除非 Benchmark 证明不足再补视觉 embedding
- [ ] 排序权重：semantic 0.50 + tag 0.25 + quality 0.15 + text 0.10 − duplicate
- [ ] 20–50 条真实运营 Query 测试集；Top5 至少 2–3 可用

### P5 模板驱动（先 CT01/CT02）
- [ ] `content_templates` 表（template_id, name, version, content_goal, user_problem, duration, status）
- [ ] 模板 JSON 版本化；每个 slot：purpose/order/min-max duration/required_tags/preferred_tags/avoid_tags/semantic_query/shot_type
- [ ] 每 slot 返回 3–10 候选 + 推荐原因；用户 SELECT/BACKUP/EXCLUDE，AI 不得最终决定

### P6 人工选镜 + AI 排序 + 粗剪
- [ ] `project_segments` 表（project_id, template_slot_id, segment_id, rank, selection_status, 时间）
- [ ] AI 仅建议排序/时长/首3秒/重复提示，不可逆决定权在用户
- [ ] FFmpeg 输出 rough_cut.mp4 + timeline.json + cuts.csv + subtitles.srt，每片段可追溯 asset/segment/source/start/end
- [ ] V1 禁止：AI 配音/花字/特效/自动发布/自动封面/复杂 BGM
- [ ] Benchmark：真实记录找素材/选镜/粗剪/修正/总耗时，不预设改善数字

### P7 CT03–CT12 + 数据反馈闭环
- [ ] 扩展顺序（按价值）：CT03 → CT05 → CT06 → CT10 → CT11 → CT12 → CT04 → CT07 → CT08 → CT09
- [ ] `performance` 表 + 微归因（attribution_status；无法精准时不假装）
- [ ] 账号 × 模板表现分析（Performance 层，非标签层）

### UI 规划（9 页）
- [ ] 首页（总/新/已处理/未处理/失败/STALE/审核/重复）
- [ ] 素材库（缩略图/路径/时长/原片成片 + Scene/ASR/OCR/Vision/Labels/Embedding 状态列 + 筛选）
- [ ] 搜索 / 未处理素材 / 重复素材 / 标签审核 / 模板库 / 视频项目 / 粗剪

---

## P1.1 已完成/进行中的需求（跟踪）
- [x] Canonical Asset Registry = `assets`（内容身份，asset_id 稳定）
- [x] `asset_processing_state`（stage 级状态 + 版本 + 指纹 + 重试 + review）
- [x] `processing_history`（每次状态转移原因）
- [x] `asset_locations`（移动/改名追踪）
- [x] should_process 幂等（fingerprint+pipeline+model 一致且 DONE → SKIP）
- [x] Stage Dependency Graph + 局部 STALE
- [ ] 文件移动/改名不产生新 asset（扫描协调）
- [ ] 文件修改 → 下游 STALE
- [ ] Missing/Offline 不删历史数据
- [ ] 增量扫描 NEW/CHANGED/MOVED/MISSING/UNCHANGED
- [ ] 第二次扫描 UNCHANGED 不重复 Probe/AI
- [ ] 分层哈希：quick 优先，Full SHA256 仅疑似重复/高价值/后台
- [ ] 素材根目录配置项（不硬编码 C/Z 盘）
- [ ] UI/CLI 状态显示 + 筛选 + Dashboard 统计
- [ ] 真实测试 Test A–G + 一致性测试
