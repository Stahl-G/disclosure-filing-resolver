"""Manifest writer for filing packages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Union

from disclosure_filing_resolver.models import EvidencePackage, FilingPackage


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


def read_manifest(manifest_path: Union[str, Path]) -> FilingPackage:
    """Read a manifest.json file and return a FilingPackage."""
    path = Path(manifest_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    return FilingPackage(**data)


def write_evidence_manifest(package: EvidencePackage, out_dir: str) -> Path:
    """Write a generic EvidencePackage manifest.json to the output directory."""
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    manifest_path = out_path / "manifest.json"

    manifest_data = package.model_dump()
    manifest_path.write_text(
        json.dumps(manifest_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest_path


def evidence_to_sources(package: EvidencePackage) -> List[Dict[str, Any]]:
    """Convert an EvidencePackage into a list of source objects.

    Each artifact in the package becomes one source entry, enriched with
    disclosure and entity metadata.  The resulting list is consumable by
    multi-agent-brief-workflow as ``sources.json``.
    """
    sources: List[Dict[str, Any]] = []
    entity_name = package.entity.legal_name

    # Build a lookup from disclosure identifiers to disclosure records
    disclosure_by_id: Dict[str, Any] = {}
    for disc in package.disclosures:
        key = disc.identifiers.get("accession_number", "")
        if key:
            disclosure_by_id[key] = disc

    for artifact in package.artifacts:
        # Try to find the parent disclosure via artifact raw data
        accession = artifact.raw.get("accession_number", "")
        disclosure = disclosure_by_id.get(accession)

        filing_date = ""
        form = ""
        if disclosure:
            filing_date = disclosure.filing_date
            form = disclosure.form

        # Also check artifact-level raw data
        if not filing_date:
            filing_date = artifact.raw.get("filing_date", "")
        if not form:
            form = artifact.raw.get("form", "")

        # Build source title
        parts = [entity_name]
        if form:
            parts.append(form)
        if artifact.role and artifact.role not in ("unknown", "cover"):
            parts.append(artifact.role.replace("_", " "))
        title = " — ".join(parts)

        source: Dict[str, Any] = {
            "title": title,
            "url": artifact.source_url,
            "source_type": "filing",
            "date": filing_date,
            "provider": artifact.provider or "sec_edgar",
            "metadata": {
                "form": form,
                "role": artifact.role,
                "document_type": artifact.document_type,
                "filename": artifact.filename,
                "file_format": artifact.file_format,
                "confidence": artifact.confidence,
            },
        }

        # Include text content if available
        if artifact.content_text:
            source["content"] = artifact.content_text

        # Include local path if downloaded
        if artifact.local_path:
            source["local_path"] = artifact.local_path

        sources.append(source)

    # If no artifacts, create a source from the disclosure itself
    if not sources and package.disclosures:
        for disc in package.disclosures:
            source = {
                "title": f"{entity_name} — {disc.form} filing",
                "url": disc.source_url,
                "source_type": "filing",
                "date": disc.filing_date,
                "provider": disc.provider or "sec_edgar",
                "metadata": {
                    "form": disc.form,
                    "disclosure_type": disc.disclosure_type,
                },
            }
            sources.append(source)

    return sources


def write_sources_json(package: EvidencePackage, out_dir: str) -> Path:
    """Write sources.json to the output directory.

    Returns the path to the sources file.
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    sources_path = out_path / "sources.json"

    sources = evidence_to_sources(package)
    sources_path.write_text(
        json.dumps(sources, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return sources_path
