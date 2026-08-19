"""Minimal local extension registry with analysis/production hooks.

Extensions are plain Python files placed in ``<data_root>/extensions/``.
Each file must expose ``register()`` and call :func:`register_hook`.
"""
from __future__ import annotations

import importlib.util
import logging
from pathlib import Path


HOOK_KINDS = ("post_analysis", "post_production")

_registered: dict[str, list] = {kind: [] for kind in HOOK_KINDS}


def register_hook(kind: str, fn) -> None:
    if kind not in HOOK_KINDS:
        raise ValueError(f"不支持的扩展钩子: {kind}")
    _registered[kind].append(fn)


def load_extensions(data_root: Path) -> None:
    folder = data_root / "extensions"
    if not folder.is_dir():
        return
    for path in sorted(folder.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"treecut_user_ext_{path.stem}", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[union-attr]
            if hasattr(module, "register"):
                module.register()
        except Exception:
            logging.getLogger("treecut").exception("加载扩展失败: %s", path)


def run_hooks(kind: str, payload) -> None:
    for fn in _registered.get(kind, ()):
        try:
            fn(payload)
        except Exception:
            logging.getLogger("treecut").exception("扩展回调失败: %s", kind)
