"""Base class for filing providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from disclosure_filing_resolver.models import (
    CompanyIdentity,
    FilingCandidate,
    FilingDocument,
    ResolveRequest,
)


class FilingProvider(ABC):
    """Abstract base for filing acquisition providers."""

    @abstractmethod
    def resolve_company(self, request: ResolveRequest) -> CompanyIdentity:
        """Resolve company identity from request."""

    @abstractmethod
    def select_filing(
        self, company: CompanyIdentity, request: ResolveRequest
    ) -> FilingCandidate:
        """Select the best filing for the given intent."""

    @abstractmethod
    def get_documents(
        self,
        company: CompanyIdentity,
        filing: FilingCandidate,
        request: ResolveRequest,
    ) -> list[FilingDocument]:
        """Get documents for the selected filing, including exhibits."""

    @abstractmethod
    def download_documents(
        self, documents: list[FilingDocument], out_dir: str
    ) -> list[FilingDocument]:
        """Download documents to local filesystem."""
