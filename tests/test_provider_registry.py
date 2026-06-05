"""Tests for provider registry and SEC EDGAR adapters."""

from unittest.mock import MagicMock, patch

import pytest

from disclosure_filing_resolver.models import (
    Artifact,
    DisclosureRecord,
    DisclosureRequest,
    EntityIdentity,
    EntityQuery,
    FilingCandidate,
    FilingDocument,
)
from disclosure_filing_resolver.providers.base import (
    DisclosureProvider,
    EnrichmentProvider,
    IdentityProvider,
)
from disclosure_filing_resolver.providers.registry import ProviderRegistry
from disclosure_filing_resolver.providers.sec_edgar.provider import (
    SECEdgarDisclosureProvider,
    SECEdgarIdentityProvider,
)


class DummyIdentityProvider(IdentityProvider):
    def resolve(self, query):
        return []


class DummyDisclosureProvider(DisclosureProvider):
    def list_disclosures(self, entity, request):
        return []

    def fetch_artifacts(self, disclosure, request):
        return []


class DummyEnrichmentProvider(EnrichmentProvider):
    def enrich(self, entity, disclosure, request):
        return []


def _make_entity() -> EntityIdentity:
    return EntityIdentity(
        legal_name="TOYO Co., Ltd",
        identifiers={
            "ticker": "TOYO",
            "cik": "1985273",
            "cik10": "0001985273",
        },
        provider="sec_edgar",
    )


def test_provider_registry_registers_and_lists_providers():
    registry = ProviderRegistry()
    identity = DummyIdentityProvider()
    disclosure = DummyDisclosureProvider()
    enrichment = DummyEnrichmentProvider()

    registry.register_identity("dummy_identity", identity)
    registry.register_disclosure("dummy_disclosure", disclosure)
    registry.register_enrichment("dummy_enrichment", enrichment)

    assert registry.get_identity("dummy_identity") is identity
    assert registry.get_disclosure("dummy_disclosure") is disclosure
    assert registry.get_enrichment("dummy_enrichment") is enrichment
    assert registry.list_providers() == {
        "identity": ["dummy_identity"],
        "disclosure": ["dummy_disclosure"],
        "enrichment": ["dummy_enrichment"],
    }


def test_provider_registry_unknown_provider_raises_key_error():
    registry = ProviderRegistry()

    with pytest.raises(KeyError, match="Identity provider not registered"):
        registry.get_identity("missing")


@patch("disclosure_filing_resolver.providers.sec_edgar.provider.TickerResolver")
@patch("disclosure_filing_resolver.providers.sec_edgar.provider.SECEdgarClient")
def test_sec_edgar_identity_provider_resolves_entity(mock_client, mock_resolver):
    resolver = mock_resolver.return_value
    resolver.resolve.return_value = MagicMock(
        to_entity_identity=MagicMock(return_value=_make_entity())
    )

    provider = SECEdgarIdentityProvider()
    results = provider.resolve(EntityQuery(ticker="TOYO"))

    assert len(results) == 1
    assert results[0].identifiers["ticker"] == "TOYO"
    resolver.resolve.assert_called_once()
    mock_client.return_value.close.return_value = None
    provider.close()


@patch("disclosure_filing_resolver.providers.sec_edgar.provider.SECEdgarProvider")
def test_sec_edgar_disclosure_provider_lists_disclosures(mock_legacy_provider):
    legacy = mock_legacy_provider.return_value
    legacy.select_filing.return_value = FilingCandidate(
        form="6-K",
        filing_date="2026-05-18",
        accession_number="0001213900-26-058577",
        primary_document="ea0290593-6k_toyo.htm",
        primary_url="https://example.com/primary.htm",
        index_url="https://example.com/index.html",
    )

    entity = _make_entity()
    request = DisclosureRequest(entity=entity, intent="quarterly", download=False)
    provider = SECEdgarDisclosureProvider()
    disclosures = provider.list_disclosures(entity, request)

    assert len(disclosures) == 1
    assert disclosures[0].form == "6-K"
    assert disclosures[0].raw["filing_candidate"]["form"] == "6-K"
    legacy.select_filing.assert_called_once()


@patch("disclosure_filing_resolver.providers.sec_edgar.provider.SECEdgarProvider")
def test_sec_edgar_disclosure_provider_fetches_artifacts(mock_legacy_provider):
    legacy = mock_legacy_provider.return_value
    legacy.get_documents.return_value = [
        FilingDocument(
            role="cover",
            filename="ea0290593-6k_toyo.htm",
            sec_url="https://example.com/primary.htm",
        )
    ]

    entity = _make_entity()
    request = DisclosureRequest(entity=entity, intent="quarterly", download=False)
    disclosure = DisclosureRecord(
        form="6-K",
        filing_date="2026-05-18",
        source_url="https://example.com/primary.htm",
        index_url="https://example.com/index.html",
        identifiers={
            "accession_number": "0001213900-26-058577",
            "primary_document": "ea0290593-6k_toyo.htm",
        },
    )

    provider = SECEdgarDisclosureProvider()
    artifacts = provider.fetch_artifacts(disclosure, request)

    assert artifacts == [
        Artifact(
            role="cover",
            filename="ea0290593-6k_toyo.htm",
            source_url="https://example.com/primary.htm",
            download_status="skipped",
            provider="sec_edgar",
        )
    ]
    legacy.get_documents.assert_called_once()
    legacy.download_documents.assert_not_called()
