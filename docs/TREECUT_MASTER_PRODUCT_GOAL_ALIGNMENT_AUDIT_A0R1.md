# TREECUT MASTER PRODUCT GOAL ALIGNMENT AUDIT A0 R1 — 证据闭合 + 当前复现 + 能力再评级
- **性质**：READ-ONLY 审计交付（报告+证据 JSON+复现产物；无产品代码改动）。对 A0 的 9 项缺陷逐条确认并闭合证据；含当前 baseline 真实复现；含能力再评级（历史证据与当前证据分离）。
- **基线**：main @ `bdc7506005c3914049f56d6c38020a0fc2797b41`（A0 交付后、A0R1 生成前 git 状态空 = clean，机器采集见 REAL_BASELINE）。
- **方法**：证据优先 = 机器采集（live DB/git/磁盘/ffprobe）> 真实产物 > 测试 > 文档。A0R1 脚本实跑生成，测试读取证据 JSON 验证（非自引用字符串）。
- **机器对应**：13 个 A0R1 JSON（见 §11 EVIDENCE INDEX）+ 9 个 A0R1 测试（9/9 PASS）。
- **A0 状态**：`DIRECTIONALLY_USEFUL_BUT_EVIDENCE_NOT_CLOSED`（保留，不因 A0R1 升级）。
- **N0 状态**：保持（N1=NO / PRESENT=YES / ESTABLISHED=NO / GEOM=NO / NEW_NEG=0），见 §10。

## 0. 一句话结论（OVERALL PRODUCT STATE）
A0 的方向性判断成立，但 A0R1 用机器证据闭合后，产品状态必须按下述三态拆分理解：
**目标链（脚本→Beat/Claim→segment 级→人工替换→9:16→3 候选→MP4/剪映）当前不存在**，第一真实阻断 = `SCRIPT_TO_BEAT_CLAIM_NOT_FOUND`（生产链只有"整段文案→整文件素材匹配"，无逐句拆分层）。
**当前简化链（真实现有代码路径）** 在 bdc7506 上实测跑到 **render**：已生成 `01_高清画面底片.mp4`（15.7MB，1080×1920 竖屏），随后被 `TTS_MODEL_LOAD_CHINESE_PATH`（sherpa-onnx 打不开中文安装路径下 LocalTTS/date.fst）阻断 → **当前 baseline 全链 E2E 未证明**。
**历史简化链** 在 2026-08-06 有真实全链产物（MP4+剪映草稿+QA passed），但 2 个 success 是**同一输入重跑**（同一 narration+media [6,5]），不是 2 次独立 E2E；且历史证据 ≠ 当前 E2E_PROVEN。
A0 的 `E2E_PROVEN` 评级大部分必须降级为 `HISTORICALLY_E2E_PROVEN`（定义见 §8）。生产素材路径有效性 A0 误报 0（\X1 映射错误），实为 **15246/15378 有效**。

## 1. A0 缺陷清单：确认与闭合（DEFECT AUDIT）
| # | 缺陷 | 确认 | A0R1 闭合方式 |
|---|---|---|---|
| A0_01 | 硬编码 dict 非机器审计 | ✅ | A0R1 脚本 live 查询 DB/git/磁盘生成 RAW_DB_EVIDENCE / SOURCE_EVIDENCE / CURRENT_REPRODUCTION / REAL_BASELINE |
| A0_02 | baseline clean 冲突 | ✅ | REAL_BASELINE 机器采集：**启动态 clean（0 untracked）**；生成态 16 untracked 全为 A0R1 自身文件（tracked 无修改）。A0 PRE_RUN 的 1 untracked 是它自己生成器写到一半 |
| A0_03 | 历史简化 E2E 与目标 E2E 混为一谈 | ✅ | THREE_E2E_TRACE 拆 A(历史简化链)/B(当前简化链)/C(目标链)；目标链第一阻断 ≠ NONE，是 SCRIPT_TO_BEAT_CLAIM_NOT_FOUND |
| A0_04 | 历史产物当作当前 E2E_PROVEN | ✅ | 能力再评级：历史产物 → HISTORICALLY_E2E_PROVEN；当前链只到 render |
| A0_05 | 能力虚高（USER_USABLE/E2E_PROVEN） | ✅ | 再评级矩阵 §8：E2E_PROVEN(11) 大部分降级；H3_desktop_ui 无真实会话 → USER_USABLE_NOT_PROVEN_LIVE |
| A0_06 | 差距计数 P2=3 错 | ✅ | A0R1 GAP_MAP P2 数组实际 2 项；测试断言计数与数组一致 |
| A0_07 | 测试自证 | ✅ | A0R1 测试读真实 baseline/db/artifact JSON 并校验 sha256，不读 RESULT 自述字符串 |
| A0_08 | 最短 MVP 阻断不完整 | ✅ | 修正为 5 项：P0_script_beat_parse / P0_tts_chinese_path / P0_current_e2e_not_proven / P1_segment_bridge / P1_9x16_multi_shot |
| A0_path_mapping_wrong | 素材路径映射用 \X1 → 0 有效 | ✅ | 用真实 sources.path（D:/E: 本地）重查 → 15246 有效（§4） |

