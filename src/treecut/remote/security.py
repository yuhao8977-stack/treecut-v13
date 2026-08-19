"""Token helpers shared by the remote hub and its clients."""
from __future__ import annotations

import secrets
from pathlib import Path


def load_or_create_token(path: Path) -> str:
    """Return the existing token or create a fresh random one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        token = path.read_text(encoding="ascii").strip()
        if len(token) >= 32:
            return token
    token = secrets.token_urlsafe(32)
    path.write_text(token, encoding="ascii")
    return token
