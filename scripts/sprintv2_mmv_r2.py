# -*- coding: utf-8 -*-
"""MMV R2 Known6 复跑 — Semantic ROI + Target Core Motion(归属/排除) + 门序修正。
qwen 输出对象+bbox JSON; TABLETOP_CORE = TABLETOP ROI 排除 SOCKET/DRAWER/PERSON 重叠;
相机补偿统一走 mmvl_master_v1.compensate_pair(CameraMotionEstimator)——R1.1 去重，本脚本不再含独立 translation/affine。"""
import base64, cv2, json, numpy as np, sqlite3, subprocess, sys, time, urllib.request
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
FRD = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\mmv2_frames")
FRD.mkdir(parents=True, exist_ok=True)
SRC = {1: r"\\X1\素材盘01\已处理素材\卖点展示类素材", 2: r"\\X1\素材盘01\已处理素材\效果展示类素材",
       4: r"\\X1\素材盘01\未处理素材\【工厂】"}
SYS = r"C:\Users\admin\github\treecut-v13\src"
sys.path.insert(0, SYS)
from treecut.services.mmvl_master_v1 import (ROI, Action, FrameSemantics, MotionMetrics,
                                             TemporalStateValidator, TemporalEvidence,
                                             TargetObjectMotionRouter, compensate_pair)
ROI_OBJ = ("输出严格 JSON(不要其它文字): {\"objects\":[{\"name\":\"TABLETOP|EXTENSION_TABLETOP|DRAWER|"
           "UPPER_THIN_DRAWER|TRACK_SOCKET|SOCKET_MODULE|PERSON|ISLAND_BODY\",\"bbox\":[x1,y1,x2,y2] 归一化0-1,"
           "\"conf\":0-1}]} 只列出实际可见对象; 无则 {\"objects\":[]}")

def ask_json(b64):
    body = json.dumps({"model": "qwen2.5vl:7b", "stream": False, "options": {"temperature": 0.0,
                       "format": "json"},
                       "messages": [{"role": "user", "content": ROI_OBJ, "images": [b64]}]}).encode()
    req = urllib.request.Request("http://localhost:11434/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=240) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d.get("message", {}).get("content", "")

def parse_rois(text, w, h, mid, ts):
    rois = []
    try:
        import re
        m = re.search(r"\{.*\}", text or "", re.S)
        data = json.loads(m.group(0)) if m else {"objects": []}
        for o in data.get("objects", []):
            nm, bb = o.get("name"), o.get("bbox")
            if not nm or not bb or len(bb) != 4:
                continue
            x1, y1, x2, y2 = [int(v * w) if v <= 1 else int(v) for v in bb]
            rois.append(ROI(nm, x1, y1, x2, y2, confidence=float(o.get("conf", 0.5)),
                            source="MODEL_DETECTED"))
    except Exception:
        pass
    return rois

def gray(f):
    return cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)

def band_motion(a_bgr, b_bgr_warped, box):
    """box ROI 内(扣 mask) absdiff 均值 → 运动代理。mask 排除区列表。"""
    x1, y1, x2, y2 = box
    a = gray(a_bgr)[y1:y2, x1:x2]
    b = gray(b_bgr_warped)[y1:y2, x1:x2]
    if a.size == 0:
        return 0.0
    return float(np.abs(a.astype(np.float32) - b.astype(np.float32)).mean() / 40.0)

def mask_diff(a_bgr, b_warp, roi, exclude_boxes):
    """ROI 运动, 排除区(归一化→像素)置零后计算。"""
    x1, y1, x2, y2 = roi
    A = gray(a_bgr); B = gray(b_warp)
    subA = A[y1:y2, x1:x2].astype(np.float32)
    subB = B[y1:y2, x1:x2].astype(np.float32)
    diff = np.abs(subA - subB)
    mask = np.ones_like(subA, dtype=bool)
    for ex in exclude_boxes:
        ex = [max(0, min(v, 1)) for v in ex] if max(ex) <= 1 else ex
        ex_px = [int(x1 + v * (x2 - x1)) for v in ex] if max(ex) <= 1 else ex
        ex = ex_px
        ex = [max(0, min(ex[i], (x2 - x1) if i % 2 == 0 else (y2 - y1))) for i in range(4)]
        mask[ex[1]:ex[3], ex[0]:ex[2]] = False
    if mask.sum() == 0:
        return 0.0
    return float(diff[mask].mean() / 40.0)

c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
CASES = [(89, Action.EXTEND, None), (52, Action.DRAWER_OPEN, None), (109, Action.DRAWER_OPEN, None),
         (51, Action.EXTEND, None), (1985, Action.EXTEND, (1.9, 4.4)), (1986, Action.EXTEND, (1.9, 4.4))]
