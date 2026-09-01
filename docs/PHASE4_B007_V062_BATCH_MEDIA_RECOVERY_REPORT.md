# Phase 4 — B007 V0.6.2 Batch Exact Media Recovery Report

## Status

**B007_V062_MEDIA_RECOVERY_PASS**

## Approval

V0.6.1 (V06_ASSISTED_PILOT1_PASS) 验收通过后，架构批准 V0.6.2 处理 Sample20 剩余 19 条。
默认 AUTO_CREATOR_NAVIGATION（搜索→定位→正常点击 Creator 卡片→平台生成合法 Frontend Detail），
无法唯一定位时 HUMAN_ASSISTED_NAVIGATION（用户只需正常点击，不下载/不复制 URL/不看 Network）。

## Method (locked disciplines)

- 输入冻结：B007_SAMPLE20_V1（20 条，不增换选）；Pilot1 预检 ALREADY_RECOVERED_VALID 后禁止重下载。
- 身份唯一：actual_note_id == expected_note_id 硬门；title 仅 NAVIGATION_HINT。
- 媒体路径：Creator 卡片正常点击 → 平台自带合法 xsec 的前台详情 → 播放器真实请求视频（PAGE_OWNED_MEDIA_OBSERVATION）。
- 媒体 URL 仅存内存生命周期内（临时签名 URL 不落 DB/JSON/MD/Log）。
- 验证：ffprobe + 全量 ffmpeg decode + SHA256 + 统一 duration 容差（max(5.0, dur*0.15)）。
- 存储：E staging(.part) → 验证通过后 shutil.move 至 Z（跨卷 os.replace 会 WinError 17）。
- 重复：SHA256 EXACT 去重；已有 blob 只建 note→canonical reference，不重复保存。
- 串行单 worker、逐条 checkpoint、可断点续跑；C-drive guard + Z gate。

## Result

- target = 20
- already recovered valid = 1
- newly recovered exact = 19
- total exact available = 20
- navigation auto success = 0 (of 19 remaining)
- human navigation required = 19 (of 19 remaining)
- navigation failed = 0
- note unavailable = 0
- identity mismatch = 0
- media not observed = 0
- validation failure = 0
- failed needs human = 0
- pending = 0

## Tech Coverage (recovered media)

- SHA256 coverage: 20/20
- ffprobe coverage: 19/20
- full decode coverage: 19/20
- duration crosscheck: 20/20
- resolution coverage: 20/20
- codec coverage: 20/20
- audio coverage: 20/20

## Duplicate Report

- recovered note count = 20
- unique SHA256 count = 20
- exact duplicate group count = 0

## Honest Limitations

- 媒体身份 = note_id + SHA256；不含视觉/语义去重（本轮只做 SHA256 EXACT）。
- 恢复不代表业务归因；与投放/表现无因果关系（沿用 V0.4 纪律）。
- 若存在 NOTE_UNAVAILABLE / FAILED_NEEDS_HUMAN，不虚构成功、不换样本。
- 标题搜索仅导航提示；身份永远以 note_id 硬门为准。

## C-Drive Guard

- C free before: None GB
- C free after: 69.6 GB

## STOP

处理完整 Sample20 后 STOP。不自动进入 V0.7（Canonical Asset / Segment / ASR / OCR / Business Cognition）。
