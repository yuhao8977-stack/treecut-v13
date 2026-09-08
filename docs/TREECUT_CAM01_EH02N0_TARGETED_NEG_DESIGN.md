# TREECUT CAM01 EH02 N0 — Targeted NEG Reference Set Design + Blind Human Review Pack

- **性质**：DESIGN + READ-ONLY CANDIDATE AUDIT + HUMAN REVIEW PACK（只设计，不跑候选算法）
- **基线 SHA**：`8f84a1a1e0f0334256adf79f752e7cfe6c84e9d3`
- **遵守**：`docs/TREECUT_CAM01_EH02_NEG_POLICY_DECISION.md`（17 条冻结）+
  MASTER HANDOFF V2.1
- **状态**：`TARGETED_NEG_DESIGN_COMPLETE=YES` · `BLIND_REVIEW_PACK_READY=YES`（审核包在
  gitignored 本地路径，见 §八）· `NEG_REFERENCE_CONTROL_PRESENT=YES` ·
  `ESTABLISHED=NO` · `NEW_NEG_REFERENCE_ADDED=0` · `NEW_STRONG_REFERENCE_ADDED=0` ·
  `GEOM_ALLOWED=NO`
- 本阶段禁止项已遵守：未改生产代码/router/S1S2S3/阈值/rules hash/METHOD_MATRIX/CALIBRATION10/
  历史 truth；未运行候选算法挑样；未按算法结果划 family；未生成最终人工结论；
  未宣布 ESTABLISHED；未进 GEOM；未扩 Stage9/AutoPublish/其他账号。

## 一、候选宇宙冻结（11 个）

有序列表与确定性 hash 见 `TREECUT_CAM01_EH02N0_CANDIDATE_UNIVERSE.json`。
统一初始状态 **REVIEW_REQUIRED**（media 不可用者标 MEDIA_UNAVAILABLE——本批 11/11 媒体可读，
无 MEDIA_UNAVAILABLE）。无 APPROVED / TARGET_VALID / REFERENCE_STRONG / CONTROL_ELIGIBLE。

| # | media_id | canonical asset_id(前缀) | source | 真实尺寸 | fps | duration_s | 顶层组(脱敏线索) |
|---|---|---|---|---|---|---|---|
| 1 | 1019 | b99eaaed… | src1 | 1728×3072 | 60 | 8.30 | 组A(32运动者+实木升降台) |
| 2 | 1025 | e2ca044d… | src1 | 1728×3072 | 60 | 11.65 | 组A(34可折叠水桶+实木桌) |
| 3 | 103 | b9e8a928… | src1 | 1728×3072 | 60 | 3.95 | 组B(113欧式沙发+实木梳妆) |
| 4 | 1600 | 287eb09d… | src1 | 1728×3072 | 60 | 5.60 | 组C(04壁挂水龙头+凉亭) |
| 5 | 1638 | d33d7735… | src1 | 2160×3840 | 60 | 3.20 | 组C(1-4 55大理石+深黑实木) |
| 6 | 1639 | ab42a8b5… | src1 | 1728×3072 | 60 | 5.70 | 组C(05烤牛肉串) |
| 7 | 2163 | 36205cd4… | src1 | 1728×3072 | 60 | 2.78 | 组D(85瓷白+深灰+黑白岩板) |
| 8 | 2208 | 9f5ad83e… | src1 | 1728×3072 | 60 | 3.45 | 组E(48大理石+运动者+深灰拼花) |
| 9 | 2211 | 924bd75c… | src1 | 1728×3072 | 60 | 6.03 | 组E(32运动者+实木·餐厅) |
| 10 | 2492 | bd94f7eb… | src1 | 2160×3840 | 60 | 0.95 | 组F(岩板白·鱼尾锅·壁挂水龙头) |
| 11 | 26023 | e8e43b09… | src4工厂 | 1728×3072 | 59.94 | 12.00 | 组G(DJI 青岛 2.18 工厂) |

