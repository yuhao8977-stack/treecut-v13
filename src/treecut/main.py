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
    parser.add_argument("--probe-assets", type=int, metavar="COUNT", default=None,
                        help="P1: 采集指定数量素材的 ffprobe 元数据与完整指纹")
    parser.add_argument("--assets-status", action="store_true", help="P1: 显示资产表状态")
    parser.add_argument("--assets-list", type=int, metavar="LIMIT", default=None,
                        help="P1: 列出资产（默认 200，加 --assets-list 1 只列已探测）")
    parser.add_argument("--probed-only", action="store_true",
                        help="P1: --assets-list 时仅列出已探测元数据的资产")
    parser.add_argument("--migrate-v12", metavar="V12_DB",
                        help="P1: 从 v12 ai_material_library.db 只读迁移素材身份")
    parser.add_argument("--inc-scan", metavar="PATH",
                        help="P1.1: 增量扫描（NEW/CHANGED/MOVED/MISSING/UNCHANGED 分类）")
    parser.add_argument("--lifecycle-dashboard", action="store_true",
                        help="P1.1: 显示各处理阶段全局统计")
    parser.add_argument("--lifecycle-list", type=int, metavar="LIMIT", default=None,
                        help="P1.1: 列出资产各阶段状态（可加 --stage-status 过滤）")
    parser.add_argument("--stage-status", metavar="STAGE",
                        help="P1.1: 与 --lifecycle-list 连用，仅显示指定阶段状态")
    parser.add_argument("--filter-status", metavar="STATUS",
                        help="P1.1: 与 --lifecycle-list 连用，仅显示指定状态（如 FAILED/STALE/PENDING）")
    parser.add_argument("--mark-stale", nargs=3, metavar=("ASSET_ID", "STAGE", "REASON"),
                        help="P1.1: 手动将某资产某阶段标记 STALE（级联下游）")
    parser.add_argument("--p2-run", type=int, metavar="COUNT", default=None,
                        help="P2: 处理指定数量素材的 scene/keyframe/asr/ocr")
    parser.add_argument("--p2-status", action="store_true",
                        help="P2: 显示 scene/keyframe/asr/ocr 阶段统计")
    parser.add_argument("--p2-no-asr", action="store_true",
                        help="P2: --p2-run 时跳过 ASR（仅 scene/keyframe/ocr）")
    parser.add_argument("--p2-no-ocr", action="store_true",
                        help="P2: --p2-run 时跳过 OCR")
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
    if args.migrate_v12:
        from treecut.library import V12Migrator
        result = V12Migrator().migrate(args.migrate_v12)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.probe_assets is not None:
        context = bootstrap()
        from treecut.library import ProbeWorker
        result = ProbeWorker(paths=context.paths).run(limit=args.probe_assets)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.assets_status:
        context = bootstrap()
        from treecut.library import AssetsManager
        manager = AssetsManager()
        print(json.dumps({
            "assets": manager.stats(),
            "pending_probes": len(manager.pending_probes(limit=1000)),
        }, ensure_ascii=False, indent=2))
        return 0
    if args.assets_list is not None or args.probed_only:
        context = bootstrap()
        from treecut.library import AssetsManager
        manager = AssetsManager()
        limit = args.assets_list if args.assets_list is not None else 200
        assets = manager.list_assets(limit=limit, probed_only=args.probed_only)
        print(json.dumps(assets, ensure_ascii=False, indent=2))
        return 0
    if args.inc_scan:
        from treecut.scanner import IncrementalScanner
        result = IncrementalScanner().scan(args.inc_scan)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.lifecycle_dashboard:
        from treecut.library.processing_state import ProcessingState
        print(json.dumps(ProcessingState().dashboard(), ensure_ascii=False, indent=2))
        return 0
    if args.lifecycle_list is not None:
        from treecut.library.processing_state import ProcessingState, STAGES
        ps = ProcessingState()
        limit = args.lifecycle_list if args.lifecycle_list is not None else 200
        stage_filter = args.stage_status or None
        status_filter = args.filter_status or None
        with ps._connect() as connection:
            where = []
            params: list = []
            if stage_filter:
                where.append("stage=?")
                params.append(stage_filter)
            if status_filter:
                where.append("status=?")
                params.append(status_filter)
            clause = f"WHERE {' AND '.join(where)}" if where else ""
            rows = connection.execute(
                f"SELECT asset_id,stage,status,model_name,model_version,input_fingerprint,"
                f"retry_count,error_message,updated_at FROM asset_processing_state {clause} "
                f"ORDER BY updated_at DESC LIMIT ?", (*params, limit)
            ).fetchall()
        print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2))
        return 0
    if args.mark_stale:
        asset_id, stage, reason = args.mark_stale
        from treecut.library.processing_state import ProcessingState
        ps = ProcessingState()
        ps.mark_stale(asset_id, stage, reason)
        affected = ps.get_asset_states(asset_id)
        print(json.dumps({
            "marked_stale": {"asset_id": asset_id, "stage": stage, "reason": reason},
            "after": {s: v.status for s, v in affected.items()},
        }, ensure_ascii=False, indent=2))
        return 0
    if args.p2_run is not None:
        context = bootstrap()
        from treecut.analysis.p2_worker import P2Worker
        worker = P2Worker(paths=context.paths,
                          include_asr=not args.p2_no_asr,
                          include_ocr=not args.p2_no_ocr)
        result = worker.run(limit=args.p2_run)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.p2_status:
        from treecut.library.processing_state import ProcessingState
        from treecut.library.segments import SegmentStore
        ps = ProcessingState()
        stats = ps.stage_stats()
        store = SegmentStore()
        with store._connect() as connection:
            segs = connection.execute("SELECT COUNT(*) n FROM segments").fetchone()["n"]
            kfs = connection.execute("SELECT COUNT(*) n FROM keyframes").fetchone()["n"]
            trs = connection.execute("SELECT COUNT(*) n FROM transcripts").fetchone()["n"]
            ocrs = connection.execute("SELECT COUNT(*) n FROM ocr_text").fetchone()["n"]
        print(json.dumps({
            "stage_stats": {k: stats.get(k, {}) for k in
                            ("scene", "keyframe", "asr", "ocr")},
            "result_counts": {"segments": segs, "keyframes": kfs,
                              "transcripts": trs, "ocr_items": ocrs},
        }, ensure_ascii=False, indent=2))
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
