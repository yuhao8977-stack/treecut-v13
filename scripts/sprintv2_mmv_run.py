# -*- coding: utf-8 -*-
"""MMV V1.1 — 真实媒体 Shadow 验证(51/52/89/109/1985/1986): 真实帧→qwen语义→CV(相机/ROI/对象运动)→时序→融合。
MODE=SHADOW: 只出判断不改生产。"""
import base64, json, sqlite3, subprocess, sys, time, urllib.request
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
FRD = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\mmv_frames")
FRD.mkdir(parents=True, exist_ok=True)
SRC = {1: r"\\X1\素材盘01\已处理素材\卖点展示类素材", 2: r"\\X1\素材盘01\已处理素材\效果展示类素材",
       4: r"\\X1\素材盘01\未处理素材\【工厂】"}
SYS = r"C:\Users\admin\github\treecut-v13\src"
sys.path.insert(0, SYS)
import cv2
import numpy as np
from treecut.services.mmvl_master_v1 import (ROI, Action, Verdict, Support, FrameSemantics, CameraMotionEstimator,
                            ROITracker, ROIMotionAttributor, TargetObjectMotionRouter,
                            TemporalStateValidator, TemporalEvidence, EvidenceFusionEngine,
                            QwenFrameAdapter, sample_video_window)

Q = ("这一帧画面: 输出一行 objects=逗号分隔的可见对象(从 PERSON/TABLETOP/DRAWER/UPPER_THIN_DRAWER/SOCKET_MODULE/"
     "TRACK_SOCKET/CABINET/柜门/收纳/物品/桌面 中选); 一行 states=(如 DRAWER_OPEN_STATE/TABLETOP_EXTENDED_STATE/无); "
     "一行 action_state=(正在拉开/正在收回/正在伸缩/正在插拔/正在放入/取出/静止/无); 一行 dominant=主体是什么。")

