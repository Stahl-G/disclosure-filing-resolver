"""Base class for filing providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from disclosure_filing_resolver.models import (
    Artifact,
    CompanyIdentity,
    DisclosureRecord,
    DisclosureRequest,
    EntityIdentity,
    EntityQuery,
    FilingCandidate,
    FilingDocument,
    Observation,
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
    ) -> List[FilingDocument]:
        """Get documents for the selected filing, including exhibits."""

    @abstractmethod
    def download_documents(
        self,
        documents: List[FilingDocument],
        out_dir: str,
        filing: FilingCandidate,
        company: CompanyIdentity,
    ) -> List[FilingDocument]:
        """Download documents to local filesystem."""


class IdentityProvider(ABC):
    """Abstract base for entity identity providers."""

    @abstractmethod
    def resolve(self, query: EntityQuery) -> List[EntityIdentity]:
        """Resolve an entity query into one or more entity identities."""


class DisclosureProvider(ABC):
    """Abstract base for disclosure providers."""

    @abstractmethod
    def list_disclosures(
        self, entity: EntityIdentity, request: DisclosureRequest
    ) -> List[DisclosureRecord]:
        """List disclosures matching a generic disclosure request."""

    @abstractmethod
    def fetch_artifacts(
        self, disclosure: DisclosureRecord, request: DisclosureRequest
    ) -> List[Artifact]:
        """Fetch artifacts for a disclosure."""


class EnrichmentProvider(ABC):
    """Abstract base for optional enrichment providers."""

    @abstractmethod
    def enrich(
        self,
        entity: EntityIdentity,
        disclosure: Optional[DisclosureRecord],
        request: DisclosureRequest,
    ) -> List[Observation]:
        """Return enriched observations for an entity or disclosure."""
