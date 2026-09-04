# -*- coding: utf-8 -*-
"""MMVV A3 — Evaluation Integrity 测试（blind 泄漏 + fail-closed + key 一致性）。

覆盖: blind_manifest_has_no_pos_neg / no_extend_token / no_media_id / no_source_path
      machine_runner_cannot_read_gt / blind_runner_fails_closed_on_forbidden_file /
      blind_runner_fails_closed_without_roi(A3_ROI_REQUIRED) / frame 字节绑定 / key 一致性。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STORAGE = REPO / "reports" / "storage"
BLIND = STORAGE / "TREECUT_MMVV_A3_MACHINE_INPUT_BLIND_V1.json"
KEY = STORAGE / "TREECUT_MMVV_A3_CASE_KEY_PRIVATE.json"
MAN = STORAGE / "TREECUT_MMVV_A3_HOLDOUT_MANIFEST.json"
GT = STORAGE / "TREECUT_MMVV_A3_HUMAN_GT.json"
SCREEN = STORAGE / "TREECUT_MMVV_A3_SCREENING.json"
AUDIT = STORAGE / "TREECUT_MMVV_A3_HOLDOUT_AUDIT.json"
RUNNER = REPO / "scripts" / "run_a3_blind.py"

MEDIA_IDS = {2521, 2549, 2551, 2209, 2280, 2544}
ASSET_IDS = {"c924db90a4644d3b86890d95a9681216", "71885540821a4324a53c3f38efbb2060",
             "185b5a0abca04232802ef3f5b49af8f9", "96a360ade5094381a48c87dbcd95cddf",
             "f39356e52dfa486b8bdf5a6d789eb02c", "06b7a15b50954cf3b934f4fdd10b8a48"}


def load_blind_module():
    spec = importlib.util.spec_from_file_location("mmv_a3_blind_build",
                                                  REPO / "scripts" / "mmv_a3_blind_build.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_blind_manifest_has_no_pos_neg():
    raw = BLIND.read_text(encoding="utf-8")
    for tok in ("A3_POS", "A3_NEG", "POS_01", "NEG_01", '"POS"', '"NEG"', "_POS_", "_NEG_"):
        assert tok not in raw, f"pos/neg 泄漏: {tok}"
    blind = json.loads(raw)
    assert all(c["opaque_case_id"].startswith("H") for c in blind["cases"])


def test_blind_manifest_has_no_extend_token():
    m = load_blind_module()
    raw = BLIND.read_text(encoding="utf-8")
    for tok in m.FORBIDDEN:
        assert tok.lower() not in raw.lower(), f"禁词泄漏: {tok}"


def test_blind_manifest_has_no_media_id():
    raw = BLIND.read_text(encoding="utf-8")
    for mid in MEDIA_IDS:
        assert str(mid) not in raw, f"media_id 泄漏: {mid}"
    for aid in ASSET_IDS:
        assert aid not in raw, f"asset_id 泄漏: {aid}"


def test_blind_manifest_has_no_source_path():
    raw = BLIND.read_text(encoding="utf-8")
    for tok in ("X1", "素材盘", ".mp4", "\\\\", "source_path", "relative_path",
                "relative_path", "海口", "南京", "深圳", "乌鲁木齐", "广州", "石家庄",
                "黑龙江", "小姐", "先生", "公牛", "轨道插座", "伸缩"):
        assert tok not in raw, f"源路径/语义泄漏: {tok}"


def test_private_key_consistent():
    key = json.loads(KEY.read_text(encoding="utf-8"))
    man = json.loads(MAN.read_text(encoding="utf-8"))
    blind = json.loads(BLIND.read_text(encoding="utf-8"))
    rows = key["mapping"]
    assert len(rows) == 6
    assert {r["opaque_case_id"] for r in rows} == {c["opaque_case_id"] for c in blind["cases"]}
    by_case = {c["case_id"]: c for c in man["cases"]}
    assert {r["original_case_id"] for r in rows} == set(by_case)
    assert {r["media_id"] for r in rows} == MEDIA_IDS


def test_blind_frames_match_originals():
    blind = json.loads(BLIND.read_text(encoding="utf-8"))
    man = json.loads(MAN.read_text(encoding="utf-8"))
    spec = importlib.util.spec_from_file_location("run_a3_blind_mod", RUNNER)
    run_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run_mod)
    dst_dir = run_mod.BLIND_FRAMES_DIR
    assert dst_dir.exists(), "blind frames dir missing"
    by_case = {c["case_id"]: c for c in man["cases"]}
    for c in blind["cases"]:
        for f in c["frames"]:
            fp = dst_dir / f["frame"]
            assert fp.exists(), f"blind 帧缺失 {f['frame']}"
            assert f["frame"].startswith(c["opaque_case_id"] + "_F")
            assert fp.stat().st_size == f["bytes"]


def test_machine_runner_cannot_read_gt():
    """runner allowlist 拒绝 GT / screening / key / 原 manifest / audit。"""
    spec = importlib.util.spec_from_file_location("run_a3_blind", RUNNER)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    for bad in (GT, SCREEN, KEY, MAN, AUDIT):
        try:
            m.ensure_allowed(bad)
            raise AssertionError(f"runner 竟允许读取: {bad.name}")
        except m.ForbiddenFileError:
            pass


def test_blind_runner_fails_closed_without_roi():
    """ROI 缺失 → A3_ROI_REQUIRED（fail closed，exit 3），绝不预测。"""
    r = subprocess.run([sys.executable, str(RUNNER)], capture_output=True, text=True,
                       timeout=120, cwd=str(REPO))
    assert r.returncode == 3, f"exit={r.returncode} out={r.stdout[-300:]}"
    assert "A3_ROI_REQUIRED" in r.stdout


def test_blind_runner_selfcheck_ok():
    r = subprocess.run([sys.executable, str(RUNNER), "--selfcheck"], capture_output=True,
                       text=True, timeout=180, cwd=str(REPO))
    assert r.returncode == 0, r.stdout[-300:]
    assert "A3_SELFCHECK_OK" in r.stdout
