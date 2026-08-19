"""Fetch a file from the child machine via chunked ship_file commands."""
from __future__ import annotations

import argparse
import base64
import json
import time
import urllib.request
from pathlib import Path

from treecut.platform.paths import RuntimePaths


CLIENT = "DESKTOP-S6KSLFM-5a56c7"
CHUNK = 1_400_000


def _api(paths, path: str, method: str = "GET", payload=None, timeout: float = 60):
    token = (paths.data_root / "config" / "api_token.txt").read_text(encoding="utf-8").strip()
    master = (paths.data_root / "config" / "master_key.txt").read_text(encoding="utf-8").strip()
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        "http://127.0.0.1:8766" + path, data=data, method=method,
        headers={"X-TreeCut-Token": token, "X-TreeCut-Master": master,
                 "Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _wait(paths, command_id: str, timeout: float = 180.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        audit = _api(paths, "/api/v1/audit?limit=30")
        for entry in audit.get("commands", []):
            if entry["command_id"] == command_id:
                if entry.get("status") in ("done", "failed"):
                    return entry
                break
        time.sleep(8)
    return {"status": "timeout", "result": ""}


def fetch(paths, source: str, output: Path) -> Path:
    offset = 0
    total = 0
    with open(output, "wb") as out:
        while True:
            note = f"{source}|{offset}" if offset else source
            created = _api(paths, f"/api/v1/clients/{CLIENT}/commands",
                           method="POST", payload={"action": "ship_file", "note": note})
            entry = _wait(paths, created["command_id"])
            if entry.get("status") != "done":
                raise RuntimeError(f"分片拉取失败: {entry.get('status')} {entry.get('result', '')[:200]}")
            result = entry.get("result") or ""
            if not result.startswith("BASE64:"):
                raise RuntimeError(f"响应格式错误: {result[:200]}")
            body, next_offset = result[7:].split("|", 1)
            data = base64.b64decode(body)
            out.write(data)
            total += len(data)
            next_offset_int = int(next_offset)
            if len(data) < CHUNK or next_offset_int <= offset:
                break
            offset = next_offset_int
    print(f"fetched {total} bytes -> {output}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="从子机分片拉取文件")
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    paths = RuntimePaths.discover()
    fetch(paths, args.source, Path(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
