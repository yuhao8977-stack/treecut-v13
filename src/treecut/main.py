"""Single TreeCut v13 command entry point."""
from __future__ import annotations

import argparse
import json

from treecut.bootstrap import bootstrap
from treecut.library import Catalog
from treecut.media import discover_drives, summarize_media
from treecut.models.registry import build_model_registry
from treecut.analysis import AnalysisWorker


def status() -> dict:
    context = bootstrap()
    paths = context.paths
    from treecut.maintenance import treecut_version
    capabilities = context.capabilities
    plan = context.model_plan
    return {
        "version": treecut_version(paths),
        "ready_for_migration": True,
        "paths": {name: str(value) for name, value in vars(paths).items()},
        "capabilities": capabilities.to_dict(),
        "model_plan": plan.to_dict(),
        "model_registry": {
            name: item.to_dict()
            for name, item in build_model_registry(capabilities).items()
        },
        "settings": vars(context.settings),
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="treecut")
    parser.add_argument("--status", action="store_true", help="显示软件和模型状态")
    parser.add_argument("--drives", action="store_true", help="显示可用磁盘和共享盘")
    parser.add_argument("--scan", metavar="PATH", help="统计指定目录中的素材")
    parser.add_argument("--catalog-scan", metavar="PATH", help="增量登记指定素材目录")
    parser.add_argument("--catalog-status", action="store_true", help="显示素材库状态")
    parser.add_argument("--analyze", type=int, metavar="COUNT", help="处理指定数量的素材分析任务")
    args = parser.parse_args()
    if args.status:
        print(json.dumps(status(), ensure_ascii=False, indent=2))
        return 0
    if args.drives:
        print(json.dumps([drive.to_dict() for drive in discover_drives()], ensure_ascii=False, indent=2))
        return 0
    if args.scan:
        print(json.dumps(summarize_media(args.scan).to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.catalog_scan:
        catalog = Catalog()
        print(json.dumps(catalog.scan(args.catalog_scan).to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.catalog_status:
        catalog = Catalog()
        print(json.dumps({
            "sources": catalog.relink_sources(),
            "stats": catalog.stats(),
            "analysis_jobs": catalog.job_stats(),
        }, ensure_ascii=False, indent=2))
        return 0
    if args.analyze is not None:
        context = bootstrap()
        result = AnalysisWorker(paths=context.paths).run(limit=args.analyze)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
