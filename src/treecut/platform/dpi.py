"""High-DPI handling so the Tk interface renders crisply on scaled displays."""
from __future__ import annotations

import ctypes
import tkinter as tk


def enable_dpi_awareness() -> None:
    """Declare per-monitor DPI awareness before any window is created."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_AWARE_V2
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _dpi_for_root(root: tk.Misc) -> int:
    try:
        value = int(ctypes.windll.user32.GetDpiForWindow(root.winfo_id()))
        if value > 0:
            return value
    except Exception:
        pass
    try:
        value = int(ctypes.windll.user32.GetDpiForSystem())
        if value > 0:
            return value
    except Exception:
        pass
    return 96


def apply_tk_scaling(root: tk.Misc) -> float:
    """Align Tk's font scaling with the real DPI; return the size factor vs 96 DPI."""
    dpi = _dpi_for_root(root)
    root.tk.call("tk", "scaling", dpi / 72.0)
    return dpi / 96.0
