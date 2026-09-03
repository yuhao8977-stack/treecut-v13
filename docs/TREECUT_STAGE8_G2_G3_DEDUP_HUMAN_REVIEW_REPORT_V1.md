# TreeCut STAGE8 G2/G3/Dedup 人工动态审核报告 V1

日期：2026-09-03

## 1. 审核结论

- G1：PASS，可正式关闭。idx63 的 `NEWPRONOUNCE@` 属于衣服实体印刷文字，随人体/透视移动，不是固定画布水印；建议回填 `CLEAN_OK / GARMENT_ENVIRONMENT_TEXT`。
- G2 Action/Subclip：`STAGE8_G2_NEEDS_REPAIR`
- G3 Claim→Visual：`STAGE8_G3_NEEDS_REPAIR`
- Dedup：`NEEDS_TUNING`，当前能抓到真实重复，但误报偏高，不宜直接作为 P0 全阻断。
- 三个上传 MP4 是“审核证据包”，不是成片，不应按成片标准要求 BGM/配音/字幕包装。

## 2. 为什么这些审核 MP4 没有 BGM、旁白，而且会重复镜头

这三个视频的目的不是发布，而是把机器候选按 Query/Beat/Pair 顺序串起来，让人判断：

1. G2：这个 Subclip 到底是不是正在做指定动作；
2. G3：听到这句脚本时，这个画面是否匹配；
3. Dedup：A/B 两段是否构成重复。

因此不加 BGM 和新旁白是正确的。实际上传文件也是 video-only 审核包。若加 BGM/新配音，会增加干扰，反而不利于判断动作方向与视觉匹配。

这里出现的“重复”分两种：

- **审核包故意重复**：同一候选会被放到 EXTEND/RETRACT 或不同 Beat 下反复测试，这是正常的。
- **算法/Production 真实重复**：例如 V2 结尾又用了与前面高度相似的人物+抽屉镜头，这是 Dedup 真正需要拦的。

不要把这两类重复混在一起。

## 3. G2 动作识别人工审核

### 3.1 最严重的问题：请求动作与机器动作标签直接相反，候选仍能进入 Top3

JSON 中多个 Query 已经明确出现：

- 请求 `EXTEND`，候选 `machine_action=RETRACT`；
- 请求 `DRAWER_OPEN`，候选 `machine_action=DRAWER_CLOSE`；
- 请求 `STORAGE_PUT_IN`，候选 `machine_action=STORAGE_TAKE_OUT/CABINET_OPEN`。

这说明 Action Retrieval 缺少最基本的“动作方向兼容硬闸”，或者硬闸未真正作用于排序/返回。

### 3.2 EXTEND 1–4

Top1/Top2：画面是手操作轨道插座旋钮，属于插座操作，不是桌面伸缩。

Top3：长桌面处于静态展开状态，没有看到“收起→拉动→变宽”的动作过程。

裁决：四个 Query 全部 BAD，Top3 中无可用 EXTEND。

### 3.3 RETRACT 1–4

仍然返回与 EXTEND 相同的一组候选：插座旋钮 + 静态桌面。

没有看到“展开→推回/收回→恢复紧凑”的 RETRACT。

裁决：四个 Query 全部 BAD。

这直接证明：当前系统没有可靠区分 EXTEND 与 RETRACT 方向。

### 3.4 DRAWER_OPEN 1–4

Top1：抽屉一开始已经处于打开状态，人物主要在讲解，没有“由关闭到打开”的完整动作。

Top2：连续帧更接近整理/关闭已打开的抽屉，机器本身也标成 `DRAWER_CLOSE`。

裁决：四个 Query 全部 BAD。

### 3.5 SOCKET_INSERT 1–4

当前返回 `NO_VALID_SOURCE_AVAILABLE`。

这不应直接算算法失败；如果库里确实没有“插入插座/插拔”动作，可以保守标素材不足。但后续脚本生产必须知道：没有动作证据时，应改写脚本，不能继续写“插拔也顺手”。

### 3.6 STORAGE_PUT_IN 1–4

Top1：静态柜体/抽屉展示，没有把物品放入的动作。

Top2：人物在已打开抽屉旁讲解/操作，更像关闭或展示。

Top3：人物确实拿着小物在抽屉附近，但连续画面更像取出后讲解，机器也标为 `STORAGE_TAKE_OUT`；无法支持严格的 `STORAGE_PUT_IN`。

