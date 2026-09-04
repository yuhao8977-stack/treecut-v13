#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MMVV A3 — BLIND MACHINE INPUT 构建器（Overnight P0：修 A3 答案泄漏）。

输入:   TREECUT_MMVV_A3_HOLDOUT_MANIFEST.json（原始冻结清单，仅取帧几何事实）
输出:   TREECUT_MMVV_A3_MACHINE_INPUT_BLIND_V1.json  ← 机器唯一输入
        TREECUT_MMVV_A3_CASE_KEY_PRIVATE.json       ← 评分专用映射（runner 禁读）
        E:\\...\\B007\\mmv_a3_blind_frames\\Hxxx_Fx.jpg  ← opaque 帧副本

原则:
- opaque_case_id 固定映射且打乱 POS/NEG 次序（避免 H001..H003 恰为全正例的位置泄漏）。
- blind 文件禁止出现: POS/NEG/YES_EXTEND/NO_EXTEND/EXTEND/RETRACT/DRAWER/伸缩/
  human_gt/expected_machine/visual_family_id/desc/客户名/源路径/文件夹/原 media_id/asset_id。
- 帧字节复制（sha256 与源帧一致），机器只见 H001_F0.jpg 这类名字。
- 该映射一旦发布即冻结；如需更换映射必须重建 key 并重新冻结 blind 集。
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
MAN = OUT / "TREECUT_MMVV_A3_HOLDOUT_MANIFEST.json"
BLIND_JSON = OUT / "TREECUT_MMVV_A3_MACHINE_INPUT_BLIND_V1.json"
KEY_JSON = OUT / "TREECUT_MMVV_A3_CASE_KEY_PRIVATE.json"
BLIND_FRAMES = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\mmv_a3_blind_frames")
sys.stdout.reconfigure(encoding="utf-8")

# 固定 opaque 映射（打乱 POS/NEG 次序，避免顺序泄漏）: opaque -> original_case_id
OPAQUE_MAP = {
    "H001": "A3_NEG_03",   # 2544 深圳徐 MINI（负例）
    "H002": "A3_POS_01",   # 2521 南京魏 伸缩60cm（正例）
    "H003": "A3_NEG_02",   # 2280 广州李 一字岩板腿（负例）
    "H004": "A3_POS_03",   # 2551 深圳于 伸缩餐桌（正例）
    "H005": "A3_NEG_01",   # 2209 乌鲁木齐燕 T型岩板腿（负例）
    "H006": "A3_POS_02",   # 2549 深圳张 伸缩餐桌（正例）
}

# 禁止出现在 blind 输出中的词元（扩展可查）
FORBIDDEN = ["POS", "NEG", "EXTEND", "RETRACT", "DRAWER", "SOCKET", "伸缩", "拉出", "收回",
             "human_gt", "expected", "visual_family", "客户", "小姐", "先生",
             "海口", "南京", "深圳", "乌鲁木齐", "广州", "石家庄", "黑龙江",
             "公牛", "轨道插座", "岩板", "亚克力", "X1", "素材盘", "media_id", "2521",
             "2549", "2551", "2209", "2280", "2544"]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_forbidden(obj, path="") -> list[str]:
    """递归扫描禁止词元，返回命中列表（用于自检）。"""
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            hits += scan_forbidden(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits += scan_forbidden(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        for tok in FORBIDDEN:
            if tok.lower() in obj.lower():
                hits.append(f"{path} :: {tok}")
    return hits


def main():
    man = json.loads(MAN.read_text(encoding="utf-8"))
    by_case = {c["case_id"]: c for c in man["cases"]}
    assert set(OPAQUE_MAP) == {f"H{i:03d}" for i in range(1, 7)}
    assert set(OPAQUE_MAP.values()) == set(by_case), "opaque 映射必须恰好覆盖 6 案例"

    BLIND_FRAMES.mkdir(parents=True, exist_ok=True)
    cases = []
    key_rows = []
    frame_sha_seen = {}
    for opaque, ocase_id in OPAQUE_MAP.items():
        c = by_case[ocase_id]
        frs = []
        for i, f in enumerate(c["frames"]):
            dst = BLIND_FRAMES / f"{opaque}_F{i}.jpg"
            shutil.copy2(Path(f["local_path"]), dst)
            sha = sha256_file(dst)
            if sha != f["sha256"]:
                raise SystemExit(f"帧复制哈希不一致: {f['frame']}")
            if sha in frame_sha_seen:
                raise SystemExit(f"帧 sha 碰撞: {opaque}_F{i}")
            frame_sha_seen[sha] = f"{opaque}_F{i}"
            frs.append({"frame": f"{opaque}_F{i}.jpg", "t_s": f["t_s"], "sha256": sha,
                        "width": f["width"], "height": f["height"], "bytes": f["bytes"]})
        cases.append({"opaque_case_id": opaque, "frames": frs,
                      "frozen_window_s": c["frozen_window_s"],
                      "source_duration_s": c["source_duration_s"]})
        key_rows.append({"opaque_case_id": opaque, "original_case_id": ocase_id,
                         "media_id": c["media_id"]})

    blind = {
        "experiment": "MMVV_A3_MACHINE_INPUT_BLIND_V1",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "algorithm_freeze_commit": man["algorithm_freeze_commit"],
        "sampling_policy": man["sampling_policy"],
        "input_boundary": (
            "本文件是 A3 预测阶段的唯一输入。案例编号为不透明标识(Hxxx)；"
            "与真实素材及人工答案的对应关系仅在评分阶段经专用密钥映射后合并。"
            "预测进程不得访问任何人工侧文件、源媒体库或识别/语义元数据。"
            "相机参数无需外部输入：由冻结算法基于本清单帧自估计。"),
        "frames_root": "mmv_a3_blind_frames",   # 相对名；绝对位置由 runner 内部常量解析（JSON 内不含任何本地路径）
        "camera_parameters": "NONE_EXTERNAL_REQUIRED(由冻结 CameraMotionEstimator 在给定帧上自估计；无外部相机元数据)",
        "cases": cases,
    }
    hits = scan_forbidden(blind)
    if hits:
        raise SystemExit(f"BLIND 泄漏自检失败: {hits[:20]}")
    serialized = json.dumps(blind, ensure_ascii=False)
    if "\\" in serialized or '"' not in serialized:
        raise SystemExit("BLIND 含本地反斜杠路径或序列化异常")
    tmp = BLIND_JSON.with_suffix(".tmp")
    tmp.write_text(json.dumps(blind, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(BLIND_JSON)

    key = {"experiment": "MMVV_A3_CASE_KEY_PRIVATE",
           "note": "仅 scoring 进程可读；机器预测 runner 禁读。与 HUMAN_GT 合并后才可评分。",
           "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "mapping": key_rows}
    tmp = KEY_JSON.with_suffix(".tmp")
    tmp.write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(KEY_JSON)
    print("WROTE", BLIND_JSON)
    print("WROTE", KEY_JSON)
    print("blind frames:", len(list(BLIND_FRAMES.glob("*.jpg"))))
    for r in key_rows:
        print(r["opaque_case_id"], "<-", r["original_case_id"], "media", r["media_id"])


if __name__ == "__main__":
    main()
