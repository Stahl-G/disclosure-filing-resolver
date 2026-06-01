"""Disclosure Filing Resolver - Deterministic SEC filing acquisition for AI agent workflows."""

from disclosure_filing_resolver.models import (
    CompanyIdentity,
    FilingCandidate,
    FilingDocument,
    FilingPackage,
    ResolveRequest,
)
from disclosure_filing_resolver.resolver import resolve_filing_package

__all__ = [
    "CompanyIdentity",
    "FilingCandidate",
    "FilingDocument",
    "FilingPackage",
    "ResolveRequest",
    "resolve_filing_package",
]

__version__ = "0.2.0"
