# TreeCut MMVV A3 — Holdout 冻结报告（A3_HOLDOUT_6_FROZEN）

- 日期：2026-09-04
- 阶段：A3（首次泛化测试准备）· 第二停点：**HOLDOUT 冻结**（人工筛选已完成）
- 算法冻结基座：`ca34678`（同源补偿 / 几何 / 时序 / 相机规则在 A3 全流程冻结，看到机器结果前**禁止任何阈值/规则修改**）
- 采样策略冻结：`A3_SAMPLING_UNIFORM_TIME_V1`
- 状态：**A3_HOLDOUT_6_FROZEN**（STOP：不运行任何 MMVV 预测，等架构师审核纯净性 + 人工 ROI 标注）

---

## 1. 人工筛选结果（架构师 L3，经 /a3/screen，2026-09-04 18:28–18:29）

| 统计 | 数量 |
|---|---|
| 候选总数 | 17 |
| YES_EXTEND | 4（2521, 2549, 2550, 2551）|
| NO_EXTEND | 13（1987,1988,1989,2209,2241,2250–2255,2280,2544）|
| UNCLEAR | 0 |

## 2. 家族与查重检查（证据）

### 2.1 公牛轨道插座家族（1985–1989）→ **SAME_VISUAL_FAMILY_AS_KNOWN（排除）**
- 全部同属 `【05】公牛轨道插座\【61】海口吴小姐【空镜岛台伸缩公牛轨道插座】【02】`。
- **帧级证据**（解码帧 sha256，t=1.9/2.525/3.15/3.775/4.4s）：
  - 1985(-1.mp4) ≡ 1986(-2(1).mp4)：5/5 时间点 sha256 完全一致 → 逐帧重复（与 A2.2 Known `CAMERA_CASE_FAMILY_SOCKET_01` unique=1 一致）。
  - 1987(-2.mp4) ≡ 1988(-3.mp4)：5/5 时间点 sha256 完全一致 → 候选池内亦存在逐帧重复对。
  - 1986 文件名 `-2(1)` 与 1987 `-2` 为同源变体；1985–1989 同客户同系列拍摄 → 与旧 Known（1985/1986）**同一视觉家族**。
- 结论：**1987/1988/1989 不得作为独立 holdout**（若使用即污染：与 Known 家族重叠 + 池内重复），全部排除。

### 2.2 深圳张小姐系列（2549/2550）
- 2549（伸缩餐桌的岛台）与 2550（岛台餐桌伸缩功能设计）同客户（深圳张小姐【59】）同材质系列 → 只取其一，**保留 2549、弃 2550**。
- 2549/2550/2551 相互粗粒度相似度 max<0.90（48×48 灰度均值差）→ 内容互不重复（不同拍摄）。

### 2.3 交叉查重
- 入选池 7 段（2521,2549,2550,2551,2209,2280,2544）任意两素材跨时间相似度 **max<0.90 → 无近重复**。
- 6 个入选案例各自 5 个均匀采样帧 sha256 互不重复（无静止重复帧）。

## 3. 污染检查（vs 旧样本集合）→ **PASS**

| 层次 | 检查 | 结果 |
|---|---|---|
| 媒体级 | 6 入选 media_id（2521,2549,2551,2209,2280,2544）∉ `A3_CANDIDATES.excluded_known_ids`（含 51,52,89,109,1984,1985,1986 与 A1/A2/G2/G3/review-memory/Known6/rule-design 全集） | PASS |
| 帧级 | holdout 30 帧 sha256 vs A1 manifest 旧 27 帧 sha256 | 零碰撞 |
| 家族级 | 无入选案例与旧 Known 视觉家族重叠（海口吴公牛家族已整体排除） | PASS |

## 4. 冻结 Holdout（3 POS + 3 NEG，各组 3/3 独立视觉家族，≥2/3 达标）

| case_id | media_id | 视觉家族 | 窗口(秒) | G1 |
|---|---|---|---|---|
| A3_POS_01 | 2521 | VF_EXTEND_60CM_WEI_NANJING（南京魏小姐 伸缩60cm） | [1.372, 7.776] | eligible(APPROVED) |
| A3_POS_02 | 2549 | VF_EXTEND_TABLE_ZHANG_SHENZHEN（深圳张小姐 伸缩餐桌） | [0.923, 5.230] | eligible |
| A3_POS_03 | 2551 | VF_EXTEND_TABLE_YU_SHENZHEN（深圳于小姐 伸缩餐桌） | [0.961, 5.447] | eligible |
| A3_NEG_01 | 2209 | VF_T_LEG_ROCK_YAN_WULUMUQI（乌鲁木齐燕先生 T型岩板腿 可伸缩） | [0.839, 4.757] | eligible |
| A3_NEG_02 | 2280 | VF_STRAIGHT_LEG_ROCK_LI_GUANGZHOU（广州李先生 一字型岩板腿 伸缩脚） | [0.937, 5.309] | eligible |
| A3_NEG_03 | 2544 | VF_MINI_EXTEND_XU_SHENZHEN（深圳徐先生 MINI伸缩岛台） | [0.850, 4.815] | eligible |

