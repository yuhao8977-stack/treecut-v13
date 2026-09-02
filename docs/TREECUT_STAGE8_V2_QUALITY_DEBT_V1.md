# Stage8 — Pilot V2 质量债务登记（G1 期间只登记，不修复）

> 登记依据：Pilot V2 人工审阅发现（V1vsV2 对比 + 视觉 QA）。
> 原则：G1 只解决"什么素材能进生产池"；以下债务按 §26 映射到后续 Gate，G1 不修。

| 债务 ID | 债务 | V2 证据 | 归属 Gate | 修法方向（仅登记，不实现） |
| --- | --- | --- | --- | --- |
| D1 | CAPTION_TOO_SMALL | V2 字幕 FontSize 55 偏小，观感接近旧小字 | G4 | 字幕字号/描边规范统一（如 60–70px + 更强描边），成片人工复核 |
| D2 | BGM_MISSING | BGM_PRESENT=False（无合法内部音乐源） | G4 | 合法/内部音乐源接入 + 人声 duck 8–12dB + 淡入淡出；无源则维持限制不冒充 |
| D3 | BEAT_VISUAL_MISMATCH | 口播"伸缩桌面"时画面含插座元素、Hook 与主张画面错位 | G3 | Claim→Visual Requirement 匹配 + 每 Beat 画面语义闸 |
| D4 | ACTION_NOT_DEMONSTRATED | "伸缩/抽屉"主张对应素材未见完整动作演示（L6/L8） | G2 | Segment→Action Window→Subclip；动作证据分级 ACTION_DEMONSTRATION_COMPLETE |
| D5 | NEAR_DUPLICATE_SHOT | 同案例近重复镜头入列未拦截 | G5 | 生产候选去重（含近重复）闸门 |
| D6 | VOICE_TIMBRE_TOO_SYNTHETIC | SAPI 机械感 | G4 | 真人克隆/更好 TTS；SAPI 仅 FALLBACK |
| D7 | SAPI_NOT_ACCEPTABLE_AS_PRIMARY_PRODUCTION_VOICE | 同上 | G4 | 明确 SAPI=FALLBACK_TTS；主声音源另立 |

## 映射总览

```
G1 什么素材能用        ← 本次执行（不修 D1–D7）
G2 什么时候正在发生动作  → D4
G3 这句文案匹配什么画面  → D3
G4 真人克隆配音+大字幕+BGM → D1, D2, D6, D7
G5 重复镜头/错配/漏音乐自动拦截 → D5
G6 Pilot V3 → 人工看片
```

## V2 已达标且不得回退（§27）

- 干净源使用（旧字幕/平台水印污染大幅下降）
- 1080×1920 渲染、真实硬烧新字幕
- AV 流级同步 ≤0.10s（实测 0.069s）
- 视频尾覆盖音频、48kHz 终音频、响度 I=-15.0 LUFS / TP=-3.4 dBTP
