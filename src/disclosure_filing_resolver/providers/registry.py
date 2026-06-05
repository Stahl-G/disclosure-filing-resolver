"""Provider registry for disclosure resolution providers."""

from __future__ import annotations

from typing import Dict, List

from disclosure_filing_resolver.providers.base import (
    DisclosureProvider,
    EnrichmentProvider,
    IdentityProvider,
)


class ProviderRegistry:
    """Registry of identity, disclosure, and enrichment providers."""

    def __init__(self) -> None:
        self._identity: Dict[str, IdentityProvider] = {}
        self._disclosure: Dict[str, DisclosureProvider] = {}
        self._enrichment: Dict[str, EnrichmentProvider] = {}

    def register_identity(self, name: str, provider: IdentityProvider) -> None:
        """Register an identity provider by name."""
        self._identity[name] = provider

    def register_disclosure(self, name: str, provider: DisclosureProvider) -> None:
        """Register a disclosure provider by name."""
        self._disclosure[name] = provider

    def register_enrichment(self, name: str, provider: EnrichmentProvider) -> None:
        """Register an enrichment provider by name."""
        self._enrichment[name] = provider

    def get_identity(self, name: str) -> IdentityProvider:
        """Get an identity provider by name."""
        try:
            return self._identity[name]
        except KeyError as exc:
            raise KeyError(f"Identity provider not registered: {name}") from exc

    def get_disclosure(self, name: str) -> DisclosureProvider:
        """Get a disclosure provider by name."""
        try:
            return self._disclosure[name]
        except KeyError as exc:
            raise KeyError(f"Disclosure provider not registered: {name}") from exc

    def get_enrichment(self, name: str) -> EnrichmentProvider:
        """Get an enrichment provider by name."""
        try:
            return self._enrichment[name]
        except KeyError as exc:
            raise KeyError(f"Enrichment provider not registered: {name}") from exc

    def list_providers(self) -> Dict[str, List[str]]:
        """List registered providers grouped by provider type."""
        return {
            "identity": sorted(self._identity),
            "disclosure": sorted(self._disclosure),
            "enrichment": sorted(self._enrichment),
        }