A0R1 过程自身又发现并修正一处同类缺陷：`audit_treecut_a0r1_final.py` 曾硬编码 `actual_baseline={clean:True,"status empty at capture"}`，与机器采集矛盾 → 已改为从 REAL_BASELINE 派生（start clean=0 untracked；generation 16 untracked 均为 A0R1 文件）。

## 2. 真实基线（REAL_BASELINE，机器采集）
- head = origin/main = `bdc7506`，branch=main，head_eq_origin=True。
- **启动态**（A0R1 任何文件生成前，git status 实测为空）：tracked_clean=True，untracked=0。
- **生成态**（REAL_BASELINE 采集时刻）：tracked 无修改（tracked_diff=[]，tracked_files_clean=True）；untracked=16，全部为 A0R1 自身输出/脚本（porcelain 16 行全为 `??`，无 `M`/`D`）。
- 测试 `test_real_baseline_clean` 断言上述两个时刻的语义，9/9 测试基于证据文件通过。

## 3. 数据库机器证据（RAW_DB_EVIDENCE）
两个同名 materials.db = 架构风险（A0 已述，A0R1 用实数闭合）：
- **生产库** `runtime_data\database\materials.db`（4 表：sources/media_files/analysis_jobs/media_tags）：media_files 15378；analysis_jobs 4347（3319 eligible / 3207 classified）；load_candidates 消费 eligible。
- **CAM 库** `runtime_data\temp\batch1\database\materials.db`（88 表）：assets 22466（distinct 22391）、segments 41834、transcripts 51543、ocr 289218；**segments 全部有 asset（orphan=0，机器连接校验）**。
- 生产链不用 asset/segment（整文件 clip）；两库身份不互连（P1_segment_bridge）。

## 4. 路径有效性修正（PATH_VALIDITY_CORRECTED）
- A0 错误：用 `\\X1\...` CAM 风格根路径映射生产 media → path_valid=0、media 5/6 不可读。
- A0R1 正确：从 sources.path 取真实根（D:/E: 本地盘）逐文件 stat。
- **结果：path_valid=15246/15378（有效 99.1%），missing=132**（源路径漂移，见 A1 first_blocker）；eligible 3260 有效 / 59 missing。