- **CALIBRATION10 overlap = 0**（候选 ∩ cal10 media_ids = ∅，已代码验证）
- **A3 / EH01 / EH02 / 训练 / 校准 overlap = 0**（cal10 为唯一校准 universe；候选全部 cal10 外）
- **duplicate/near-duplicate cluster**：duplicate_groups 表中 11 候选 + 2543 均无成员记录
  → near-dup 需真实画面人工比对，N0 不运行算法 → 标 **UNKNOWN（待 N1 人工确认）**
- **与 2543 同源/近重复**：候选均非 2543 同文件；2492 与 2543 同属 src1 第 21 组目录
  （folder-hint 一致）→ **潜在同拍摄序列，需人工确认（potential only）**；其余组别不同
- NO_ACTION 证据层级：全部来自 `TREECUT_POSTA3_HUMAN_REVIEW_V1.json` media 级 verdict
  （**media-level only**，无 frame/ROI 级人工复核记录）→ 证据层级 = MEDIA_LEVEL_ONLY

## 二、两种 family 的严格定义（N0 冻结）

### A. visual_content_family（视觉内容 family — 样本多样性）
判定依据（仅供人工审核，N0 不自动判定）：canonical source/asset · 场景类型 · 目标物体与
材质/纹理 · 构图与目标占比 · 拍摄方式 · camera motion · 遮挡 · 人物/锅具/手部动态干扰 ·
场景切换 · 动作类型或无动作表现。
**强制规则**：
1. 三种算法验证同一视觉样本，仍只算 1 个 visual family；
2. V24/GFTT 同 FEATURE_LOCAL 链，不得重复计独立算法佐证；
3. 同一 canonical asset 或近重复镜头不得拆成多个 family；
4. 同一视频多个 pair 若场景视觉条件相同只计 1 family；
5. 不同 media_id 本身不足证明不同 family；
6. 至少不同 source/near-dup cluster 且存在实质视觉条件差异；
7. 2543 为已有 family anchor，但不得强行把其他候选归入或排除该 family。
**N0 全部候选 final visual_family_id = UNKNOWN**（等人工审核，见 schema）。

### B. algorithm_evidence_family（算法证据 family — 方法来源）
FEATURE_LOCAL / FEATURE_LOCAL_ENSEMBLE / SEMANTIC_DENSE_LK / GLOBAL_CAMERA / 其他正式方法链。
仅用于 N2 算法评价阶段；N0/N1 不参与判定。

## 三、数据泄漏隔离

- 审核界面**不暴露**：GFTT/V24/DENSE/GLOBAL 状态、router route/rule/reason、
  structural verdict、sym P90、expected strong/partial/conflict、任何算法成功概率、
  为凑 3 family 的预期。
- 匿名 reviewer code **R01–R11**（固定随机 seed 打乱展示顺序；映射单独保存于
  gitignored reviewer_map.json；界面默认不显示真实 media_id 与算法信息）。
- 隔离证明：候选 ∉ CALIBRATION10 36-pair universe（overlap=0）；候选不参与 router
  阈值/规则修改；family 与人工标签先冻结，算法评价后运行（N1→N2 顺序）；任何算法失败
  不得事后重写 family 定义（N1 冻结 hash 为不可变基线）。

## 四、盲审帧包（本地 gitignored）

