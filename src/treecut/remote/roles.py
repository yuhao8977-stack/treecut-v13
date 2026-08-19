"""Master vs. slave role separation for remote management.

Only the master installation holds the master key, so slave installs can never
reach the hub's administration endpoints over the network.
"""
from __future__ import annotations

from pathlib import Path

from treecut.remote.security import load_or_create_token


MASTER_KEY_NAME = "master_key.txt"


def master_key_path(paths) -> Path:
    return paths.data_root / "config" / MASTER_KEY_NAME


def is_master(paths) -> bool:
    path = master_key_path(paths)
    return path.is_file() and len(path.read_text(encoding="ascii").strip()) >= 32


def load_or_create_master_key(paths) -> str:
    """Create the master key on the designated master machine only."""
    return load_or_create_token(master_key_path(paths))
