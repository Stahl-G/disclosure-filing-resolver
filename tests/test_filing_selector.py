"""Tests for filing selection logic."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from disclosure_filing_resolver.exceptions import FilingNotFoundError
from disclosure_filing_resolver.models import ResolveRequest
from disclosure_filing_resolver.providers.sec_edgar.filing_selector import select_filing

FIXTURES = Path(__file__).parent / "fixtures"


def _mock_client(fixture_name: str) -> MagicMock:
    """Create a mock client returning fixture submissions data."""
    client = MagicMock()
    client.config.base_url = "https://data.sec.gov"
    data = json.loads((FIXTURES / fixture_name).read_text())
    client.get_json.return_value = data
    return client


class TestAnnualSelection:
    def test_tsla_selects_10k(self):
        client = _mock_client("tsla_submissions_sample.json")
        request = ResolveRequest(ticker="TSLA", intent="annual")
        result = select_filing(client, "1318605", "0001318605", request)

        assert result.form == "10-K"
        # filing_date is the SEC filing date (when submitted), not the report date
        assert result.filing_date == "2026-01-25"
        assert "10-K" in result.reasons[0]

    def test_csiq_selects_20f_annual(self):
        """CSIQ is a foreign private issuer; annual intent selects 20-F."""
        client = _mock_client("csiq_submissions_sample.json")
        request = ResolveRequest(ticker="CSIQ", intent="annual")
        result = select_filing(client, "1375877", "0001375877", request)

        assert result.form == "20-F"
        assert result.filing_date == "2025-04-30"


class TestQuarterlySelection:
    def test_tsla_selects_10q(self):
        client = _mock_client("tsla_submissions_sample.json")
        request = ResolveRequest(ticker="TSLA", intent="quarterly")
        result = select_filing(client, "1318605", "0001318605", request)

        assert result.form == "10-Q"
        assert result.filing_date == "2026-04-25"

    def test_toyo_falls_back_to_6k(self):
        client = _mock_client("toyo_submissions_sample.json")
        request = ResolveRequest(ticker="TOYO", intent="quarterly")
        result = select_filing(client, "1985273", "0001985273", request)

        assert result.form == "6-K"
        assert result.filing_date == "2026-05-18"

    def test_csiq_quarterly_selects_6k(self):
        """CSIQ is a foreign private issuer; quarterly intent selects 6-K."""
        client = _mock_client("csiq_submissions_sample.json")
        request = ResolveRequest(ticker="CSIQ", intent="quarterly")
        result = select_filing(client, "1375877", "0001375877", request)

        assert result.form == "6-K"
        assert result.filing_date == "2026-05-14"
        # Should mention foreign private issuer context
        reasons_text = " ".join(result.reasons)
        assert "6-K" in reasons_text or "Foreign" in reasons_text


class TestSemiannualSelection:
    def test_toyo_6k_semiannual(self):
        client = _mock_client("toyo_submissions_sample.json")
        request = ResolveRequest(ticker="TOYO", intent="semiannual")
        result = select_filing(client, "1985273", "0001985273", request)

        assert result.form == "6-K"


class TestSpecificForm:
    def test_specific_form_6k(self):
        client = _mock_client("toyo_submissions_sample.json")
        request = ResolveRequest(ticker="TOYO", intent="specific_form", form_hint="6-K")
        result = select_filing(client, "1985273", "0001985273", request)

        assert result.form == "6-K"
        assert result.filing_date == "2026-05-18"

    def test_specific_form_not_found(self):
        client = _mock_client("toyo_submissions_sample.json")
        request = ResolveRequest(ticker="TOYO", intent="specific_form", form_hint="S-1")
        with pytest.raises(FilingNotFoundError):
            select_filing(client, "1985273", "0001985273", request)


class TestNoFilings:
    def test_empty_submissions_raises(self):
        client = MagicMock()
        client.get_json.return_value = {"filings": {"recent": {}, "files": []}}
        request = ResolveRequest(ticker="EMPTY", intent="quarterly")
        with pytest.raises(FilingNotFoundError):
            select_filing(client, "0000000", "0000000000", request)
