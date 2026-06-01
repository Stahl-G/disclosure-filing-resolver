"""Manifest writer for filing packages."""

from __future__ import annotations

import json
from pathlib import Path

from disclosure_filing_resolver.models import FilingPackage


def write_manifest(package: FilingPackage, out_dir: str) -> Path:
    """Write manifest.json to the output directory.

    Returns the path to the manifest file.
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    manifest_path = out_path / "manifest.json"

    manifest_data = package.model_dump()
    manifest_path.write_text(
        json.dumps(manifest_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest_path


def read_manifest(manifest_path: str | Path) -> FilingPackage:
    """Read a manifest.json file and return a FilingPackage."""
    path = Path(manifest_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    return FilingPackage(**data)
