"""P1.1: 增量扫描与文件身份协调（NEW/CHANGED/MOVED/MISSING/UNCHANGED）。"""

from .incremental import IncrementalScanResult, IncrementalScanner

__all__ = ["IncrementalScanResult", "IncrementalScanner"]
