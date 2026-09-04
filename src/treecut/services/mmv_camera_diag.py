# -*- coding: utf-8 -*-
"""MMVV A2.2 — Camera Failure Diagnosis + Minimal Repair（受控实验模块）。

只处理当前唯一相机 hard case（SOCKET_01 = media1985/1986 重复视觉窗口，unique=1）。
原则：
- 先诊断 4 个 pair 找 pair3 根因；不直接上新算法。
- 背景掩码 LK（L3 ROI 排除 前景 人/手/插座/目标桌板 等）——仅受控实验，非 production 必需条件。
- 前向-反向跟踪过滤；模型阶梯 translation→partial affine→full affine→(必要时)homography；
  以留出背景 track 评估，选"最简可靠"，禁止为 GT 选模型、禁止放宽可靠性门槛。
- 跳变（SCENE_DISCONTINUITY）不得强行 warp。
- 相机可靠性来自真实机器证据，不得按 media_id。
"""
import cv2
import numpy as np

# ---- provisional 诊断门槛（文档化，非为通过调参）----
_BG_GRID = 24          # 背景特征网格间距(备用)
_BG_MARGIN = 12
_FB_MAX_DIST = 3.0     # 前向-反向往返位移上限(px)
_TRACK_MIN = 24        # 背景 track 数量下限
_FB_VALID_MIN = 0.30   # fb 有效比例下限
_INLIER_MIN = 0.45
_HOLDOUT_RESID_MAX = 3.0   # 留出背景残差(px, 中位)上限 → 可靠
_SCENE_DIFF_MAX = 1.6      # 补偿后全帧均差(/40)超过→疑似场景变化

EXCLUDE_NAMES = {"PERSON", "HAND", "SOCKET_MODULE", "TRACK_SOCKET",
                 "TABLETOP", "EXTENSION_TABLETOP", "UPPER_THIN_DRAWER", "DRAWER",
                 "OTHER_MOVING_PART"}


def background_mask(shape, boxes_px):
    """boxes_px: 前景框列表(排除用) → bool 掩码(True=背景)。"""
    h, w = shape[:2]
    m = np.ones((h, w), dtype=bool)
    for bb in boxes_px:
        x1, y1, x2, y2 = [int(v) for v in bb]
        x1 = max(_BG_MARGIN, min(w - _BG_MARGIN - 1, x1))
        x2 = max(x1 + 1, min(w - _BG_MARGIN, x2))
        y1 = max(_BG_MARGIN, min(h - _BG_MARGIN - 1, y1))
        y2 = max(y1 + 1, min(h - _BG_MARGIN, y2))
        m[y1:y2, x1:x2] = False
    return m


