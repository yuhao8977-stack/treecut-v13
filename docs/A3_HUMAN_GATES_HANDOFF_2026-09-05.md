# A3 人工门控交接说明（Observability Review + 30 帧 ROI）

- 日期：2026-09-05 · 状态：两门控页面就绪待人工执行；机器侧保持 fail-closed
- 纪律：执行者全程**不得**打开 `TREECUT_MMVV_A3_CASE_KEY_PRIVATE.json` 或 `TREECUT_MMVV_A3_HUMAN_GT.json`；
  只按画面判断，不按"应该是正是负"判断。页面本身不含 GT/POS/NEG/media/客户信息（已核验）。

## 1. 门控一：A3 时间可观测性人工审阅

- 文件：`reports/storage/TREECUT_MMVV_A3_TEMPORAL_OBSERVABILITY_REVIEW.html`（双击本地打开即可；
  或查看 Overnight 桌面包同文件）
- 对象：H001–H006，每案例 5 帧 + 帧间指标表（帧差/边缘差/光流/相机平移/前景残留代理/静态区间比）
- 只回答一个问题：**这 5 张冻结帧之间，桌板/台面有没有清晰可辨认的伸缩位移过程？**
- 选项：`action_visible` 动作过程充分 / `endpoints_only` 只有起止状态 / `static` 基本静态 /
  `unclear` 看不清 / `unsuitable` 采样不适合判断
- 操作：每案例勾选一项 → 点底部「导出人工结论」下载 JSON
  （建议把下载的 `a3_obs_human_answers.json` 放到 `reports/storage/`）
- 重要：observability 只是"帧间存在时间变化"的信号（H001–H006 全 STRONG_CHANGE，且相机位移可达几十 px，
  如 H002 相机约 76px），**它不能代替你直接看画面**。真正要判断的是画面里桌板/台面本体是否在位移。

## 2. 门控二：A3 30 帧人工 ROI

- 页面：http://127.0.0.1:8933/a3/roi （本地服务已在跑；显示 H001–H006，每案例 F0–F4 共 30 帧）
- 对象规则：
  - 关键目标：`桌板/台面 TABLETOP`、`伸缩桌板 EXTENSION_TABLETOP`、`岛台主体 ISLAND_BODY`
  - 重叠干扰也尽量框：`人 PERSON`、`手 HAND`（A2 已证明"人动≠桌板动"）
  - 可选：`抽屉 DRAWER`、`轨道插座 TRACK_SOCKET`、`插座模块 SOCKET_MODULE`
- 操作：
  - 选标签 →「开始框选」→ 拖出矩形；每帧画完点「保存当前图片 (S)」
  - 快捷键：`A`/`D` 切帧，`S` 保存，`Delete` 删除选中
  - 「复制上一帧框(草稿)」会把上一帧的框带过来——必须逐框人工确认并调整后才保存，不会自动提交
- 保存去向：`reports/storage/TREECUT_MMVV_A3_HUMAN_GT_ROI_BLIND.json`
  （当前 0 框 → `run_a3_blind.py` 保持 `A3_ROI_REQUIRED` fail-closed；保存 ≥1 框且帧哈希绑定通过后才解锁）
- 完成判据：6 案例 × 5 帧全部有框（页面右上角显示"已完成案例 X/6"）

## 3. 两项完成后的严格序列（等待架构师批准指令）

1. `run_a3_blind.py --selfcheck`（盲帧完整性）
2. 架构师批准 → **blind prediction**（H001–H006，只读 blind 输入 + ROI_BLIND）
3. 固化 `A3_MACHINE_PREDICTIONS_BLIND.json` 的 sha256（预测哈希先于打开任何人工答案）
4. 评分进程才读 `CASE_KEY_PRIVATE` + `HUMAN_GT` 合并出分
- 全程：不调参、不换帧、不加辅助帧、不改冻结算法（ca34678）

## 4. 就绪核验记录（2026-09-05）

- /a3/roi → 200；/api/a3/blind → 200；/api/a3/blind-rois → 200（0 框）；
  /a3/bframes/H001_F0.jpg、H006_F4.jpg → 200（帧可达）
- Observability HTML：6 组单选齐备；无 GT/POS/NEG/media/客户词元
  （唯一 '2549' 命中位于 base64 图像数据内，为巧合，非泄漏）
- 越界框保存被拒（400）；合法保存→读回→清空已验证
