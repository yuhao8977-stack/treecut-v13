# -*- coding: utf-8 -*-
"""Create VOICE_REFERENCE_REVIEW.html (local, 15 segments with controls)."""
import json
from pathlib import Path

PROFILE = Path(r"E:\TreeCutRuntime\voice_profiles\VOICE_001")
SEG = PROFILE / "segments"
m = json.loads((PROFILE / "vc0_local_manifest.json").read_text(encoding="utf-8"))
segs = sorted(m["segments"], key=lambda s: s["start_s"])
prio = {"seg13": 1, "seg23": 1, "seg25": 1, "seg27": 1}
segs.sort(key=lambda s: (prio.get(s["segment_id"], 2), s["start_s"]))
cards = []
for s in segs:
    sid = s["segment_id"]
    cards.append(
        '<div class="card" data-id="{sid}">'
        "<h3>{sid} {start}–{end}s（{dur}s）</h3>"
        '<audio controls src="segments/{sid}.wav"></audio><br>'
        'ASR 转写(可编辑):<textarea rows="2" cols="70" data-f="transcript">{tr}</textarea><br>'
        '是否为目标说话人:<select data-f="speaker"><option>YES</option><option>NO</option></select> '
        '噪声/提示音/多人重叠:<select data-f="noise">'
        "<option>CLEAN</option><option>NOISE_TONE</option>"
        "<option>MULTI_SPEAKER</option><option>UNKNOWN</option></select> "
        '允许作为零样本参考:<select data-f="allow"><option>NO</option><option>YES</option></select>'
        "</div>".format(sid=sid, start=s["start_s"], end=s["end_s"],
                        dur=s["duration_s"], tr=s.get("transcript", "")))
cards_html = "\n".join(cards)
html = """<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>VC0 参考音频人工审核</title><style>.card{border:1px solid #999;margin:8px;padding:8px}</style>
</head><body><h1>VOICE_REFERENCE_REVIEW (VOICE_001)</h1>
<p>逐条试听并核对：目标说话人 / 是否干净 / 是否允许作零样本参考；修改 ASR 使与实际语音逐字一致。</p>
__CARDS__
<button onclick="exportResult()">导出 review_result.json</button>
<pre id="out"></pre>
<script>
function exportResult(){
 var out={voice_profile_id:'VOICE_001',reviewed_at:new Date().toISOString(),segments:[]};
 document.querySelectorAll('.card').forEach(function(c){
   var r={segment_id:c.dataset.id,
          transcript:c.querySelector('[data-f=transcript]').value,
          speaker:c.querySelector('[data-f=speaker]').value,
          noise:c.querySelector('[data-f=noise]').value,
          allow_zero_shot:c.querySelector('[data-f=allow]').value};
   out.segments.push(r);
 });
 document.getElementById('out').textContent=JSON.stringify(out,null,1);
 var a=document.createElement('a');
 a.href='data:application/json,'+encodeURIComponent(JSON.stringify(out,null,1));
 a.download='review_result.json'; a.click();
}
</script></body></html>"""
html = html.replace("__CARDS__", cards_html)
(PROFILE / "VOICE_REFERENCE_REVIEW.html").write_text(html, encoding="utf-8")
print("reference review html written; segments", len(segs))
