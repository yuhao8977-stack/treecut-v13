# -*- coding: utf-8 -*-
"""V0.2 — B007 Creator Sync 真实运行探针。

用真实 B007 Profile（TREECUT_DATA_ROOT 指向用户数据根）：
启动 Edge → 3 固定 Tab → 账号门 → 观察 Creator 笔记列表响应 → 归一化 → 幂等入库
→ 覆盖/异常/产物。只读业务数据，禁止视频恢复；不打印凭证。

用法：
  set TREECUT_DATA_ROOT=<用户数据根>
  python scripts/b007_creator_sync_probe.py --workspace B007 [--export]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from treecut.browser.config import load_config  # noqa: E402
from treecut.browser.main import BrowserRuntime  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    parser = argparse.ArgumentParser(prog="b007-creator-sync-probe")
    parser.add_argument("--workspace", default="B007")
    parser.add_argument("--profile-root", default="")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--export", action="store_true", help="尝试官方导出（DOM 依赖）")
    parser.add_argument("--url", default="", help="Creator 笔记列表页真实 URL（覆盖默认候选）")
    args = parser.parse_args(argv)

    config = load_config()
    config.workspace_id = args.workspace
    if args.profile_root:
        config.profile_root = args.profile_root
    config.validate()

    runtime = BrowserRuntime(config)
    print("== B007 CREATOR SYNC PROBE ==")
    print("profile_dir =", runtime.workspace.workspace_dir)
    binding = runtime.workspace.load_binding()
    print("binding =", bool(binding),
          "creator_xhs_id =", binding.creator_xhs_id if binding else None)
    try:
        runtime.workspace.acquire_lock()
    except RuntimeError as error:
        print(f"PROFILE_LOCKED: {error}")
        return 2
    try:
        runtime.start_browser(headless=args.headless)
        reconcile = runtime.reconcile_tabs()
        print(f"tabs_after_reconcile = {reconcile['actual']}")
        summary = runtime.run_creator_sync(export_enabled=args.export,
                                           note_list_url=args.url or None)
        print("---- CREATOR SYNC SUMMARY ----")
        for key, value in summary.items():
            print(f"{key} = {value}")
        print("ACCEPTANCE_PROBE", "B007_V02_CREATOR_SYNC_" +
              ("PASS" if summary["engine_state"] == "SUCCESS" else summary["engine_state"]))
        return 0
    finally:
        runtime.close()
        print("CREATOR_SYNC_PROBE_DONE（优雅关闭完成）")


if __name__ == "__main__":
    sys.exit(main())
