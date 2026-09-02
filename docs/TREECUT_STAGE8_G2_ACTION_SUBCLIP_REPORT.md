# STAGE8 G2 — 动作理解 + Best Subclip 报告

状态：**ENGINEERING_EVALUATION + HUMAN_VALIDATION_PENDING**（机器/qwen=L2 候选，非 L3）

## 结论速览
- 动作证据级已落地（OBJECT_PRESENT/FUNCTION_VISIBLE/ACTION_START/IN_PROGRESS/END/COMPLETE 不可互换；代码层仅产出 START/IN_PROGRESS/END 语义）
- ActionSubclipService：时序帧证据 → 动作窗 → subclip（pre/post roll），**非整段默认**；semantic_correct 与 boundary_usable 分离
- PATH/ASR 文本仅 PATH_HINT/TEXT_HINT：文件夹"伸缩"不证明动作；qwen 帧级证据为准（15 资产 ×5 帧 + 伸缩组 +2 有界补充 = 87 帧 L2 候选）
- 硬负回归（单元测试）：轨道插座特写 ≠ EXTEND/RETRACT；纯插座资产(1590-92)在 EXTEND 检索中无窗口
- **V2 风格回归**：口播"拉开变宽/收起不占位"+插座特写 → ACTION_MATCH=FAIL（matcher+QA 双层）

## 工程评估
- 窗口产出 28（EXTEND 6 / RETRACT 6 / DRAWER_OPEN 2 / DRAWER_CLOSE 2 / CABINET 4/4 / STORAGE 2/2）
- 真伸缩文件夹素材 2482/2483/2484 出 EXTEND 窗（2482 subclip ≈5.09–7.59s，动作单帧粗定位）
- 命名带"伸缩"的插座空镜(1984-86) qwen 判其确有加宽动作 → **路径提示被证伪为"非真值"**（这正是 §13 要防的；此类素材不因文件夹名即信）
- 校准集 15 段（正/负/硬负混合）已建，帧级状态 L2；L3 待人工
- 限制如实记录：a) 帧采样粒度粗(5帧+2)，动作窗按帧量化，起止精度 ±0.3s 左右；b) EXTEND 与 RETRACT 方向在单帧问题下未区分(同帧同窗) → 需更细问题或更多帧；c) 15 资产覆盖 5 动作组，非全池

## 输出
- TREECUT_G2_ACTION_TAXONOMY_V1.json / ACTION_CALIBRATION_V1.json / TEMPORAL_EVIDENCE_V1.json(87帧 L2) / ACTION_QUERY20_V1.json / SUBCLIP_WINDOWS_V1.json / HARD_NEGATIVES_V1.json
- TREECUT_G2_HUMAN_REVIEW_V1.html（12 查询 × Top3 可播放 subclip + GOOD/BAD/UNSURE）
