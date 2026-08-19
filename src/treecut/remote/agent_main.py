"""Standalone remote agent entry point (also used by the desktop app)."""
from __future__ import annotations

import argparse
import json
import threading
import time

from treecut.platform.paths import RuntimePaths
from treecut.remote.agent import RemoteAgent
from treecut.remote.config import RemoteConfig, default_client_id, load_config, save_config


def _configure(paths: RuntimePaths) -> RemoteConfig:
    config_path = paths.data_root / "config" / "remote.json"
    config = load_config(config_path)
    if not config.client_id:
        config.client_id = default_client_id()
    print("=== 树剪远程助手配置 ===")
    print(f"本机标识：{config.client_id}")
    print("请先在这台电脑上双击「启动远程管理端.cmd」，")
    print("然后把里面显示的地址和口令填写到下面。")
    config.hub_url = input("管理端地址（例如 http://192.168.1.100:8766）：").strip()
    config.token = input("管理端口令：").strip()
    auto = input("是否自动发现主机（两台在同一局域网时推荐，直接回车=是）：").strip().lower()
    config.auto_discover = auto not in ("n", "no", "0", "否")
    if not config.valid():
        raise SystemExit("配置不完整：地址和口令都不能为空")
    save_config(config_path, config)
    print("配置已保存。")
    return config


def main() -> None:
    parser = argparse.ArgumentParser(description="树剪远程客户端")
    parser.add_argument("--configure", action="store_true", help="重新填写管理端地址与口令")
    parser.add_argument("--once", action="store_true", help="只上报一次后退出")
    args = parser.parse_args()
    paths = RuntimePaths.discover()
    paths.ensure()
    config_path = paths.data_root / "config" / "remote.json"
    config = load_config(config_path)
    if not config.client_id:
        # treecut_client_id_patch: auto-fill a missing client id instead of
        # dropping into interactive configure mode and hanging with no stdin.
        config.client_id = default_client_id()
        save_config(config_path, config)
    if args.configure or not config.valid():
        config = _configure(paths)
    log_path = paths.logs / "remote.log"

    def logger(message: str) -> None:
        try:
            with open(log_path, "a", encoding="utf-8") as stream:
                stream.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {message}\n")
        except OSError:
            pass

    agent = RemoteAgent(paths, config, logger=logger)
    if args.once:
        outcome = agent.run_once()
        print(json.dumps(outcome, ensure_ascii=True))
        return
    if not config.standalone:
        config.standalone = True
        save_config(config_path, config)
    agent.run(stop=threading.Event())


if __name__ == "__main__":
    main()
