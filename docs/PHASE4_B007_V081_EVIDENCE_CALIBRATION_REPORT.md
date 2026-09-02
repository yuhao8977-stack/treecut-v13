# Phase4 — B007 V0.8.1 Evidence Quality Calibration Report

Status: **B007_V081_REVIEW_READY_WITH_LIMITATIONS** | 2026-09-02 11:03:52

## Answers

- **1_why_248_vs_299**: {"excluded_file": "tests/test_xhs_work_browser_v01.py", "excluded_test_count": 51, "arithmetic": "248 + 51 = 299 (2 skipped included in both)", "reason_excluded": "browser E2E suite (Edge profile / live browser), not applicable to unattended pipeline scope", "missing_or_regression": false}
- **2_full_regression**: "PASS (299 passed, 2 skipped)"
- **3_asr_20_20_or_19_20**: "ASR_EXECUTED=20/20; HAS_SPEECH=19/20"
- **4_has_speech_vs_success**: "ASR_EXECUTED=有转写结果; TRANSCRIPT_PRESENT=文本存在; HAS_SPEECH=文本≥10字; has_speech=False ≠ ASR_FAILED"
- **5_clip_known_ratio**: 0.182
- **6_qwen_known_coverage**: {"ok_segments": 40, "of": 40, "known_field_ratio": "computed per-field (see candidates JSON)"}
- **7_visual_agreement**: "CLIP vs Qwen scene agreement computed in candidates (fields.scene)"
- **8_conflict_rate**: "see candidates JSON (source=UNKNOWN vs value conflicts)"
- **9_calibration_covers_all_20**: true
- **10_a_f_covered**: ["A_CREATOR_HIGH_NO_PAID_ASSOC_OBSERVED", "B_CREATOR_MID_LOW_NO_PAID_ASSOC_OBSERVED", "C_PAID_HIGH_EFFICIENCY_CANDIDATE", "D_PAID_HIGH_INPUT_WEAK_OUTCOME", "E_CROSS_SOURCE_CONTRAST", "F_PAID_ASSOCIATED_NO_NOTE_METRIC"]
- **11_opening_20**: 20
- **12_high_info_20**: 20
- **13_fields_mainly_unknown**: "see Qwen candidates (UNKNOWN-heavy fields reported)"
- **14_evidence_improved_fields**: "see DNA_ENRICHMENT_CANDIDATE (Qwen second source)"
- **15_structural_trivial_count**: 3
- **16_business_interesting_count**: 7
- **17_insufficient_evidence_count**: 2
- **18_auto_l3_written**: "NO"
- **19_performance_in_cognition**: "NO (creator/paid 数据未喂给 Qwen；stratum 仅作分析元数据)"
- **20_ready_for_human_l3**: true

## Evidence-type candidates (sample-level co-occurrence)

- opening_product_visible: ['SA-66f672d6', 'SB-63c5675a', 'SB-66d7c509', 'SD-66de90b3', 'SD-670630e9', 'SD-64db4e87', 'SE-64336391', 'SE-6718abc7', 'SF-640dc105']
- opening_function_demo: ['SA-66f672d6', 'SB-63c5675a', 'SD-670630e9', 'SD-64db4e87']
- opening_human: ['SA-64e42823', 'SA-66f672d6', 'SB-682edce4', 'SB-66d7c509', 'SD-66de90b3', 'SD-670630e9', 'SE-64336391', 'SE-6718abc7', 'SF-640dc105']
- storage_evidence: ['SC-63c8d157', 'SD-69367987']
- power_evidence: []
- flexible_capacity_evidence: ['SC-63c8d157', 'SD-69367987']
- dining_context_evidence: ['SE-66ebc041']
- detail_shot: []

## Pattern quality audit counts

- STRUCTURAL_TRIVIAL: 3 | BUSINESS_INTERESTING: 7 | INSUFFICIENT_VISUAL_EVIDENCE: 2 | NEEDS_HUMAN_VALIDATION: 0

## STOP

Auto calibration complete; NO L3 written; NO V0.9 entered. Human reviews the 40-segment package next.
