"""Enqueue a remote command on a client and wait for its result (UTF-8 safe)."""
from __future__ import annotations

import argparse
import json
import time
import urllib.request

from treecut.platform.paths import RuntimePaths


def _api(paths, path: str, method: str = "GET", payload=None, timeout: float = 30):
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


def main() -> int:
    parser = argparse.ArgumentParser(description="远程执行命令并等待结果")
    parser.add_argument("--client", required=True)
    parser.add_argument("--note", required=True)
    parser.add_argument("--action", default="exec")
    parser.add_argument("--timeout", type=float, default=240.0)
    args = parser.parse_args()

    paths = RuntimePaths.discover()
    created = _api(paths, f"/api/v1/clients/{args.client}/commands",
                   method="POST", payload={"action": args.action, "note": args.note})
    command_id = created["command_id"]
    print(f"command_id={command_id}")
    deadline = time.time() + args.timeout
    result = None
    while time.time() < deadline:
        audit = _api(paths, "/api/v1/audit?limit=50")
        for entry in audit.get("commands", []):
            if entry["command_id"] == command_id:
                status = entry.get("status")
                if status in ("done", "failed"):
                    result = entry
                break
        if result is not None:
            break
        time.sleep(8)
    if result is None:
        print("RESULT_TIMEOUT")
        return 2
    log = paths.logs / "remote_exec_results.json"
    history = []
    if log.is_file():
        try:
            history = json.loads(log.read_text(encoding="utf-8"))
        except Exception:
            history = []
    history.append({"command_id": command_id, "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "client": args.client, "note": args.note, "entry": result})
    log.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RESULT_STATUS=" + result.get("status", ""))
    return 0 if result.get("status") == "done" else 1


if __name__ == "__main__":
    raise SystemExit(main())