裁决：四个 Query 全部 BAD。

### 3.7 G2 人审结果

- 有候选 Query：16
- 无有效素材 Query：4（SOCKET_INSERT）
- Top1 可用：0/16
- Top3 含可用指定动作：0/16（严格动作标准）
- 动作方向兼容：FAIL
- 动作完整性：FAIL
- Boundary 指标：当前不适合计算，因为大多数候选连动作本身都不对

**G2 最终：NEEDS_REPAIR。**

## 4. G2 根因分析与必须修正

### P0-1 Requested Action Compatibility Gate

在 TopK 形成前先执行：

- `requested=EXTEND`，`candidate=RETRACT` → REJECT
- `requested=DRAWER_OPEN`，`candidate=DRAWER_CLOSE` → REJECT
- `requested=STORAGE_PUT_IN`，`candidate=TAKE_OUT` → REJECT

只有当 machine_action 为 UNKNOWN/UNCERTAIN 时，才允许进入更贵的 temporal/Qwen 二次判定。

### P0-2 不能再把 STATIC FUNCTION 当 ACTION

- 桌面已经伸出 = `FUNCTION_VISIBLE`
- 手正在拉出并发生几何变化 = `EXTEND`

两者必须分开。

### P0-3 Action Direction 必须用时序变化而不是单帧语义

对于 EXTEND/RETRACT、OPEN/CLOSE、PUT_IN/TAKE_OUT，至少比较 before/mid/after 中目标物体位置、开合程度、物品相对容器位置的变化方向。

### P0-4 20 个独立 Segment 校准仍太少

当前 132 帧只是时序证据，不是 132 个独立样本。继续扩到 80–120 个 segment 级样本是合理的，但 Qwen 只用于 20–30 个难例，不应全量烧预算。

## 5. G3 Claim→Visual 人工审核

### 5.1 当前 16 Beats 过度切碎

当前脚本被拆成：

- B1 岛台想好用
- B2 这三个细节最值得看
- B3 第一
- B4 上层薄抽
- B5 收纳小物不弯腰
- B6 打开就能拿到
- ...

这种“每个短语一个 Beat”的拆法不适合视觉剪辑。

“第一/第二/第三”不应该独立找镜头；泛化 Hook/CTA 也不一定要每句话换镜。

建议改成 5 个 `VISUAL_BEAT`：

1. Hook：岛台想好用，这三个细节最值得看
2. Detail 1：第一，上层薄抽，收纳小物不弯腰，打开就能拿到
3. Detail 2：第二，轨道插座，吃火锅煮茶都方便，插拔也顺手
4. Detail 3：第三，伸缩桌面，来客时一拉就变宽，平时收起来不占位
5. CTA：厨房好不好用，全在这些小细节里

每个视觉 Beat 内可以包含多个 Atomic Claims，并允许 1–3 个镜头覆盖，而不是 16 句就强制 16 次检索。

### 5.2 核心 Beat 无候选

B4 `上层薄抽`：无候选。

B6 `打开就能拿到`：无候选。

B8 `轨道插座`：无候选，尽管系统别处明明存在轨道插座素材，说明 G3 matcher 与素材能力存在断接。

B10 `插拔也顺手`：无候选。

核心主张无候选时，系统必须：

- 改写脚本删掉无证据 Claim；或
- 重新检索素材；或
- BLOCK Production。

不能留空后继续生成成片。

### 5.3 B5 收纳小物不弯腰

Top1 只能算“抽屉/小物展示的弱支持”，没有明确完整 PUT_IN；Top2/3 不支持 PUT_IN。

严格按当前 `required_action=STORAGE_PUT_IN`：BAD。

### 5.4 B12/B13/B14 伸缩/收回

三条 Beat 都使用同一组 2482/2483/2484。

实际动态审核中，这些镜头主要是人物站在岛台旁讲解、手势、静态桌面；没有清晰的“桌面由收起到拉开”的几何变化。

更严重的是：

- B12/B13 要求 EXTEND
- B14 要求 RETRACT
- 系统仍返回同一组、同一时间窗

这证明 EXTEND/RETRACT 方向没有真正进入 Claim→Visual 硬闸。

裁决：B12/B13/B14 全部 BAD。