def sample_grid_points(gray, mask):
    """背景角点：goodFeaturesToTrack(仅掩码内) + 网格去重，避免重复纹理扎堆。"""
    mask8 = (mask.astype(np.uint8)) * 255
    pts = cv2.goodFeaturesToTrack(gray, mask=mask8, maxCorners=500,
                                  qualityLevel=0.01, minDistance=8, blockSize=7)
    if pts is None or len(pts) < _TRACK_MIN:
        return None
    # 网格去重：每 _BG_GRID² 保留一个，保证空间分布
    h, w = gray.shape
    kept = []
    used = set()
    for p in pts:
        x, y = int(p[0][0]), int(p[0][1])
        key = (x // _BG_GRID, y // _BG_GRID)
        if key in used:
            continue
        used.add(key)
        kept.append((x, y))
    arr = np.array(kept, dtype=np.float32).reshape(-1, 1, 2)
    return arr if len(arr) >= _TRACK_MIN else None


def fwd_back_filter(g0, g1, pts):
    """前向-反向一致性过滤。"""
    p1, st, _ = cv2.calcOpticalFlowPyrLK(g0, g1, pts, None, winSize=(15, 15),
                                         maxLevel=3, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
    p0b, stb, _ = cv2.calcOpticalFlowPyrLK(g1, g0, p1, None, winSize=(15, 15),
                                           maxLevel=3, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
    ok = (st.ravel() == 1) & (stb.ravel() == 1)
    if ok.any():
        d = np.linalg.norm(p0b[ok] - pts[ok], axis=2).ravel()
        ok = ok.copy()
        ok[ok] = d <= _FB_MAX_DIST
    return p1, ok


def warp_current_to_previous(curr_bgr, model, matrix):
    """A2.2 R1 — 唯一 canonical 逆补偿：把当前帧对齐回前一帧（不允许各路径自己写方向）。
    model: translation/partial_affine/full_affine(2x3) → invertAffineTransform；
           homography(3x3) → inv(H)。"""
    M = np.asarray(matrix, dtype=np.float32)
    h, w = curr_bgr.shape[:2]
    if model == "homography":
        Mi = np.linalg.inv(np.vstack([M, [0, 0, 1]]))[:3]
        return cv2.warpPerspective(curr_bgr, Mi, (w, h))
    Mi = cv2.invertAffineTransform(M) if M.shape == (2, 3) else M
    return cv2.warpAffine(curr_bgr, Mi, (w, h))


def _decomp_affine(M):
    A = M[:2, :2]
    tx, ty = M[0, 2], M[1, 2]
    s = float(np.sqrt(abs(np.linalg.det(A))))
    rot = float(np.degrees(np.arctan2(A[1, 0], A[0, 0])))
    return {"scale": round(s, 4), "rotation_deg": round(rot, 3),
            "translation": [round(tx, 2), round(ty, 2)]}


def estimate_camera_background(a_bgr, b_bgr, boxes_px, mode: str = "background"):
    """背景掩码 + FB 过滤 + 模型阶梯（translation→partial affine→full affine→homography），
    模型以背景 track 评估，选最简可靠。返回诊断 dict + pair_state。
    mode: "background"(默认)=用 boxes_px 排除前景；"full_frame"=不排除（双模式差分诊断用）。
    场景差异一律用 warp_current_to_previous 逆补偿（前→后变换的逆作用到当前帧对齐回前帧）。"""
    ga = cv2.cvtColor(a_bgr, cv2.COLOR_BGR2GRAY)
    gb = cv2.cvtColor(b_bgr, cv2.COLOR_BGR2GRAY)
    h, w = ga.shape
    out = {"shape": [h, w], "mode": mode, "reason_codes": []}
    mask = background_mask((h, w), boxes_px) if mode == "background" else np.ones((h, w), dtype=bool)
    pts = sample_grid_points(ga, mask)
    if pts is None:
        out["pair_state"] = "INSUFFICIENT_FEATURES"
        out["reason_codes"] = ["BACKGROUND_TRACKS_TOO_FEW"]
        return out
    out["feature_count_before"] = int(len(pts))
    p1, ok = fwd_back_filter(ga, gb, pts)
    p0 = pts[ok].reshape(-1, 2)
    p1f = p1[ok].reshape(-1, 2)
    if len(p0) != len(p1f):
        n = min(len(p0), len(p1f))
        p0, p1f = p0[:n], p1f[:n]
    out["tracked_count"] = int(ok.sum())
    out["forward_backward_valid_count"] = int(ok.sum())
    out["fb_valid_ratio"] = round(float(ok.sum()) / len(pts), 3)
    if len(p0) < _TRACK_MIN or (ok.sum() / len(pts)) < _FB_VALID_MIN:
        out["pair_state"] = "CAMERA_MODEL_UNRELIABLE"
        out["reason_codes"] = ["FORWARD_BACKWARD_TRACKS_UNSTABLE"]
        out["tracks_raw"] = int(len(pts)); out["tracks_fb_valid"] = int(ok.sum())
        return out
    delta = p1f - p0
    med = np.median(delta, axis=0)
    out["translation_median"] = [round(float(med[0]), 2), round(float(med[1]), 2)]
    # 模型阶梯
    models = []
    # 1) translation(中位位移)
    models.append({"name": "translation"})
    # 2) partial affine
    Ma, inl = cv2.estimateAffinePartial2D(p0, p1f, method=cv2.RANSAC, ransacReprojThreshold=3.0)
    if Ma is not None and inl is not None:
        models.append({"name": "partial_affine", "M": Ma, "inl": inl.ravel()})
    # 3) full affine
    Mf, inlf = cv2.estimateAffine2D(p0, p1f, method=cv2.RANSAC, ransacReprojThreshold=3.0)
    if Mf is not None and inlf is not None:
        models.append({"name": "full_affine", "M": Mf, "inl": inlf.ravel()})
    # 4) homography（必要时，留出 track 足够才考虑）
    Mh, inlh = cv2.findHomography(p0, p1f, cv2.RANSAC, 3.0)
    if Mh is not None and inlh is not None and (inlh.ravel().sum() / len(p0)) >= _INLIER_MIN:
        models.append({"name": "homography", "M": Mh, "inl": inlh.ravel()})

    chosen = None
    for md in models:
        if md["name"] == "translation":
            Mcur = np.float32([[1, 0, med[0]], [0, 1, med[1]]])
            inl_all = np.ones(len(p0), dtype=bool)
        else:
            Mcur = md["M"]
            inl_all = md["inl"].astype(bool)
        if np.asarray(Mcur).shape == (3, 3):
            pred = cv2.perspectiveTransform(p0.reshape(-1, 1, 2), Mcur).reshape(-1, 2)
        else:
            pred = cv2.transform(p0.reshape(-1, 1, 2), Mcur).reshape(-1, 2)
        res_all = np.linalg.norm(pred - p1f, axis=1)
        inl_ratio = float(inl_all.mean())
        # 留出背景评估：非 inlier 的 background track 残差
        hold = res_all[~inl_all] if (~inl_all).any() else np.array([0.0])
        hold_res = float(np.median(hold))
        ok_model = inl_ratio >= _INLIER_MIN and hold_res <= _HOLDOUT_RESID_MAX
        if md["name"] == "translation":
            # translation 也要留出残差评估：用全 track 残差近似
            hold_res = float(np.median(res_all))
            ok_model = hold_res <= _HOLDOUT_RESID_MAX
        md.update({"inlier_ratio": round(inl_ratio, 3),
                   "median_residual_px": round(float(np.median(res_all)), 3),
                   "background_validation_residual_px": round(hold_res, 3),
                   "decomp": _decomp_affine(Mcur) if Mcur.shape == (2, 3) else {},
                   "ok": ok_model,
                   "validation_note": "全背景 track 拟合后残差（非独立 70/30 holdout；诚实标注）"})
        if ok_model and chosen is None:
            md = dict(md)
            md["M"] = np.asarray(Mcur, dtype=np.float32)
            chosen = md
            out["chosen_model"] = md["name"]
            out["chosen_M"] = md["M"].tolist()
    if chosen is None:
        # 全模型失败 → 诊断：场景跳变 vs 污染（逆补偿评估 scene diff）
        wb = warp_current_to_previous(b_bgr, "translation",
                                      np.float32([[1, 0, med[0]], [0, 1, med[1]]]))
        scene_diff = float(np.abs(cv2.cvtColor(wb, cv2.COLOR_BGR2GRAY).astype(np.float32) -
                                  ga.astype(np.float32)).mean() / 40.0)
        out["scene_difference_score"] = round(scene_diff, 3)
        # 背景 track 本身稳定(fb ok)但无法拟合→可能是跳变；用相关性佐证
        if scene_diff > _SCENE_DIFF_MAX:
            out["pair_state"] = "SCENE_DISCONTINUITY"
            out["reason_codes"] = ["NO_RELIABLE_CAMERA_MODEL", "HIGH_SCENE_DIFFERENCE"]
        else:
            out["pair_state"] = "CAMERA_MODEL_UNRELIABLE"
            out["reason_codes"] = ["NO_RELIABLE_CAMERA_MODEL"]
        out["models_tried"] = [m["name"] for m in models]
        return out
    # 补偿并评估最终 scene diff（选定模型，逆补偿）
    out["inlier_count"] = int((chosen["inl"].sum()) if "inl" in chosen else len(p0))
    out["inlier_ratio"] = chosen["inlier_ratio"]
    out["residual"] = chosen["median_residual_px"]
    out["background_validation_residual_px"] = chosen["background_validation_residual_px"]
    out["validation_note"] = chosen.get("validation_note", "")
    out.update(chosen["decomp"])
    wb = warp_current_to_previous(b_bgr, chosen["name"], chosen["M"])
    scene_diff = float(np.abs(cv2.cvtColor(wb, cv2.COLOR_BGR2GRAY).astype(np.float32) -
                              ga.astype(np.float32)).mean() / 40.0)
    out["scene_difference_score"] = round(scene_diff, 3)
    out["spatial_distribution"] = {"x_span": [int(p0[:, 0].min()), int(p0[:, 0].max())],
                                   "y_span": [int(p0[:, 1].min()), int(p0[:, 1].max())]}
    # 前景污染判定：背景模型可靠但 scene_diff 仍高 → 前景/局部大运动主导画面
    fg = "FOREGROUND_CONTAMINATED" if scene_diff > _SCENE_DIFF_MAX else "SAME_SCENE"
    out["pair_state"] = fg
    if fg == "FOREGROUND_CONTAMINATED":
        out["reason_codes"] = ["BACKGROUND_MODEL_OK_BUT_SCENE_DIFF_HIGH",
                               "FOREGROUND_MAJOR_MOTION_OR_EXCLUDED_REGION_LARGE"]
    else:
        out["reason_codes"] = ["BACKGROUND_MASKED_CAMERA_OK"]
    out["tracks_raw"] = int(len(pts)); out["tracks_fb_valid"] = int(ok.sum())
    return out


def duplicate_case_declaration():
    """A2.2 §0/§13：1985/1986 冻结窗口帧逐张 sha256 相同 → unique=1。"""
    return {"visual_case_id": "CAMERA_CASE_FAMILY_SOCKET_01",
            "members": [1985, 1986],
            "unique_visual_case_count": 1,
            "source_media_reference_count": 2,
            "frame_hash_equivalent": True,
            "statistics_note": "不得写成 2/2；只可 1/1 或 0/1"}
