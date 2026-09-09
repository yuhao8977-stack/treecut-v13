# -*- coding: utf-8 -*-
"""B0 — model-root resolution priority unit tests:
TREECUT_MODEL_ROOT env > local runtime pointer file > install_root/models."""
import os
from pathlib import Path

from treecut.platform.paths import RuntimePaths, configure_models_path


def _resolved(tmp_path, monkeypatch, *, env=None, pointer=None, install_models=None):
    install = tmp_path / "install"
    data = tmp_path / "data"
    (install / "models").mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)
    if env is None:
        monkeypatch.delenv("TREECUT_MODEL_ROOT", raising=False)
    else:
        monkeypatch.setenv("TREECUT_MODEL_ROOT", str(env))
    if pointer is not None:
        configure_models_path(data, pointer)
    return RuntimePaths._resolve_models(install, data)


def test_fallback_install_models(tmp_path, monkeypatch):
    assert _resolved(tmp_path, monkeypatch) == (tmp_path / "install" / "models").resolve()


def test_local_pointer_wins_over_fallback(tmp_path, monkeypatch):
    ptr = tmp_path / "permanent_models"
    ptr.mkdir()
    assert _resolved(tmp_path, monkeypatch, pointer=ptr) == ptr.resolve()


def test_env_wins_over_pointer(tmp_path, monkeypatch):
    ptr = tmp_path / "permanent_models"
    ptr.mkdir()
    env = tmp_path / "env_models"
    env.mkdir()
    assert _resolved(tmp_path, monkeypatch, env=env, pointer=ptr) == env.resolve()


def test_pointer_ignored_when_dir_missing(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir(parents=True, exist_ok=True)
    cfg = data / "config"
    cfg.mkdir()
    (cfg / "models_path.txt").write_text(str(tmp_path / "not_there"), encoding="utf-8")
    install = tmp_path / "install"
    (install / "models").mkdir(parents=True, exist_ok=True)
    monkeypatch.delenv("TREECUT_MODEL_ROOT", raising=False)
    assert RuntimePaths._resolve_models(install, data) == (install / "models").resolve()


def test_configure_writes_pointer_file(tmp_path):
    data = tmp_path / "data"
    ptr = tmp_path / "m"
    ptr.mkdir()
    out = configure_models_path(data, ptr)
    assert out.is_file()
    assert out.read_text(encoding="utf-8").strip() == str(ptr.resolve())
