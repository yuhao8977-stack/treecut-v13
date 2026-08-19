"""Canary marker: detects any external restore that overwrites the source tree.

If this file or the CANARY value changes unexpectedly, the src directory was
restored from a stale copy and the code review fixes need re-application.
"""

CANARY = "treecut-review-fix-round-2026-08-06-19:38"
