"""Run the remote management hub (bind to the LAN for client access)."""
from __future__ import annotations

import argparse
import socket

import uvicorn

from treecut.platform.paths import RuntimePaths
from treecut.remote.discovery import HubResponder
from treecut.remote.hub import create_hub_app
from treecut.remote.roles import is_master
from treecut.remote.security import load_or_create_token
from treecut.remote.autostart import ensure_autostart


def lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def main() -> None:
    parser = argparse.ArgumentParser(description="启动树剪远程管理端")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    probe = socket.socket()
    try:
        probe.bind(("0.0.0.0", args.port))
    except OSError:
        print(f"端口 {args.port} 已被占用：远程管理端可能已在本机运行")
        print("（例如桌面窗口里已打开过“远程管理”），无需重复启动。")
        return
    finally:
        probe.close()
    paths = RuntimePaths.discover()
    paths.apply_environment()
    token = load_or_create_token(paths.data_root / "config" / "api_token.txt")
    app = create_hub_app(paths, token=token)
    responder = HubResponder(token, args.port)
    responder.start()
    ensure_autostart("hub", paths.install_root, args.port)
    print(f"远程管理端已启动，局域网地址：http://{lan_ip()}:{args.port}")
    print("口令（在另一台电脑的远程助手里填写）：")
    print(token)
    if is_master(paths):
        print("本机已设为主程序：远程管理功能仅在本机开放。")
    else:
        print("注意：本机不是主程序，管理功能不会显示。")
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    finally:
        responder.stop()


if __name__ == "__main__":
    main()