fx = {x["media_id"]: x for x in json.loads((OUT / "_v11_flexible_merged_direction.json").read_text(encoding="utf-8"))}
results = []
for mid, req, fw in CASES:
    r = c.execute("SELECT source_id, relative_path FROM media_files WHERE id=?", (int(mid),)).fetchone()
    path = str(Path(SRC[r[0]]) / r[1])
    cap = cv2.VideoCapture(path)
    dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / max(cap.get(cv2.CAP_PROP_FPS), 1)
    cap.release()
    s, e = fw if fw else (fx[mid]["merged_window_s"] if mid in fx else (0.15 * dur, 0.85 * dur))
    e = min(e, dur - 0.2)
    n = 5
    ts = [s + i * (e - s) / (n - 1) for i in range(n)]
    frames = []
    cap = cv2.VideoCapture(path)
    for t in ts:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ok, f = cap.read()
        if ok:
            frames.append(f)
    cap.release()
    if len(frames) < 3:
        results.append({"media_id": mid, "error": "frames<3"})
        continue
    h, w = frames[0].shape[:2]
    # ROI acquisition: qwen2.5vl 无法可信多对象bbox(回显/绝对坐标) → 用布局启发式+运动簇归属(机械)
    frame_rois = []
    for i, f in enumerate(frames):
        frame_rois.append([ROI("PERSON", int(w*0.15), int(h*0.02), int(w*0.85), int(h*0.6), source="HEURISTIC"),
                           ROI("TABLETOP", int(w*0.08), int(h*0.50), int(w*0.92), int(h*0.98), source="HEURISTIC"),
                           ROI("DRAWER", int(w*0.08), int(h*0.45), int(w*0.92), int(h*0.98), source="HEURISTIC")])
        print("r2 heuristic", mid, i, flush=True)
    # 目标对象框(多数帧出现的 MODEL_DETECTED 优先)
    def best_roi(name):
        cand = [roi for fr in frame_rois for roi in fr if roi.name == name and roi.source == "MODEL_DETECTED"]
        if not cand:
            cand = [roi for fr in frame_rois for roi in fr if roi.name == name]
        if not cand:
            return None
        xs = [roi.x1 for roi in cand]; xe = [roi.x2 for roi in cand]
        ys = [roi.y1 for roi in cand]; ye = [roi.y2 for roi in cand]
        return ROI(name, min(xs), min(ys), max(xe), max(ye), source=cand[0].source)
    target_name = "TABLETOP" if req in (Action.EXTEND, Action.RETRACT) else "DRAWER"
    target = best_roi(target_name)
    sock = best_roi("TRACK_SOCKET") or best_roi("SOCKET_MODULE")
    pers = best_roi("PERSON")
    if target is None:
        target = ROI(target_name, int(w*0.1), int(h*0.5), int(w*0.9), int(h*0.95), source="HEURISTIC")
    if pers is None:
        pers = ROI("PERSON", int(w*0.15), int(h*0.02), int(w*0.85), int(h*0.55), source="HEURISTIC")
    ex_boxes = []
    if sock is not None:
        ex_boxes.append([sock.x1, sock.y1, sock.x2, sock.y2])
    # 目标 ROI 交集 person → 排除重叠(person overlap discount)
    tbox = [target.x1, target.y1, target.x2, target.y2]
    # CV: 逐对 → 相机补偿 + 运动簇归属: 人带与"小移动簇(插座/手等)"不并进桌面核心
    roi_motion = {}; pers_mot = 0.0; glob_mot = 0.0; cam_ok = True; cam_t = 0.0; sock_mot = 0.0
    def small_cluster_boxes(diff_img, thresh=18, max_area_frac=0.08):
        """|diff|>thresh 的二值连通域, 面积<max_area_frac 的簇盒子(视为非桌面整体运动的局部部件)"""
        _, bw = cv2.threshold(diff_img, thresh, 255, cv2.THRESH_BINARY)
        n, lab, stats, cent = cv2.connectedComponentsWithStats(bw.astype(np.uint8), connectivity=8)
        boxes = []
        total = bw.shape[0] * bw.shape[1]
        for i in range(1, n):
            if stats[i, cv2.CC_STAT_AREA] < 60:
                continue
            if stats[i, cv2.CC_STAT_AREA] / total > max_area_frac:
                continue
            boxes.append((int(stats[i, cv2.CC_STAT_LEFT]), int(stats[i, cv2.CC_STAT_TOP]),
                          int(stats[i, cv2.CC_STAT_LEFT] + stats[i, cv2.CC_STAT_WIDTH]),
                          int(stats[i, cv2.CC_STAT_TOP] + stats[i, cv2.CC_STAT_HEIGHT])))
        return boxes
    for i in range(len(frames) - 1):
        wb, cm = compensate_pair(frames[i], frames[i + 1])  # 唯一相机实现(CameraMotionEstimator)
        # 目标带 diff
        x1, y1, x2, y2 = tbox
        subA = gray(frames[i])[y1:y2, x1:x2].astype(np.float32)
        subB = gray(wb)[y1:y2, x1:x2].astype(np.float32)
        diff_band = np.abs(subA - subB).astype(np.uint8)
        mask = np.ones_like(subA, dtype=bool)
        # 排除 person 重叠带
        px1 = max(0, min(x2, pers.x1)); px2 = max(x1, min(x2, pers.x2))
        py1 = max(0, min(y2, pers.y1)); py2 = max(y1, min(y2, pers.y2))
        if px2 > px1 and py2 > py1:
            mask[py1 - y1:py2 - y1, px1 - x1:px2 - x1] = False
        # 小移动簇(局部部件) → SOCKET/other 另计, 从核心排除
        small_boxes = small_cluster_boxes(diff_band)
        sock_band_sum = 0.0
        for bx in small_boxes:
            lx = max(0, bx[0] - x1); ly = max(0, bx[1] - y1)
            rx = min(x2 - x1, bx[2] - x1); ry = min(y2 - y1, bx[3] - y1)
            if rx > lx and ry > ly:
                mask[ly:ry, lx:rx] = False
                sock_band_sum += float(diff_band[ly:ry, lx:rx].mean() / 40.0)
        core = float(diff_band[mask].mean() / 40.0) if mask.sum() else 0.0
        ps = float(np.abs(gray(wb)[pers.y1:pers.y2, pers.x1:pers.x2].astype(np.float32) -
                          gray(frames[i])[pers.y1:pers.y2, pers.x1:pers.x2].astype(np.float32)).mean() / 40.0) if pers.x2 > pers.x1 else 0.0
        g = float(np.abs(gray(wb).astype(np.float32) - gray(frames[i]).astype(np.float32)).mean() / 40.0)
        roi_motion[target_name] = max(roi_motion.get(target_name, 0.0), core)
        roi_motion["PERSON"] = max(roi_motion.get("PERSON", 0.0), ps)
        roi_motion["SOCKET_OR_SMALL_OTHER"] = max(roi_motion.get("SOCKET_OR_SMALL_OTHER", 0.0), sock_band_sum)
        pers_mot = max(pers_mot, ps); glob_mot = max(glob_mot, g)
        cam_t = max(cam_t, cm.translation_px); cam_ok = cam_ok and cm.reliable
    sock_mot = roi_motion.get("SOCKET_OR_SMALL_OTHER", 0.0)
    # heuristic ROI 政策: 若 target source HEURISTIC 且方向动作 → 最高 UNSURE(除非 core 极强)
    core = roi_motion.get(target_name, 0.0)
    roi_src = target.source
    metrics = MotionMetrics(global_motion_px=round(glob_mot, 3), camera_residual=round(cam_t, 2),
                            roi_motion={k: round(v, 3) for k, v in roi_motion.items()},
                            roi_edge_shift={}, roi_geometry_change={},
                            person_overlap_ratio={target_name: round(min(1.0, pers_mot / max(core, 1e-6)), 3)})
    sems = [FrameSemantics(timestamp_s=ts[i], objects=list({r.name for r in fr}),
                           states=[], rois=fr, dominant_visual=None) for i, fr in enumerate(frame_rois)]
    mid_i = len(frames) // 2
    router = TargetObjectMotionRouter()
    tv = TemporalStateValidator(router)
    ev = TemporalEvidence(before=sems[0], middle=sems[mid_i], after=sems[-1], motion=metrics,
                          requested_action=req, model_action=Action.UNKNOWN)
    vres = tv.validate(ev)
    verdict = str(vres.verdict)
    # 门序/ROI 政策覆写: 若 target 未动(core 低于阈值)且方向动作 → FAIL(NO_TARGET_OBJECT_MOTION)
    moved = core >= 0.045 or (core >= 0.03 and roi_src == "MODEL_DETECTED")
    if not moved and verdict != "Verdict.FAIL":
        verdict = "Verdict.FAIL"
        vres.mandatory["target_object_motion"] = "FAIL"
    if roi_src == "HEURISTIC" and verdict == "Verdict.PASS":
        verdict = "Verdict.UNSURE"  # heuristic ROI 不得单独方向 PASS
    print("CASE", mid, "->", verdict, "core", round(core, 3), "sock", roi_motion.get("SOCKET_MODULE"),
          "person", round(pers_mot, 3), "roi_src", roi_src, flush=True)
    results.append({"media_id": mid, "requested": str(req), "window": [round(s, 2), round(e, 2)],
                    "verdict": verdict, "mandatory": vres.mandatory, "reason_codes": vres.reason_codes,
                    "roi_motion": {k: round(v, 3) for k, v in roi_motion.items()},
                    "target_roi": target.__dict__, "socket_roi": sock.__dict__ if sock else None,
                    "person_roi": pers.__dict__, "roi_source": roi_src,
                    "core_motion": round(core, 3), "camera_translation_px": round(cam_t, 2),
                    "camera_reliable": cam_ok, "fusion_note": "heuristic 不得 PASS; 门序=visible→moved→direction"})
json.dump(results, open(OUT / "_mmv_r2_results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("R2 DONE", len(results))
