"""Large-file hashing utilities for exact duplicate detection (P1).

Strategy (第二阶段总指令 C3 文件 Fingerprint):
- 小文件 (< 1 MiB): 全量 SHA256。
- 大文件: 分块读取的完整 SHA256（可选 skip 首尾策略仅用于快速预筛，
  正式指纹用完整分块哈希），内存占用 O(block_size)。
- 附带快速预筛指纹 (size + 首尾 1 MiB) 用于扫描阶段的 cheap 去重。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

DEFAULT_BLOCK_SIZE = 4 * 1024 * 1024  # 4 MiB
QUICK_TAIL_SIZE = 1024 * 1024  # 1 MiB


def full_sha256(path: str | Path, block_size: int = DEFAULT_BLOCK_SIZE) -> str:
    """Complete streaming SHA256 of a file. Memory capped at block_size."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while True:
            chunk = stream.read(block_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def quick_fingerprint(path: str | Path, size: int | None = None) -> str:
    """Cheap fingerprint: size + first/last 1 MiB. For scan-time dedup."""
    p = Path(path)
    if size is None:
        size = p.stat().st_size
    digest = hashlib.sha256()
    digest.update(str(size).encode("ascii"))
    with p.open("rb") as stream:
        head = stream.read(QUICK_TAIL_SIZE)
        digest.update(head)
        if size > QUICK_TAIL_SIZE:
            stream.seek(max(0, size - QUICK_TAIL_SIZE))
            digest.update(stream.read(QUICK_TAIL_SIZE))
    return digest.hexdigest()


def partial_fingerprint(path: str | Path, size: int | None = None,
                        head_bytes: int = QUICK_TAIL_SIZE,
                        tail_bytes: int = QUICK_TAIL_SIZE) -> str:
    """Alias of quick_fingerprint with explicit head/tail sizes."""
    return quick_fingerprint(path, size)


def verify_sha256(path: str | Path, expected: str, block_size: int = DEFAULT_BLOCK_SIZE) -> bool:
    """Recompute full SHA256 and compare with expected."""
    return full_sha256(path, block_size) == expected.lower()
