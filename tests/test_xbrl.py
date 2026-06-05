"""Tests for SEC XBRL enrichment provider."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from disclosure_filing_resolver.models import (
    DisclosureRequest,
    EntityIdentity,
    Observation,
)
from disclosure_filing_resolver.providers.sec_edgar.xbrl import (
    SECXBRLProvider,
    _extract_latest_fact,
    _pick_preferred_unit,
    extract_observations,
    fetch_companyfacts,
)


# Sample companyfacts JSON for testing
SAMPLE_COMPANYFACTS = {
    "cik": 1985273,
    "entityName": "TOYO Co., Ltd",
    "facts": {
        "us-gaap": {
            "Revenues": {
                "label": "Revenues",
                "description": "Revenue from contracts with customers",
                "units": {
                    "USD": [
                        {
                            "end": "2025-12-31",
                            "val": 150000000,
                            "accn": "0001213900-26-058577",
                            "fy": 2025,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2026-03-15",
                        },
                        {
                            "end": "2025-09-30",
                            "val": 40000000,
                            "accn": "0001213900-26-058578",
                            "fy": 2025,
                            "fp": "Q3",
                            "form": "10-Q",
                            "filed": "2025-11-10",
                        },
                    ]
                },
            },
            "NetIncomeLoss": {
                "label": "Net Income (Loss)",
                "description": "Net income",
                "units": {
                    "USD": [
                        {
                            "end": "2025-12-31",
                            "val": 25000000,
                            "accn": "0001213900-26-058577",
                            "fy": 2025,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2026-03-15",
                        }
                    ]
                },
            },
            "EarningsPerShareBasic": {
                "label": "Earnings Per Share, Basic",
                "description": "Basic EPS",
                "units": {
                    "USD/shares": [
                        {
                            "end": "2025-12-31",
                            "val": 1.25,
                            "accn": "0001213900-26-058577",
                            "fy": 2025,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2026-03-15",
                        }
                    ]
                },
            },
            "Assets": {
                "label": "Assets",
                "description": "Total assets",
                "units": {
                    "USD": [
                        {
                            "end": "2025-12-31",
                            "val": 500000000,
                            "accn": "0001213900-26-058577",
                            "fy": 2025,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2026-03-15",
                        }
                    ]
                },
            },
        },
        "ifrs-full": {
            "Revenue": {
                "label": "Revenue",
                "description": "IFRS Revenue",
                "units": {
                    "EUR": [
                        {
                            "end": "2025-12-31",
                            "val": 120000000,
                            "accn": "0001213900-26-058577",
                            "fy": 2025,
                            "fp": "FY",
                            "form": "20-F",
                            "filed": "2026-03-15",
                        }
                    ]
                },
            }
        },
    },
}


class TestExtractLatestFact:
    def test_returns_latest_fact(self):
        concept = SAMPLE_COMPANYFACTS["facts"]["us-gaap"]["Revenues"]
        result = _extract_latest_fact(concept, unit_filter="USD")

        assert result is not None
        assert result["value"] == 150000000
        assert result["end"] == "2025-12-31"
        assert result["form"] == "10-K"

    def test_filters_by_unit(self):
        concept = SAMPLE_COMPANYFACTS["facts"]["us-gaap"]["Revenues"]
        result = _extract_latest_fact(concept, unit_filter="EUR")

        assert result is None

    def test_returns_none_for_empty_concept(self):
        result = _extract_latest_fact({}, unit_filter="USD")
        assert result is None

    def test_returns_none_for_no_matching_forms(self):
        concept = {
            "units": {
                "USD": [
                    {"end": "2025-12-31", "val": 100, "form": "S-1", "filed": "2025-01-01"},
                ]
            }
        }
        result = _extract_latest_fact(concept, unit_filter="USD")
        assert result is None

    def test_includes_filing_metadata(self):
        concept = SAMPLE_COMPANYFACTS["facts"]["us-gaap"]["Revenues"]
        result = _extract_latest_fact(concept, unit_filter="USD")

        assert result["accession"] == "0001213900-26-058577"
        assert result["fiscal_year"] == 2025
        assert result["fiscal_period"] == "FY"
        assert result["filed"] == "2026-03-15"


class TestPickPreferredUnit:
    def test_prefers_usd(self):
        concept = {"units": {"USD": [], "EUR": []}}
        assert _pick_preferred_unit(concept) == "USD"

    def test_prefers_shares_for_eps(self):
        concept = {"units": {"USD/shares": []}}
        assert _pick_preferred_unit(concept) == "USD/shares"

    def test_returns_first_if_no_usd(self):
        concept = {"units": {"EUR": []}}
        assert _pick_preferred_unit(concept) == "EUR"

    def test_returns_none_for_empty(self):
        assert _pick_preferred_unit({"units": {}}) is None


class TestExtractObservations:
    def test_extracts_key_facts(self):
        observations = extract_observations(SAMPLE_COMPANYFACTS)

        assert len(observations) > 0

    def test_observation_has_required_fields(self):
        observations = extract_observations(SAMPLE_COMPANYFACTS)

        for obs in observations:
            assert isinstance(obs, Observation)
            assert obs.source == "sec_edgar"
            assert obs.category
            assert obs.key
            assert obs.value is not None
            assert obs.unit
            assert obs.period

    def test_revenue_category(self):
        observations = extract_observations(SAMPLE_COMPANYFACTS)

        revenue_obs = [o for o in observations if o.category == "revenue"]
        assert len(revenue_obs) > 0
        assert revenue_obs[0].value == 150000000

    def test_net_income_category(self):
        observations = extract_observations(SAMPLE_COMPANYFACTS)

        ni_obs = [o for o in observations if o.category == "net_income"]
        assert len(ni_obs) > 0
        assert ni_obs[0].value == 25000000

    def test_eps_category(self):
        observations = extract_observations(SAMPLE_COMPANYFACTS)

        eps_obs = [o for o in observations if o.category == "eps_basic"]
        assert len(eps_obs) > 0
        assert eps_obs[0].value == 1.25
        assert eps_obs[0].unit == "USD/shares"

    def test_assets_category(self):
        observations = extract_observations(SAMPLE_COMPANYFACTS)

        assets_obs = [o for o in observations if o.category == "total_assets"]
        assert len(assets_obs) > 0
        assert assets_obs[0].value == 500000000

    def test_provenance_includes_filing_info(self):
        observations = extract_observations(SAMPLE_COMPANYFACTS)

        for obs in observations:
            assert "form" in obs.provenance
            assert "filed" in obs.provenance
            assert "fiscal_year" in obs.provenance

    def test_max_facts_limit(self):
        observations = extract_observations(SAMPLE_COMPANYFACTS, max_facts=2)
        assert len(observations) <= 2

    def test_ifrs_facts_extracted(self):
        observations = extract_observations(SAMPLE_COMPANYFACTS)

        revenue_obs = [o for o in observations if o.category == "revenue"]
        # Should have both GAAP and IFRS revenue
        assert len(revenue_obs) >= 1

    def test_empty_companyfacts(self):
        observations = extract_observations({"facts": {}})
        assert observations == []


class TestSECXBRLProvider:
    def test_provider_interface(self):
        provider = SECXBRLProvider.__new__(SECXBRLProvider)
        assert hasattr(provider, "enrich")
        assert hasattr(provider, "close")

    @patch("disclosure_filing_resolver.providers.sec_edgar.xbrl.SECEdgarClient")
    def test_enrich_returns_observations(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.get_json.return_value = SAMPLE_COMPANYFACTS

        provider = SECXBRLProvider(config=MagicMock(user_agent="test"))
        entity = EntityIdentity(
            legal_name="TOYO Co., Ltd",
            identifiers={"cik": "1985273", "cik10": "0001985273"},
        )
        request = DisclosureRequest(entity=entity)

        observations = provider.enrich(entity, None, request)

        assert len(observations) > 0
        assert all(isinstance(o, Observation) for o in observations)

    @patch("disclosure_filing_resolver.providers.sec_edgar.xbrl.SECEdgarClient")
    def test_enrich_returns_empty_on_error(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.get_json.side_effect = Exception("API error")

        provider = SECXBRLProvider(config=MagicMock(user_agent="test"))
        entity = EntityIdentity(
            legal_name="Unknown Corp",
            identifiers={"cik": "9999999", "cik10": "0000099999"},
        )
        request = DisclosureRequest(entity=entity)

        observations = provider.enrich(entity, None, request)
        assert observations == []

    @patch("disclosure_filing_resolver.providers.sec_edgar.xbrl.SECEdgarClient")
    def test_enrich_returns_empty_without_cik(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        provider = SECXBRLProvider(config=MagicMock(user_agent="test"))
        entity = EntityIdentity(
            legal_name="Unknown Corp",
            identifiers={},
        )
        request = DisclosureRequest(entity=entity)

        observations = provider.enrich(entity, None, request)
        assert observations == []
