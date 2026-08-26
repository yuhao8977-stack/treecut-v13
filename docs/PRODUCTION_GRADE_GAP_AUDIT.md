# TreeCut 生产级架构差距审计（PRODUCTION_GRADE_GAP_AUDIT）

> 日期: 2026-08-25 | 模式: 只读审计（未修改任何代码/数据库/配置）
> 方法: 源码逐行核查 + 数据库实时统计 + git 历史交叉验证
> 结论粒度: 每项 YES / PARTIAL / NO，附代码文件/函数/表/字段实证

---

# A. 数据与数据库

## A1. assets=22465 vs media_files=28096 职责与 Canonical

**结论: `assets` 是 Canonical Asset Source of Truth。**

| 项 | 值 |
|---|---|
| assets | 22465（asset_id 主键，仅视频） |
| media_files | 28096（发现的所有文件，含图片 4782/音频 3/视频 23311） |
| media_files 无 assets 关联 | 5631（图片/音频未建资产） |

**模块 → 表 → ID 引用矩阵（实证）：**

| 模块 | 表 | ID 字段 |
|---|---|---|
| cognitive/production.py `_asset_pool` | content_classification JOIN assets JOIN media_files | c.asset_id / a.media_id / m.id |
| cognitive/brain.py / industry.py | transcripts/ocr_text/segments/keyframes | asset_id |
| cognitive/vision.py `enrich_asset` | keyframes | asset_id |
| cognitive/value.py `_get_features` | content_classification/scene_semantics | asset_id |
| workflow/matching.py `load_candidates` | media_files JOIN analysis_jobs | m.id (media_id) |
| roughcut/engine.py `_resolve_segment` | segments JOIN assets JOIN media_files | segment_id → asset_id → media_id |
| library/* (任务系统) | analysis_tasks | asset_id |

**发现: 新旧两套链路并存**——认知系统(asset_id) 与 P4检索/roughcut(media_id/segment_id) 使用不同 ID 体系。

## A2. 同一物理视频是否拥有多个 asset/media 身份

**结论: PARTIAL（有重复检测机制，但身份模型不统一）**

- `fingerprint_quick` / `fingerprint_full`（assets 表）—— 存在，但 **asset_processing_state fingerprint 阶段 DONE=0**（从未执行）
- `duplicate_groups` 表：**0 行**（从未运行去重）
- `asset_locations` 23311 行 = media_files 视频数，每视频一条
- P1.1 有去重设计（test_p1_migrate），但当前库 **duplicate_groups=0** → 无法证明"无重复"，仅能说"未检测出重复"

## A3. segments 生成方式与时长分布

**结论: 混合（ContentDetector 优先 + 固定 5s 兜底），非纯 scene 级。**

实证（segments 表 41814 行）：

| 指标 | 值 |
|---|---|
| 平均时长 | 4.19s |
| 中位数 | 5.0s |
| P10 | 2.0s |
| P90 | 5.0s |
| 每 asset 平均最大 scene_no | 0.87 |
| scene_no=1 的 asset | 9635 (43%) |
| 单段 asset | 8716 |

代码实证: `scenes/detector.py` — ContentDetector(threshold=27) 检测，失败/不可用回退均匀分段。**5s 聚集强烈提示大量素材走了固定兜底**（P9 批量场景降级提交 73b53a4 记录）。

## A4. 生产模块调用 asset_id 还是 segment_id

**结论: 两套生产链路使用不同粒度：**

| 模块 | 粒度 | 函数 |
|---|---|---|
| cognitive/production.py（Phase5 生产） | **asset_id**（整素材截取前 3-15s） | `_pick_slots`/`_build_edit_plan` |
| roughcut/engine.py（P6 粗剪） | **segment_id** | `_resolve_segment`/`build` |
| workflow/matching.py（P4 检索） | **media_id** | `match_materials` |
| sort_advisor.py | segment_id | `project_segments` |

**Phase5 生产不经过 segment 粒度**（槽位直接选 asset 头部片段），P6 粗剪才用 segment。

## A5. content_classification=140 vs content_value=22465

**结论: 22325 条价值评分基于"无认知分类的兜底分"。**

代码路径实证（value.py）：
- `_get_features()` → content_classification 无行 → `content_type=""`
- `TYPE_BASE[""] = 30` → 基准 30 分
- `_score_dims()` 中仅 ASR/OCR 关键词加分（KEYWORD_HINTS）与惩罚逻辑生效
- 因此 22325 条分数 = 30×权重拆分 + 关键词分，**无内容类型锚定、无元素加分**

## A6. scene_semantics 覆盖率

**结论: PARTIAL（覆盖率极低）**

| 维度 | 数量 | 覆盖率 |
|---|---|---|
| 覆盖 asset | 141 | **0.63%** (141/22465) |
| 覆盖 segment | 0（segment_id 全为 NULL） | 0% |
| 覆盖 keyframe | 不适用（表无 keyframe_id 字段） | - |

表结构实证: `scene_semantics(asset_id, segment_id NULL 全空, semantic, action, lens_value, confidence, model_version)`。语义只挂在 asset 级，**无 segment 级语义**。

---

# B. 认知系统

## B7. segment 是否拥有 11 个认知字段

**结论: NO（segment 级认知字段全部缺失）**

| 字段 | 有/无 | 来源 | 存在位置 |
|---|---|---|---|
| scene | NO（仅 scene_no 编号） | - | segments.scene_no |
| product | NO | - | - |
| material | NO | - | - |
| function | NO | - | - |
| action | PARTIAL | - | scene_semantics.action（asset 级，全空串） |
| shot_type | NO | - | - |
| people | NO | - | - |
| quality | PARTIAL | - | segments.quality_score（**全部=0**） |
| content_role | NO | - | - |
| business_value | NO | - | - |

**核心缺失: 认知结果全部挂在 asset/content_classification 级，segment 级无任何语义字段。**

## B8. CLIP 输入粒度与动作识别

**结论: 输入=keyframe（每 asset 前 3 帧）；无时间序列/动作识别。**

- `vision.py enrich_asset`: `SELECT image_path FROM keyframes WHERE asset_id=? ORDER BY timestamp_ms LIMIT 3`
- `understand_frames`: 单帧独立零样本分类，聚合 `_aggregate`（按标签去重）
- **没有**帧间差分、光流、时序建模、动作识别代码。**明确回答: 无动作识别。**

## B9. "桌面关闭→拉出→展开"伸缩动作能否识别

**结论: NO（基于现有代码能力明确回答）**

- 无 ASR/OCR → 文本信号为零
- CLIP 仅对 3 帧静态图像做场景/产品/材质/功能标签分类
- 功能标签虽含"岛台伸缩功能"，但**单帧无法判断"伸缩动作发生"**（需要多帧时序）
- 现有代码无光流/帧差/视频级分类 → **不能识别伸缩动作**

## B10. confidence gate（低成本→强模型分层）

**结论: NO（不存在）**

- 无"低置信度触发强模型"的调度逻辑
- CLIP 固定对每素材 3 帧跑（vision.py），无按置信度分支
- ASR/OCR/场景 各阶段独立固定执行，无动态降级/升级
- **明确回答: 无 confidence gate。**

---

# C. 检索与自动选材

## C11. 脚本理解调用链

**结论: 关键词匹配 + 领域词扩展 + BGE/CLIP 重排（组合，无 LLM）**

调用链（workflow/matching.py）：
```
match_materials(query, candidates, domain_terms, bge_scores, clip_scores)
  → _terms() 中文 2/3/4-gram 切词
  → domain_terms 领域词扩展 query
  → 逐素材 6 字段匹配（speech/vision/objects/filename/category/tags）
  → base_score = 0.65*coverage + 0.12*source_weight + 0.02*len(matched)
  → BGE-M3 重排 (bge_score-0.90)*1.2, 上限+0.12
  → CLIP 重排 (clip_score-0.15)*0.35, 上限+0.08
  → learning_adjustment
```

**明确回答: 无 LLM 参与脚本理解。** 注意：Phase5 production.py 的 `_asset_pool` **完全不解析脚本**（只按 content_type 取池），与 P4 matching 是两条独立链路。

## C12. production.py 槽位选材评分公式

**结论: 单一启发式分数，非语义匹配。**

`_asset_pool` 评分公式（production.py L143）：
```
score = keyframes数×2 + segments数 + confidence×10
```
槽位选材（`_pick_slots`）：从按 score 排序的池中**顺序取第一个未用素材**，角色不参与匹配（role 仅作 narration_hint）。

**槽位与素材无语义关联**——"卖点拆解"槽位可能选到任意产品素材。

## C13. Top-K 候选镜头

**结论: PARTIAL**

- P4 matching.py: `limit=12` Top-K ✅，返回排序结果
- P6 roughcut: project_segments 有 rank/selection_status（selected/backup）→ 多候选 ✅
- **Phase5 production.py: 只取第一名**（`for asset in pool: if asset_id not in used: chosen=asset; break`）→ 无 Top-K ❌

## C14. continuity_score（镜头连续性）

**结论: NO（六项全部不存在）**

| 连续性维度 | 有/无 |
|---|---|
| 场景连续 | NO |
| 人物连续 | NO |
| 产品连续 | NO |
| 色调连续 | NO |
| 动作连续 | NO |
| 景别变化 | NO |

无任何 continuity/sequence 评分代码（grep 确认 roughcut/planning/matching 均无）。

## C15. global sequence optimization

**结论: NO**

- production.py: 每个槽位独立取最高分素材（顺序贪心）
- roughcut: 按 slot_order 固定排序渲染
- **无全局序列优化**（如 Viterbi/DP 组合优化）

---

# D. 重复镜头

## D16. segment 被哪些生产视频使用

**结论: NO（无记录）**

- production_plans 只有 plan_json（含 asset 级 picks），**无 segment 使用明细表**
- project_segments 表**不存在**于当前库（grep 确认仅 roughcut 代码引用，建表未执行或已删除）
- 无法回答"segment X 被哪些成片用过"

## D17. 跨视频 reuse cooldown

**结论: NO（无冷却机制）**

## D18. 近重复视频识别（pHash/CLIP embedding/visual_cluster）

**结论: PARTIAL**

| 机制 | 有/无 | 实证 |
|---|---|---|
| pHash | PARTIAL | assets.fingerprint_quick/full 字段存在，但 fingerprint 阶段 DONE=0（未执行） |
| CLIP embedding | PARTIAL | search/embedding.py BGE-M3 建 segment embedding（embedding stage DONE=17211），非视觉 |
| visual_cluster | NO | 无聚类表/代码 |
| duplicate_groups | 空表 | 0 行 |

## D19. 已生成视频重复率统计

**结论: 无法统计（无数据基础）**

- 自动生成视频仅 2 个（production_plans: 客户案例001 draft_ready、产品介绍001 rendered）
- 无 segment 使用记录 → 无法计算重复 segment 率/asset 率
- 无视觉近重复检测 → 无法计算近重复率
- **明确说明: 无法统计。**

---

# E. 声音/字幕/BGM/时间线

## E20. narration.wav 是否真实 TTS

**结论: YES（真实 TTS 合成）**

- `output/narration.py`: `from treecut.models.tts_local import synthesize`
- tts_local.py: sherpa_onnx OfflineTtsVitsModelConfig（onnx + tokens.txt + lexicon）
- 实证: 产品介绍001/narration.wav **176,478 字节**（非 2 秒静音占位——静音占位仅当 TTS 失败时生成）
- 生产输出文件清单: narration.wav / bgm.mp3 / narration.srt / preview.mp4 / jianying_draft 全存在

## E21. 声音克隆模型

**结论: NO（不存在声音克隆）**

- tts_local 只有标准 VITS-TTS，无 cloning/说话人微调
- 无声音克隆模型、无依赖、无 GPU 需求、无输入输出规格（**明确回答: 不存在**）

## E22. 字幕来源与 word-level timestamp

**结论: PARTIAL**

- 字幕来源: `split_subtitle_cues()`（narration.py L70）按字符数/标点切分脚本文本 → **来自脚本，非 ASR**
- narration.srt 实证内容: **空文件**（产品介绍001 生成时无脚本文本传入）
- **word-level timestamp: NO**（无 whisper word_timestamps 使用，仅 cue 级切分）
- P4 链路的 speech.segments 有起止时间（句级），非 word 级

## E23. BGM 选择

**结论: NO（占位）**

- production.py `_render`: bgm 不存在时生成 **2 秒静音占位**（anullsrc）
- bgm.mp3 实证 = 静音占位
- 无 BGM 曲库、无选择逻辑

## E24. BPM/情绪/energy/beat 分析

**结论: NO（全部无）**

- 无 BPM/情绪/energy/beat 检测代码（grep 确认）
- mix_background_music 仅做 volume 混音 + 尾部 fade

## E25. 统一 Timeline 模型

**结论: PARTIAL（4 轨真实实现，2 轨无）**

jianying.py `build_jianying_draft`（pyJianYingDraft）实证轨道：

| 轨道 | 实现状态 |
|---|---|
| video（主画面） | YES（VideoSegment 真实） |
| voice（配音） | YES（AudioMaterial voice_timeline.wav） |
| bgm（背景音乐） | YES（AudioMaterial bgm_timeline.wav，循环） |
| subtitle（字幕） | YES（TextSegment，但当前 srt 空 → 实际无字幕内容） |
| fx（特效） | NO（无轨道） |
| sfx（音效） | NO（无轨道） |

---

# F. 学习系统

## F26. learning_rules 237 条样本分布

实证（learning_rules 表 + accuracy_review 关联）：

| 样本档位 | 条数（按唯一 ai→human 组合聚合） |
|---|---|
| 来自 1 样本 | ~227 条组合（绝大多数） |
| ≥2 样本 | 10 条组合 |
| ≥3 样本 | 8 条组合 |
| ≥5 样本 | 6 条组合（岩板→岩板29/岛台→岛台23/工厂14/未识别→无明确14/客户案例→产品介绍10 等） |
| ≥10 样本 | 5 条组合 |

**结论: 96% 规则来自 1 个样本（噪声级），仅 5-6 条组合有统计意义。**

## F27. 冲突规则检测

**结论: YES（存在冲突）**

| AI 输出 | 人工判定 A | 人工判定 B | 冲突类型 |
|---|---|---|---|
| 客户案例 | 产品介绍 (10次) | 功能展示 (7次) | 强冲突 |
| 产品介绍 | 产品展示 (4次) | 功能展示 (4次) | 强冲突 |
| 岛台、岩板岛台 | 岛台 (23次) | 伸缩岛台 (6次) | 强冲突 |
| 未识别 | 无明确功能 (14次) | 其他 (3次) | 中冲突 |

## F28. 反馈学习实际改变什么

**结论: 仅改变知识库权重；其余全 NO。**

| 项 | YES/NO | 实证 |
|---|---|---|
| 关键词 | NO | learning.py 不修改关键词表 |
| 规则 | PARTIAL | `_extract_keyword_rule` 生成"建议"文本，写入 learning_rules.rule（不生效） |
| 权重 | **YES** | `_update_content_type_weight` UPDATE knowledge_entries SET weight (content_type 域) |
| prompt | NO | 无 LLM |
| embedding | NO | 无 embedding 更新 |
| 知识库 | PARTIAL | 仅 weight 字段，无新词条写入 |
| 模型参数 | NO | |
| 排序模型 | NO | matching.py 的 learning_adjustment 读 feedback_adjustments（外部传入，无训练） |

**重要: learning.py 的 `_collect_feedback` 查询 `error_type='content_type_mismatch'`，但实际写入的是 `'content_type'`（accuracy_ui.py）→ 该采集路径实际匹配 0 条（实证 learning-engine 仅 1 条 summary）。**

## F29. episodic memory（上下文/候选/选择/拒绝原因回放）

**结论: NO（无 episodic memory）**

- 无保存"候选集+人工选择+拒绝原因"并后续检索的表
- project_segments 表不存在；human_feedback 0 行

## F30. pairwise preference data（preferred/rejected）

**结论: NO**

- 无 preferred/rejected 成对记录表
- roughcut 的 selection_status 概念存在但表未落库

## F31. preference ranker / fine-tune / LoRA

**结论: NO（无任何训练）**

---

# G. 知识库

## G32. 39 条知识结构

**结论: 扁平结构，仅 name/keywords/weight/version。**

knowledge_entries 字段: domain/category/name/aliases/description/keywords/weight/version/active

| 能力 | 有/无 |
|---|---|
| parent-child | NO |
| aliases | YES（JSON 数组字段，但 industry.py 未使用 aliases 匹配） |
| relations | NO |
| positive evidence | NO |
| negative evidence | NO |
| scope | NO（category 近似，非作用域） |
| source | NO |
| version | YES（domain 级 version="1.0"，非条目级） |
| TTL | NO |
| confidence | NO（weight 近似，非置信度） |

## G33. 知识库参与各流程

| 流程 | 参与 | 代码路径 |
|---|---|---|
| 脚本分析 | **NO** | matching.py 用 domain_terms（外部字典），不查 knowledge_entries |
| 素材理解 | YES | industry.py `_score_entries` → knowledge.query(domain) |
| 检索 | NO | search/embedding.py 用 BGE-M3，不查知识库 |
| 模板匹配 | PARTIAL | template.py 用 content_type 映射（非知识库条目） |
| 商业评分 | PARTIAL | 关键词硬编码，非知识库 |

## G34. RAG/FTS/embedding retrieval

**结论: 知识检索 = 全量 39 条一次性加载（SQL 全查），无 RAG。**

- knowledge.query → `SELECT * FROM knowledge_entries WHERE active=1 AND domain=?`（无 LIMIT）
- 39 条全量载入内存逐条关键词匹配
- **无 FTS 索引、无知识 embedding 检索**

## G35. 联网搜索能力

**结论: NO**

- 无联网搜索模块、无来源验证、无自动写入知识库能力
- 知识库只能手工编辑 JSON 后 load_domain

---

# H. 架构与代码

## H36. main.py CLI 命令数

**结论: 62 个 add_argument，main.py 605 行。**

- CLI 命令: 62 个（scan/catalog/inc-scan/p2/p2.5/p3/embed/search/roughcut/template/brain/accuracy/value/quality 全系列）
- 业务逻辑直接写在 main.py 的 if-args 分支（每个命令 5-20 行内联逻辑）→ **main.py 承载大量编排逻辑，非薄壳**

## H37. service layer

**结论: PARTIAL**

- 认知层有模块级服务（Brain/IndustryEngine/ProductionEngine 等）
- 但 UI 与 CLI **不共享同一服务实例**：accuracy_ui 直接连 DB + 调用引擎；brain-ui 同理
- 无统一 service 层/依赖注入；CLI 各自 bootstrap()

## H38. 数据库迁移版本与 rollback

**结论: PARTIAL（有版本记录，无 rollback）**

- schema_version 表: 3 行（analysis_tasks=1 / quality_validation=1 / cognitive=1）
- 迁移 = `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ADD COLUMN`（幂等前向）
- **无 down-migration / rollback 机制**

## H39. 自动化测试

实证（tests/ 目录 11 文件）：

| 类型 | 数量 |
|---|---|
| unit/integration（test_*.py） | 41 个 def test_ |
| end-to-end | 0 |
| pytest 总数 | 41 |
| 通过率 | **未运行（本次只读审计未执行）** |
| coverage | **无 coverage 配置**（pyproject.toml 存在但未验证覆盖配置） |

测试覆盖: P1/P1.1/P2/P3/P4/P5/P6/P7/task_store/claim（**不含 cognitive 模块、不含 accuracy/value**）

## H40. CI 配置

**结论: NO（无 .github/workflows）**

---

# I. 模型与版本

## I41. AI 分析结果是否记录版本

**结论: PARTIAL**

| 字段 | 有/无 | 实证 |
|---|---|---|
| model_name | PARTIAL | content_classification.model_version（"brain-industry-v2"等） |
| model_version | PARTIAL | 同上，但 ASR/OCR/场景结果无版本 |
| prompt_version | NO | |
| knowledge_version | PARTIAL | knowledge_entries.version（"1.0"） |
| algorithm_version | PARTIAL | segments.algorithm_version |
| created_at | YES | 各表均有 |

accuracy_test.ai_analysis JSON **无版本字段**（无法区分批次）。

## I42. 换模型后区分新旧结果

**结论: PARTIAL**

- content_classification.model_version 可区分（v1/v2）
- 但 accuracy_test.ai_analysis、transcripts、ocr_text **无版本标记**
- **部分能区分（分类），大部分不能（转录/OCR/测试集）**

---

# J. 生产质量

## J43. production.py 自动生成视频的质量检测

**结论: 全部 NO（无任何质量检测）**

| 检测项 | 有/无 |
|---|---|
| 黑帧 | NO |
| 无音频 | NO |
| 重复镜头 | NO |
| 字幕越界 | NO |
| 字幕遮挡 | NO |
| 画面比例 | NO |
| 音量 | PARTIAL（仅 bgm 混音 volume 参数） |
| 音画同步 | NO |
| 脚本覆盖 | NO |
| 镜头语义匹配 | NO |

（narration.py 有 BGM 混音后的 duration 校验，非上述检测。）

## J44. 单镜头重新生成

**结论: NO（只能整条重做）**

- production.py 无单 segment 级再渲染接口
- EditPlan 整体构建 → 整体渲染

## J45. AI候选/人工接受/人工拒绝记录

**结论: PARTIAL（概念存在，落库缺失）**

- roughcut 代码引用 project_segments(selection_status: selected/backup) —— **但表不存在于当前库**
- human_feedback 表 **0 行**
- accuracy_review 记录了 AI vs 人工差异（内容类型/场景等）—— 这是唯一真实存在的反馈记录，但**不含镜头级选择数据**

---

# 六类分级汇总

## 【已真实实现】YES

| 项 | 证据 |
|---|---|
| GPU-ASR | faster-whisper + cuBLAS DLL |
| OCR 管道 | 289218 行 / 13846 asset |
| 场景检测 | ContentDetector + 固定兜底，41814 segments |
| 内容分类 V2 | 双层结构 + 证据机制，85.9% |
| 真实 TTS 成片 | narration.wav 176KB，sherpa-onnx VITS |
| 4 轨剪映草稿 | video/voice/bgm/subtitle（pyJianYingDraft） |
| 知识库加载 | JSON→SQLite 幂等同步 |
| 反馈记录 | learning_rules 237 + accuracy_review 100 |
| 内容价值评分 | 5维 + ABCD 池，22465 条 |
| 多 Worker 并行 | 原子领取 + 瓶颈加权 |
| 知识权重学习 | `_update_content_type_weight` |

## 【部分实现】PARTIAL

| 项 | 证据 |
|---|---|
| 资产身份（asset/media 双表） | 两套 ID 体系并存 |
| 去重检测 | fingerprint 字段在，阶段 DONE=0 |
| scene_semantics | 141 asset (0.63%)，无 segment 级 |
| BGE embedding | 17211 asset，非全量 |
| Top-K 候选 | P4/P6 有，Phase5 无 |
| 字幕 | 有 cue 切分，但 srt 空、无 word-level |
| 模型版本记录 | 分类有，转录/OCR 无 |
| 数据库迁移 | 有版本，无 rollback |
| 人工反馈记录 | 内容级有，镜头级无 |

## 【只有 Demo】

| 项 | 证据 |
|---|---|
| Phase5 自动生产 | 仅 2 个 production_plans，1 个 rendered（preview 规格 540x960），无质量校验 |
| BGM | 静音占位（anullsrc） |
| 剪映字幕 | 空 srt 占位 |

## 【没有实现】NO

| 项 |
|---|
| segment 级认知字段（11 项全缺） |
| 动作/时间序列识别 |
| 伸缩动作识别 |
| confidence gate |
| LLM 脚本理解 |
| continuity_score（6 项全无） |
| global sequence optimization |
| segment 使用记录 / reuse cooldown |
| 视觉近重复聚类 |
| 声音克隆 |
| BPM/情绪/beat 分析 |
| fx/sfx 轨道 |
| episodic memory / pairwise preference |
| ranker / fine-tune / LoRA |
| RAG 知识检索 / 联网搜索 |
| service layer / CI |
| 生产质量检测（10 项全无） |
| 单镜头再生成 |

## 【存在技术债】

| 项 | 说明 |
|---|---|
| learning.py 采集路径失效 | 查 error_type='content_type_mismatch'，实际写入 'content_type' → 采集 0 条 |
| 新旧链路并存 | matching(media_id) vs production(asset_id) vs roughcut(segment_id) 三套 |
| project_segments 表缺失 | 代码引用、表未建 |
| main.py 62 命令内联 | 无 service 层，编排逻辑堆积 |
| 迁移无 rollback | 升级不可回退 |
| 繁简映射手工表 | 71 字，新词需人工扩充 |
| OCR 6383 pending | 历史重跑未完成，覆盖率 61.63% |

## 【存在数据风险】

| 项 | 说明 |
|---|---|
| content_value 22325 条为兜底分 | 无认知锚定，分数不可作为选材依据 |
| scene_semantics 覆盖率 0.63% | 认知语义几乎未覆盖 |
| fingerprint/duplicate 未执行 | 无法证明无重复素材 |
| learning_rules 96% 单样本 | 噪声规则，含强冲突（客户案例→产品介绍/功能展示） |
| 相关系数 0.631 基于 20 样本 | 统计显著但置信区间宽 |
| accuracy_test 无版本字段 | 结果无法回溯批次 |
| 生产视频无质量数据 | 无法验证成片可用性 |

---

# 结论

TreeCut 当前**感知与理解层基本真实可用**（分析管道、GPU-ASR、内容分类、TTS 成片、知识库），但**生产决策层存在系统性缺口**：segment 级认知字段全缺、无动作识别、无连续性/全局优化、无质量检测、反馈学习未闭环（采集路径失效 + 无排序训练）。

按用户既定路线（暂缓自动生产），**下一阶段系统级重构的核心应聚焦**：
1. segment 级语义化（认知下钻到 segment）
2. confidence gate 与动作识别（视觉时序）
3. 生产链路统一（asset/segment/script 三线合一）+ 质量闸门
4. 反馈学习闭环修复（error_type 对齐 + 偏好数据落库）

*本报告全部结论基于源码与数据库实证，未做任何修改。*
