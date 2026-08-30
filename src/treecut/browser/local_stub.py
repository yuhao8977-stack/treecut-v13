"""XHS Work Browser V0.1 — TreeCut Local Service 参考 stub 入口（§46 Test D 人工验证）。

用法：
  python -m treecut.browser.local_stub [--port 28888]
起停后，在 Work Browser 控制台查看 TreeCut Local 状态切换（CONNECTED / DISCONNECTED / 自动恢复）。
"""
from __future__ import annotations

import argparse
import sys
import time

from treecut.browser.local_bridge import LocalServiceStub


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="treecut-xhs-local-stub")
    parser.add_argument("--port", type=int, default=28888)
    args = parser.parse_args(argv)
    stub = LocalServiceStub(port=args.port)
    addr = stub.start()
    print(f"TreeCut Local Service stub running at http://{addr}/health  (Ctrl+C 停止)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("stopping...")
    finally:
        stub.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
