"""Command-line entry to export a diagnostic bundle for off-machine analysis."""
from __future__ import annotations

import argparse
from pathlib import Path

from treecut.maintenance import export_diagnostic_bundle
from treecut.platform.paths import RuntimePaths


def main() -> None:
    parser = argparse.ArgumentParser(description="导出树剪诊断包")
    parser.add_argument("--out", default=None, help="诊断包保存目录（默认软件所在目录）")
    args = parser.parse_args()
    paths = RuntimePaths.discover()
    paths.ensure()
    destination = Path(args.out) if args.out else paths.install_root
    bundle = export_diagnostic_bundle(paths, destination)
    print(f"诊断包已生成：{bundle}")
    print("请把该 zip 文件带回开发电脑，交给 Codex 分析。")


if __name__ == "__main__":
    main()
