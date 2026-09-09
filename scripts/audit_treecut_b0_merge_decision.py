# -*- coding: utf-8 -*-
"""TREECUT B0 — merge decision evidence for the 4 E-vs-HEAD differing files.

Direction finding (machine): the E install is an OLDER deployment snapshot, not a
deliberately pruned build of HEAD:
  * E src/treecut/library/ contains only catalog.py + classification.py +
    __init__.py(6 lines); HEAD also has assets/migrate/probe modules + 27-line
    __init__ (research features added after the E snapshot was built).
  * E src/treecut has NO services/ package; HEAD desktop.py imports
    treecut.services.review_center lazily (review-center entry added after E).
  * E desktop.py removed the review-center method/button that HEAD has.
  * E main.py (74 lines) lacks the research CLI flags HEAD has.
  * 85/101 E .py are byte-equal to HEAD (production chain included) => the E
    snapshot was built from an earlier HEAD whose production chain already
    matched today's HEAD.

MERGE DECISION (per file):
  config/settings.py   -> keep HEAD (adds asr_device field + validation with
                          default 'auto'; no E module reads it; harmless, keeps
                          repo research consumers intact)
  desktop.py           -> keep HEAD (adds review-center entry; lazy import of
                          treecut.services.review_center; deps live in repo tree
                          and will be synced to E)
  library/__init__.py  -> keep HEAD (superset exports; submodules live in repo
                          tree and will be synced to E)
  main.py              -> keep HEAD (superset CLI; research flags remain
                          available; runtime entry unchanged)
E-install sync: full-tree copy of repo src/treecut -> E src/treecut (excluding
__pycache__) so E_INSTALL_EQ_HEAD holds and every import resolves on E.
Risk control: production behavior is unchanged (85 files already byte-equal);
post-sync verified by compileall + provenance rerun (expect E_CONTENT_EQ_HEAD
for every file) + import/path/TTS smokes (later phases).
"""
import json
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")

decision = {
    "experiment": "TREECUT_B0_SOURCE_TRUTH_MERGE_DECISION",
    "finding": "E install is an OLDER deployment snapshot of repo HEAD "
               "(missing services/, library assets/migrate modules, review-center "
               "desktop entry, research CLI flags); production chain 85/101 files "
               "byte-equal to HEAD.",
    "merge_rule": "keep HEAD content for all 4 differing files (newer, "
                  "self-consistent superset) + full-tree sync repo src/treecut -> "
                  "E src/treecut; production behavior preserved (85 files equal); "
                  "no direct E overwrite of HEAD features.",
    "per_file": [
        {"file": "src/treecut/config/settings.py", "decision": "keep HEAD",
         "reason": "HEAD adds asr_device='auto' field+validation; E has no reader; "
                   "keeps repo research consumers intact"},
        {"file": "src/treecut/desktop.py", "decision": "keep HEAD",
         "reason": "HEAD adds lazy review-center entry (imports "
                   "treecut.services.review_center only on click); deps synced to E"},
        {"file": "src/treecut/library/__init__.py", "decision": "keep HEAD",
         "reason": "HEAD superset exports match repo submodules; E snapshot predates "
                   "them; synced to E makes imports resolve"},
        {"file": "src/treecut/main.py", "decision": "keep HEAD",
         "reason": "HEAD superset CLI; runtime entry unchanged; research flags kept"},
    ],
    "e_install_evidence": {
        "e_library_modules": ["catalog.py", "classification.py", "__init__.py"],
        "e_has_services_pkg": False,
        "e_has_scheduler": True,
        "head_desktop_lazy_import": "treecut.services.review_center (inside "
                                    "_open_review_center)",
        "equal_production_files": "85/101 E .py byte-equal to HEAD "
                                  "(SOURCE_PROVENANCE E_CONTENT_EQ_HEAD)"},
}
(OUT / "TREECUT_B0_SOURCE_TRUTH_MERGE_DECISION.json").write_text(
    json.dumps(decision, ensure_ascii=False, indent=1), encoding="utf-8")
print("merge decision written")
