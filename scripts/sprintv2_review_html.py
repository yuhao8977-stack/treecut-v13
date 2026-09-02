# -*- coding: utf-8 -*-
"""晨间审核包: G2/G3 HUMAN_REVIEW HTML(可播放 subclip) + V2 旧错演示。"""
import json, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")

def enc(path):
    from urllib.parse import quote
    return quote(path)

# ===== G2 review: Query20 动作查询 Top subclips =====
q20 = json.loads((OUT / "TREECUT_G2_ACTION_QUERY20_V1.json").read_text(encoding="utf-8"))["queries"]
windows = json.loads((OUT / "TREECUT_G2_SUBCLIP_WINDOWS_V1.json").read_text(encoding="utf-8"))["windows"]
paths = {w["media_id"]: w.get("asset_path") for w in windows}
rows = []
for q in q20[:12]:
    t3 = q.get("top3") or []
    cells = []
    for c in t3:
        p = paths.get(c["media_id"])
        if not p:
            cells.append("<td>无路径</td>")
            continue
        s, e = c["subclip"]
        link = f"/file?p={enc(p)}#t={s},{e}"
        cells.append(f"<td><a href='{link}' target='_blank'>▶ {c['media_id']} [{s}–{e}s]</a><br/>"
                     f"act {c['action_window'][0]}–{c['action_window'][1]}s b={c['boundary_usable']}<br/>"
                     f"<button onclick='mark(this,\"GOOD\")'>GOOD</button> "
                     f"<button onclick='mark(this,\"BAD\")'>BAD</button> "
                     f"<button onclick='mark(this,\"UNSURE\")'>UNSURE</button>")
    while len(cells) < 3:
        cells.append("<td>—</td>")
    rows.append(f"<tr><td>{q['qid']}<br/>{q['action']}</td><td>{q['top3_n']}</td>" + "".join(cells) + "</tr>")

g2_html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"/>
<title>G2 Human Review</title><style>
body{{font-family:'Microsoft YaHei';margin:16px}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #bbb;padding:6px;font-size:13px;vertical-align:top}}th{{background:#eee}}
.g{{color:#0a7a0a}}.b{{color:#c00}}</style></head><body>
<h2>STAGE8 G2 — 动作/Subclip 人工审核（HUMAN_VALIDATION_PENDING）</h2>
<p>点 ▶ 播放 subclip 窗口(非整段)。逐条给 GOOD/BAD/UNSURE，回填后我更新校准。</p>
<table><tr><th>Query(动作)</th><th>命中</th><th>Top1</th><th>Top2</th><th>Top3</th></tr>{''.join(rows)}</table>
<p>V2 硬负回归(单元测试): 伸缩口播→插座特写 = FAIL；轨道插座纯特写(1590-92)在 EXTEND 查询中被拒。</p>
</body></html>"""
(OUT / "TREECUT_G2_HUMAN_REVIEW_V1.html").write_text(g2_html, encoding="utf-8")
print("G2 review html saved")

# ===== G3 review: beats + claim + selected + V2 demo =====
proj = json.loads((OUT / "TREECUT_WORKBENCH_PROJECT_V1.json").read_text(encoding="utf-8"))
v2reg = json.loads((OUT / "TREECUT_G3_PILOT_V2_REGRESSION_V1.json").read_text(encoding="utf-8"))["regressions"]
brows = []
for b in proj["beats"]:
    sel = b.get("selected")
    cl = b.get("claim") or {}
    selcell = "—"
    if sel:
        p = sel.get("path")
        if p:
            s = (sel.get("subclip") or {}).get("start_s", 0)
            e = (sel.get("subclip") or {}).get("end_s", 0)
            selcell = f"<a href='/file?p={enc(p)}#t={s},{e}' target='_blank'>▶ {sel['media_id']} [{s}–{e}s]</a>"
    brows.append(f"<tr><td>{b['id']}</td><td>{cl.get('text','')[:50]}</td>"
                 f"<td>{cl.get('required_action')}/{cl.get('required_object')}</td>"
                 f"<td>{selcell}</td><td>{b['qa_note']}</td><td>"
                 f"<button onclick='mark(this,\"GOOD\")'>GOOD</button> <button onclick='mark(this,\"BAD\")'>BAD</button></td></tr>")
v2rows = "".join(
    f"<tr><td>{r['narration']}</td><td>轨道插座特写</td><td>{r['matcher_result']}</td><td>{'; '.join(r['reasons'])}</td></tr>"
    for r in v2reg)
g3_html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"/>
<title>G3 Human Review</title><style>
body{{font-family:'Microsoft YaHei';margin:16px}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #bbb;padding:6px;font-size:13px}}th{{background:#eee}}
.g{{color:#0a7a0a}}.b{{color:#c00}}</style></head><body>
<h2>STAGE8 G3 — Claim→Visual 人工审核</h2>
<p>脚本 beats + 系统选择(或 NO_VALID_CANDIDATE)。</p>
<table><tr><th>Beat</th><th>口播</th><th>Claim(动作/对象)</th><th>选中候选</th><th>QA</th><th>判定</th></tr>{''.join(brows)}</table>
<h3>V2 旧错演示：口播伸缩/收起 → 轨道插座特写必须被拒（新行为）</h3>
<table><tr><th>口播</th><th>视觉</th><th>结果</th><th>原因</th></tr>{v2rows}</table>
</body></html>"""
(OUT / "TREECUT_G3_HUMAN_REVIEW_V1.html").write_text(g3_html, encoding="utf-8")
print("G3 review html saved")
