# TREECUT MASTER PRODUCT AUDIT A0 R2 — Evidence Chain Closure + TTS Controlled A/B
- **性质**：审计交付（报告 + 机器证据 JSON + 受控复现；无产品代码改动、无永久 TTS 修复）。
- **基线**：main @ `02c1fc8abb4f28ec45745bb4e484a4efa0bb5bef`；开始前机器证明 HEAD=origin/main、工作树 clean；**初始 git 原始输出先写入仓库外 audit temp**（`E:\EchoBird-main\_treecut_audit_temp\preflight_20260908_183213\`）后才创建任何仓库文件。
- **架构裁决基线**：A0R1_SUBSTANTIVE_FINDINGS=PROVISIONALLY_ACCEPTED；A0R1_EVIDENCE_CLOSURE=NO；PERMANENT_TTS_REPAIR=NO；TEMPORARY_TTS_ASCII_AB=YES；TRACK_A=NO；N1/GEOM/CAM_PRODUCTION=NO。
- **方法**：证据优先=机器采集（live git/SQLite/磁盘/ffprobe/pytest JUnit）。A0R2 脚本实跑生成；测试读证据 JSON + sha256 校验；禁硬编码数值。

## 0. 一句话结论
A0R1 的五项证据缺口逐条闭合，并产生**一个 P0 级新发现与一个受控根因确认**：
1. **BASELINE_SELF_CONTAINED=False（P0）**：E 安装实际运行源码不属 Git HEAD —— `src/treecut/models/` 整包 12 个 .py（含 tts_local.py、vision_florence.py、cache.py）被 repo `.gitignore` 的 `models/` 模式忽略、**从未入 git**（`git log --all` 为空）；另有 4 个文件（config/settings.py、desktop.py、library/__init__.py、main.py）E 内容与 HEAD 不同（E 更新）。→ 任何"当前 run 精确对应 Git baseline"的声称不成立；复现必须显式锚定 E-install 运行源码。
2. **TTS_NON_ASCII_ROOT_CAUSE=CONFIRMED（受控 A/B）**：同一 LocalTTS 模型字节，A（中文路径）sherpa-onnx 打开 date.fst 失败；B（纯 ASCII 复制）正常加载并合成 7.059s WAV；两侧 20 文件/182MB/hash 完全一致。
3. **CURRENT_REDUCED_E2E=PASS（仅批准的一次）**：以 ASCII 模型根 + E-install 运行源码，全链跑通到 `TreeCut_成片.mp4`（1080×1920@30+音轨 25.1s）+ 剪映草稿 + cover + QA passed（1857s）。
4. 附带机器发现：语义复核 CLIP 路径报错 `'BaseModelOutputWithPooling' object has no attribute 'norm'`（clip_scored=0，BGE 3260 兜底）→ E1 语义复核部分失效。
5. 测试真相修正：12 失败 = 7 ENVIRONMENT_MISMATCH（GPU/CPU）+ 2 TEST_ISOLATION_DEFECT（顺序依赖，full+iso+reorder 三重证据）+ 3 TEST_ISOLATION_DEFECT_COLLECTION（r11 workbench：单独过、任意套件位置都挂 → 收集期 'server' 模块 sys.modules 冲突；full+iso+reorder 顺序证据证明与执行顺序无关）。

## 1. 五项缺口闭合（对架构师核出问题逐条回应）
| 缺口 | 证据 | 结论 |
|---|---|---|
| 1 source provenance（blob 返回字面 HEAD:...） | SOURCE_PROVENANCE：git ls-files --error-unmatch / cat-file -e / rev-parse 全记录 rc/stdout/stderr；三方 SHA-256（E 运行文件 CRLF→LF 归一 vs HEAD blob；repo core.autocrlf=true 已计入） | **确认**：tts_local.py 等 12 文件在 HEAD 不存在（gitignore `models/`），rev-parse 必然失败→A0R1 源码采集记录到命令字符串；**BASELINE_SELF_CONTAINED=False** |
| 2 复现脚本与被取证运行不同路径 | 单一正式 runner `audit_treecut_a0r2_repro_runner.py`：每次唯一 run_id；禁硬编码目录；RUN_MANIFEST 含 baseline/git/python/版本/env/DB copy sha/完整 request/media ids/模型路径/输出目录 + 运行期实际 import 模块 sha | **闭合**：本次 E2E 从 runner 真实返回生成 CURRENT_REPRODUCTION |
| 3 机器证据仍硬编码 / 测试自证 | RAW_TEST_RUNS 由 pytest JUnit XML + raw log 解析生成（命令从日志头读取）；final/result/matrix/gap 全部从证据 JSON 派生 | **闭合**：脚本无 586/570/12 等常量 |
| 4 baseline JSON 字段生成脚本没有 | REAL_BASELINE 注解字段（start_state 等）为 A0R1 补写；A0R2 RAW_PREFLIGHT 由生成脚本直接产出全部字段，无人工补写 | **闭合**（新基线无此类字段） |
| 5 TTS 根因未 A/B 确认 | 受控 A/B 见 §5 | **CONFIRMED** |
| 6 能力矩阵虚高（ASR/OCR 等） | CORRECTED_CAPABILITY_MATRIX：无生产 caller/DB bridge → **DATA_PRESENT_SHADOW / NOT_PRODUCTION_CONNECTED**（机器：production import closure 21 模块，asr/ocr/vision 均不在其中） | **修正** |

## 2. RAW_PREFLIGHT（机器）
- head = origin/main = `02c1fc8...`，branch=main，head_eq_origin=True，worktree clean（porcelain/diff 空，rc=0 全录）。
- 解释器：system Python 3.12.10（CPU torch）；runtime Python 3.12.13（torch 2.6.0+cu124 cuda True；sherpa_onnx 1.13.4；onnxruntime 1.28.0）；ffmpeg 8.1.1（bundled）。E 盘剩余 154.2GB（copy 前记录）。

## 3. SOURCE_PROVENANCE（101 个 E 运行 .py）
- **85 E_CONTENT_EQ_HEAD**（EOL 归一后与 HEAD blob 一致）
- **12 NOT_IN_HEAD**：全部位于 `treecut/models/`（`__init__`、cache、object_detection、policy、registry、semantic_matching、speech_sensevoice、speech_whisper、tts_local、validation、vision_florence、vision_qwen）—— 被 repo `.gitignore` 第 14 行 `models/` 忽略，`git ls-files src/treecut/models/` 为空，`git log --all -- ...tts_local.py` 为空 → **从未入 git**。
- **4 E_CONTENT_DIFFERS_HEAD**：config/settings.py、desktop.py、library/__init__.py、main.py（E 安装版本比 HEAD 新；repo worktree==HEAD clean）。
- 显式检查：tts_local.py / vision_florence.py / cache.py → NOT_IN_HEAD（tracked=False）。
- **BASELINE_SELF_CONTAINED=False → P0**。复现/审计后续一律以 E-install src 为运行锚点并记录模块 sha（runner 已实现 imported_module_source_sha）。

## 4. BEAT/CLAIM 机器搜索与生产调用图
- E 运行 src：模块名含 beat/claim = 0；内容命中 6 文件（注释/字符串提及，无拆分层实现）。
- repo worktree src：模块名命中 2（services/visual_beat.py 等 = CAM 研究，**E 安装不存在**）；内容命中 28。
- **production import closure**（从 `application/production.py` AST 闭包）：21 个 treecut 模块可达，**beat/claim 模块 = 0**。
- **TARGET_BEAT_LAYER = NOT_FOUND（机器证据）**，第一阻断保持 SCRIPT_TO_BEAT_CLAIM_NOT_FOUND。

## 5. TTS 受控 A/B（仅诊断；原模型零改动）
- LocalTTS 源目录：20 文件 / 191,246,256 字节；关键文件 sha256 记录（model.onnx 170,429,550B、date.fst 59,154B、lexicon.txt 6,837,671B、tokens.txt、model.int8.onnx 133B 占位）。
- **A（原中文路径 E:\树剪整理\...）**：rc=1 — `kaldi-io.cc Error opening input stream 'E:\树剪整理\02_安装程序\TreeCut_v13\models\LocalTTS\vits-melo-tts-zh_en\date.fst'`（与产品 STATUS 同源错误）。
- **B（COPY 至 E:\EchoBird-main\_treecut_audit_temp\a0r2_tts_ab_20260908_183905\LocalTTS，纯 ASCII）**：rc=0 — 加载成功，合成 7.059s WAV（622,636B，sha256 30acb655...）。
- 两侧 inventory 相同（20 文件/字节/hash 全等）。判定（规则内）→ **TTS_NON_ASCII_ROOT_CAUSE=CONFIRMED**（A fail + B pass + hashes 同）。对照 sherpa-onnx 开放问题 #3885（非 ASCII 路径），本次为 TreeCut 自身同模型 A/B 实证。
- 原模型未移动/删除/覆盖；B 目录保留待架构师清理决定。

## 6. CURRENT REDUCED E2E（正式 runner，唯一批准一次）
- runner：`audit_treecut_a0r2_repro_runner.py` --model-root `a0r2_models_ascii_20260908_184122`（models 全量 COPY 95 文件 11,172,542,902B 至 ASCII 根；TREECUT_MODEL_ROOT/TREECUT_DATA_ROOT env 由代码 platform/paths.py:28 支持，**零产品代码改动**）。
- **PASS**，run_id `20260908_184606_986514`，1857s。产物：`01_高清画面底片.mp4` 12.3MB → `02_配音字幕预览.mp4` 12.5MB → `03_配音音乐预览.mp4` 12.7MB → `TreeCut_成片.mp4` 8.95MB（ffprobe 1080×1920@30 + 音轨，25.1s）→ `TreeCut_剪映草稿/`（draft）→ cover.jpg → production_report.json（quality.passed=True，critical fails=[]，40 matches/25.0s）。
- STATUS.json state=success；DB 为 production materials.db 的 COPY（不触正式库）。
- RUN_MANIFEST 记录：baseline sha、git 状态、python/版本、TREECUT env、DB copy sha、完整 request、40 media ids（report.matches 首 8: 13557/13613/13630/13566/13608/13610/13617/13619）、模型路径、输出目录、**imported_module_source_sha**（运行期实际导入模块 sha，均指向 E 安装 src）。
- 附带缺陷（机器证据，production_report.json semantic_models.errors）：**Chinese-CLIP 语义复核报错** `'BaseModelOutputWithPooling' object has no attribute 'norm'` → clip_scored=0，BGE 3260 兜底完成匹配。E1 复核能力=部分失效（产品缺陷，列入 matrix E1 note 与 NEXT 建议，非本次授权范围）。

## 7. RAW_TEST_RUNS（双解释器 + 顺序证据，JUnit 派生；614 tests 全量）
| 运行 | tests | product failures | 说明 |
|---|---|---|---|
| system_full（CPU torch，字母序） | 614 | 12 | 7 GPU + 5 隔离类（audit 自测排除，junit 原始值另录） |
| runtime_full（CUDA torch） | 614 | 3 | 仅 r11 workbench（收集期冲突，与解释器无关） |
| iso_r11 / iso_stage3_mini / iso_stage3_dev | 12/10/11 | 0 | 单独运行全过 |
| reorder_first（r11+stage3 置首） | 614 | 10 | 7 GPU + 3 r11 collection（置首仍挂） |

分类（full + iso + reorder 三重证据，均机器记录）：
- **7 ENVIRONMENT_MISMATCH**：stage2_vision GPU 测试（系统 py CPU 必败、runtime py CUDA 通过）。
- **2 TEST_ISOLATION_DEFECT（顺序依赖）**：stage3_mini_v2::test_v2_smoke_on_sample、stage3_model_dev::test_people_output_structure —— full 挂、iso 过、置首过。
- **3 TEST_ISOLATION_DEFECT_COLLECTION**：r11 workbench×3 —— full 挂、iso 过、**置首仍挂**（顺序无关）→ 收集期 `server` 模块 sys.modules 冲突（AttributeError server.PROJECT_FILE；runtime 下同样挂 3 个，证明非 CUDA 环境因素）。
- 结论：12 失败 ≠ clean-green；5 隔离类为测试基建缺陷（不因单独通过而删除）；7 GPU 类为环境不匹配（非产品缺陷）。

## 8. HISTORICAL（relpath manifest + canonical hash）
- `TREECUT_A0R2_HISTORICAL_RELPATH_MANIFEST.json`：4 项目全部文件以**项目相对路径为 key**（如 `20260806_110330_049600/TreeCut_成片.mp4`），exists/size/sha256/ffprobe 实采，无同名覆盖。
- `TREECUT_A0R2_HISTORICAL_CANONICAL_INPUT.json`：每项目从自身 production_report.json 解析完整 selling+narration+media ids+plan+preset → canonical sha256。2 个 success 项目 hash **相同**（b368c734e42a…）→ unique input=1（同输入重跑确认，非 40 字前缀法）。

## 9. CORRECTED_CAPABILITY_MATRIX（语义修正摘选）
- B2_ASR / B3_OCR / B4_vision / segment_level：**DATA_PRESENT_SHADOW / NOT_PRODUCTION_CONNECTED**（CAM 库 51543 transcripts / 289218 ocr / assets 22466 / segments 41834；数据在但 production import closure 无消费模块、身份桥缺失）。
- D2_script_beat_claim：NOT_FOUND_IN_PRODUCTION（闭包机器证据）。
- X1_cam_eh：UNIT_TESTED_SHADOW / NOT_PRODUCTION_CONNECTED（repo 研究模块不在 E 安装）。
- G3_tts：BLOCKED_AT_LOAD(CHINESE_PATH) / PASS_AT_ASCII_PATH（A/B 证据）。
- H1/H2/G4/G5：NOT_REACHED_CURRENT → **REACHED_IN_E2E_RUN**（ASCII 根 E2E PASS 后）。
- E1_retrieval：DATA_CONNECTED + note（CLIP 报错、BGE 兜底）；F2：E2E_PROVEN_CURRENT_RENDER；C3：CODE_PATH_CONNECTED（无 before/after 反事实）；H3：USER_USABLE_NOT_PROVEN_LIVE。

## 10. CORRECTED_GAP_MAP（ROOT_CAUSE / ACCEPTANCE_GATE 分离）
- **ROOT_CAUSE（4）**：RC_script_beat_parse；RC_tts_non_ascii_model_path（CONFIRMED）；RC_baseline_not_self_contained（新 P0）；RC_prod_cam_identity_split。
- **ACCEPTANCE_GATE（7）**：GATE_current_e2e_to_final（ASCII 根 PASS，中文根未过 → 永久修复待批）；目标 MVP 尚缺 ×5（human review/replace、old-subtitle policy、segment bridge、9:16 multi-shot、candidate generation）+ GATE_target_beat_claim。
- current_e2e_not_proven 按裁决归入 gate，不再重复计独立根因。

## 11. RESULT 关键字段（机器派生）
A0R1_SUBSTANTIVE_FINDINGS=PROVISIONALLY_ACCEPTED；A0R1_EVIDENCE_CLOSURE=NO；BASELINE_SELF_CONTAINED=**False**；TTS_NON_ASCII_ROOT_CAUSE=**CONFIRMED**；CURRENT_REDUCED_E2E=**PASS**（ASCII 模型根、E-install 运行码）；TARGET_BEAT_LAYER=NOT_FOUND；TRACK_A_ALLOWED=NO；N1/GEOM/CAM_PRODUCTION=NO；NEXT_BLOCKER=按顺序下一步为【永久 ASCII model-root 修复批准 → 多输入 E2E → Track A Beat/Claim 契约】。

## 12. EVIDENCE / FINAL RESPONSE
- 证据：`reports/storage/TREECUT_A0R2_*.json`（RAW_PREFLIGHT / SOURCE_PROVENANCE / BEAT_CLAIM_SEARCH / HISTORICAL_RELPATH_MANIFEST / HISTORICAL_CANONICAL_INPUT / RAW_TEST_RUNS / TTS_AB_RESULT / CURRENT_REPRODUCTION / CORRECTED_CAPABILITY_MATRIX / CORRECTED_GAP_MAP / EVIDENCE_INDEX / RESULT）+ 主报告本文件 + 脚本 `scripts/audit_treecut_a0r2_{preflight,provenance,beat_search,historical,tts_ab,test_truth,repro_runner,final}.py` + `tests/test_audit_treecut_a0r2.py`（数据驱动，读证据+sha256）。
- 复现实物（仓库外，保留待清理）：`E:\EchoBird-main\_treecut_audit_temp\a0r2_models_ascii_20260908_184122\`（95 文件 10.4GB）、`a0r2_repro_20260908_184606_986514\`（含成片）、`a0r2_tts_ab_20260908_183905\`（B 模型副本 182MB）。
- 未执行：永久 TTS 修复 / Track A / Track B / N1 / GEOM / CAM 接生产 / 任何产品代码修改 / 第 2 次 E2E。**STOP，等待架构师裁决。**
