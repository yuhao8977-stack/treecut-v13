"""Optional update-channel check; no-op without a configured channel URL."""
from __future__ import annotations

import json
import shutil
import urllib.request


def check_for_updates(current_version: str, channel_url: str | None = None,
                      timeout: int = 10) -> dict:
    if not channel_url:
        return {"available": False, "current": current_version, "reason": "no_channel"}
    try:
        request = urllib.request.Request(channel_url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        latest = str(payload.get("version") or "")
        return {
            "available": bool(latest) and latest != current_version,
            "current": current_version,
            "latest": latest or None,
            "url": payload.get("url"),
            "notes": payload.get("notes") or "",
        }
    except Exception as error:
        return {
            "available": False, "current": current_version,
            "reason": f"check_failed:{type(error).__name__}",
        }


def download_update(url: str, destination, timeout: int = 600):
    """Download a release artifact to the given destination path."""
    from pathlib import Path
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=timeout) as response, destination.open("wb") as stream:
        shutil.copyfileobj(response, stream)
    if destination.stat().st_size == 0:
        raise RuntimeError("下载的文件为空")
    return destination
