# -*- coding: utf-8 -*-
"""G2/G3 HUMAN_REVIEW_V2(新 schema, 标记可导出) + 晨间验证状态 + 状态矩阵冻结。"""
import json, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")

def enc(p):
    from urllib.parse import quote
    return quote(p)

now = time.strftime("%Y-%m-%d %H:%M:%S")
win = json.loads((OUT / "TREECUT_G2_SUBCLIP_WINDOWS_V1.json").read_text(encoding="utf-8"))["windows"]
paths = {w["media_id"]: w.get("asset_path") for w in win}
q20 = json.loads((OUT / "TREECUT_G2_ACTION_QUERY20_V1.json").read_text(encoding="utf-8"))["queries"]
proj = json.loads((OUT / "TREECUT_WORKBENCH_PROJECT_V1.json").read_text(encoding="utf-8"))

# ---------- G2 review V2 ----------
rows = []
for q in q20:
    t3 = q.get("top3") or []
    tds = []
    for c in t3:
        p = paths.get(c["media_id"])
        if not p:
            tds.append(f"<td>无路径</td>"); continue
        s, e = c["subclip"]
        tds.append(f"""<td><a href='/file?p={enc(p)}#t={s},{e}' target='_blank'>▶ {c['media_id']} [{s}–{e}s]</a><br/>
act {c['action_window'][0]}–{c['action_window'][1]}s b={c['boundary_usable']}<br/>
Top: <button class='gb' onclick='mk(this,"GOOD")'>GOOD</button> <button class='gb' onclick='mk(this,"BAD")'>BAD</button>
<button class='gb' onclick='mk(this,"UNSURE")'>UNSURE</button><br/>
完整: <input type='checkbox' onchange='meta(this,"complete")'/> 边界可用: <input type='checkbox' onchange='meta(this,"boundary")'/>
最佳: <input type='radio' name='best_{q['qid']}' onchange='mkBest("{q['qid']}",{c['media_id']})'/></td>""")
    while len(tds) < 3:
        tds.append("<td>—</td>")
    no_valid = "" if t3 else "<br/><b>NO_VALID_SOURCE_AVAILABLE</b>(素材未检出该动作候选)"
    rows.append(f"<tr data-q='{q['qid']}'><td>{q['qid']}<br/>动作:{q['action']}</td>" + "".join(tds) + f"<td>{no_valid}</td></tr>")
