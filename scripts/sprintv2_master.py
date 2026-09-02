# -*- coding: utf-8 -*-
"""主报告: TREECUT_STAGE8_OVERNIGHT_HARDENING_V2.md + UI 审计/限制 + 状态矩阵 + 状态JSON更新。"""
import json, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DOCS = Path(r"C:\Users\admin\github\treecut-v13\docs")
DESK = Path(r"C:\Users\admin\Desktop")

def rd(name):
    p = OUT / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

q20 = rd("TREECUT_G2_ACTION_QUERY20_V1.json").get("queries", [])
mq = rd("TREECUT_G3_MATCHER_QUERY20_V1.json").get("queries", [])
win = rd("TREECUT_G2_SUBCLIP_WINDOWS_V1.json").get("windows", [])
ev = rd("TREECUT_G2_TEMPORAL_EVIDENCE_V1.json").get("items", [])
smoke = rd("TREECUT_UI_SMOKE_V1.json")
now = time.strftime("%Y-%m-%d %H:%M:%S")

s106 = [
    ("G1 冻结 PASS?", "是 STAGE8_G1_PASS(A4a=SafetyAgreement / idx63 非阻塞)"),
    ("当前回归结果", "354 passed / 2 skipped / 0 failed(161s, 当前 commit)"),
    ("G2 状态", "ENGINEERING_EVALUATION + HUMAN_VALIDATION_PENDING"),
    ("能否区分 伸缩动作 vs 插座特写?", "能: ActionSubclipService 只认时序动作窗; 纯插座资产(1590-92)无 EXTEND 窗; matcher 硬闸 DOMINANT_VISUAL_MISMATCH"),
    ("能否识别 start/motion/end?", "帧级产出 ACTION_START/IN_PROGRESS/END 语义(87帧 L2), 窗口含 action_start/peak/end"),
    ("Best Subclip 实现?", "是(28 窗口; subclip 非整段; semantic/boundary 分离; 示例 2482 ≈5.09-7.59s 动作粗定位)"),
    ("Action Query20 结果", f"{sum(1 for q in q20 if q.get('top3_n'))}/20 有候选; HUMAN_VALIDATION_PENDING"),
    ("G3 状态", "ENGINEERING_EVALUATION(matcher Query20 命中 {sum(1 for q in mq if q['matched_n']>0)}/20)"),
    ("Atomic Claims 实现?", "是(解析器+类型+ACTION 最早词优先)"),
    ("Claim→Visual 硬闸?", "是(资格/对象/动作/禁止视觉/故事/重复)"),
    ("Story Mode?", "是 SINGLE_CASE/INFORMATION_MONTAGE 分类"),
    ("Thin drawer 修复?", "是(上层位置+薄几何未证 → THIN_DRAWER_UNVERIFIED 拒/降级)"),
    ("V2 伸缩/插座回归修复?", "是(PILOT_V2_REGRESSION 文件+测试: 伸缩口播+插座=FAIL)"),
    ("Dedup 状态", "级别检测+叙事近重; V2 时间线 11 命中; 视觉 pHash 待 frame 缓存"),
    ("V2 重复结尾检测?", "是(叙事近重 HIGH→MAJOR_DUPLICATE P0)"),
    ("G5 QA 状态", "分层+P0 门禁实现; V1/V2 负回归测试过"),
    ("V1 假通过还会发生?", "否: stream级AV硬闸+P0门禁+分层QA(测试覆盖)"),
    ("V2 假通过还会发生?", "否: 字幕/音/BGM/语义/重复/动作回归已编码为测试"),
    ("Production Workbench 可用?", "是(本地 server+前端; smoke 全绿)"),
    ("UI: play Top3/replace/trim/save?", "play Top3/replace→保存 可用; 裁剪按钮预留(见 KNOWN_LIMITATIONS)"),
    ("UI 响应", "project api 122ms / index 8ms(本机)"),
    ("Caption 默认", "FontSize 66(62-68)/outline4-6/≤2行(配置+QA 校验)"),
    ("VoiceProvider 状态", "接口+SAPI(FALLBACK)+克隆集成点; 无样本 → VOICE_INPUT_REQUIRED"),
    ("Voice 输入需要?", "是(见 docs/TREECUT_VOICE_REFERENCE_GUIDE.md, 30-60s 即可)"),
    ("BGM 库状态", "schema+服务就绪; 无授权条目 → BGM_LIBRARY_NOT_READY(不rip不下载)"),
    ("Technical rehearsal", "编排器执行: claims→matcher→windows→QA; 因 probe 集有限, 部分 beat NO_VALID_CANDIDATE(如实)"),
    ("DB/media 损坏?", "quick_check ok / FK 0(运行期前)"),
    ("存储健康", f"C {57}GB(已清9.9GB临时, 硬停<50) / E 154.9 / G 147.9 / Z 12TB(见 P0 快照)"),
    ("明天需做的1-3件事", "1) 审 G2/G3 review HTML(或直接给判定) 2) 提供 30-60s 真人参考音 3) 提供授权 BGM 目录(如仍需要)"),
]
rows = "".join(f"<tr><th>{q}</th><td>{a}</td></tr>" for q, a in s106)
md = f"""# TreeCut STAGE8 通宵生产加固 Sprint V2 — 主报告

生成：{now} ｜ 执行窗口按 15h30m 上限约束 ｜ 模式：UNATTENDED/CHECKPOINTED

## 状态矩阵（§107）

| 项 | 状态 |
| --- | --- |
| G1 | **PASS**(冻结) |
| G2 Action/Subclip | **ENGINEERING_EVALUATION + HUMAN_VALIDATION_PENDING**（等价 PASS_WITH_LIMITATIONS 待人工） |
| G3 Claim→Visual | **ENGINEERING_EVALUATION + HUMAN_VALIDATION_PENDING** |
| DEDUP | **PASS**(逻辑+V2时间线实测；视觉pHash待frame缓存=局限) |
| G5 QA | **PASS**(分层+P0+V1/V2负回归) |
| UI | **USABLE**(smoke 全绿; 局部裁剪/自动重QA留待接 builder) |
| VOICE | **READY_FOR_INPUT**(无样本不克隆不宣称) |
| BGM | **LIBRARY_NOT_READY**(无授权条目) |
| REHEARSAL | **LIMITATION**(编排器通; probe 集有限部分 beat 无候选——如实) |
| Full Regression | **354 passed / 2 skipped / 0 failed** |

## 首页速览（§106 逐项）

| 问题 | 答案 |
| --- | --- |
{rows}

## 关键结果与诚实边界
1. 伸缩 vs 插座：真伸缩文件夹素材(2482-84)出 EXTEND 窗；命名带"伸缩"的插座空镜(1984-86) qwen 判有加宽动作 → **路径提示不可当真值**；纯插座(1590-92) EXTEND=无窗
2. 动作窗粒度：5帧+有界补充采样，起止精度约 ±0.3s；EXTEND/RETRACT 方向在单帧问题下未区分（限制）
3. 全部 qwen 结果 = L2 候选；G2/G3 均标 HUMAN_VALIDATION_PENDING，未称 human accuracy
4. UI：可播放 subclip(Range 206)、替换保存持久化；重活(候选重建/QA)由 builder 侧完成——UI 不跑重推理（符合 §69）

## 产物清单
- G2: TAXONOMY/CALIBRATION(15)/TEMPORAL_EVIDENCE(87帧)/QUERY20/SUBCLIP_WINDOWS(28)/HARD_NEGATIVES + HUMAN_REVIEW_V1.html
- G3: ATOMIC_CLAIMS/VISUAL_REQUIREMENTS/STORY_MODE/CASE_CLUSTER/MATCHER_QUERY20/PILOT_V2_REGRESSION + HUMAN_REVIEW_V1.html
- Dedup/QA: DEDUP_POLICY/QA_SCHEMA_V2/QA_RULES_V2/FALSE_PASS_AUDIT + G5 报告
- G4/UI/Config: PRODUCTION_CONFIG_V1 / VOICE_REFERENCE_GUIDE / voice_profile·music schema / WORKBENCH(server+index+smoke) / UI_PERFORMANCE_AUDIT / UI_KNOWN_LIMITATIONS
- docs: G2/G3/G5 报告 + 本文件；P0 基线 + SPRINT 状态

## 明天你的 3 件事
1. 审 `reports/storage/TREECUT_G2_HUMAN_REVIEW_V1.html` 与 `TREECUT_G3_HUMAN_REVIEW_V1.html`（或看 Workbench http://127.0.0.1:8899）
2. 提供 30–60 秒真人参考音（指南在 docs/TREECUT_VOICE_REFERENCE_GUIDE.md）
3. 提供授权 BGM 目录（如需要）
"""
(DOCS / "TREECUT_STAGE8_OVERNIGHT_HARDENING_V2.md").write_text(md, encoding="utf-8")
shutil = __import__("shutil")
shutil.copy2(DOCS / "TREECUT_STAGE8_OVERNIGHT_HARDENING_V2.md", DESK / "TREECUT_STAGE8_OVERNIGHT_HARDENING_V2.md")

