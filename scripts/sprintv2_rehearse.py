# -*- coding: utf-8 -*-
"""技术预演正式落盘(非Pilot V3) + G2/G3 review HTML 刷新 + 主报告数字刷新。"""
import json, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DOCS = Path(r"C:\Users\admin\github\treecut-v13\docs")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")
from treecut.services.production_qa import (ProductionQAService, check_claim_supported,
                                            check_action_demonstrated, check_beat_visual_alignment,
                                            check_caption_size, check_bgm, check_voice_provider,
                                            check_story_consistent, check_dedup)
from treecut.config.production import state_flags

proj = json.loads((OUT / "TREECUT_WORKBENCH_PROJECT_V1.json").read_text(encoding="utf-8"))
win = json.loads((OUT / "TREECUT_G2_SUBCLIP_WINDOWS_V1.json").read_text(encoding="utf-8"))["windows"]
ev = json.loads((OUT / "TREECUT_G2_TEMPORAL_EVIDENCE_V1.json").read_text(encoding="utf-8"))["items"]

# ---- 预演链: Source→Claims→Matcher→ActionSubclip→Dedup→QA(真实组件) ----
checks = []
chain = []
beat_summary = []
for b in proj.get("beats", []):
    claim = b.get("claim") or {}
    sel = b.get("selected")
    n_cand = len(b.get("candidates") or [])
    if not sel:
        checks.append(check_claim_supported(False, claim.get("id", "?")))
        checks.append(check_action_demonstrated("NOT_PRESENT", claim.get("required_action")))
        checks.append(check_beat_visual_alignment(False))
        beat_summary.append({"beat": b["id"], "text": claim.get("text", "")[:30],
                             "candidates": n_cand, "selected": None, "status": "NO_CANDIDATE"})
    else:
        acts = sel.get("actions") or []
        ok_act = claim.get("required_action") in acts if claim.get("required_action") else True
        checks.append(check_action_demonstrated("ACTION_DEMONSTRATION_COMPLETE" if ok_act else "FUNCTION_VISIBLE",
                                                claim.get("required_action")))
        checks.append(check_beat_visual_alignment(ok_act))
        beat_summary.append({"beat": b["id"], "text": claim.get("text", "")[:30],
                             "candidates": n_cand, "selected": sel.get("media_id"),
                             "status": "OK" if ok_act else "MISMATCH"})
# 时间线级重复(选中 media 重复)
mids = [(b.get("selected") or {}).get("media_id") for b in proj.get("beats", []) if b.get("selected")]
dup_high = len(mids) != len(set(mids))
checks += [check_dedup([{"pair": [], "level": "SAME_ASSET_NEAR_DUPLICATE", "strength": "HIGH"}] if dup_high else []),
           check_caption_size(66), check_bgm(False, required=True),
           check_voice_provider("SAPI", production_ready=False),
           check_story_consistent(True)]
