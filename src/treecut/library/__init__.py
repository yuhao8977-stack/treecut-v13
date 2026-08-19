"""Persistent material catalog."""

from .catalog import Catalog, ScanResult
from .classification import PreliminaryCategory, classify_filename
from .assets import AssetRecord, AssetsManager
from .hash_utils import full_sha256, quick_fingerprint, verify_sha256
from .migrate_v12 import MigrationResult, V12Migrator
from .probe_worker import ProbeRunResult, ProbeWorker
from .processing_state import (
    ProcessingState, StageState, STAGES, ALL_STATUSES,
    STATUS_NEW, STATUS_PENDING, STATUS_PROCESSING, STATUS_DONE,
    STATUS_PARTIAL, STATUS_FAILED, STATUS_SKIPPED, STATUS_STALE, STATUS_REVIEW,
)
from .segments import SegmentStore
from .classification_store import ClassificationStore

__all__ = [
    "Catalog", "ScanResult", "PreliminaryCategory", "classify_filename",
    "AssetRecord", "AssetsManager",
    "full_sha256", "quick_fingerprint", "verify_sha256",
    "MigrationResult", "V12Migrator",
    "ProbeRunResult", "ProbeWorker",
    "ProcessingState", "StageState", "STAGES", "ALL_STATUSES",
    "STATUS_NEW", "STATUS_PENDING", "STATUS_PROCESSING", "STATUS_DONE",
    "STATUS_PARTIAL", "STATUS_FAILED", "STATUS_SKIPPED", "STATUS_STALE", "STATUS_REVIEW",
    "SegmentStore", "ClassificationStore",
]