- 目录：`E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\eh02n0_blind\`
  （gitignored；Git 只存 manifest/hash/脱敏引用）
- 抽帧规则（**预先固定，与算法表现无关**）：
  - 时间轴代表帧：每候选均匀抽 ≤5 帧（覆盖全局）
  - 场景边界帧：用固定 ffprobe scene 阈值 0.4（只读，不改参数调优）
  - t0/t1 pair 候选：均匀取早期/晚期各 1 帧供人工选 pair——**不得按"哪对更易匹配"选择**
  - 固定 seed=20260908 打乱展示
- 每候选输出：全局代表帧 / 场景边界帧 / t0-t1 候选 / 原始时间戳 / frame sha256 /
  是否跨 scene cut / 原始尺寸 / 无算法预测画面 / ROI 框选入口（复用 mmv_a1_annotate
  /posta3/roi 服务语义，不建平行 UI）
- 视频与大图不进 Git。

## 五、人工审核字段（schema，见 HUMAN_REVIEW_SCHEMA.json）

reviewer_code / media_available / NO_ACTION_pair_confirmed(Y/N/U) / target_visible_at_t0 /
target_visible_at_t1 / target_unique_at_t0 / target_unique_at_t1 / same_target_identity /
scene_cut_between_pair / severe_occlusion / ROI_t0 / ROI_t1 / proposed_visual_family /
visual_family_reason / near_duplicate_of / reviewer_notes / reviewed_at /
reviewer_identity_version。
**预注册资格规则**（未来可入算法评价，需同时满足）：frame-level NO_ACTION=YES + t0/t1
target visible + t0/t1 target unique + same target identity + 无 scene cut + ROI 有效 +
非已排除近重复样本。**N0 不填任何人工结论**——只创建模板与审核任务。

## 六、候选多样性分析（待人工确认，非正式 verdict）

- 实际可读：**11/11**（ffprobe 全部成功）
- canonical asset：**11**（各 1 个 asset_id，互不相同）
- duplicate/near-dup cluster：duplicate_groups 无成员 → **0 已知 / UNKNOWN 待人工**
- 明显同拍摄序列（folder 线索，脱敏）：组A=1019+1025、组C=1600+1638+1639、组E=2208+2211
  ——共 3 组疑似同序列（各算潜在 1 family 候选）
- 26023：src4 工厂 DJI（1728×3072@59.94，青岛 2.18）——与其余 src1 展示类**不同源**，
  形成独立工厂场景候选的**潜在**依据（需人工确认）
- 除 2543 已有 family 外，理论上最多还能形成：约 **5–7 个潜在候选 family**（组A/B/C/D/E/F/G
  各异，但 2492 可能与 2543 同第 21 组目录 → 潜在重叠）
- 是否至少 2 个新潜在 visual family：**potential=YES**（src1 展示类至少 2 组差异 + src4 工厂），
  但**非正式结论**——须人工画面确认
- 若不足缺什么：正式 NEG 负样本类型缺口 = 不同场景/物体/拍摄/干扰组合的**独立视觉 family**
  （工厂/户外/多目标遮挡类更少）

## 七、预注册后续阶段（只设计不执行）

- **N1 HUMAN_FRAME_ROI_REVIEW_FREEZE**：用户完成人工审核 → 冻结 frame pair/ROI/NO_ACTION/
  visual family → 生成不可变 annotation hash。
- **N2 FROZEN_ROUTER_NEG_EVALUATION**：用当前 frozen router/rules hash、不调阈值，对 N1
  批准样本运行既有证据路线 → 计算 target-valid/REFERENCE_STRONG/control_eligible。
- **N3 NEG_REFERENCE_CONTROL_DECISION**：检查是否 ≥3 独立 visual family；不满足保持
  ESTABLISHED=NO；满足也只关闭 NEG control gate；**仍不得自动进 GEOM**（GEOM 需单独批准）。

## 八、输出与边界

Git 新增（本 commit 仅 4 文件）：
1. `docs/TREECUT_CAM01_EH02N0_TARGETED_NEG_DESIGN.md`（本文件）
2. `reports/storage/TREECUT_CAM01_EH02N0_CANDIDATE_UNIVERSE.json`
3. `reports/storage/TREECUT_CAM01_EH02N0_HUMAN_REVIEW_SCHEMA.json`
4. `reports/storage/TREECUT_CAM01_EH02N0_REVIEW_PACK_MANIFEST.json`

本地 gitignored 审核包：blind review HTML / 临时缩略图·审核帧 / reviewer_code 映射 /
ROI 审核入口（`runtime_data\temp\batch1\eh02n0_blind\`）。
视频/大图/DB/权重不入 Git。

## 九、完成判定

`TARGETED_NEG_DESIGN_COMPLETE=YES` · `BLIND_REVIEW_PACK_READY=YES`；
保持 `PRESENT=YES` · `ESTABLISHED=NO` · `NEW_NEG_REFERENCE_ADDED=0` ·
`NEW_STRONG_REFERENCE_ADDED=0` · `GEOM_ALLOWED=NO`。
**NEXT_BLOCKER = HUMAN_FRAME_ROI_REVIEW_FREEZE**（等你亲自查看盲审页面并确认每候选
画面/ROI/family；Harness 不能替代）。
