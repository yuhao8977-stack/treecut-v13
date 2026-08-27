# TreeCut Phase 2 验证报告（VALIDATION_SNAPSHOT_V1）

> 生成时间: 2026-08-26 | 快照: VALIDATION_SNAPSHOT_V1
> 冻结 commit: 5c99564 | 模型: rules+clip-v1 v1.0
> 状态: **规则修改前的第一次独立验证快照**，禁止自动修复

## 1. 样本统计
- 样本总数: **300**
- 有效人工审核: **282**
- 跳过: 0
- 待定: 18

## 2. 各字段真实指标（accuracy/precision/recall/F1/UNKNOWN/confusion）

| 字段 | n | answered | accuracy% | macro-P | macro-R | macro-F1 | UNKNOWN率% | UNKNOWN但人工可判 |
|---|---|---|---|---|---|---|---|---|
| scene | 300 | 23 | 60.9 | 0.2 | 0.127 | 0.156 | 91.7 | 259 |
| product | 300 | 106 | 45.3 | 0.302 | 0.243 | 0.178 | 62.0 | 176 |
| material | 300 | 3 | 0.0 | 0.0 | 0.0 | 0.0 | 98.7 | 279 |
| function | 300 | 50 | 58.0 | 0.442 | 0.498 | 0.373 | 83.0 | 232 |
| action | 300 | 26 | 69.2 | 0.471 | 0.457 | 0.428 | 91.3 | 256 |
| shot_type | 300 | 0 | 0 | 0 | 0 | 0 | 100.0 | 282 |
| people_presence | 300 | 281 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 |

### Confusion Matrix（AI行 × 人工列，主要字段）

**scene**
```
{
 "工厂": {
  "工厂": 14
 },
 "客户家": {
  "工厂": 6,
  "展厅": 1
 },
 "装修完成的房间": {
  "工厂": 1
 },
 "安装现场": {
  "工厂": 1
 },
 "展厅": {}
}
```

**product**
```
{
 "岛台": {
  "岛台": 45,
  "吧台": 1,
  "伸缩岛台": 52
 },
 "餐桌": {
  "岛台": 3,
  "伸缩岛台": 1
 },
 "伸缩岛台": {
  "伸缩岛台": 3,
  "岛台": 1
 },
 "吧台": {}
}
```

**function**
```
{
 "收纳": {
  "抽屉": 15,
  "收纳": 4,
  "其他": 1
 },
 "轨道插座": {
  "轨道插座": 13,
  "其他": 1
 },
 "伸缩": {
  "伸缩": 10,
  "抽屉": 1
 },
 "抽屉打开收纳": {
  "抽屉": 1
 },
 "抽屉": {
  "抽屉": 1
 },
 "水吧": {
  "轨道插座": 1
 },
 "隐藏电器": {
  "抽屉": 1,
  "隐藏电器": 1
 },
 "其他": {}
}
```

**material**
```
{
 "白色亮光台面": {
  "岩板": 1
 },
 "实木": {
  "岩板": 2
 },
 "岩板": {}
}
```

## 3. 质量评分
- 人工质量样本: 275
- 人工质量均值: 58.6 / 中位: 60.0
- 范围: 10.0-70.0
- **AI quality 全为 -1（Phase2 未实现），AI vs Human MAE 无法计算**（AI quality 全为 -1（Phase2 未实现），无法计算 AI vs Human MAE；待 Phase 3 技术质量接入）

## 4. Boundary 审核
- Boundary 审核样本: 300
- boundary_start_ok: yes=140 no=142 可用率=46.7%
- boundary_end_ok: yes=210 no=72 可用率=70.0%
- action_complete: yes=262 no=17 可用率=87.3%
- semantic_complete: yes=251 no=25 可用率=83.7%
- cut_mid_action: yes=26 no=250 可用率=8.7%
- cut_mid_sentence: yes=28 no=248 可用率=9.3%
- usable_as_edit_unit: yes=275 no=9 可用率=91.7%

## 5. Evidence Error Analysis
- function 错误样本: 21
- 错误中含 ASR 证据: 20
- 错误中含 OCR 证据: 9
- 错误中含 CLIP 证据: 1
- 错误样本平均 overlap_ratio: 0.585

## 6. TOP 错误类别（field: AI→人工 count）

- **product**: 岛台 → 伸缩岛台（52 条）
- **function**: 收纳 → 抽屉（15 条）
- **scene**: 客户家 → 工厂（6 条）
- **action**: 收纳/关闭 → 拉出/展开（4 条）
- **product**: 餐桌 → 岛台（3 条）
- **material**: 实木 → 岩板（2 条）
- **product**: 岛台 → 吧台（1 条）
- **function**: 收纳 → 其他（1 条）
- **action**: 收纳/关闭 → 讲解/演示（1 条）
- **scene**: 装修完成的房间 → 工厂（1 条）
- **material**: 白色亮光台面 → 岩板（1 条）
- **function**: 抽屉打开收纳 → 抽屉（1 条）
- **function**: 轨道插座 → 其他（1 条）
- **function**: 水吧 → 轨道插座（1 条）
- **product**: 伸缩岛台 → 岛台（1 条）