def ask(b64):
    body = json.dumps({"model": "qwen2.5vl:7b", "stream": False, "options": {"temperature": 0.0},
                       "messages": [{"role": "user", "content": Q, "images": [b64]}]}).encode()
    req = urllib.request.Request("http://localhost:11434/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.loads(r.read().decode("utf-8"))["message"]["content"]

def sha(img):
    import hashlib
    return hashlib.sha256(img.tobytes()).hexdigest()[:16]

def heur_roi(name, w, h, frame):
    """启发式 ROI(qwen 无 bbox 时回退; source 标注 HEURISTIC)。"""
    if name == "PERSON":
        return ROI("PERSON", int(w*0.15), int(h*0.02), int(w*0.85), int(h*0.60), source="HEURISTIC")
    if name == "TABLETOP":
        return ROI("TABLETOP", int(w*0.10), int(h*0.55), int(w*0.90), int(h*0.95), source="HEURISTIC")
    if name in ("DRAWER", "UPPER_THIN_DRAWER"):
        return ROI(name, int(w*0.10), int(h*0.45), int(w*0.90), int(h*0.95), source="HEURISTIC")
    if name == "SOCKET_MODULE":
        return ROI(name, int(w*0.25), int(h*0.55), int(w*0.75), int(h*0.95), source="HEURISTIC")
    return ROI(name, 0, int(h*0.3), w, int(h*0.9), source="HEURISTIC")

def parse_sem(raw, t, w, h):
    objs, states, act, dom = [], [], "", None
    for ln in (raw or "").splitlines():
        if ln.startswith("objects="):
            objs = [x.strip() for x in ln.split("=", 1)[1].split(",") if x.strip()]
        elif ln.startswith("states="):
            states = [x.strip() for x in ln.split("=", 1)[1].split(",") if x.strip()]
        elif ln.startswith("action_state="):
            act = ln.split("=", 1)[1].strip()
        elif ln.startswith("dominant="):
            dom = ln.split("=", 1)[1].strip()
    # 兜底关键词
    objs = objs or []
    if "人" in (raw or "") and "PERSON" not in objs:
        objs.append("PERSON")
    for k, o in (("桌面", "TABLETOP"), ("抽屉", "DRAWER"), ("插座", "SOCKET_MODULE")):
        if k in (raw or "") and o not in objs:
            objs.append(o)
    rois = [heur_roi(o, w, h, None) for o in objs if o in ("PERSON", "TABLETOP", "DRAWER",
                                                            "UPPER_THIN_DRAWER", "SOCKET_MODULE")]
    return FrameSemantics(timestamp_s=t, objects=objs, states=states, rois=rois,
                          interactions=[act] if act else [],
                          dominant_visual=dom or None), act

c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
CASES = [
    (89, Action.EXTEND, None),
    (52, Action.DRAWER_OPEN, None),
    (109, Action.DRAWER_OPEN, None),
    (51, Action.EXTEND, None),
    (1985, Action.EXTEND, (1.9, 4.4)),
    (1986, Action.EXTEND, (1.9, 4.4)),
]
fx = {x["media_id"]: x for x in json.loads((OUT / "_v11_flexible_merged_direction.json").read_text(encoding="utf-8"))}
man = {m["media_id"]: m for m in json.loads((OUT / "_g2_probe_manifest.json").read_text(encoding="utf-8"))}

results = []
for mid, req, fixed_win in CASES:
    r = c.execute("SELECT source_id, relative_path FROM media_files WHERE id=?", (int(mid),)).fetchone()
    if not r:
        results.append({"media_id": mid, "error": "no file"})
        continue
    path = str(Path(SRC[r[0]]) / r[1])
    if not Path(path).exists():
        results.append({"media_id": mid, "error": "missing"})
        continue
    cap = cv2.VideoCapture(path)
    dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / max(cap.get(cv2.CAP_PROP_FPS), 1)
    cap.release()
    if fixed_win:
        s, e = fixed_win
    elif mid in fx:
        s, e = fx[mid]["merged_window_s"]
    else:
        s, e = 0.15 * dur, 0.85 * dur
    e = min(e, dur - 0.2)
    n = 5
    ts = [s + i * (e - s) / (n - 1) for i in range(n)]
    frames, times = [], []
    cap = cv2.VideoCapture(path)
    for t in ts:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ok, f = cap.read()
        if ok:
            frames.append(f)
            times.append(t)
    cap.release()
    if len(frames) < 3:
        results.append({"media_id": mid, "error": "frames<3"})
        continue
    h, w = frames[0].shape[:2]
    # qwen 语义(真实帧 → hash 记录 REAL_FRAME_PAYLOAD)
    sems, acts = [], []
    qwen_frames = []
    for i, (f, t) in enumerate(zip(frames, times)):
        small = f if f.shape[1] <= 480 else cv2.resize(f, (480, int(f.shape[0] * 480 / f.shape[1])))
        okk, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 88])
        raw = ask(base64.b64encode(buf.tobytes()).decode())
        sem, act = parse_sem(raw, t, w, h)
        sem_extra = sem
        sems.append(sem_extra)
        acts.append(act)
        qwen_frames.append({"idx": i, "ts": round(t, 2), "sha256": sha(f), "model": "qwen2.5vl:7b",
                            "raw_tail": (raw or "")[:150]})
        print("qwen", mid, i, "ok", flush=True)
    # CV: 相邻帧 compare + 追踪
    attr = ROIMotionAttributor()
    estimator = CameraMotionEstimator()
    tracker = ROITracker()
    target_roi = None
    person_roi = None
    for f, sem in zip(frames, sems):
        for roi in sem.rois:
            if roi.name == "TABLETOP" and target_roi is None and req in (Action.EXTEND, Action.RETRACT):
                target_roi = roi.clip(w, h)
            if roi.name in ("DRAWER", "UPPER_THIN_DRAWER") and target_roi is None and req in (Action.DRAWER_OPEN, Action.DRAWER_CLOSE):
                target_roi = roi.clip(w, h)
            if roi.name == "PERSON" and person_roi is None:
                person_roi = roi.clip(w, h)
    if target_roi is None:
        target_roi = heur_roi("TABLETOP" if req in (Action.EXTEND, Action.RETRACT) else "DRAWER", w, h, None).clip(w, h)
    if person_roi is None:
        person_roi = heur_roi("PERSON", w, h, None).clip(w, h)
    metrics_list = []
    cams = []
    prev = None
    for f in frames:
        if prev is not None:
            mm, cm = attr.compare(prev, f, [target_roi], [person_roi])
            metrics_list.append(mm)
            cams.append(cm)
        prev = f
    # 聚合
    agg = {}
    for k in ("global_motion_px", "camera_residual"):
        vals = [getattr(m, k) for m in metrics_list]
        agg[k] = round(sum(vals) / len(vals), 3) if vals else 0.0
    for key in ("roi_motion", "roi_edge_shift", "roi_geometry_change", "person_overlap_ratio"):
        vals = {}
        for m in metrics_list:
            for k2, v in getattr(m, key).items():
                vals[k2] = max(vals.get(k2, 0.0), v)
        agg[key] = {k2: round(v, 3) for k2, v in vals.items()}
    cam_avg = {"translation_px": round(sum(cm.translation_px for cm in cams) / len(cams), 2) if cams else 0,
               "reliable": bool(cams and all(cm.reliable for cm in cams))}
    mid_idx = len(frames) // 2
    # model_action: qwen 动作文本映射
    act_txt = " ".join(acts)
    model_action = Action.UNKNOWN
    if any(k in act_txt for k in ("伸缩", "拉出", "变宽", "展开")):
        model_action = Action.EXTEND
    elif any(k in act_txt for k in ("收回", "收起")):
        model_action = Action.RETRACT
    elif any(k in act_txt for k in ("拉开", "打开抽屉")):
        model_action = Action.DRAWER_OPEN
    router = TargetObjectMotionRouter()
    router_dec = router.analyze(req, metrics_list[len(metrics_list)//2] if metrics_list else None) if metrics_list else None
    tv = TemporalStateValidator(router)
    ev = TemporalEvidence(before=sems[0], middle=sems[mid_idx], after=sems[-1],
                          motion=metrics_list[len(metrics_list)//2] if metrics_list else None,
                          requested_action=req, model_action=model_action)
    vres = tv.validate(ev)
    fusion = EvidenceFusionEngine().fuse(vres)
    # 帧缩略存档
    for i, f in enumerate(frames):
        cv2.imencode(".jpg", cv2.resize(f, (270, 480)))[1].tofile(str(FRD / f"m{mid}_{i}.jpg"))
    results.append({"media_id": mid, "requested": str(req), "window": [round(s,2), round(e,2)],
                    "qwen_frames": qwen_frames, "aggregate": agg, "camera": cam_avg,
                    "target_roi": target_roi.__dict__, "person_roi": person_roi.__dict__,
                    "model_action": str(model_action), "temporal_verdict": str(vres.verdict),
                    "observed_action": str(vres.observed_action), "target_object": vres.target_object,
                    "mandatory": vres.mandatory, "reason_codes": vres.reason_codes,
                    "fusion": fusion, "frames_dir": [f"m{mid}_{i}.jpg" for i in range(len(frames))]})
    print("CASE", mid, "->", vres.verdict, vres.mandatory, flush=True)

json.dump(results, open(OUT / "_mmv_real_results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("DONE", len(results))
