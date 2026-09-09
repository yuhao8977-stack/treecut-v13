"""Process-level model cache so repeated productions avoid re-loading models."""
from __future__ import annotations

import ctypes
from typing import Callable


_CACHE: dict[str, object] = {}
_HEAVY_PREFIXES = ("bge:", "clip:")
_RAM_GB: float | None = None


def _ram_gb() -> float:
    global _RAM_GB
    if _RAM_GB is not None:
        return _RAM_GB

    class _MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    try:
        status = _MemoryStatus()
        status.dwLength = ctypes.sizeof(_MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            _RAM_GB = round(status.ullTotalPhys / 2**30, 1)
        else:
            _RAM_GB = 0.0
    except Exception:
        _RAM_GB = 0.0
    return _RAM_GB


def get(kind: str, loader: Callable[[], object]) -> object:
    # On low-RAM machines heavy models are loaded per call and released, so a
    # resident BGE/CLIP cache cannot starve concurrent analysis workers.
    if kind.startswith(_HEAVY_PREFIXES) and 0 < _ram_gb() < 24:
        return loader()
    if kind not in _CACHE:
        _CACHE[kind] = loader()
    return _CACHE[kind]


def clear() -> None:
    _CACHE.clear()