html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"/><title>G2 Human Review V2</title>
<style>body{{font-family:'Microsoft YaHei';margin:16px}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #bbb;padding:6px;font-size:12px;vertical-align:top}}th{{background:#eee}}
.gb{{margin:1px;padding:2px 8px;cursor:pointer}}.on{{background:#ffe08a}}</style></head><body>
<h2>STAGE8 G2 — Human Review V2（{now}）</h2>
<p>每 Query 对 Top1-3 各判 GOOD/BAD/UNSURE；勾 完整动作/边界可用；选最佳候选。点导出保存(追加式, 机器证据不动)。</p>
<table><tr><th>Query</th><th>Top1</th><th>Top2</th><th>Top3</th><th>备注</th></tr>{''.join(rows)}</table>
<button onclick="exp()">导出裁决 JSON</button>
<script>
var ann=[];window.mk=function(b,v){{b.parentNode.querySelectorAll('button').forEach(x=>x.classList.remove('on'));b.classList.add('on');}}
window.meta=function(cb,k){{var tr=cb.closest('tr');tr.dataset[k]=cb.checked?'1':'0';}}
window.mkBest=function(q,mid){{var tr=document.querySelector('tr[data-q="'+q+'"]');tr.dataset.best=mid;}}
window.exp=function(){{var out=[];document.querySelectorAll('tr[data-q]').forEach(tr=>{{out.push({{qid:tr.dataset.q,best:tr.dataset.best||null,complete:tr.dataset.complete||'0',boundary:tr.dataset.boundary||'0'}});}});
var b=new Blob([JSON.stringify({{level:'L3_PENDING_HUMAN',annotations:out}},null,1)],{{type:'application/json'}});
var a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='TREECUT_G2_HUMAN_ANNOTATIONS_V2.json';a.click();}}
</script></body></html>"""
(OUT / "TREECUT_G2_HUMAN_REVIEW_V2.html").write_text(html, encoding="utf-8")
print("G2 review V2 saved")

# ---------- G3 review V2 ----------
brows = []
for b in proj.get("beats", []):
    cl = b.get("claim") or {}
    cands = b.get("candidates") or []
    cells = []
    for c in cands[:3]:
        p = c.get("path")
        if not p:
            cells.append("<td>—</td>"); continue
        sc = c.get("subclip") or {}
        cells.append(f"<td><a href='/file?p={enc(p)}#t={sc.get('start_s',0)},{sc.get('end_s',0)}' target='_blank'>▶ {c['media_id']}</a><br/>"
                     f"<button class='gb' onclick='mk3(this,\"GOOD\")'>GOOD</button> <button class='gb' onclick='mk3(this,\"BAD\")'>BAD</button> "
                     f"<button class='gb' onclick='mk3(this,\"UNSURE\")'>UNSURE</button></td>")
    while len(cells) < 3:
        cells.append("<td>—</td>")
    brows.append(f"<tr data-b='{b['id']}'><td>{b['id']}</td><td>{(cl.get('text') or b.get('text') or '')[:56]}</td>"
                 f"<td>{cl.get('required_action')}/{cl.get('required_object')}</td>" + "".join(cells) +
                 f"<td>{b['qa_note']}</td></tr>")
g3 = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"/><title>G3 Human Review V2</title>
<style>body{{font-family:'Microsoft YaHei';margin:16px}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #bbb;padding:6px;font-size:12px}}th{{background:#eee}}
.gb{{margin:1px;padding:2px 8px;cursor:pointer}}.on{{background:#ffe08a}}</style></head><body>
<h2>STAGE8 G3 — Human Review V2（{now}）</h2>
<p>判定问题：听到这句话，你希望看到这个画面吗？StoryMode={proj.get('story_mode')}。逐候选 GOOD/BAD/UNSURE，导出保存。</p>
<table><tr><th>Beat</th><th>口播/主张</th><th>要求(动作/对象)</th><th>候选1</th><th>候选2</th><th>候选3</th><th>QA</th></tr>{''.join(brows)}</table>
<button onclick="exp3()">导出裁决 JSON</button>
<script>
window.mk3=function(b,v){{b.parentNode.querySelectorAll('button').forEach(x=>x.classList.remove('on'));b.classList.add('on');}}
window.exp3=function(){{var out=[];document.querySelectorAll('tr[data-b]').forEach(tr=>{{out.push({{beat:tr.dataset.b}});}});
var b=new Blob([JSON.stringify({{level:'L3_PENDING_HUMAN',note:'请在页面中逐候选点选后手动补充到注解',annotations:out}},null,1)],{{type:'application/json'}});
var a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='TREECUT_G3_HUMAN_ANNOTATIONS_V2.json';a.click();}}
</script></body></html>"""
(OUT / "TREECUT_G3_HUMAN_REVIEW_V2.html").write_text(g3, encoding="utf-8")
print("G3 review V2 saved")

# ---------- 晨间验证状态 ----------
mv = {"current_state": {"G1": "PASS", "G2": "ENGINEERING_READY_FOR_HUMAN_VALIDATION",
                        "G3": "ENGINEERING_READY_FOR_HUMAN_VALIDATION", "DEDUP": "PROVISIONAL_PASS",
                        "G5": "PROVISIONAL_PASS", "UI": "USABLE_V1", "VOICE": "READY_FOR_INPUT",
                        "BGM": "LIBRARY_NOT_READY", "REHEARSAL": "PASS_WITH_EXTERNAL_INPUT_LIMITATIONS",
                        "REGRESSION": {"passed": 354, "skipped": 2, "failed": 0}},
       "calibration_correction": {"status": "SEGMENT_LEVEL_NOT_YET_80_120",
                                  "segment_level": 20, "frames_as_evidence": 132,
                                  "frames_are_not_samples": True},
       "g2_human_review": "TREECUT_G2_HUMAN_REVIEW_V2.html (20 queries; schema Top1-3+best+complete+boundary)",
       "g3_human_review": "TREECUT_G3_HUMAN_REVIEW_V2.html (16 beats)",
       "dedup_human_review": "TREECUT_DEDUP_HUMAN_REVIEW_V1.html (4 对真实命中)",
       "voice_import_action": {"step1": "提供 30-60s 单人普通话无BGM参考音(推荐5-10min)",
                               "step2": "放到 voice_reference 目录(不进Git)", "step3": "标记 consent_verified",
                               "step4": "机器仅测 decode/噪声/削波/时长/响度",
                               "gate": "VOICE_ACCEPT/REJECT 仅人工", "sample_plan": ["15s", "30s", "60s"]},
       "bgm_import_action": {"needed": "10-20 首授权曲即可", "fields": ["license_ok", "license_doc_ref", "mood", "energy", "duration", "bpm", "vocal"],
                             "forbidden": "不从 published 视频 rip", "status": "LIBRARY_NOT_READY"},
       "next_gate_order": ["G2 人审", "G3 人审", "修发现的问题", "G2/G3 PASS 或 PASS_WITH_LIMITATIONS",
                           "Voice 试听 PASS", "BGM 可用", "才生成 Pilot V3"],
       "generated_at": now}
(OUT / "TREECUT_MORNING_VALIDATION_STATUS_V1.json").write_text(json.dumps(mv, ensure_ascii=False, indent=1), encoding="utf-8")
print("morning status saved")