每案例 5 帧全分辨率 JPEG（q=2，ffmpeg 帧精确解码），帧 sha256 已记录于 manifest。

## 5. 采样策略冻结（统一，不挑帧）

```
policy_id: A3_SAMPLING_UNIFORM_TIME_V1
mode:      uniform_time_window
window:    [0.15, 0.85] × duration（与人工筛选所看时间戳一致）
frames:    5 / 案例 @ relative [0.15, 0.35, 0.50, 0.65, 0.85]
```
所有案例同一策略；机器输入仅限 manifest，禁止另选帧/挑帧。

## 6. GT 隔离（答案不进入机器侧）

| 文件 | 职责 | 机器可否读 |
|---|---|---|
| `TREECUT_MMVV_A3_HOLDOUT_MANIFEST.json` | machine-only 输入清单（无 human_gt/expected_verdict/label） | 是（唯一输入） |
| `TREECUT_MMVV_A3_HUMAN_GT.json` | 人工答案（评分时按 case_id 合并） | 否 |
| `TREECUT_MMVV_A3_SCREENING.json` | 人工筛选日志 | 否 |
| `TREECUT_MMVV_A3_HUMAN_GT_ROI.json` | L3 对象框（机器特征输入；框内无答案） | ROI 标注后是 |

## 7. 人工 ROI 页面（新建）

- URL：**http://127.0.0.1:8933/a3/roi**
- 对象集合（架构师限定）：桌板/台面(TABLETOP)、伸缩桌板(EXTENSION_TABLETOP)、岛台主体(ISLAND_BODY) 为关键目标；可选 人(PERSON)、手(HAND)、抽屉(DRAWER)、轨道插座(TRACK_SOCKET)、插座模块(SOCKET_MODULE)。
- **无 AI 预填、无动作/方向/结论输入**；只保存人工框（annotation_source=L3_HUMAN_ROI）。
- 6 案例 × 5 帧 = 30 帧全部可标注，保存到 `TREECUT_MMVV_A3_HUMAN_GT_ROI.json`。

## 8. 12 项报告

1. 筛选统计：17 候选 → **YES_EXTEND=4 / NO_EXTEND=13 / UNCLEAR=0**
2. 冻结案例：POS = A3_POS_01(2521)/A3_POS_02(2549)/A3_POS_03(2551)；NEG = A3_NEG_01(2209)/A3_NEG_02(2280)/A3_NEG_03(2544)
3. 标签来源：架构师人工筛选（screening 时间戳见 HUMAN_GT.screened_at）
4. 视觉家族：POS 3/3 独立（南京魏/深圳张/深圳于）；NEG 3/3 独立（乌鲁木齐燕/广州李/深圳徐）
5. 1987–89 结论：与旧 Known 1985/1986 同【61】海口吴家族 → **SAME_VISUAL_FAMILY_AS_KNOWN**，排除（含 1987≡1988 逐帧重复证据）
6. 旧集重叠：无（2521/2549/2551/2209/2280/2544 均不在 excluded_known_ids）
7. 污染检查：**PASS**（媒体级无重叠 / 帧 sha 与 A1 旧帧零碰撞 / 家族级无重叠）
8. GT 隔离：答案仅存 HUMAN_GT + SCREENING；manifest 无答案字段；机器输入边界已在 manifest 声明
9. 采样冻结：A3_SAMPLING_UNIFORM_TIME_V1（统一均匀窗口，与筛选同时间戳，禁挑帧）
10. ROI 页面：http://127.0.0.1:8933/a3/roi（8 类对象、无 AI 预填、无动作答案）
11. 提交：见 git（本报告配套 commit）
12. 状态：**A3_HOLDOUT_6_FROZEN**

## 9. 下一步（等待架构师）

1. 审核 holdout 纯净性（本报告 + AUDIT 证据）。
2. 人工 ROI 标注 30 帧（/a3/roi）。
3. 批准后：机器以冻结算法（ca34678）对 manifest 作答（只读 manifest + ROI，不读 GT）；**不 tune、不自动修复**，如实报告 PASS/FAIL/UNSURE；若 NO 案例出现 False PASS → NEEDS_REPAIR 并 STOP。
