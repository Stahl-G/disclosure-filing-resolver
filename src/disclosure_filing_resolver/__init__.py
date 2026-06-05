"""Disclosure Filing Resolver - Deterministic SEC filing acquisition for AI agent workflows."""

from disclosure_filing_resolver.manifest import (
    evidence_to_sources,
    write_evidence_manifest,
    write_sources_json,
)
from disclosure_filing_resolver.models import (
    Artifact,
    CompanyIdentity,
    DisclosureRecord,
    DisclosureRequest,
    EntityIdentity,
    EntityQuery,
    EvidencePackage,
    FilingCandidate,
    FilingDocument,
    FilingPackage,
    Observation,
    ResolveRequest,
)
from disclosure_filing_resolver.providers.registry import ProviderRegistry
from disclosure_filing_resolver.resolver import (
    create_default_registry,
    resolve_disclosure,
    resolve_filing_package,
)

__all__ = [
    "Artifact",
    "CompanyIdentity",
    "DisclosureRecord",
    "DisclosureRequest",
    "EntityIdentity",
    "EntityQuery",
    "EvidencePackage",
    "FilingCandidate",
    "FilingDocument",
    "FilingPackage",
    "Observation",
    "ProviderRegistry",
    "ResolveRequest",
    "create_default_registry",
    "evidence_to_sources",
    "resolve_disclosure",
    "resolve_filing_package",
    "write_evidence_manifest",
    "write_sources_json",
]

__version__ = "0.3.0"
