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
    parser.add_argument("--p2.5-run", type=int, metavar="COUNT", default=None,
                        nargs="?", const=0, dest="p25_run",
                        help="P2.5: 并行分析（默认3 Worker）指定数量素材（缺省=全部剩余）")
    parser.add_argument("--p2.5-workers", type=int, default=3, metavar="N",
                        dest="p25_workers",
                        help="P2.5: Worker 进程数（默认 3：视觉/ASR/OCR 各一）")
    parser.add_argument("--p2.5-stages", default="scene,keyframe,asr,ocr",
                        dest="p25_stages", metavar="STAGES",
                        help="P2.5: 参与分析的阶段（逗号分隔）")
    parser.add_argument("--p2.5-force", action="store_true",
                        dest="p25_force",
                        help="P2.5: 强制并行（即使检测到旧 P2 进程正在处理）")
    parser.add_argument("--p2.5-status", action="store_true",
                        dest="p25_status",
                        help="P2.5: 显示任务调度状态（analysis_tasks 统计）")
    parser.add_argument("--asr-device", default=None, metavar="DEVICE",
                        dest="asr_device",
                        help="ASR 推理设备: auto/cpu/cuda（默认 auto，自动检测 GPU）")
    parser.add_argument("--quality-review", action="store_true",
                        help="P2.7: 启动 AI 分析质量验证 UI（人工抽检）")
    parser.add_argument("--quality-sample", type=int, default=100, metavar="N",
                        dest="quality_sample",
                        help="P2.7: 抽检样本数量（默认 100）")
    parser.add_argument("--quality-report", action="store_true",
                        help="P2.7: 生成质量报告（准确率/OCR/损坏资产）并打印")
    parser.add_argument("--p3-run", type=int, metavar="COUNT", default=None,
                        help="P3: 成片/原片分类 + 重复识别 + TC_CONTENT_TAGS 标签")
    parser.add_argument("--p3-status", action="store_true",
                        help="P3: 显示分类/标签/重复统计")
    parser.add_argument("--labels", metavar="ASSET_ID",
                        help="P3: 列出某资产标签")
    parser.add_argument("--add-label", nargs=3, metavar=("ASSET_ID", "CATEGORY", "LABEL"),
                        help="P3: 人工添加标签（human_override 优先）")
    parser.add_argument("--embed", type=int, metavar="COUNT", default=None,
                        help="P4: 为素材生成 segment embedding 并建 FAISS 索引")
    parser.add_argument("--embed-status", action="store_true",
                        help="P4: 显示向量索引状态")
    parser.add_argument("--index-text", action="store_true",
                        help="P4: 重建 FTS5 全文索引（transcripts/ocr）")
    parser.add_argument("--search", metavar="QUERY",
                        help="P4: 混合检索（如 '客户家 无人 全景 伸缩岛台'）")
    parser.add_argument("--search-topk", type=int, default=5,
                        help="P4: --search 返回条数（默认 5）")
    parser.add_argument("--template-register", action="store_true",
                        help="P5: 注册 CT01/CT02 模板到库")
    parser.add_argument("--brain-status", action="store_true",
                        help="认知体系: 显示数据库表与知识库状态")
    parser.add_argument("--brain-knowledge", action="store_true",
                        help="认知体系: 加载/热更新 TreeCut_AI_Brain 知识库到数据库")
    parser.add_argument("--brain-analyze", metavar="ASSET_ID",
                        help="认知体系: 对单个素材运行完整认知链（Layer 0-6）")
    parser.add_argument("--brain-batch", type=int, metavar="N", default=None,
                        dest="brain_batch",
                        help="认知体系: 对 N 个素材批量运行行业理解（默认从抽检队列取 100）")
    parser.add_argument("--brain-ui", action="store_true",
                        help="认知体系: 启动认知结果人工确认 UI")
    parser.add_argument("--brain-learn", action="store_true",
                        help="认知体系: 执行一次反馈学习（差异→规则→权重更新）")
    parser.add_argument("--brain-learn-status", action="store_true",
                        dest="brain_learn_status",
                        help="认知体系: 反馈学习状态（待处理反馈量）")
    parser.add_argument("--brain-produce", nargs="+", metavar=("TEMPLATE_ID", "PROJECT"),
                        default=None, dest="brain_produce",
                        help="认知体系: 按模板生成成片（如 --brain-produce T001 客户案例001）")
    parser.add_argument("--brain-produce-status", action="store_true",
                        dest="brain_produce_status",
                        help="认知体系: 生产计划状态")
    parser.add_argument("--template-list", action="store_true",
                        help="P5: 列出已注册模板")
    parser.add_argument("--template-recommend", nargs=3, metavar=("TID", "VERSION", "SLOT"),
                        help="P5: 为模板槽位推荐候选镜头")
    parser.add_argument("--template-select", nargs=5,
                        metavar=("PROJECT", "TID", "SLOT", "SEGMENT", "STATUS"),
                        help="P5: 保存选镜结果（candidate/selected/backup/excluded）")
    parser.add_argument("--advise-sort", metavar="PROJECT",
                        help="P6: AI 排序建议（只建议不改）")
    parser.add_argument("--roughcut", nargs=2, metavar=("PROJECT", "OUT_DIR"),
                        help="P6: 按选镜生成 FFmpeg 粗剪（rough_cut+timeline+cuts+srt）")
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
    if args.p25_status:
        from treecut.analysis.scheduler import TaskScheduler
        context = bootstrap()
        print(json.dumps(TaskScheduler(context.paths).status(),
                         ensure_ascii=False, indent=2))
        return 0
    if args.p25_run is not None or args.p25_workers != 3 or args.p25_force or args.asr_device:
        # --p2.5-run 显式 0 或缺省均代表"处理全部剩余"
        context = bootstrap()
        from treecut.analysis.scheduler import TaskScheduler
        scheduler = TaskScheduler(context.paths)
        stages = [s.strip() for s in args.p25_stages.split(",") if s.strip()]
        limit = args.p25_run if (args.p25_run or 0) > 0 else None
        result = scheduler.run(workers=args.p25_workers, limit=limit,
                               stages=stages, force=args.p25_force,
                               asr_device=args.asr_device)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.quality_review:
        # P2.7: 启动人工质量验证 UI
        context = bootstrap()
        from treecut.quality_validation.ui import QualityReviewApp
        app = QualityReviewApp(context.paths.databases / "materials.db")
        app.mainloop()
        return 0
    if args.quality_report:
        # P2.7: 生成质量报告
        context = bootstrap()
        from treecut.quality_validation.store import QualityValidationStore
        from treecut.quality_validation.report import ReportBuilder
        store = QualityValidationStore(context.paths.databases / "materials.db")
        store.ensure_schema()
        rb = ReportBuilder(context.paths.databases / "materials.db")
        report = {
            "coverage": rb.analysis_coverage(),
            "ocr": rb.ocr_analysis(),
            "asr": rb.asr_analysis(),
            "feedback": store.feedback_stats(),
            "broken": {"count": store.count_broken()},
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.brain_status:
        # 认知体系状态
        context = bootstrap()
        from treecut.cognitive import Brain
        brain = Brain(context.paths.databases / "materials.db")
        print(json.dumps(brain.status(), ensure_ascii=False, indent=2))
        return 0
    if args.brain_knowledge:
        # 加载/热更新知识库
        context = bootstrap()
        from treecut.cognitive import KnowledgeLoader
        loader = KnowledgeLoader(context.paths.databases / "materials.db")
        results = loader.load_all()
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0
    if args.brain_analyze:
        # 单素材完整认知链
        context = bootstrap()
        from treecut.cognitive import Brain
        brain = Brain(context.paths.databases / "materials.db")
        print(json.dumps(brain.analyze(args.brain_analyze),
                         ensure_ascii=False, indent=2))
        return 0
    if args.brain_batch is not None:
        # 批量行业理解（默认从 sample_100.json 取；N>0 则随机取 N 个有分析数据的素材）
        context = bootstrap()
        from treecut.cognitive import IndustryEngine
        engine = IndustryEngine(context.paths.databases / "materials.db")
        sample_file = context.paths.databases / "sample_100.json"
        asset_ids = []
        if sample_file.exists() and args.brain_batch == 0:
            import json as _json
            with open(sample_file, encoding="utf-8") as f:
                asset_ids = [s["asset_id"] for s in _json.load(f)]
        else:
            n = args.brain_batch if args.brain_batch > 0 else 100
            conn = sqlite3.connect(
                "file:" + str(context.paths.databases / "materials.db").replace("\\", "/") + "?mode=ro", uri=True)
            rows = conn.execute(
                "SELECT DISTINCT a.asset_id FROM assets a "
                "JOIN transcripts t ON t.asset_id=a.asset_id "
                "ORDER BY RANDOM() LIMIT ?", (n,)).fetchall()
            conn.close()
            asset_ids = [r[0] for r in rows]
        if not asset_ids:
            print(json.dumps({"error": "无可用素材（需先生成 sample_100.json 或素材有 ASR 数据）"},
                             ensure_ascii=False, indent=2))
            return 1
        result = engine.batch(asset_ids, persist=True)
        print(json.dumps({k: v for k, v in result.items() if k != "results"},
                         ensure_ascii=False, indent=2))
        return 0
    if args.brain_ui:
        # 认知结果人工确认 UI
        context = bootstrap()
        from treecut.cognitive.ui import CognitiveReviewApp
        app = CognitiveReviewApp(context.paths.databases / "materials.db")
        app.mainloop()
        return 0
    if args.brain_learn_status:
        # 反馈学习状态
        context = bootstrap()
        from treecut.cognitive import LearningEngine
        engine = LearningEngine(context.paths.databases / "materials.db")
        print(json.dumps(engine.status(), ensure_ascii=False, indent=2))
        return 0
    if args.brain_learn:
        # 执行反馈学习
        context = bootstrap()
        from treecut.cognitive import LearningEngine
        engine = LearningEngine(context.paths.databases / "materials.db")
        result = engine.learn()
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.brain_produce_status:
        # 生产计划状态
        context = bootstrap()
        from treecut.cognitive import ProductionEngine
        engine = ProductionEngine(context.paths.databases / "materials.db")
        print(json.dumps({"status": engine.status(),
                          "plans": engine.list_plans()},
                         ensure_ascii=False, indent=2))
        return 0
    if args.brain_produce:
        # 认知生产：按模板生成成片
        context = bootstrap()
        from treecut.cognitive import ProductionEngine
        engine = ProductionEngine(context.paths.databases / "materials.db")
        template_id = args.brain_produce[0]
        project = args.brain_produce[1] if len(args.brain_produce) > 1 else None
        result = engine.produce(template_id, project)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.p3_run is not None:
        from treecut.analysis.p3_worker import P3Worker
        worker = P3Worker()
        result = worker.run(limit=args.p3_run)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.p3_status:
        from treecut.library.classification_store import ClassificationStore
        cls = ClassificationStore()
        with cls._connect() as connection:
            types = {
                row["asset_type"]: row["n"]
                for row in connection.execute(
                    "SELECT asset_type,COUNT(*) n FROM asset_types GROUP BY asset_type"
                ).fetchall()
            }
            labels = connection.execute("SELECT COUNT(*) n FROM labels").fetchone()["n"]
            dup_groups = connection.execute(
                "SELECT COUNT(*) n FROM duplicate_groups").fetchone()["n"]
            human = connection.execute(
                "SELECT COUNT(*) n FROM labels WHERE source='human'").fetchone()["n"]
        print(json.dumps({
            "asset_types": types, "total_labels": labels,
            "human_labels": human, "duplicate_groups": dup_groups,
        }, ensure_ascii=False, indent=2))
        return 0
    if args.labels:
        from treecut.library.classification_store import ClassificationStore
        cls = ClassificationStore()
        labels = cls.list_labels(asset_id=args.labels)
        print(json.dumps(labels, ensure_ascii=False, indent=2))
        return 0
    if args.add_label:
        asset_id, category, label = args.add_label
        from treecut.library.classification_store import ClassificationStore
        cls = ClassificationStore()
        cls.save_human_label(asset_id, label, category=category)
        print(json.dumps({"added": {"asset_id": asset_id, "category": category,
                                     "label": label, "source": "human"}},
                         ensure_ascii=False, indent=2))
        return 0
    if args.embed is not None:
        from treecut.analysis.embedding_worker import EmbeddingWorker
        worker = EmbeddingWorker()
        result = worker.run(limit=args.embed)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.embed_status:
        from treecut.search.embedding import EmbeddingIndexer
        idx = EmbeddingIndexer()
        print(json.dumps(idx.stats(), ensure_ascii=False, indent=2))
        return 0
    if args.index_text:
        from treecut.search.hybrid import HybridSearch
        hs = HybridSearch()
        n = hs.index_texts()
        print(json.dumps({"fts_indexed": n}, ensure_ascii=False, indent=2))
        return 0
    if args.search:
        from treecut.search.hybrid import HybridSearch
        hs = HybridSearch()
        result = hs.search(args.search, top_k=args.search_topk)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.template_register:
        from treecut.templates import list_templates
        from treecut.templates.engine import TemplateEngine
        engine = TemplateEngine()
        for t in list_templates():
            engine.register_template(t)
        print(json.dumps({"registered": engine.list_registered()},
                         ensure_ascii=False, indent=2))
        return 0
    if args.template_list:
        from treecut.templates.engine import TemplateEngine
        engine = TemplateEngine()
        print(json.dumps(engine.list_registered(), ensure_ascii=False, indent=2))
        return 0
    if args.template_recommend:
        tid, version, slot = args.template_recommend
        from treecut.templates.engine import TemplateEngine
        engine = TemplateEngine()
        candidates = engine.recommend_slot(tid, version, int(slot), top_k=10)
        print(json.dumps([c.to_dict() for c in candidates], ensure_ascii=False, indent=2))
        return 0
    if args.template_select:
        project, tid, slot, segment, status = args.template_select
        from treecut.templates.engine import TemplateEngine
        engine = TemplateEngine()
        engine.save_selection(project, tid, "1.0", int(slot), segment, status)
        print(json.dumps({"saved": {"project": project, "slot": int(slot),
                                    "segment": segment, "status": status}},
                         ensure_ascii=False, indent=2))
        return 0
    if args.advise_sort:
        from treecut.roughcut import SortAdvisor
        advisor = SortAdvisor()
        suggestion = advisor.advise(args.advise_sort)
        print(json.dumps(suggestion.to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.roughcut:
        project, out_dir = args.roughcut
        from treecut.roughcut import RoughCutEngine
        engine = RoughCutEngine()
        result = engine.build(project, out_dir)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