### 5.5 G3 最终裁决

`STAGE8_G3_NEEDS_REPAIR`

主要原因：

1. Visual Beat 粒度错误；
2. 核心 Claim 大量无候选；
3. No-candidate 没有触发脚本改写/生产阻断；
4. EXTEND/RETRACT 共用候选；
5. G2 动作错误向 G3 传染；
6. 同一候选在相邻多个 Beat 反复使用，后续会造成成片重复和节奏单调。

## 6. Dedup 人工审核

### PAIR01

收纳抽屉 vs 轨道插座/电源，主体内容和叙事功能不同。

裁决：`FALSE_POSITIVE`。

### PAIR02

同一黄色衣服人物、同一岛台、同一抽屉区域、近似构图，且在同一短视频内承担相近叙事视觉，产生明显重复感。

裁决：`TRUE_DUPLICATE / NARRATIVE_NEAR_DUPLICATE`。

### PAIR03

电源/轨道插座画面 vs CTA/抽屉人物画面，语义和主体明显不同。

裁决：`FALSE_POSITIVE`。

### PAIR04

长桌面全景 vs 插座旋钮近景，明显不是重复。

裁决：`FALSE_POSITIVE`。

当前 4 对中只有 1 对人工确认重复，说明：

- 召回真实重复的能力存在；
- 但误报率高；
- 当前 `NARRATIVE_NEAR_DUPLICATE` 不适合全部升级为 P0 HARD FAIL。

尤其 Pair04 JSON 中出现 `narrative overlap score 5: []`：高分但解释特征为空，需修正评分/解释一致性。

建议：

- Exact segment / source-time overlap / 强 pHash：可 P0；
- Narrative near duplicate：先 WARNING + rerank penalty；
- 只有多证据一致或人工确认的 narrative duplicate 才升 P0。

## 7. idx63 最终裁决

`NEWPRONOUNCE@` 是印在人物衣服上的实体文字。

它随人物身体位置、尺度、透视一起变化，不固定在屏幕坐标；不是平台水印，也不是后期品牌 overlay。

最终：

- `idx63 = CLEAN_OK`
- `environment_text_present / garment_print = PRESENT`
- `platform_watermark = ABSENT`

G1 可彻底关闭 PASS。

## 8. 关于“这些视频没有背景音乐”的充分解释

### 审核包

G2/G3/Dedup 这三条视频没有 BGM 是正确设计：它们是 QA/Human Review Evidence，不是成品。重复候选、黑卡、机器标签都是为了评审而存在。

### 正式 Pilot

Pilot V2 没有 BGM 则仍是生产缺陷。正式信息流 Production 应继续保持：

- `BGM_REQUIRED = TRUE`（除非模板明确 NO_BGM_INTENTIONAL）
- 仅授权/公司自有/明确可商用曲库
- 人声优先，BGM duck
- 最终 -14~-16 LUFS，True Peak <= -1dBTP

两者不能混为一谈。

## 9. 当前 Stage8 状态更新

- G1：PASS
- G2：NEEDS_REPAIR
- G3：NEEDS_REPAIR
- Dedup：NEEDS_TUNING
- G5：框架可保留，但必须吸收本轮人审结果后重新验证；不能继续称完全 PASS
- UI：USABLE V1，可保留
- Voice：READY_FOR_INPUT
- BGM：LIBRARY_NOT_READY
- Pilot V3：继续禁止生成

## 10. 下一轮优先级

### 第一优先：G2 Repair

1. requested_action 与 candidate_action 方向硬闸
2. STATIC vs ACTION 分离
3. 时序方向识别
4. 扩 segment-level calibration 80–120
5. 重新跑 Query20，必须先达到人工门槛

### 第二优先：G3 Repair

1. 文本 Beat → Visual Beat 聚合
2. No-valid-candidate policy
3. Script auto-rewrite / claim dropping
4. action evidence 接入 matcher
5. 同候选跨 Beat 重复惩罚

### 第三优先：Dedup Tuning

1. Pair02 保留正例
2. Pair01/03/04 作为 false-positive negatives
3. narrative duplicate 从 P0 降为 warning/penalty，除非多证据确认
4. 修复 score 高但 reason=[] 的解释一致性

完成以上三项并通过新一轮人审后，再进入真人 Voice Clone + 授权 BGM + Pilot V3。
