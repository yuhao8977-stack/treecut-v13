# treecut auto material scan - self running, resumable (v2)
import os, sys, time, traceback
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "src"))
os.environ.setdefault("TREECUT_DATA_ROOT", os.path.join(BASE, "runtime_data"))
from treecut.bootstrap import bootstrap
from treecut.library import Catalog
from treecut.analysis.pool import AnalysisPool
from treecut.analysis.parallel import suggest_workers

LOG = os.path.join(BASE, "runtime_data", "logs", "auto_scan.log")
def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("%s | %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass

def main():
    log("AUTO_SCAN start")
    context = bootstrap()
    catalog = Catalog(context.paths.databases / "materials.db")
    sources_file = os.path.join(BASE, "scan_sources.txt")
    sources = []
    if os.path.isfile(sources_file):
        with open(sources_file, encoding="utf-8") as f:
            sources = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    log("AUTO_SCAN sources=" + repr(sources))
    from treecut.config.settings import save_settings
    for source in sources:
        if not os.path.isdir(source):
            log("skip missing source: " + source)
            continue
        if source not in context.settings.material_sources:
            context.settings.material_sources.append(source)
    save_settings(context.settings, context.paths)
    for source in sources:
        if not os.path.isdir(source):
            continue
        try:
            started = time.time()
            result = catalog.scan(source)
            log("scan %s -> total=%d added=%d changed=%d errors=%d (%.1fs)"
                % (source, result.total, result.added, result.changed, result.errors, time.time() - started))
        except Exception as e:
            log("scan error %s: %s" % (source, e))
    workers = suggest_workers(context.settings.analysis_workers, context.capabilities.ram_gb)
    log("analysis workers=" + str(workers))
    pool = AnalysisPool(catalog.db_path, workers=workers)
    try:
        while True:
            remaining = len(catalog.pending_jobs(limit=1))
            if remaining == 0:
                break
            run = pool.run_batch(min(workers * 3, remaining), progress=lambda text, pct=None: log(text))
            log("batch done: ok=%d retry=%d failed=%d claimed=%d"
                % (run.succeeded, run.retried, run.failed, run.claimed))
            if run.claimed == 0:
                break
    finally:
        pool.close()
    log("AUTO_SCAN finished")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        try:
            with open(LOG, "a", encoding="utf-8") as f:
                f.write("FATAL: %s\n" % traceback.format_exc())
        except Exception:
            pass
        raise SystemExit(1)