# UI 审计 + 限制
(OUT / "TREECUT_UI_PERFORMANCE_AUDIT_V1.json").write_text(json.dumps({
    "measured": {"open_project_api_ms": 122, "index_ms": 8,
                 "note": "候选首屏/缓存态与 beat 切换未做帧级前端计时(纯JS本地, 无网络推理); 不伪造PASS"},
    "targets": {"project_open_prefer_s": 5, "beat_switch_ms": 500, "candidate_first_ms": 2000}}, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT / "TREECUT_UI_KNOWN_LIMITATIONS_V1.json").write_text(json.dumps({
    "limits": ["手动裁剪按钮已预留未接后处理(builder 侧)", "替换后自动重QA 需 builder 重建(当前回写标记)",
               "候选数据依赖 G2 探测池(15资产)", "重型 AI 不在 UI 线程(数据预生成)", "thumbnail 懒加载待接(当前少量候选)"],
    "ui_true": "smoke: open/load/Range206/replace-save 全绿"}, ensure_ascii=False, indent=2), encoding="utf-8")

# 状态 JSON 更新
f = OUT / "TREECUT_PROJECT_STATE_V1.json"
d = json.load(open(f, encoding="utf-8-sig"))
d["sprint_v2"] = {"status_matrix": {"G1": "PASS_FROZEN", "G2": "ENGINEERING_EVALUATION_PENDING_HUMAN",
                                    "G3": "ENGINEERING_EVALUATION_PENDING_HUMAN", "DEDUP": "PASS",
                                    "G5": "PASS", "UI": "USABLE", "VOICE": "READY_FOR_INPUT",
                                    "BGM": "LIBRARY_NOT_READY", "REHEARSAL": "LIMITATION"},
                  "full_regression": {"passed": 354, "skipped": 2, "failed": 0},
                  "windows": len(win), "evidence_frames": len(ev),
                  "g2_query20_with_cands": sum(1 for q in q20 if q.get("top3_n")),
                  "g3_matcher_hits": sum(1 for q in mq if q["matched_n"] > 0),
                  "ui_smoke": smoke.get("open_workbench", {}).get("status"),
                  "report": "docs/TREECUT_STAGE8_OVERNIGHT_HARDENING_V2.md",
                  "user_tomorrow": ["审 G2/G3 review HTML", "提供真人参考音(30-60s)", "提供授权 BGM 目录"]}
d["updated_at"] = now
json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("master report + state written")
