"""Verify every immutable release file against the generated SHA-256 manifest."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from generate_release_metadata import immutable_files, sha256


def verify(root: Path) -> list[str]:
    manifest_path = root / "release" / "release_manifest.json"
    if not manifest_path.is_file():
        return ["missing release/release_manifest.json"]
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {item["path"]: item for item in data.get("files") or []}
    actual = {relative.as_posix(): path for path, relative in immutable_files(root)}
    errors = []
    for name in sorted(set(expected) - set(actual)):
        errors.append(f"missing: {name}")
    for name in sorted(set(actual) - set(expected)):
        errors.append(f"unexpected: {name}")
    common = sorted(set(expected) & set(actual))
    for index, name in enumerate(common, 1):
        item, path = expected[name], actual[name]
        size = path.stat().st_size
        if size != item["bytes"]:
            errors.append(f"size mismatch: {name}")
        elif sha256(path) != item["sha256"]:
            errors.append(f"sha256 mismatch: {name}")
        if index % 100 == 0 or item["bytes"] >= 100_000_000 or index == len(common):
            print(f"Verified {index}/{len(common)}: {name}", flush=True)
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors = verify(args.root.resolve())
    if errors:
        print("\n".join(errors))
        raise SystemExit(1)
    print("Release manifest verification passed.")


if __name__ == "__main__":
    main()
