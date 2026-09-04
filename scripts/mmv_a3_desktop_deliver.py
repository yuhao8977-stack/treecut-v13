#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MMVV A3 — 桌面交付物生成：完整 HTML 报告(含 30 帧画廊) + 产物副本。

输出目录: C:\\Users\\admin\\Desktop\\TreeCut_MMVV_A3_2026-09-04\\
  - 00_先读我_A3_HOLDOUT完整报告.html   (自包含，浏览器直接打开)
  - 01_TREECUT_MMVV_A3_REPORT.md       (报告 md 副本)
  - TREECUT_MMVV_A3_HOLDOUT_MANIFEST.json / _HUMAN_GT.json / _HOLDOUT_AUDIT.json / _SCREENING.json / _CANDIDATES.json
  - frames\\m<media>_<i>.jpg            (6 案例 × 5 帧 = 30 帧，供画廊引用)
"""
from __future__ import annotations

import html
import json
import shutil
import sys
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
DOCS = REPO / "docs"
FRAMES_SRC = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\mmv_a3_holdout_frames")
DESK = Path(r"C:\Users\admin\Desktop\TreeCut_MMVV_A3_2026-09-04")
sys.stdout.reconfigure(encoding="utf-8")


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def esc(v):
    return html.escape(str(v if v is not None else ""))


man = load("TREECUT_MMVV_A3_HOLDOUT_MANIFEST.json")
aud = load("TREECUT_MMVV_A3_HOLDOUT_AUDIT.json")
gt = load("TREECUT_MMVV_A3_HUMAN_GT.json")
scr = load("TREECUT_MMVV_A3_SCREENING.json")

DESK.mkdir(parents=True, exist_ok=True)
fr = DESK / "frames"
fr.mkdir(parents=True, exist_ok=True)

# ---- 复制 30 帧 ----
for c in man["cases"]:
    for f in c["frames"]:
        shutil.copy2(Path(f["local_path"]), fr / f["frame"])

# ---- 复制 JSON / md 产物 ----
for n in ["TREECUT_MMVV_A3_HOLDOUT_MANIFEST.json", "TREECUT_MMVV_A3_HUMAN_GT.json",
          "TREECUT_MMVV_A3_HOLDOUT_AUDIT.json", "TREECUT_MMVV_A3_SCREENING.json",
          "TREECUT_MMVV_A3_CANDIDATES.json"]:
    shutil.copy2(OUT / n, DESK / n)
shutil.copy2(DOCS / "TREECUT_MMVV_A3_REPORT.md", DESK / "01_TREECUT_MMVV_A3_REPORT.md")

# ---- HTML 组装 ----
P = []
A = P.append
A("<!DOCTYPE html><html lang='zh'><head><meta charset='utf-8'/>")
A("<title>TreeCut MMVV A3 · Holdout 冻结完整报告</title>")
A("<style>body{font-family:'Microsoft YaHei',sans-serif;margin:0;background:#f5f6f8;color:#222;line-height:1.7}")
A("header{padding:18px 26px;background:#1f2937;color:#fff}")
A("h1{font-size:20px;margin:0 0 6px}h2{font-size:17px;border-left:5px solid #1a73e8;padding-left:10px;margin-top:34px}")
A(".wrap{max-width:1100px;margin:0 auto;padding:18px 26px 60px}")
A("table{border-collapse:collapse;width:100%;margin:10px 0;background:#fff;font-size:13px}")
A("th,td{border:1px solid #d5dbe3;padding:6px 9px;text-align:left;vertical-align:top}")
A("th{background:#eef2f7}.badge{display:inline-block;background:#0a7d33;color:#fff;padding:2px 12px;border-radius:12px;font-size:13px}")
A(".badge.stop{background:#b3261e}.warn{background:#fff8e1;border:1px solid #f0d070;padding:10px 14px;border-radius:8px;font-size:13px}")
A(".ok{background:#e6f4ea;border:1px solid #a5d6b2;padding:8px 12px;border-radius:8px}")
A(".casebox{border:1px solid #cfd6e0;background:#fff;border-radius:10px;padding:12px 14px;margin:14px 0}")
A(".casebox h3{margin:2px 0 6px;font-size:15px}")
A(".imgs{display:flex;gap:8px;flex-wrap:wrap}")
A(".imgs figure{margin:0;width:210px}")
A(".imgs img{width:210px;border:1px solid #bbb;background:#000}")
A("figcaption{font-size:11px;color:#555}")
A(".mono{font-family:Consolas,monospace;font-size:12px;background:#f0f2f5;padding:1px 5px;border-radius:4px}")
A("li{margin:4px 0}.small{font-size:12px;color:#666}</style></head><body>")

A("<header><h1>TreeCut MMVV A3 · 泛化验证准备（第二停点）完整报告</h1>")
A(f"<span style='font-size:13px;color:#cfe0ff'>状态：<b style='color:#7dffa0'>A3_HOLDOUT_6_FROZEN</b>（STOP —— 未运行任何机器预测，等架构师审核）</span>"
  f"<span style='font-size:13px;color:#cfe0ff;margin-left:22px'>算法冻结基座 <span class='mono' style='background:#334155;color:#ffe08a'>ca34678</span> · 采样冻结 <span class='mono' style='background:#334155;color:#ffe08a'>A3_SAMPLING_UNIFORM_TIME_V1</span></span></header>")
A("<div class='wrap'>")

A("<div class='warn'><b>STOP 纪律：</b>本次停点只做「冻结 + 查重 + GT 隔离 + ROI 页面」，不运行 MMVV 预测。"
  "下一步顺序：① 架构师审核 holdout 纯净性（本报告 + AUDIT）→ ② 人工在 ROI 页标注 30 帧 → ③ 批准后机器以冻结算法作答（只读 manifest+ROI，不读 GT，不 tune，如实报告 PASS/FAIL/UNSURE）。"
  "若 NO 案例出现 False PASS → NEEDS_REPAIR 并 STOP。</div>")

# ---- 阅读清单 ----
A("<h2>一、需要读的内容（阅读清单）</h2><table><tr><th>顺序</th><th>文件</th><th>职责 / 读什么</th><th>机器可否读</th></tr>")
A("<tr><td>1</td><td class='mono'>本 HTML（先读我）</td><td>12 项报告、筛选统计、家族/查重证据、冻结清单与 30 帧画廊、下一步</td><td>—（人工）</td></tr>")
A("<tr><td>2</td><td class='mono'>TREECUT_MMVV_A3_HOLDOUT_AUDIT.json</td><td>冻结审计：筛选统计、1985–89 家族排除的帧级证据、污染三层检查、GT 隔离、ROI 页状态</td><td>—（人工）</td></tr>")
A("<tr><td>3</td><td class='mono'>TREECUT_MMVV_A3_HOLDOUT_MANIFEST.json</td><td>机器唯一输入清单：6 案例 × 5 帧（t_s/sha256/尺寸）+ 采样策略 + 源 sha256 + G1 资格</td><td><b>是（唯一）</b></td></tr>")
A("<tr><td>4</td><td class='mono'>TREECUT_MMVV_A3_HUMAN_GT.json</td><td>人工答案：每案例 human_gt + 期望机器结果（评分时按 case_id 合并）</td><td>否（评分前禁读）</td></tr>")
A("<tr><td>5</td><td class='mono'>TREECUT_MMVV_A3_SCREENING.json</td><td>人工筛选日志（17 候选标签与时间戳）</td><td>否</td></tr>")
A("<tr><td>6</td><td class='mono'>frames/（30 张）</td><td>冻结帧全分辨率 JPEG（画廊可点开逐帧查看）</td><td>是（作为特征输入）</td></tr>")
A("<tr><td>7</td><td><a href='http://127.0.0.1:8933/a3/roi'>ROI 标注页 /a3/roi</a></td><td>人工对象框标注（桌板/伸缩桌板/岛台主体 + 可选人/手/抽屉/轨道插座/插座模块），无 AI 预填、无动作答案</td><td>ROI 保存后机器读取</td></tr></table>")

# ---- 12 项 ----
A("<h2>二、12 项报告</h2>")
A(f"<table><tr><th>#</th><th>项目</th><th>结论</th></tr>")
rows12 = [
    ("1", "人工筛选统计", f"17 候选 → YES_EXTEND={aud['screening_summary']['YES_EXTEND']} / NO_EXTEND={aud['screening_summary']['NO_EXTEND']} / UNCLEAR={aud['screening_summary']['UNCLEAR']}（架构师 18:28–18:29 完成）"),
    ("2", "冻结案例", "POS：A3_POS_01(2521)/A3_POS_02(2549)/A3_POS_03(2551)；NEG：A3_NEG_01(2209)/A3_NEG_02(2280)/A3_NEG_03(2544)"),
    ("3", "标签来源", "架构师人工筛选（screened_at 见 HUMAN_GT），notes 为空"),
    ("4", "视觉家族", "POS 3/3 独立（南京魏/深圳张/深圳于）；NEG 3/3 独立（乌鲁木齐燕/广州李/深圳徐）—— 均 ≥2/3 达标"),
    ("5", "1987–89 结论", "SAME_VISUAL_FAMILY_AS_KNOWN（与旧 Known 1985/1986 同【61】海口吴家族）→ 排除；1987≡1988 逐帧重复证据见 AUDIT"),
    ("6", "旧集重叠", "无（6 media_id 均不在 excluded_known_ids）"),
    ("7", "污染检查", "PASS（媒体级无重叠 / 30 帧 sha 与 A1 旧 27 帧零碰撞 / 家族级无 Known 重叠）"),
    ("8", "GT 隔离", "答案仅存 HUMAN_GT+SCREENING；manifest 无答案字段（泄漏扫描零命中）；机器输入边界已在 manifest 声明"),
    ("9", "采样冻结", "A3_SAMPLING_UNIFORM_TIME_V1（均匀窗口[0.15,0.85]×duration，5帧/案例，与筛选同时间戳，禁挑帧）"),
    ("10", "ROI 页面", "http://127.0.0.1:8933/a3/roi（8 类对象、无 AI 预填、无动作/方向/结论输入）"),
    ("11", "提交", "75c3017（已推送 origin/main；docs/报告 + 5 JSON + runner + ROI 页 + server 扩展，8 文件 +1329 行）"),
    ("12", "状态", "A3_HOLDOUT_6_FROZEN"),
]
for n, t, v in rows12:
    A(f"<tr><td>{n}</td><td><b>{esc(t)}</b></td><td>{esc(v)}</td></tr>")
A("</table>")

# ---- 筛选明细 ----
A("<h2>三、人工筛选明细（17 候选）</h2><table><tr><th>media_id</th><th>标签</th><th>筛选时间</th><th>归属</th></tr>")
sel_ids = [c["media_id"] for c in man["cases"]]
for mid in sorted(scr["verdicts"], key=int):
    v = scr["verdicts"][mid]
    sel = "✅ 入选 " + next((c["case_id"] for c in man["cases"] if c["media_id"] == int(mid)), "")
    fam = ""
    if int(mid) in (1987, 1988, 1989):
        fam = "（Known 家族 → 排除）"
    if int(mid) in (2550,):
        fam = "（与 2549 同客户 → 弃用）"
    A(f"<tr><td>{mid}</td><td><b>{esc(v['label'])}</b></td><td>{esc(v['at'])}</td><td>{esc(sel)}{esc(fam)}</td></tr>")
A("</table>")

# ---- 家族/污染证据 ----
A("<h2>四、家族与污染检查（证据摘要，全文见 AUDIT）</h2>")
A("<table><tr><th>检查</th><th>结论</th><th>帧级证据</th></tr>")
A("<tr><td>1985–89 公牛轨道插座家族（【61】海口吴小姐）</td><td><b>SAME_VISUAL_FAMILY_AS_KNOWN → 1987/1988/1989 排除</b></td><td>1985≡1986、1987≡1988 在 t=1.9/2.525/3.15/3.775/4.4s 解码帧 sha256 完全一致（逐帧重复）；1986'-2(1)'与1987'-2'同源变体，与旧 Known CAMERA_CASE_FAMILY_SOCKET_01 同案例</td></tr>")
A("<tr><td>深圳张小姐 2549/2550</td><td>同客户系列 → 仅取 2549</td><td>2549/2550/2551 互不重复（粗粒度相似度 max&lt;0.90，不同拍摄）</td></tr>")
A("<tr><td>入选池 7 段交叉近重复</td><td>无</td><td>任意两素材跨时间粗粒度相似度 max&lt;0.90</td></tr>")
A("<tr><td>污染（vs 旧样本）</td><td class='ok'>PASS</td><td>媒体级：6 media_id ∉ excluded_known_ids；帧级：30 sha vs A1 旧 27 sha 零碰撞；家族级：无 Known 家族重叠</td></tr></table>")

# ---- 冻结清单 + 画廊 ----
A("<h2>五、冻结 Holdout 清单（6 案例 × 5 帧 = 30 帧，全分辨率）</h2>")
A("<table><tr><th>case_id</th><th>media_id</th><th>视觉家族 / 描述</th><th>窗口(秒)</th><th>G1</th><th>源 sha256(前12)</th></tr>")
for c in man["cases"]:
    A(f"<tr><td><b>{esc(c['case_id'])}</b></td><td>{c['media_id']}</td><td>{esc(c['visual_family_id'])}<br/><span class='small'>{esc(c['desc'])}</span></td>"
      f"<td>[{c['frozen_window_s'][0]}, {c['frozen_window_s'][1]}]</td><td>{'✅ eligible' if c['g1_eligible'] else '❌'}</td>"
      f"<td class='mono'>{c['source_sha256'][:12]}</td></tr>")
A("</table>")
for c in man["cases"]:
    A(f"<div class='casebox'><h3>{esc(c['case_id'])} · media {c['media_id']} · {esc(c['visual_family_id'])}"
      f" <span class='small'>窗口 [{c['frozen_window_s'][0]},{c['frozen_window_s'][1]}]s · G1={'是' if c['g1_eligible'] else '否'}</span></h3>")
    A(f"<div class='small'>{esc(c['desc'])}</div>")
    A("<div class='imgs'>")
    for f in c["frames"]:
        A(f"<figure><img src='frames/{f['frame']}' alt='{f['frame']}' loading='lazy'/>"
          f"<figcaption>#{f['idx']} t={f['t_s']}s · {f['width']}×{f['height']} · {f['bytes']}B<br/>"
          f"<span class='mono'>{f['sha256'][:16]}</span></figcaption></figure>")
    A("</div></div>")

# ---- GT 表 ----
A("<h2>六、人工 GT（答案；评分前机器禁读）</h2><table><tr><th>case_id</th><th>media_id</th><th>human_gt</th><th>期望机器结果</th><th>筛选时间</th></tr>")
for a in gt["answers"]:
    A(f"<tr><td>{esc(a['case_id'])}</td><td>{a['media_id']}</td><td>{esc(a['human_gt'])}</td><td>{esc(a['expected_machine'])}</td><td>{esc(a['screened_at'])}</td></tr>")
A("</table>")

# ---- 采样与 GT 隔离 ----
A("<h2>七、采样策略冻结 + GT 隔离</h2>")
sp = man["sampling_policy"]
A(f"<table><tr><th>采样策略</th><th>取值</th></tr>"
  f"<tr><td>policy_id</td><td class='mono'>{esc(sp['policy_id'])}</td></tr>"
  f"<tr><td>mode / 窗口</td><td>uniform_time_window · relative [{sp['relative_window'][0]}, {sp['relative_window'][1]}] × duration</td></tr>"
  f"<tr><td>帧数 / 时间点</td><td>{sp['frames_per_case']} / 案例 @ {sp['relative_fractions']}</td></tr>"
  f"<tr><td>抽取</td><td>{esc(sp['extraction'])}</td></tr>"
  f"<tr><td>说明</td><td>{esc(sp['note'])}</td></tr></table>")
A("<div class='ok'><b>机器输入边界：</b>" + esc(man["machine_input_boundary"]) + "</div>")

A("<h2>八、下一步（等待架构师）</h2><ol>"
  "<li>审核本报告 + AUDIT 的 holdout 纯净性（6 案例、家族/查重/污染证据、GT 分离）。</li>"
  "<li>在 <a href='http://127.0.0.1:8933/a3/roi'>ROI 页 /a3/roi</a> 完成 30 帧人工对象框标注（桌板/伸缩桌板/岛台主体为关键目标）。</li>"
  "<li>批准后：机器以冻结算法（ca34678）对 manifest 作答——只读 manifest+ROI，不读 GT，不 tune，如实报告 PASS/FAIL/UNSURE；NO 案例出现 PASS 即 False PASS → NEEDS_REPAIR 并 STOP。</li></ol>")

A(f"<p class='small'>生成：{man['generated_at']} · 提交 75c3017 · 本文件夹 = 完整交付（报告/JSON/30帧/画廊）· 仓库对应 docs/TREECUT_MMVV_A3_REPORT.md</p>")
A("</div></body></html>")

html_doc = "\n".join(P)
(DESK / "00_先读我_A3_HOLDOUT完整报告.html").write_text(html_doc, encoding="utf-8")
print("WROTE", DESK / "00_先读我_A3_HOLDOUT完整报告.html", len(html_doc), "bytes")
print("frames copied:", len(list(fr.glob("*.jpg"))))