## 5. 历史产物清单（HISTORICAL_ARTIFACT_MANIFEST，真实磁盘 + ffprobe + sha256）
`E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\output\projects\` 4 个 20260806 项目：
- **failed ×2**：`20260806_102314_697635`（"卖点或文案不能为空"）；`20260806_102815_919887`（"合格素材不足：计划 0.0 秒，目标 30.0 秒"）→ fail-closed 真实生效。
- **success ×2**：`20260806_110330_049600`、`20260806_120231_028104` — production_report：同一 narration 前 40 字符 + media [6,5]、30.0s、quality_passed=True；`01_高清画面底片.mp4` 1080×1080@30 30.0s（ffprobe）；`02_配音字幕预览.mp4`、`03_BGM混音.mp4`、TreeCut_成片.mp4、TreeCut_剪映草稿（draft_content.json 30000000µs、tracks、45 materials、canvas 1080×1080）、cover、report 均在盘。
- **关键判定：unique_inputs=1** → 2 个 success = **同一输入重跑**，非 2 次独立 E2E。

## 6. 当前复现（CURRENT_REPRODUCTION，bdc7506 实测）
`E:\...\runtime_data\temp\a0r1_repro3\output\projects\20260908_172116_125160\`（E-install src 与 C-repo 哈希一致；runtime python CUDA；3 帧小样本目标 9:16）：
- **实测到达：render 完成** — `01_高清画面底片.mp4` 存在 15.7MB（竖屏 1080×1920，ffprobe 校验）。
- 链上已真实执行：素材加载（load_candidates 从真实 DB）→ semantic scoring → matching → edit_plan → render（ffmpeg）。
- **第一阻断：`TTS_MODEL_LOAD_CHINESE_PATH`** — STATUS.json state=failed；错误为 sherpa_onnx OfflineTts 打开 `LocalTTS/vits-melo-tts-zh_en/date.fst` 失败（date.fst 真实存在 57.8KB；安装路径含中文 `E:\树剪整理\...`；历史成功环境 `E:\treecut-v13` 无中文）。
- 结论：当前简化链 **mp4_render_generated=True，final_mp4=False，jianying=False，PASS=False**。修复方向（如拷贝 LocalTTS 至 ASCII 路径）属模型路径改动，须架构师批准，本审计**未执行**。

## 7. 三 E2E 状态拆分（THREE_E2E_TRACE）
| 链 | 定义/范围 | 实测状态 | 最后到达 | 第一真实阻断 |
|---|---|---|---|---|
| A 历史简化链 | 2026-08-06 现网代码链 | 2 success（同输入重跑）+ 2 fail | jianying_draft（MP4+草稿+QA passed 均存在） | 无（历史链内） |
| B 当前简化链 | bdc7506 实测 | failed（渲染后 TTS 阻断） | render（竖屏 mp4 已生成） | TTS_MODEL_LOAD_CHINESE_PATH |
| C 目标链 | script→Beat/Claim→segment 级→人工替换→时间线→9:16→3 候选→MP4/剪映 | 不存在 | script_input（仅手工整段 narration） | **SCRIPT_TO_BEAT_CLAIM_NOT_FOUND** |

C 链未到达：Beat/Claim 解析、segment 级候选、人工确认/替换循环、3 候选生成、目标链 E2E。

## 8. 能力再评级（CAPABILITY_MATRIX，current vs historical 分离）
级别：NOT_FOUND / BLOCKED_AT_LOAD / NOT_REACHED_CURRENT / DATA_CONNECTED / CODE_PATH_CONNECTED / UNIT_TESTED_SHADOW / E2E_PROVEN_CURRENT_RENDER / HISTORICALLY_E2E_PROVEN / USER_USABLE_NOT_PROVEN_LIVE。
| capability | current_level | historical_level | 证据要点 |
|---|---|---|---|
| A1_scan | DATA_CONNECTED | DATA_CONNECTED | 15378 media；first blocker=源路径漂移(132 missing) |
| B2_ASR | DATA_CONNECTED | DATA_CONNECTED | faster-whisper + 51543 transcripts(CAM) |
| B3_OCR | DATA_CONNECTED | DATA_CONNECTED | RapidOCR + 289218 ocr(CAM) |
| B4_vision | DATA_CONNECTED | DATA_CONNECTED | Florence captions/objects in analysis_jobs |
| E1_retrieval | DATA_CONNECTED | HISTORICALLY_E2E_PROVEN | load_candidates 实跑 3260；当前复现中 matching 真实执行；下游被 TTS 阻断 |
| F2_render_mp4 | **E2E_PROVEN_CURRENT_RENDER** | HISTORICALLY_E2E_PROVEN | a0r1_repro3 竖屏 mp4 15.7MB 实存（当前 baseline） |
| G3_tts | BLOCKED_AT_LOAD | HISTORICALLY_E2E_PROVEN | 当前 date.fst 中文路径失败；历史 E:\treecut-v13 无中文成功 |
| G4_subtitle | NOT_REACHED_CURRENT | HISTORICALLY_E2E_PROVEN | 上游 TTS 阻断；历史烧录 srt 存在 |
| G5_bgm | NOT_REACHED_CURRENT | HISTORICALLY_E2E_PROVEN | 上游阻断 |
| H1_mp4_final | NOT_REACHED_CURRENT | HISTORICALLY_E2E_PROVEN | 历史 TreeCut_成片.mp4；当前 TTS 阻断 |
| H2_jianying | NOT_REACHED_CURRENT | HISTORICALLY_E2E_PROVEN | 历史 draft_content.json 实存；当前未到达 |
| H3_desktop_ui | USER_USABLE_NOT_PROVEN_LIVE | CODE_EXISTS | 731 行 Tk 实存；本审计无真实 UI 启动/会话证据 |
| D2_script_beat | NOT_FOUND | NOT_FOUND | 生产链无 beat 层 |
| C3_feedback | CODE_PATH_CONNECTED | CODE_PATH_CONNECTED | FeedbackStore.adjustments 被 production.py:178 读；无前后排序反事实 → 非 E2E_PROVEN |
| X1_cam_eh | UNIT_TESTED_SHADOW | UNIT_TESTED_SHADOW | 无生产 caller |

## 9. 差距图（GAP_MAP，计数与数组机器一致）
- **P0_PRODUCT_BLOCKERS（3）**：P0_script_beat_parse；P0_tts_chinese_path；P0_current_e2e_not_proven。
- **P1_PRODUCT（4）**：P1_source_gate_prod（eligible flag 而非 A4/Source gate）；P1_segment_bridge（两库不互连）；P1_old_subtitle（OCR 有但生产拒/裁策略未验证）；P1_9x16_multi_shot（历史 1080×1080 2 整片段；repro 竖屏渲染成功但被 TTS 阻断，多镜头混剪未验证）。
- **P2_PRODUCT（2）**：P2_bgm_library（单内置 mixkit mp3）；P2_voice_clone（melo TTS 非克隆）。
- **RESEARCH（3）**：R1_cam_eh（CAM/EH/GEOM/N0 shadow，未接生产）；R2_auto_publish（非目标）；R3_team_ops。
- 统一规则：P0=阻当前半自动闭环 / P1=较强自动化所需 / P2=规模体验 / RESEARCH=不阻 MVP。

## 10. 测试真相（TEST_TRUTH，双解释器实测）
- 系统 python（CPU torch，pytest 全量 586 collected）：570 passed / 12 failed / 4 xfailed，184.57s。failures_by_file：test_stage2_vision 7、test_source_audit_r11 3、test_stage3_mini_v2 1、test_stage3_model_dev 1。
- runtime python（CUDA torch）：test_stage2_vision **13/13 PASS**（50.64s）。
- **分类**：7 个 GPU 失败 = `ENVIRONMENT_MISMATCH_CONFIRMED`（系统 py CPU；runtime py 全过，非产品缺陷）；5 个（r11×3 + stage3×2）= `TEST_ISOLATION_DEFECT`（单独跑过、全量顺序下失败，保留为缺陷未删除）。
- A0R1 自身测试 9/9 PASS（读证据文件 + sha256 校验）。
- 结论：12 failed ≠ clean-green；隔离缺陷即使单独通过仍是缺陷。

## 11. EVIDENCE INDEX（13 个 A0R1 JSON，含 sha256）
`reports/storage/TREECUT_A0R1_*.json` ×13：REAL_BASELINE、RAW_DB_EVIDENCE、PATH_VALIDITY_CORRECTED、SOURCE_EVIDENCE、HISTORICAL_ARTIFACT_MANIFEST、CURRENT_REPRODUCTION、THREE_E2E_TRACE、TEST_TRUTH、GAP_MAP、CAPABILITY_MATRIX、DEFECT_AUDIT、RESULT、EVIDENCE_INDEX（索引含 12 条目 sha256，测试校验 exists+sha256 一致）。
脚本：`scripts/audit_treecut_a0r1_{db,path,historical,source,repro,baseline,final}.py`；测试：`tests/test_audit_treecut_a0r1.py`（9/9 PASS）。

## 12. FINAL RESPONSE（交付清单）
1. 报告：本文件（docs/TREECUT_MASTER_PRODUCT_GOAL_ALIGNMENT_AUDIT_A0R1.md）。
2. 证据：13 个 TREECUT_A0R1_*.json（机器采集，sha256 入索引）。
3. 脚本：7 个 audit_treecut_a0r1_*.py（live 查询，非硬编码）。
4. 测试：tests/test_audit_treecut_a0r1.py **9/9 PASS**（读证据文件）。
5. 复现实物：a0r1_repro3 `01_高清画面底片.mp4` 15.7MB（竖屏，render 实证）。
6. 三态结论：目标链第一阻断 SCRIPT_TO_BEAT_CLAIM_NOT_FOUND；当前简化链阻断 TTS_MODEL_LOAD_CHINESE_PATH（到 render）；历史 2 success = 同输入重跑。
7. N0 保持：N1=NO / PRESENT=YES / ESTABLISHED=NO / GEOM=NO / NEW_NEG=0。
8. **STOP**：按架构师指令，A0R1 只报告；不启动 Track A / Track B / N1 / GEOM / 开发 / 第 4 次复现。等待架构师裁决。
