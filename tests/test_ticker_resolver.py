"""Tests for ticker to CIK resolution."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from disclosure_filing_resolver.models import ResolveRequest
from disclosure_filing_resolver.providers.sec_edgar.ticker_resolver import (
    TickerResolver,
    _pad_cik,
    _strip_cik,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _mock_client() -> MagicMock:
    """Create a mock SEC client with fixture data."""
    client = MagicMock()
    client.config.base_url = "https://data.sec.gov"
    tickers_data = json.loads((FIXTURES / "company_tickers_sample.json").read_text())
    client.get_json.return_value = tickers_data
    return client


class TestCIKPadding:
    def test_pad_cik_short(self):
        assert _pad_cik(12345) == "0000012345"

    def test_pad_cik_exact(self):
        assert _pad_cik(1234567890) == "1234567890"

    def test_pad_cik_string(self):
        assert _pad_cik("12345") == "0000012345"

    def test_strip_cik_leading_zeros(self):
        assert _strip_cik("0001985273") == "1985273"

    def test_strip_cik_no_zeros(self):
        assert _strip_cik("1985273") == "1985273"


class TestTickerResolver:
    def test_resolve_by_ticker(self):
        client = _mock_client()
        resolver = TickerResolver(client)
        request = ResolveRequest(ticker="TOYO")
        result = resolver.resolve(request)

        assert result.ticker == "TOYO"
        assert result.cik == "1985273"
        assert result.cik10 == "0001985273"
        assert result.name == "TOYO Co., Ltd"

    def test_resolve_by_ticker_case_insensitive(self):
        client = _mock_client()
        resolver = TickerResolver(client)
        request = ResolveRequest(ticker="tsla")
        result = resolver.resolve(request)

        assert result.ticker == "TSLA"
        assert result.cik == "1318605"
        assert result.name == "Tesla, Inc."

    def test_resolve_by_cik(self):
        client = _mock_client()
        resolver = TickerResolver(client)
        request = ResolveRequest(cik="1985273")
        result = resolver.resolve(request)

        assert result.cik == "1985273"
        assert result.cik10 == "0001985273"

    def test_resolve_by_company_name(self):
        client = _mock_client()
        resolver = TickerResolver(client)
        request = ResolveRequest(company_name="Canadian Solar")
        result = resolver.resolve(request)

        assert result.ticker == "CSIQ"
        assert result.cik == "1823486"

    def test_resolve_not_found(self):
        from disclosure_filing_resolver.exceptions import CompanyNotFoundError

        client = _mock_client()
        resolver = TickerResolver(client)
        request = ResolveRequest(ticker="NONEXISTENT")
        with pytest.raises(CompanyNotFoundError):
            resolver.resolve(request)

    def test_resolve_no_input(self):
        from disclosure_filing_resolver.exceptions import CompanyNotFoundError

        client = _mock_client()
        resolver = TickerResolver(client)
        request = ResolveRequest()
        with pytest.raises(CompanyNotFoundError):
            resolver.resolve(request)
