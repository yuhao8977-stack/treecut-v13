"""Build a TreeCut update package and upload it to the local remote hub."""
from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path

from treecut.platform.paths import RuntimePaths
from treecut.remote.update_pack import make_update_package


def main() -> int:
    parser = argparse.ArgumentParser(description="推送树剪更新包到本机远程管理端")
    parser.add_argument("--version", default="13.5.5")
    parser.add_argument("--notes", default="新增程序内成片预览；桌面自动生成快捷方式；任务记录可预览成片")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--url", default="http://127.0.0.1:8766")
    args = parser.parse_args()

    paths = RuntimePaths.discover()
    token = (paths.data_root / "config" / "api_token.txt").read_text(encoding="utf-8").strip()
    master = (paths.data_root / "config" / "master_key.txt").read_text(encoding="utf-8").strip()
    package = paths.temp / f"treecut_update_{args.version}.zip"

    make_update_package(paths.install_root, args.version, args.notes, package, force=args.force)
    data = package.read_bytes()
    query = (f"/api/v1/updates?version={urllib.parse.quote(args.version)}"
             f"&notes={urllib.parse.quote(args.notes)}&force={1 if args.force else 0}")
    request = urllib.request.Request(
        args.url + query, data=data, method="POST",
        headers={
            "X-TreeCut-Token": token,
            "X-TreeCut-Master": master,
            "Content-Type": "application/octet-stream",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        body = json.loads(response.read().decode("utf-8"))
    print(f"pushed {body.get('version')} update_id={body.get('update_id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