### 典型错误样本
```json
[
 {
  "segment_id": "020461667bd9435e97ffe567cb7d5e49",
  "field": "function",
  "ai": "收纳",
  "human": "抽屉",
  "confidence": 0.85,
  "evidence": {
   "asr_hits": [
    [
     1010,
     "兩邊做了上層薄粗"
    ],
    [
     4690,
     "筷子、勺子、紫金牙線分區中"
    ]
   ],
   "asr_text": "兩邊做了上層薄粗 筷子、勺子、紫金牙線分區中",
   "ocr_text": "具 21 无坤宝岛台 源头杜绝 过程控制 生产部 111 21 关坤宝岛台 源头杜绝 过程控制 生产部 111 111 21 天坤宝岛台 源头杜绝 过程控制 生产部 111 111",
   "keyframes": [
    0,
    2500,
    4984,
    5000
   ],
   "clip_tags": []
  },
  "overlap_ratio": 0.736
 },
 {
  "segment_id": "02846d5f7cc34462a2ab8b92c55e0825",
  "field": "scene",
  "ai": "客户家",
  "human": "工厂",
  "confidence": 0.85,
  "evidence": {
   "asr_hits": [
    [
     4770,
     "如果家里面有宝宝"
    ],
    [
     6450,
     "我们可以做这样子的设计"
    ],
    [
     7890,
     "反客碰"
    ]
   ],
   "asr_text": "如果家里面有宝宝 我们可以做这样子的设计 反客碰",
   "ocr_text": "ERED STUI ERED STUN 消火栓 H·R 火警119 EDST 消火栓 H·R 火警119 佛山市 利水兴消防设备有限公司",
   "keyframes": [
    4984,
    5000,
    6912,
    8809
   ],
   "clip_tags": []
  },
  "overlap_ratio": 0.379
 },
 {
  "segment_id": "032c352e70ce4ec0bc98da056b2e4aa1",
  "field": "product",
  "ai": "岛台",
  "human": "吧台",
  "confidence": 0.85,
  "evidence": {
   "asr_hits": [
    [
     0,
     "而且结合开放技术团做个虚择段"
    ],
    [
     2840,
     "整个空间产量显大"
    ]
   ],
   "asr_text": "而且结合开放技术团做个虚择段 整个空间产量显大",
   "ocr_text": "以前的制造业，是工厂生产什么，市场就卖什么根本，听不见消费者的呐喊 岛台 然面，传承不是守旧，是带着历史去未来开疆拓士！ 现在的我们，坚持以用户思维做产品！镌刻在骨血里的匠人精神，正在身先士卒去突破行业的短板 探索传统制造业的能力边界，以柔",
   "keyframes": [
    0,
    2500,
    4984
   ],
   "clip_tags": []
  },
  "overlap_ratio": 0.568
 },
 {
  "segment_id": "09d52700b6114b2f99869eea69f6d71e",
  "field": "scene",
  "ai": "客户家",
  "human": "工厂",
  "confidence": 0.85,
  "evidence": {
   "asr_hits": [
    [
     9500,
     "讓家裡面的整個空間非常險大"
    ]
   ],
   "asr_text": "讓家裡面的整個空間非常險大",
   "ocr_text": "",
   "keyframes": [
    9984,
    10000,
    11523,
    13030
   ],
   "clip_tags": []
  },
  "overlap_ratio": 0.657
 },
 {
  "segment_id": "09f514b80e394bdab5ef7cd25d6909b6",
  "field": "function",
  "ai": "收纳",
  "human": "抽屉",
  "confidence": 0.85,
  "evidence": {
   "asr_hits": [
    [
     180,
     "倒台做高5公分可以增加两个上层薄抽筷子勺子紫金牙线"
    ]
   ],
   "asr_text": "倒台做高5公分可以增加两个上层薄抽筷子勺子紫金牙线",
   "ocr_text": "加装 121-AC4 63A141 位老 到本工 拍视频 音直播， 只允许拍自起下单 的成品 禁止拍他 人的成品 谢谢大家的配合 向上 tique 加装 121-A 63Al 位老 拍视频 只允许拍 的成品， 人的成品 谢谢大家的 itiq",
   "keyframes": [
    0,
    2500,
    4984,
    5000
   ],
   "clip_tags": []
  },
  "overlap_ratio": 0.964
 },
 {
  "segment_id": "0ca01792998e4fc4aeb3b28a449ddc7b",
  "field": "product",
  "ai": "岛台",
  "human": "伸缩岛台",
  "confidence": 0.85,
  "evidence": {
   "asr_hits": [
    [
     2140,
     "导台跟桌面高度相差有20公分"
    ]
   ],
   "asr_text": "导台跟桌面高度相差有20公分",
   "ocr_text": "",
   "keyframes": [
    0,
    2500,
    4984,
    5000
   ],
   "clip_tags": []
  },
  "overlap_ratio": 0.572
 },
 {
  "segment_id": "0e6e0fcab21c4a17aad5c7c8c86902c0",
  "field": "product",
  "ai": "餐桌",
  "human": "岛台",
  "confidence": 0.85,
  "evidence": {
   "asr_hits": [
    [
     4460,
     "餐桌的位置可以容納12個人一起吃飯"
    ]
   ],
   "asr_text": "餐桌的位置可以容納12個人一起吃飯",
   "ocr_text": "",
   "keyframes": [
    4984,
    5000,
    7254,
    9493
   ],
   "clip_tags": []
  },
  "overlap_ratio": 0.546
 },
 {
  "segment_id": "1328a3c07e80437a840e1c83d2de489b",
  "field": "product",
  "ai": "岛台",
  "human": "伸缩岛台",
  "confidence": 0.85,
  "evidence": {
   "asr_hits": [
    [
     400,
     "3219"
    ],
    [
     2040,
     "这款导台选择了"
    ]
   ],
   "asr_text": "3219 这款导台选择了",
   "ocr_text": "以前的制造业，是工厂生产 然而，传承不是守旧，是带表 宝岛台 现在的我们，坚持以用户思维 探索传统制造业的能力边界， 制造业需要以不一样的形态， 以重塑制造业的 BARBL 以前的制造业，是 然而，传承不是守 宝岛台 现在的我们，坚持以 探",
   "keyframes": [
    0,
    2500,
    4984,
    5000
   ],
   "clip_tags": []
  },
  "overlap_ratio": 0.352
 },
 {
  "segment_id": "192c2be90233443b856126983ccaacf8",
  "field": "function",
  "ai": "收纳",
  "human": "抽屉",
  "confidence": 0.85,
  "evidence": {
   "asr_hits": [
    [
     2860,
     "另一面做的是三层大抽屉"
    ],
    [
     5420,
     "可以放点零食"
    ],
    [
     6500,
     "也可以放点收纳都可以的"
    ]
   ],
   "asr_text": "另一面做的是三层大抽屉 可以放点零食 也可以放点收纳都可以的",
   "ocr_text": "精工细作 放术至善 工艺部 仙秘界 高级胶粘带 BOPP-—8008 精工细作 放术至善 工艺部 仙秋米 高级胶粘带 BOPP-—8008 不至善 工艺部 高级胶粘带 BOPP—8008 工 高级 BOPP",
   "keyframes": [
    4984,
    5000,
    7104,
    9193
   ],
   "clip_tags": []
  },
  "overlap_ratio": 0.494
 },
 {
  "segment_id": "192c2be90233443b856126983ccaacf8",
  "field": "action",
  "ai": "收纳/关闭",
  "human": "拉出/展开",
  "confidence": 0.85,
  "evidence": {
   "asr_hits": [
    [
     2860,
     "另一面做的是三层大抽屉"
    ],
    [
     5420,
     "可以放点零食"
    ],
    [
     6500,
     "也可以放点收纳都可以的"
    ]
   ],
   "asr_text": "另一面做的是三层大抽屉 可以放点零食 也可以放点收纳都可以的",
   "ocr_text": "精工细作 放术至善 工艺部 仙秘界 高级胶粘带 BOPP-—8008 精工细作 放术至善 工艺部 仙秋米 高级胶粘带 BOPP-—8008 不至善 工艺部 高级胶粘带 BOPP—8008 工 高级 BOPP",
   "keyframes": [
    4984,
    5000,
    7104,
    9193
   ],
   "clip_tags": []
  },
  "overlap_ratio": 0.494
 }
]
```

## 7. 置信度与冲突分析
- 高置信(≥0.8)但错误: **76** 条
- 低置信(<0.5)但正确: **147** 条
- UNKNOWN但人工可明确判断: **282** 条
- AI与人工完全冲突: **86** 条

## 8. 结论

- 本报告为 **VALIDATION_SNAPSHOT_V1**（规则修改前独立验证快照）
- **未自动修复任何错误**（政策：禁止）
- 后续若据此修改规则/知识库/模型，这 300 条将转为 **CALIBRATION_CORPUS_V1**（可学习集），不再作为独立验证集
