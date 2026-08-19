"""A single rotating log location for desktop, CLI and API."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .paths import RuntimePaths


def configure_logging(paths: RuntimePaths | None = None, verbose: bool = False) -> logging.Logger:
    paths = paths or RuntimePaths.discover()
    paths.ensure()
    logger = logging.getLogger("treecut")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(
        paths.logs / "treecut.log", maxBytes=10 * 1024 * 1024,
        backupCount=5, encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger
