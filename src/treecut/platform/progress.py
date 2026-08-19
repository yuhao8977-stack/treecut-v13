"""Single progress-reporting contract shared by worker, API and desktop."""
from __future__ import annotations

from typing import Callable


ProgressCallback = Callable[[str, float | None], None]


def no_progress(message: str, percent: float | None = None) -> None:
    """Default reporter used by headless callers."""
