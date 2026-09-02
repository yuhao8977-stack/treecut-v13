# STAGE8 G3 — Claim → Visual Matcher 报告

状态：**ENGINEERING_EVALUATION + HUMAN_VALIDATION_PENDING**

## 结论速览
- 原子主张解析落地：按句拆分 → 类型（ACTION/MATERIAL_PROPERTY/HARDWARE_PROPERTY/DIMENSION/SPACE/CASE…）；ACTION 词最早出现优先
- ClaimVisualMatcher：硬闸优先（资格/所需对象/所需动作/禁止视觉/故事冲突/重复）→ 排序；软信号不得压过语义失败
- 禁止推断已编码：岩板→耐高温 / 抽屉→静音滑轨 / 文件夹"伸缩"→动作 / ASR插座→视觉插座（单元测试）
- Story Mode：SINGLE_CASE（这一款/客户/定制…） vs INFORMATION_MONTAGE（通用语言）
- 上层薄抽规则：无"上层+薄+抽屉结构"视觉证据 → 降级 DRAWER / THIN_DRAWER_UNVERIFIED 拒绝
- **V2 永久回归**：伸缩/收起口播 + 轨道插座特写 → REJECT（DOMINANT_VISUAL_MISMATCH）；薄抽口播+普通下层抽屉 → REJECT（单元测试通过）
- matcher Query20（V2 风格主张）：14/20 命中匹配候选（library 覆盖内）；插座候选在伸缩/收起查询中被显式拒

## 局限(如实)
- 对象/场景/案例侧信息目前主要来自路径提示与 G2 探测动作侧；visual object 细粒度(薄抽vs普通抽屉、上层vs下层)需更细视觉证据或 L3
- case_cluster 仅骨架(UNKNOWN)，真实聚类待 lineage/视觉相似接入
- story 实体一致性对 MONTAGE 宽松；SINGLE_CASE 需 ≥70% 同案 — 用真实案例素材时验证

## 输出
- TREECUT_G3_ATOMIC_CLAIMS_V1 / VISUAL_REQUIREMENTS_V1 / STORY_MODE_V1 / CASE_CLUSTER_V1 / MATCHER_QUERY20_V1 / PILOT_V2_REGRESSION_V1 / G3_HUMAN_REVIEW_V1.html
