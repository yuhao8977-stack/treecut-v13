#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MMVV A3 — HOLDOUT 冻结 runner（机器侧唯一输入清单 + 帧抽取）。

人工筛选完成后执行本脚本一次：按统一采样策略抽取 6 个 holdout 案例的
全分辨率帧（每案例 5 帧，均匀窗口 [0.15,0.85]·duration，帧精确解码），
计算帧 sha256/尺寸/字节、源文件 sha256、G1 资格，
写出 TREECUT_MMVV_A3_HOLDOUT_MANIFEST.json（machine-only：不含任何
human_gt/expected_verdict/筛选标签 —— 答案只存在于 HUMAN_GT 文件）。

策略冻结: A3_SAMPLING_UNIFORM_TIME_V1（与人工筛选同时间戳，禁止挑帧）。
算法冻结: ALGORITHM_FREEZE_COMMIT=ca34678（几何/时序/相机规则不得在
A3 看到机器结果后修改）。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8")

FRAMES_ROOT = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\mmv_a3_holdout_frames")
OUT = REPO / "reports" / "storage"
MANIFEST = OUT / "TREECUT_MMVV_A3_HOLDOUT_MANIFEST.json"
CANDIDATES = OUT / "TREECUT_MMVV_A3_CANDIDATES.json"
FFMPEG = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
FFPROBE = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffprobe.exe"
ALGORITHM_FREEZE_COMMIT = "ca34678"
SAMPLING_POLICY = {
    "policy_id": "A3_SAMPLING_UNIFORM_TIME_V1",
    "mode": "uniform_time_window",
    "relative_window": [0.15, 0.85],
    "frames_per_case": 5,
    "relative_fractions": [0.15, 0.35, 0.50, 0.65, 0.85],
    "extraction": "ffmpeg 帧精确解码（-i 在前，-ss 在后），全分辨率 JPEG q=2",
    "note": "所有 holdout 案例同一策略；与人工筛选所看时间戳一致；机器输入仅限 manifest，禁止另选帧/挑帧。",
}

# case_id(含筛选组别，架构师批准命名) -> 素材/家族/描述
CASE_SPECS = [
    {"case_id": "A3_POS_01", "media_id": 2521, "asset_id": "c924db90a4644d3b86890d95a9681216",
     "visual_family_id": "VF_EXTEND_60CM_WEI_NANJING",
     "desc": "南京魏小姐 岛台总长2.6m 伸缩60cm（微水泥奶油色+杏黄柚木 铁牛01）"},
    {"case_id": "A3_POS_02", "media_id": 2549, "asset_id": "71885540821a4324a53c3f38efbb2060",
     "visual_family_id": "VF_EXTEND_TABLE_ZHANG_SHENZHEN",
     "desc": "深圳张小姐 伸缩餐桌的岛台（微水泥奶油白+兰亭香樟木纹岩板）"},
    {"case_id": "A3_POS_03", "media_id": 2551, "asset_id": "185b5a0abca04232802ef3f5b49af8f9",
     "visual_family_id": "VF_EXTEND_TABLE_YU_SHENZHEN",
     "desc": "深圳于小姐 伸缩餐桌岛台（微水泥奶油白+兰亭香樟木纹岩板）"},
    {"case_id": "A3_NEG_01", "media_id": 2209, "asset_id": "96a360ade5094381a48c87dbcd95cddf",
     "visual_family_id": "VF_T_LEG_ROCK_YAN_WULUMUQI",
     "desc": "乌鲁木齐燕先生 岛台餐桌角T字型可伸缩（宝格丽紫+纯黑+北美黑胡桃 T型岩板腿）"},
    {"case_id": "A3_NEG_02", "media_id": 2280, "asset_id": "f39356e52dfa486b8bdf5a6d789eb02c",
     "visual_family_id": "VF_STRAIGHT_LEG_ROCK_LI_GUANGZHOU",
     "desc": "广州李先生 岛台伸缩脚6.5cm厚岩板（咖色+深黑+黑白 一字型岩板腿）"},
    {"case_id": "A3_NEG_03", "media_id": 2544, "asset_id": "06b7a15b50954cf3b934f4fdd10b8a48",
     "visual_family_id": "VF_MINI_EXTEND_XU_SHENZHEN",
     "desc": "深圳徐先生 MINI伸缩岛台 小户型（雪山石纹）"},
]
CHOSEN_MEDIA = {s["media_id"] for s in CASE_SPECS}


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def probe_duration(path: str) -> float:
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "json", path], capture_output=True)
    d = json.loads(r.stdout.decode("utf-8", "replace"))
    return float(d["format"]["duration"])


