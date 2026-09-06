#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MMVV A3 — TEMPORAL OBSERVABILITY AUDIT（P1，Overnight）。

只读机器侧盲输入（TREECUT_MMVV_A3_MACHINE_INPUT_BLIND_V1.json + opaque 帧），
在完全不读 Human GT / 原 manifest / screening 的进程中计算时间可观测性证据：
  全局帧差 / 光流摘要 / 相机平移代理 / 前景残留代理 / 边缘差 / 场景跳变 / 静态区间比。
只输出 TEMPORAL_SIGNAL ∈ {STRONG_CHANGE, MODERATE_CHANGE, LOW_CHANGE,
DISCONTINUITY, UNKNOWN} —— 不做动作 verdict，不改动任何帧与采样。

阈值仅用于审计描述（非冻结算法，不改 ca34678 逻辑）。

输出: reports/storage/TREECUT_MMVV_A3_TEMPORAL_OBSERVABILITY.json
      reports/storage/TREECUT_MMVV_A3_TEMPORAL_OBSERVABILITY_REVIEW.html（中文人工审阅）
"""
from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
BLIND_JSON = OUT / "TREECUT_MMVV_A3_MACHINE_INPUT_BLIND_V1.json"
JSON_OUT = OUT / "TREECUT_MMVV_A3_TEMPORAL_OBSERVABILITY.json"
HTML_OUT = OUT / "TREECUT_MMVV_A3_TEMPORAL_OBSERVABILITY_REVIEW.html"
BLIND_FRAMES = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\mmv_a3_blind_frames")
sys.stdout.reconfigure(encoding="utf-8")

# 审计阈值（仅审计描述；非冻结算法阈值）
TH = {"jump_diff": 0.32, "strong_mean": 0.09, "moderate_mean": 0.035,
      "static_diff": 0.018, "strong_max": 0.24, "discont_iso": 0.38}


def imread_gray(p: Path):
    data = np.fromfile(str(p), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    return img


def pair_metrics(g0, g1):
    """帧对指标：diff(0..1), edge 差, flow 摘要, 相机平移代理, 前景残留代理。"""
    h0, w0 = g0.shape[:2]
    scale = 0.5
    s0 = cv2.resize(g0, (int(w0 * scale), int(h0 * scale)), interpolation=cv2.INTER_AREA)
    s1 = cv2.resize(g1, (int(w0 * scale), int(h0 * scale)), interpolation=cv2.INTER_AREA)
    d = float(np.abs(s0.astype(np.float32) - s1.astype(np.float32)).mean() / 255.0)
    e0 = cv2.Canny(s0, 80, 160)
    e1 = cv2.Canny(s1, 80, 160)
    edge_diff = float(np.abs(e0.astype(np.float32) - e1.astype(np.float32)).mean() / 255.0)
    flow = cv2.calcOpticalFlowFarneback(s0, s1, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2) / scale   # 回原分辨率尺度
    flow_mean = float(mag.mean())
    flow_median = float(np.median(mag))
    # 稀疏 LK 相机平移代理（鲁棒中位数）
    pts0 = cv2.goodFeaturesToTrack(s0, maxCorners=240, qualityLevel=0.01,
                                   minDistance=12, blockSize=7)
    tx = ty = None
    if pts0 is not None and len(pts0) >= 10:
        p1, st, _ = cv2.calcOpticalFlowPyrLK(s0, s1, pts0, None, winSize=(21, 21),
                                             maxLevel=2)
        good0 = pts0[st.ravel() == 1]
        good1 = p1[st.ravel() == 1]
        if len(good0) >= 8:
            v = (good1 - good0).reshape(-1, 2)
            tx = float(np.median(v[:, 0])) / scale
            ty = float(np.median(v[:, 1])) / scale
    cam_mag = (tx ** 2 + ty ** 2) ** 0.5 if tx is not None else None
    fg_residual = max(0.0, flow_mean - (cam_mag if cam_mag is not None else 0.0))
    return {"diff": round(d, 4), "edge_diff": round(edge_diff, 4),
            "flow_mean": round(flow_mean, 3), "flow_median": round(flow_median, 3),
            "cam_tx_px": round(tx, 3) if tx is not None else None,
            "cam_ty_px": round(ty, 3) if ty is not None else None,
            "cam_mag_px": round(cam_mag, 3) if cam_mag is not None else None,
            "foreground_residual_proxy": round(fg_residual, 3)}


def classify(pairs):
    """TEMPORAL_SIGNAL（审计用确定性规则）。"""
    diffs = [p["diff"] for p in pairs]
    mean = float(np.mean(diffs))
    mx = float(np.max(diffs))
    jumps = sum(1 for x in diffs if x > TH["jump_diff"])
    static_pairs = sum(1 for x in diffs if x < TH["static_diff"])
    n = len(diffs)
    if jumps >= 1 and mean < 0.05 and static_pairs >= n - 1:
        return "DISCONTINUITY"
    if jumps >= 1 and mean < TH["moderate_mean"]:
        return "DISCONTINUITY"
    if mean >= TH["strong_mean"] or mx >= TH["strong_max"]:
        return "STRONG_CHANGE"
    if mean >= TH["moderate_mean"] or mx >= 0.12:
        return "MODERATE_CHANGE"
    return "LOW_CHANGE"


def main():
    blind = json.loads(BLIND_JSON.read_text(encoding="utf-8"))
    doc = {"experiment": "MMVV_A3_TEMPORAL_OBSERVABILITY",
           "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "note": ("只读盲输入；不含人工答案与动作结论；TEMPORAL_SIGNAL 仅为"
                    "“冻结5帧是否包含可观测时间变化”的审计信号，非 MMVV verdict。"),
           "thresholds_note": "审计阈值仅供描述，非冻结算法阈值(ca34678 未改动)",
           "cases": []}
    html_cases = []
    for c in blind["cases"]:
        oid = c["opaque_case_id"]
        frs = c["frames"]
        frames_px = []
        for f in frs:
            fp = BLIND_FRAMES / f["frame"]
            g = imread_gray(fp)
            if g is None:
                raise SystemExit(f"读帧失败 {f['frame']}")
            frames_px.append(g)
        pairs = [pair_metrics(frames_px[i], frames_px[i + 1])
                 for i in range(len(frames_px) - 1)]
        signal = classify(pairs)
        static_ratio = round(sum(1 for p in pairs if p["diff"] < TH["static_diff"])
                             / len(pairs), 3)
        case = {"opaque_case_id": oid, "frames": len(frs),
                "pairs": [{"pair": f"{frs[i]['t_s']}->{frs[i+1]['t_s']}", **pairs[i]}
                          for i in range(len(pairs))],
                "static_interval_ratio": static_ratio,
                "frame_diff_mean": round(float(np.mean([p["diff"] for p in pairs])), 4),
                "frame_diff_max": round(float(np.max([p["diff"] for p in pairs])), 4),
                "flow_mean_overall": round(float(np.mean([p["flow_mean"] for p in pairs])), 3),
                "camera_motion_max_px": round(float(np.nanmax(
                    [p["cam_mag_px"] if p["cam_mag_px"] is not None else 0.0
                     for p in pairs])), 3),
                "TEMPORAL_SIGNAL": signal}
        doc["cases"].append(case)
        # 供 HTML 的小图（宽度 300）
        thumbs = []
        for f in frs:
            fp = BLIND_FRAMES / f["frame"]
            img = cv2.imdecode(np.fromfile(str(fp), dtype=np.uint8), cv2.IMREAD_COLOR)
            h, w = img.shape[:2]
            tw = 300
            th = int(h * tw / w)
            small = cv2.resize(img, (tw, th), interpolation=cv2.INTER_AREA)
            ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 72])
            thumbs.append("data:image/jpeg;base64," + base64.b64encode(buf).decode())
        html_cases.append({"oid": oid, "signal": signal,
                           "thumbs": thumbs,
                           "frames": frs, "pairs": pairs,
                           "mean": case["frame_diff_mean"], "mx": case["frame_diff_max"],
                           "flow": case["flow_mean_overall"], "cam": case["camera_motion_max_px"],
                           "static_ratio": static_ratio})
        print(oid, signal, "diff_mean", case["frame_diff_mean"], "flow", case["flow_mean_overall"],
              "cam_mx", case["camera_motion_max_px"])
    tmp = JSON_OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(JSON_OUT)
    # ---- HTML 中文审阅页（不显示 GT / POS / NEG / 动作结论）----
    H = []
    H.append("<!DOCTYPE html><html lang='zh'><head><meta charset='utf-8'/>")
    H.append("<title>TreeCut A3 · 时间可观测性人工审阅（Overnight P1）</title>")
    H.append("<style>body{font-family:'Microsoft YaHei';margin:0;background:#f5f6f8;color:#222}")
    H.append("header{padding:16px 24px;background:#1f2937;color:#fff}")
    H.append("h1{font-size:18px;margin:0 0 4px}h2{font-size:15px;margin:26px 0 8px;border-left:5px solid #1a73e8;padding-left:8px}")
    H.append(".wrap{max-width:1080px;margin:0 auto;padding:16px 22px 70px}")
    H.append(".casebox{background:#fff;border:1px solid #d2d9e2;border-radius:10px;padding:12px 14px;margin:14px 0}")
    H.append("table{border-collapse:collapse;font-size:12px;margin:6px 0}td,th{border:1px solid #d5dbe3;padding:3px 7px}")
    H.append(".sig{font-weight:bold;padding:2px 10px;border-radius:10px}")
    H.append(".S-STRONG_CHANGE{background:#7dffa0}.S-MODERATE_CHANGE{background:#ffe08a}.S-LOW_CHANGE{background:#e0e0e0}.S-DISCONTINUITY{background:#ffb3b3}")
    H.append(".imgs{display:flex;gap:8px;flex-wrap:wrap}.imgs figure{margin:0;text-align:center}")
    H.append(".imgs img{width:150px;border:1px solid #aaa}figcaption{font-size:10px;color:#555}")
    H.append(".judge{margin-top:8px;font-size:13px}")
    H.append("button{padding:5px 12px;border-radius:6px;border:1px solid #888;cursor:pointer;background:#fff}")
    H.append("button.p{background:#1a73e8;color:#fff;border-color:#1a73e8}</style></head><body>")
    H.append("<header><h1>TreeCut A3 · 冻结 5 帧的时间可观测性人工审阅</h1>")
    H.append("<div style='font-size:12px;color:#cfe0ff'>目的：判断“这 5 张冻结帧是否足以看到桌板/台面的动作过程”（只审采样是否可观察，不改帧、不改采样、不做动作结论）。页面不含任何人工答案与正负信息。</div></header>")
    H.append("<div class='wrap'>")
    H.append("<div style='background:#fff8e1;border:1px solid #f0d070;padding:10px 14px;border-radius:8px;font-size:13px'>")
    H.append("<b>怎么看：</b>每案例 5 帧按时间顺序排列（帧间为均匀采样）。指标含义：<b>帧差均值/最大</b>（相邻帧灰度变化，0-1）、<b>光流均值</b>（像素运动）、<b>相机平移最大</b>（稀疏特征中位平移）、<b>静态区间比</b>（几乎无变化的帧对占比）。")
    H.append("判断依据是画面内容本身：<i>桌板/台面是否在帧间发生了可辨认的伸缩位移</i>。请为每案例选一项；"
             "六项完成后点【保存人工审核结果】，直接存入 reports/storage（无需下载文件）。"
             "若本页非由本地服务打开（地址不是 http://127.0.0.1:8933/a3/observability），请改用该地址打开才能保存。</div>")
    H.append("<div class='savebar' style='position:sticky;top:0;background:#fff;border:1px solid #ccc;"
             "border-radius:8px;padding:8px 12px;margin:10px 0;z-index:5;display:flex;gap:12px;align-items:center'>"
             "<span id='prog' style='font-weight:bold'>已完成 0/6</span>"
             "<button id='saveBtn' class='p' style='padding:7px 18px'>保存人工审核结果</button>"
             "<span id='saveMsg' style='color:#0a7d33;font-size:13px'></span></div>")
    for cs in html_cases:
        H.append(f"<div class='casebox'><h2>案例 <span class='mono'>{cs['oid']}</span>"
                 f" <span class='sig S-{cs['signal']}'>{cs['signal']}</span></h2>")
        H.append("<div class='imgs'>")
        for i, f in enumerate(cs["frames"]):
            H.append(f"<figure><img src='{cs['thumbs'][i]}'/>"
                     f"<figcaption>F{i} @ {f['t_s']}s</figcaption></figure>")
        H.append("</div>")
        H.append("<table><tr><th>相邻帧对</th><th>帧差</th><th>边缘差</th><th>光流均值</th>"
                 "<th>相机平移(px)</th><th>前景残留代理</th></tr>")
        for i, p in enumerate(cs["pairs"]):
            lbl = f"{cs['frames'][i]['t_s']}->{cs['frames'][i+1]['t_s']}"
            H.append(f"<tr><td>{lbl}</td><td>{p['diff']}</td><td>{p['edge_diff']}</td>"
                     f"<td>{p['flow_mean']}</td><td>{p['cam_mag_px'] if p['cam_mag_px'] is not None else '-'}</td>"
                     f"<td>{p['foreground_residual_proxy']}</td></tr>")
        H.append("</table>")
        H.append(f"<div>帧差均值 {cs['mean']} / 最大 {cs['mx']} · 光流均值 {cs['flow']} · "
                 f"相机平移最大 {cs['cam']}px · 静态区间比 {cs['static_ratio']}</div>")
        H.append(f"<div class='judge'>人工判断（只选一项）：")
        for k, v in [("ACTION_PROCESS_VISIBLE", "能看清连续动作过程"),
                     ("ENDPOINTS_ONLY", "只能看到前后状态，看不清连续过程"),
                     ("MOSTLY_STATIC", "基本是静态展示"),
                     ("UNCLEAR", "看不清 / 无法判断")]:
            H.append(f"<label style='margin-right:10px'><input type='radio' name='j_{cs['oid']}' value='{k}'/> {v}</label>")
        H.append(f"<br/><span style='font-size:12px;color:#666'>备注（可选）：</span>"
                 f"<input type='text' id='n_{cs['oid']}' style='width:70%;padding:3px 6px;border:1px solid #bbb;border-radius:4px' placeholder='补充说明（如：桌腿位移但桌板未见位移）'/>")
        H.append("</div></div>")
    H.append("<button class='p' id='saveBtn2' style='padding:7px 18px;margin-bottom:30px'>保存人工审核结果</button>")
    H.append("<script>")
    H.append("const OIDS=['H001','H002','H003','H004','H005','H006'];")
    H.append("function curAns(){return OIDS.map(oid=>{const r=document.querySelector(`input[name=j_${oid}]:checked`);")
    H.append("const n=document.getElementById('n_'+oid);return {opaque_case_id:oid,")
    H.append("observability_label:r?r.value:null,human_note:n?n.value:''};});}")
    H.append("function countDone(){return curAns().filter(a=>a.observability_label).length;}")
    H.append("function prog(){const d=countDone();document.getElementById('prog').textContent=`已完成 ${d}/6`;return d;}")
    H.append("function persist(){try{localStorage.setItem('a3_obs_v1',JSON.stringify(curAns()));}catch(e){}}")
    H.append("function setFrom(arr){arr.forEach(a=>{const el=document.querySelector(`input[name=j_${a.opaque_case_id}][value=${a.observability_label}]`);")
    H.append("if(el&&a.observability_label){el.checked=true;}const n=document.getElementById('n_'+a.opaque_case_id);")
    H.append("if(n&&a.human_note){n.value=a.human_note;}});prog();}")
    H.append("function bind(){OIDS.forEach(oid=>{document.querySelectorAll(`input[name=j_${oid}]`).forEach(r=>r.onchange=()=>{persist();prog();});")
    H.append("const n=document.getElementById('n_'+oid);if(n){n.oninput=persist;}});}")
    H.append("async function saveNow(){const ans=curAns();const missing=ans.filter(a=>!a.observability_label).length;")
    H.append("if(missing){alert(`还有 ${missing} 个案例未完成审核（请先选完 H001-H006 六项）`);return;}")
    H.append("try{const r=await fetch('/api/a3/observability/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({answers:ans})});")
    H.append("const j=await r.json();if(j.ok){document.getElementById('saveMsg').textContent='✅ 已保存 6/6 → reports/storage/TREECUT_MMVV_A3_OBSERVABILITY_HUMAN_V1.json';persist();}")
    H.append("else{alert('保存失败：'+j.error);}}catch(e){alert('保存失败：请确认通过 http://127.0.0.1:8933/a3/observability 打开本页（本地服务未运行或跨域）');}}")
    H.append("async function init2(){bind();prog();")
    H.append("try{const r=await fetch('/api/a3/observability-human');if(r.ok){const d=await r.json();")
    H.append("if(d&&d.answers&&d.answers.length){setFrom(d.answers);document.getElementById('saveMsg').textContent='已恢复此前保存的审核结果';return;}}}catch(e){}")
    H.append("try{const s=localStorage.getItem('a3_obs_v1');if(s){const arr=JSON.parse(s);if(arr&&arr.length){setFrom(arr);")
    H.append("document.getElementById('saveMsg').textContent='已从本机草稿恢复（未保存到服务端，请点保存）';}}}catch(e){}")
    H.append("if(location.protocol==='file:'){document.getElementById('saveMsg').textContent='⚠ 当前为本地文件打开：请改用 http://127.0.0.1:8933/a3/observability 才能保存';}}")
    H.append("document.getElementById('saveBtn').onclick=saveNow;document.getElementById('saveBtn2').onclick=saveNow;init2();")
    H.append("</script></div></body></html>")
    HTML_OUT.write_text("\n".join(H), encoding="utf-8")
    print("WROTE", JSON_OUT)
    print("WROTE", HTML_OUT)


if __name__ == "__main__":
    main()
