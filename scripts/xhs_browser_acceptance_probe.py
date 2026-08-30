# -*- coding: utf-8 -*-
"""XHS Work Browser V0.1.2 — 真实验收探针（A–F 证据）。

用真实 B007 Profile（需 TREECUT_DATA_ROOT 指向用户实际数据根）：
- 自启 Edge（无 --no-sandbox）→ 3 固定 Tab 打开真实三站（登录态由 Profile 恢复）
- 自动串行检测三站 Session/身份（含 SPA 有界重试）
- reconcile 后输出实际 Tab 数
- 优雅关闭（CDP Browser.close → LevelDB 落盘）

只读操作，不采集业务数据；不打印任何 cookie/token/签名。
用法：
  set TREECUT_DATA_ROOT=<用户数据根>  （如 runtime_data/temp/batch1）
  python scripts/xhs_browser_acceptance_probe.py --workspace B007 [--headless]
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from treecut.browser.config import load_config  # noqa: E402
from treecut.browser.main import BrowserRuntime  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)  # 管道输出逐行可见（避免缓冲导致无输出）
    parser = argparse.ArgumentParser(prog="xhs-browser-acceptance-probe")
    parser.add_argument("--workspace", default="B007")
    parser.add_argument("--profile-root", default="", help="覆盖 Profile 根目录")
    parser.add_argument("--headless", action="store_true", help="无窗口模式（无法验证真实登录态）")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                        datefmt="%H:%M:%S")
    config = load_config()
    config.workspace_id = args.workspace
    if args.profile_root:
        config.profile_root = args.profile_root
    config.validate()

    runtime = BrowserRuntime(config)
    print("==", "XHS WORK BROWSER ACCEPTANCE PROBE", "workspace=", args.workspace, "==")
    print("profile_dir =", runtime.workspace.workspace_dir)
    print("profile_exists =", runtime.workspace.exists())
    print("binding =", bool(runtime.workspace.load_binding()))
    try:
        runtime.workspace.acquire_lock()
    except RuntimeError as error:
        print(f"PROFILE_LOCKED: {error} （另一实例正在运行，跳过探测）")
        return 2

    try:
        local = runtime.local_status()
        print("treecut_local =", local)

        runtime.start_browser(headless=args.headless)
        tabs = runtime.ensure_tabs()
        reconcile = tabs.reconcile()
        print(f"tabs_after_reconcile = {reconcile['actual']} "
              f"(closed_duplicates={reconcile['closed_duplicates']}, "
              f"left_untouched={reconcile['left_untouched']})")

        roles = runtime.check_roles()
        print("---- PER-ROLE REAL STATUS ----")
        for role, info in roles.items():
            print(f"{role}: tab_alive={info['tab_alive']} "
                  f"session={info['session']} identity={info['identity']} "
                  f"account_name={info['account_name']} account_id={info['account_id']} "
                  f"binding={info['binding']}")
        ok = all(r["tab_alive"] for r in roles.values())
        valid_count = sum(1 for r in roles.values() if r["session"] == "SESSION_VALID")
        print(f"---- RESULT: tabs={len(runtime._context.pages)} sessions_valid={valid_count}/3 ----")
        print("ACCEPTANCE_PROBE", "PASS" if (ok and valid_count >= 1) else "PARTIAL")
        return 0
    finally:
        runtime.close()
        print("ACCEPTANCE_PROBE_DONE（优雅关闭完成）")


if __name__ == "__main__":
    sys.exit(main())

