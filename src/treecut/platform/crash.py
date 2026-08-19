"""Crash handler that persists a timestamped traceback before exiting."""
from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path


def install_crash_handler(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)

    def handler(exc_type, exc_value, exc_traceback) -> None:
        path = log_dir / f"crash_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        try:
            with open(path, "w", encoding="utf-8") as stream:
                traceback.print_exception(exc_type, exc_value, exc_traceback, file=stream)
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = handler
