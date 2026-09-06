# -*- coding: utf-8 -*-
"""MMVV A3 — Prediction-side 测试（blind runner/scorer；GT 未解封时运行）。

覆盖: selfcheck 真实帧 hash / ROI hash / 179 / coverage / freeze / 无 stale；
runner 禁读 GT/key/obs；统一 EXTEND；无 per-case 分支；目标 fail-closed；
冻结 EXCLUDE_NAMES 未被新标签改动；预测文件无 GT 字段；hash 先于 GT；
scorer 拒缺 hash / 拒篡改 / 只用 human_gt；FP 与状态门定义。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STORAGE = REPO / "reports" / "storage"
RUNNER = REPO / "scripts" / "run_a3_blind.py"
SCORER = REPO / "scripts" / "score_a3_after_prediction.py"
PRED = STORAGE / "TREECUT_MMVV_A3_MACHINE_PREDICTIONS_BLIND.json"
PRED_SHA = STORAGE / "TREECUT_MMVV_A3_MACHINE_PREDICTIONS_BLIND.sha256.txt"
LOCK = STORAGE / "TREECUT_MMVV_A3_PREDICTION_LOCK_V1.json"
ROI = STORAGE / "TREECUT_MMVV_A3_HUMAN_GT_ROI_BLIND.json"
GT = STORAGE / "TREECUT_MMVV_A3_HUMAN_GT.json"
KEY = STORAGE / "TREECUT_MMVV_A3_CASE_KEY_PRIVATE.json"
OBS = STORAGE / "TREECUT_MMVV_A3_OBSERVABILITY_HUMAN_V1.json"

FROZEN_EXCLUDE = {"PERSON", "HAND", "SOCKET_MODULE", "TRACK_SOCKET", "TABLETOP",
                  "EXTENSION_TABLETOP", "UPPER_THIN_DRAWER", "DRAWER", "OTHER_MOVING_PART"}


def load_mod(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_selfcheck_verifies_actual_hashes_and_179():
    trio = [PRED, PRED_SHA, LOCK]
    moved = []
    for p in trio:
        if p.exists():
            bk = p.with_suffix(".tstbak")
            p.replace(bk)
            moved.append((p, bk))
    try:
        r = subprocess.run([sys.executable, str(RUNNER), "--selfcheck"], capture_output=True,
                           text=True, timeout=300, cwd=str(REPO))
        assert r.returncode == 0, r.stdout[-400:]
        assert "A3_SELFCHECK_PASS" in r.stdout
    finally:
        for p, bk in moved:
            bk.replace(p)


def test_prediction_runner_cannot_read_gt_key_observability():
    m = load_mod(RUNNER, "run_a3_blind_pred")
    for bad in (GT, KEY, OBS,
                STORAGE / "TREECUT_MMVV_A3_HOLDOUT_MANIFEST.json",
                STORAGE / "TREECUT_MMVV_A3_HOLDOUT_AUDIT.json"):
        try:
            m.ensure_allowed(bad)
            raise AssertionError(f"runner 竟允许读取 {bad.name}")
        except m.ForbiddenFileError:
            pass


def test_same_requested_action_for_all_cases():
    d = json.loads(PRED.read_text(encoding="utf-8"))
    assert d["requested_action"] == "EXTEND"
    assert len(d["cases"]) == 6
    assert all(c["requested_action"] == "EXTEND" for c in d["cases"])
    src = RUNNER.read_text(encoding="utf-8")
    assert "if oid ==" not in src and "if opaque ==" not in src


def test_ambiguous_target_fails_closed():
    m = load_mod(RUNNER, "run_a3_blind_amb")
    single = [{"object_name": "EXTENSION_TABLETOP", "bbox_pixel": [1, 2, 3, 4]}]
    bb, state, lab = m.resolve_target(single)
    assert state == "TARGET_SINGLE" and bb == [1, 2, 3, 4] and lab == "EXTENSION_TABLETOP"
    bb2, st2, _ = m.resolve_target([{"object_name": "EXTENSION_TABLETOP", "bbox_pixel": [1, 1, 2, 2]},
                                    {"object_name": "EXTENSION_TABLETOP", "bbox_pixel": [3, 3, 4, 4]}])
    assert st2 == "TARGET_IDENTITY_AMBIGUOUS" and bb2 is None


def test_missing_target_does_not_auto_generate():
    m = load_mod(RUNNER, "run_a3_blind_miss")
    bb, state, _ = m.resolve_target([{"object_name": "HAND", "bbox_pixel": [1, 1, 5, 5]}])
    assert state == "TARGET_NOT_VISIBLE" and bb is None


def test_extra_roi_label_does_not_change_frozen_rule():
    from treecut.services.mmv_camera_diag import EXCLUDE_NAMES
    assert EXCLUDE_NAMES == FROZEN_EXCLUDE
    assert "ROCK_TABLE_LEG" not in EXCLUDE_NAMES and "CABINET_DOOR" not in EXCLUDE_NAMES


def test_prediction_contains_no_gt_fields():
    raw = PRED.read_text(encoding="utf-8")
    d = json.loads(raw)
    for tok in ("human_gt", "expected_verdict", "expected_machine", "original_case_id",
                "YES_EXTEND", "NO_EXTEND", "A3_POS", "A3_NEG", "2521", "2549", "2551",
                "2209", "2280", "2544", "魏小姐", "张小姐", "于小姐", "海口", "X1"):
        assert tok not in raw, f"预测文件泄漏: {tok}"
    assert all(c["machine_verdict"] in ("PASS", "FAIL", "UNSURE") for c in d["cases"])


def test_prediction_hash_written_before_gt():
    import hashlib
    sha = hashlib.sha256(PRED.read_bytes()).hexdigest()
    txt = PRED_SHA.read_text(encoding="utf-8").strip().split()[0]
    assert sha == txt
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    assert lock["prediction_sha256"] == sha
    assert lock["gt_opened"] is False
    assert lock["algorithm_freeze_commit"] == "ca34678"


def _scorer_mod():
    return load_mod(SCORER, "score_a3_pred")


def _tmp_setup(tmp_path, verdicts=("PASS", "FAIL", "UNSURE", "PASS", "FAIL", "UNSURE"),
               labels=("YES_EXTEND", "YES_EXTEND", "NO_EXTEND", "NO_EXTEND", "YES_EXTEND", "NO_EXTEND"),
               expected_contrarian=False):
    pred = {"cases": [{"opaque_case_id": f"H{i+1:03d}", "machine_verdict": verdicts[i]}
                      for i in range(6)],
            "roi_sha256": "x" * 64, "algorithm_freeze_commit": "ca34678"}
    key = {"mapping": [{"opaque_case_id": f"H{i+1:03d}",
                        "original_case_id": f"O{i+1}", "media_id": i + 1} for i in range(6)]}
    answers = []
    for i in range(6):
        em = "NOT_PASS" if labels[i] == "NO_EXTEND" else "PASS"
        if expected_contrarian:
            em = "PASS" if labels[i] == "NO_EXTEND" else "NOT_PASS"
        answers.append({"case_id": f"O{i+1}", "human_gt": labels[i] + ": 测试", "expected_machine": em})
    gt = {"answers": answers}
    pd_ = tmp_path / "pred.json"
    import hashlib
    pd_.write_text(json.dumps(pred), encoding="utf-8")
    sha = hashlib.sha256(pd_.read_bytes()).hexdigest()
    (tmp_path / "pred.sha").write_text(f"{sha}  pred.json\n", encoding="utf-8")
    (tmp_path / "key.json").write_text(json.dumps(key), encoding="utf-8")
    (tmp_path / "gt.json").write_text(json.dumps(gt), encoding="utf-8")
    (tmp_path / "lock.json").write_text(json.dumps({"prediction_sha256": sha, "gt_opened": False}),
                                        encoding="utf-8")
    return pd_


def test_scorer_rejects_missing_hash(tmp_path):
    m = _scorer_mod()
    pd_ = _tmp_setup(tmp_path)
    try:
        m.score(pd_, tmp_path / "key.json", tmp_path / "gt.json",
                tmp_path / "no_sha", tmp_path / "lock.json", tmp_path / "out.json")
        raise AssertionError("应拒绝缺 hash")
    except SystemExit as e:
        assert "A3_PREDICTION_SHA_MISSING" in str(e)


def test_scorer_rejects_changed_prediction(tmp_path):
    m = _scorer_mod()
    pd_ = _tmp_setup(tmp_path)
    # 篡改预测后再跑 → hash mismatch，且不得读取/应用 GT（提前退出即可证明）
    pd_.write_text(json.dumps({"cases": []}), encoding="utf-8")
    try:
        m.score(pd_, tmp_path / "key.json", tmp_path / "gt.json",
                tmp_path / "pred.sha", tmp_path / "lock.json", tmp_path / "out.json")
        raise AssertionError("应拒绝篡改")
    except SystemExit as e:
        assert "PREDICTION_HASH_MISMATCH" in str(e)


def test_scorer_ignores_expected_machine_field(tmp_path):
    m = _scorer_mod()
    pd_ = _tmp_setup(tmp_path, expected_contrarian=True)
    out = m.score(pd_, tmp_path / "key.json", tmp_path / "gt.json",
                  tmp_path / "pred.sha", tmp_path / "lock.json", tmp_path / "out.json")
    rows = {r["opaque_case_id"]: r for r in out["rows"]}
    # expected_machine 与 human_gt 矛盾时，category 必须跟 human_gt
    assert rows["H001"]["category"] == "TP"          # YES+PASS
    assert rows["H002"]["category"] == "FN"          # YES+FAIL
    assert rows["H003"]["category"] == "UNSURE_NEG"  # NO+UNSURE
    assert rows["H005"]["category"] == "FN"          # YES+FAIL (expected 说 NOT_PASS 但被忽略)


def test_false_pass_definition_correct():
    m = _scorer_mod()
    assert m.classify("PASS", "NO_EXTEND") == "FP"
    assert m.classify("FAIL", "YES_EXTEND") == "FN"
    assert m.classify("PASS", "YES_EXTEND") == "TP"
    assert m.classify("FAIL", "NO_EXTEND") == "TN"
    assert m.classify("UNSURE", "YES_EXTEND") == "UNSURE_POS"
    assert m.classify("UNSURE", "NO_EXTEND") == "UNSURE_NEG"


def test_status_gate_correct():
    m = _scorer_mod()
    assert m.status_from_counts(3, 3, 3, 3, fp=1) == "A3_CORE_GENERALIZATION_NEEDS_REPAIR"
    assert m.status_from_counts(2, 3, 2, 3, fp=0) == "A3_CORE_GENERALIZATION_PROMISING"
    assert m.status_from_counts(1, 3, 2, 3, fp=0) == "A3_CORE_GENERALIZATION_PARTIAL"
    assert m.status_from_counts(0, 3, 0, 3, fp=0) == "A3_CORE_GENERALIZATION_PARTIAL"
    assert m.extend_positive_recognition(0, 3) == "NOT_ESTABLISHED"
    assert m.extend_positive_recognition(1, 3) == "NOT_ESTABLISHED"
    assert m.extend_positive_recognition(2, 3) == "SUPPORTED_ON_THIS_SMALL_HOLDOUT"