def extract_frame(path: str, ts: float, out: Path) -> None:
    subprocess.run([FFMPEG, "-y", "-i", path, "-ss", f"{ts:.3f}", "-frames:v", "1",
                    "-q:v", "2", str(out)], check=True, capture_output=True)


def main():
    cand = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    by_mid = {c["media_id"]: c for c in cand["candidates"]}
    missing = CHOSEN_MEDIA - set(by_mid)
    if missing:
        raise SystemExit(f"候选缺失: {missing}")
    excluded = set(cand["excluded_known_ids"])
    overlap = CHOSEN_MEDIA & excluded
    if overlap:
        raise SystemExit(f"与已知排除集合重叠(禁止): {overlap}")

    FRAMES_ROOT.mkdir(parents=True, exist_ok=True)
    cases = []
    frame_sha_seen = {}
    for spec in CASE_SPECS:
        c = by_mid[spec["media_id"]]
        src = c["path"]
        dur = probe_duration(src)
        w0, w1 = round(dur * 0.15, 3), round(dur * 0.85, 3)
        frs = []
        for i, frac in enumerate(SAMPLING_POLICY["relative_fractions"]):
            ts = round(w0 + i * (w1 - w0) / 4.0, 3)
            fname = f"m{spec['media_id']}_{i}.jpg"
            fp = FRAMES_ROOT / fname
            extract_frame(src, ts, fp)
            sha = sha256_file(fp)
            if sha in frame_sha_seen:
                raise SystemExit(f"帧 sha256 碰撞: {fname} == {frame_sha_seen[sha]}")
            frame_sha_seen[sha] = fname
            import cv2
            img = cv2.imdecode(np.fromfile(str(fp), dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                raise SystemExit(f"imdecode 失败: {fp}")
            h, w = img.shape[:2]
            frs.append({"idx": i, "frame": fname, "t_s": ts, "sha256": sha,
                        "width": int(w), "height": int(h), "bytes": fp.stat().st_size,
                        "local_path": str(fp)})
        # G1 资格
        from treecut.services.production_source import ProductionSourceService
        svc = ProductionSourceService()
        ok, info = svc.is_media_production_eligible(spec["media_id"], strict=True)
        cases.append({
            "case_id": spec["case_id"], "media_id": spec["media_id"],
            "asset_id": spec["asset_id"],
            "visual_family_id": spec["visual_family_id"], "desc": spec["desc"],
            "source_path": src, "source_sha256": sha256_file(Path(src)),
            "source_duration_s": round(dur, 3), "frozen_window_s": [w0, w1],
            "g1_eligible": ok, "g1_evidence": info,
            "frames": frs,
        })
        print(f"{spec['case_id']} media={spec['media_id']} dur={dur:.2f} "
              f"window=[{w0},{w1}] frames={len(frs)} g1={ok}")

    doc = {
        "experiment": "MMVV_A3_HOLDOUT",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "algorithm_freeze_commit": ALGORITHM_FREEZE_COMMIT,
        "sampling_policy": SAMPLING_POLICY,
        "machine_input_boundary": (
            "本文件是 A3 机器侧唯一输入清单。禁止读取含人工答案的文件："
            "TREECUT_MMVV_A3_HUMAN_GT.json / TREECUT_MMVV_A3_SCREENING.json；"
            "本清单不含 human_gt/expected_verdict/筛选标签。"),
        "frames_dir": str(FRAMES_ROOT),
        "cases": cases,
    }
    tmp = MANIFEST.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(MANIFEST)
    print("WROTE", MANIFEST)


if __name__ == "__main__":
    main()
