"""Persistent material catalog."""

from .catalog import Catalog, ScanResult
from .classification import PreliminaryCategory, classify_filename
from .assets import AssetRecord, AssetsManager
from .hash_utils import full_sha256, quick_fingerprint, verify_sha256
from .migrate_v12 import MigrationResult, V12Migrator
from .probe_worker import ProbeRunResult, ProbeWorker

__all__ = [
    "Catalog", "ScanResult", "PreliminaryCategory", "classify_filename",
    "AssetRecord", "AssetsManager",
    "full_sha256", "quick_fingerprint", "verify_sha256",
    "MigrationResult", "V12Migrator",
    "ProbeRunResult", "ProbeWorker",
]
