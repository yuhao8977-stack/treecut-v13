# -*- coding: utf-8 -*-
"""V2 引擎→现有服务 映射审计与状态记录(附录 §12)。"""
import json, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")
import treecut.services.visual_understanding_v2 as V2
mapping = {
    "TemporalActionValidator": "src/treecut/services/action_subclip.py(apply_action_gate+R2 门; build_windows 状态转移)",
    "IslandClaimLibrary": "src/treecut/services/claim_visual.py(原子主张/类型) + visual_beat.py(领域合同)",
    "DomainVisualCritic": "src/treecut/services/claim_visual.py(ClaimVisualMatcher 硬闸: 资格/对象/动作/反向/禁止视觉/故事/重复)",
    "VisualBeatGrouper": "src/treecut/services/visual_beat.py(group_visual_beats R4: 16→4-5 视觉 Beat 保留 Atomic Claims)",
    "NoCandidateResolver": "src/treecut/services/visual_beat.py(audit_action_availability + suggest_script_fix R5: SEARCH_MORE→REWRITE→DROP/BLOCK)",
    "DuplicateCritic": "src/treecut/services/production_dedup.py(R7: 叙事近重 WARNING+贡献; P0 仅硬重复) + production_qa.check_dedup",
    "ExampleAdjudicationMemory": "reports/storage/TREECUT_REVIEW_EXAMPLE_MEMORY_V1.json(窗口级负例记忆, review_scope=SUBCLIP_WINDOW)"}
kb = json.loads((OUT / "TREECUT_VISUAL_SEMANTIC_KB_V1.json").read_text(encoding="utf-8"))
mem = json.loads((OUT / "TREECUT_REVIEW_EXAMPLE_MEMORY_V1.json").read_text(encoding="utf-8"))
f = OUT / "TREECUT_PROJECT_STATE_V1.json"
d = json.load(open(f, encoding="utf-8-sig"))
d["v2_integration"] = {"engine_module": "src/treecut/services/visual_understanding_v2.py",
                       "engine_tests": "tests/test_treecut_visual_understanding_engine_v2.py (10/10)",
                       "mapping": mapping,
                       "kb_loaded": bool(kb),
                       "negative_memory_window_scoped": True,
                       "negative_memory_entries": len(mem.get("memory", [])),
                       "supports_by_segment": len(mem.get("supports_by_segment", {})),
                       "blacklist_corrected": "whole-asset EXCLUDE → 窗口级负例记忆(素材可跨动作/窗口复用, 如1985仍可TRACK_SOCKET)",
                       "expanded_retrieval": "RUNNING(_g2_expand_results.json)",
                       "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("state v2_integration recorded; memory entries:", len(mem.get("memory", [])),
      "| supports:", len(mem.get("supports_by_segment", {})))
