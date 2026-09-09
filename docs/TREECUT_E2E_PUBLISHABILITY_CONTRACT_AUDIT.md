# TREECUT E2E PUBLISHABILITY CONTRACT AUDIT（人工验收失败冻结）

- **性质**：只读审计/冻结记录，零产品代码改动（先审计、后开发）。
- **样本**：`TreeCut_成片_A0R2_ASCII模型根E2E.mp4`（run a0r2_repro_20260908_184606_986514）。
- **人工裁决（架构师逐段观看）**：技术链跑通，但**人工验收 FAIL、内容质量 FAIL、不可发布**。
- B0 基线（源码统一/模型根/TTS）仍 **PASS，不推翻**。

## 裁决拆分
| 状态 | 裁决 |
|---|---|
| 源码与模型运行基线 | PASS |
| 技术E2E：能生成 MP4 与剪映草稿 | PASS |
| 人工观看验收 | **FAIL** |
| 内容质量 | **FAIL** |
| 可直接发布 | **NO** |

## 机器数字（production_report.json / ffprobe / wave 实测）
- 成片 25.100s；旁白 wav **11.633s**（64 字）；无旁白尾段 **13.467s**；覆盖率 **46.35%**。
- 画面计划 7 段共 25.0s（固定 ~4s 切片，clip_seconds=4）。
- 字幕随旁白于 11.633s 结束；后半仅 BGM + 素材原字幕。
- Chinese-CLIP **0 条成功评分**（`'BaseModelOutputWithPooling' object has no attribute 'norm'`）；BGE 3260 文本检索兜底。
- `quality_passed=true` = **误判**（见 QA 机制）。

## 逐段缺陷（人工）
0-4s 双重字幕；4-8s 最高三层文字；8-11.63s 新字幕过大压岛台；11.63-16s 旁白/字幕结束画面继续 + 近似重复镜头；
16-20s 只剩 BGM+原字幕；20-23s 静音讲解人像（嘴动无人声）；23-25.1s ~4 次变化、末段碎片跳跃。

## 三个根因（含代码路径证据，均来自 E 安装/HEAD 一致源码）
1. **字幕三层问题（RC1）**：新字幕固定字号/位置（narration.py:270 FontSize=19）；原字幕为烧录像素；
   生产链无原字幕检测/拒绝/去除（OCR 数据在 CAM 旁路库，P1_old_subtitle OPEN）。
2. **脚本/配音/画面时长脱节（RC2）**：64 字→11.633s vs 画面 25s 独立铺满；
   planning.py:39-73 `_fill_plan` 只按 clip 长度铺目标时长、无旁白输入；
   narration.py:203-211 `validate_narration_fit` 只禁"配音>画面"，不拦过短；
   build_srt 字幕随旁白结束（11.633s）；无 Script→Beat/Claim→镜头层。
3. **选材与镜头编排未建立（RC3）**：CLIP=0 报错 → BGE 文本兜底（semantic_matching.py:100-132）；
   整段固定 ~4s 截取非 segment；41834 segments 未桥接生产（P1_segment_bridge）；
   无口播人像/重复镜头/原片内切镜/最短镜头限制。

## QA 误判机制
quality/inspection.py:78-97 `inspect_final_video`：仅查 文件存在/字节/ffprobe/时长±0.5/尺寸/**音轨存在**
（BGM 常驻 → has_audio=True），无旁白覆盖率/内容检查 → `quality_passed=true` 属误判。

## 必装硬性拦截（架构师规则，冻结待实施）
旁白覆盖率 <95% 失败；结尾无旁白 >0.8s 且非片尾失败；BGM 不计旁白；旁白过短→重写脚本或缩短视频禁静默补空镜；
画面长度服从真实旁白；按旁白时间轴拆分信息点配镜头；脏素材（大区原字幕/标题/口播人像）默认拒绝→OCR 文字区记录→
底部字幕遮罩/跟踪修复→再生成新字幕（小字号≤两行、动态安全区）；口播无对应人声否决；禁重复/近重复画面；跨原片切镜重裁；
末段禁 <1s 碎片；每镜头对应旁白信息点；**Chinese-CLIP 失败不得判内容质量通过**。

## NEXT_BLOCKER
**E2E_PUBLISHABILITY_CONTRACT_AND_DEFECT_FREEZE**（即使修好 CLIP，字幕与 13.47s 空旁白仍在，
故不再只写 CHINESE_CLIP_SEMANTIC_RERANKER）。

## 实施顺序（先审计后开发，等待批准逐步执行）
1. 冻结本样本（本文件）。2. 审计旁白/字幕/视觉规划/素材来源/QA 真实代码路径（§根因证据已完成初轮）。
3. 修"旁白-时长契约" + 错误 QA 放行。4. 原字幕拒绝/去除 + 新字幕安全区。5. 修 Chinese-CLIP + segment 级选材。
6. 口播人像/重复画面/碎片切镜限制。7. 两脚本/两场景重新生成。8. 两条人工验收合格后才批准 Beat/Claim 开发。
本阶段未做任何产品代码修改；未进入 N1/GEOM/CAM。