qa_svc = ProductionQAService()
res = qa_svc.run(checks)
flags = state_flags({"caption": {"fontsize": 66}}, voice_ready=False, music_assets=[])
rehearsal = {
    "title": "STAGE8 技术预演(非 Pilot V3; 不渲染成片)",
    "chain": ["ProductionSourceService(G1)", "Atomic Claims parse", "ClaimVisualMatcher",
              "ActionSubclipService(108帧L2证据)", "Production Dedup", "ProductionQAService"],
    "inputs": {"script_beats": len(proj.get("beats", [])), "evidence_frames": len(ev),
               "windows": len(win), "beats_with_selected": sum(1 for b in proj.get("beats", []) if b.get("selected"))},
    "beat_summary": beat_summary,
    "qa_verdict": res["verdict"],
    "flags": flags,
    "no_silent_fallback": {"voice": "VOICE_INPUT_REQUIRED(SAPI 仅 FALLBACK, 不宣称生产音)",
                           "bgm": "BGM_LIBRARY_NOT_READY(不 rip/不下载/不静音冒充)"},
    "not_pilot_v3": True,
    "rendered_video": None,
    "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
(OUT / "TREECUT_STAGE8_REHEARSAL_V1.json").write_text(json.dumps(rehearsal, ensure_ascii=False, indent=1), encoding="utf-8")
print("rehearsal saved; beats selected:", sum(1 for b in proj.get("beats", []) if b.get("selected")),
      "| verdict ready:", res["verdict"]["READY_FOR_HUMAN_REVIEW"])

# ---- G2/G3 review HTML 刷新(用新窗口/新项目) ----
def enc(p):
    from urllib.parse import quote
    return quote(p)
q20 = json.loads((OUT / "TREECUT_G2_ACTION_QUERY20_V1.json").read_text(encoding="utf-8"))["queries"]
paths = {w["media_id"]: w.get("asset_path") for w in win}
rows = []
for q in q20[:12]:
    cells = []
    for c in (q.get("top3") or []):
        p = paths.get(c["media_id"])
        if not p:
            cells.append("<td>无路径</td>"); continue
        s, e = c["subclip"]
        ms = c.get("motion_support", "?")
        cells.append(f"<td><a href='/file?p={enc(p)}#t={s},{e}' target='_blank'>▶ {c['media_id']} [{s}–{e}s]</a><br/>"
                     f"act {c['action_window'][0]}–{c['action_window'][1]}s b={c['boundary_usable']} motion={ms}<br/>"
                     f"<button onclick='mark(this,\"GOOD\")'>GOOD</button> <button onclick='mark(this,\"BAD\")'>BAD</button> "
                     f"<button onclick='mark(this,\"UNSURE\")'>UNSURE</button>")
    while len(cells) < 3:
        cells.append("<td>—</td>")
    rows.append(f"<tr><td>{q['qid']}<br/>{q['action']}</td><td>{q['top3_n']}</td>" + "".join(cells) + "</tr>")
(OUT / "TREECUT_G2_HUMAN_REVIEW_V1.html").write_text(
    f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"/><title>G2 Human Review</title><style>
body{{font-family:'Microsoft YaHei';margin:16px}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #bbb;padding:6px;font-size:13px;vertical-align:top}}th{{background:#eee}}</style></head><body>
<h2>STAGE8 G2 — 动作/Subclip 人工审核（HUMAN_VALIDATION_PENDING）</h2>
<p>点 ▶ 播放 subclip 窗口(非整段)。motion=WEAK 表示证据强度低(稀疏采样)，请人工确认真实性。</p>
<table><tr><th>Query(动作)</th><th>命中</th><th>Top1</th><th>Top2</th><th>Top3</th></tr>{''.join(rows)}</table>
</body></html>""", encoding="utf-8")

brows = []
for b in proj.get("beats", []):
    sel = b.get("selected"); cl = b.get("claim") or {}
    selcell = "—"
    if sel and sel.get("path"):
        p = sel["path"]; s = (sel.get("subclip") or {}).get("start_s", 0); e = (sel.get("subclip") or {}).get("end_s", 0)
        selcell = f"<a href='/file?p={enc(p)}#t={s},{e}' target='_blank'>▶ {sel['media_id']} [{s}–{e}s]</a>"
    brows.append(f"<tr><td>{b['id']}</td><td>{cl.get('text','')[:50]}</td><td>{cl.get('required_action')}/{cl.get('required_object')}</td>"
                 f"<td>{selcell}</td><td>{b['qa_note']}</td><td><button onclick='mark(this,\"GOOD\")'>GOOD</button> "
                 f"<button onclick='mark(this,\"BAD\")'>BAD</button></td></tr>")
(OUT / "TREECUT_G3_HUMAN_REVIEW_V1.html").write_text(
    f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"/><title>G3 Human Review</title><style>
body{{font-family:'Microsoft YaHei';margin:16px}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #bbb;padding:6px;font-size:13px}}th{{background:#eee}}</style></head><body>
<h2>STAGE8 G3 — Claim→Visual 人工审核</h2>
<table><tr><th>Beat</th><th>口播</th><th>Claim</th><th>选中候选</th><th>QA</th><th>判定</th></tr>{''.join(brows)}</table>
<p>V2 旧错演示见 TREECUT_G3_PILOT_V2_REGRESSION_V1.json（伸缩口播→插座 = REJECT）。</p>
</body></html>""", encoding="utf-8")
print("review html refreshed")
