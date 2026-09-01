# OVERNIGHT B007 V0.7 + CONDITIONAL V0.8 EXECUTION SUMMARY

```json
{
  "title": "OVERNIGHT B007 V0.7 + CONDITIONAL V0.8 EXECUTION SUMMARY",
  "generated_at": "2026-09-01 21:24:47",
  "v07_final_status": "B007_V07_PASS_WITH_LIMITATIONS",
  "v08_started": true,
  "v08_final_status": "B007_V08_DNA_EVIDENCE_PASS_WITH_LIMITATIONS",
  "media": {
    "target": 20,
    "media_references": 20,
    "asset_count": 20,
    "asset_reuse_new": {
      "new": 20,
      "reuse": 0
    },
    "segment_count": 374,
    "segments_per_asset": 18.7,
    "timeline_coverage": 1.0
  },
  "coverage": {
    "asr_notes": 20,
    "asr_utterances": 536,
    "asr_chars": 4806,
    "ocr_items": 1990,
    "visual_frames": 373,
    "visual_known_ratio": 0.182,
    "cognition_segments": 374,
    "claim_status_distribution": {
      "UNKNOWN": 3728,
      "SUPPORTED": 12
    },
    "unknown_ratio": 0.997,
    "dna_records": 20,
    "dna_patterns": 12,
    "dna_counterexamples": 83
  },
  "exceptions": [],
  "quarantine": [],
  "tests": {
    "pytest": "248 passed, 2 skipped"
  },
  "db_integrity": {
    "media_vs_registry": true,
    "segment_within_duration": true,
    "keyframe_paths_exist": true,
    "claims_json_valid": true,
    "asr_segment_consistent": true
  },
  "storage": {
    "c_free_gb": 67.4,
    "e_free_gb": 155.1,
    "z_ok": true,
    "z_media_files": 20
  },
  "commits": {
    "v07": "d5d70ec",
    "v08": "(see git log)"
  },
  "next_step": "V0.7 PASS_WITH_LIMITATIONS + V0.8 DNA EVIDENCE PASS_WITH_LIMITATIONS; STOP per ABSOLUTE STOP rule (no V0.9/Template/AutoCut/Production). Review OVERNIGHT summary + DNA human review report before any next phase.",
  "abslute_stop": "No V0.9 / template / AutoCut / production / auto-publish entered."
}
```
