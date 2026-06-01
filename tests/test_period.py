"""Tests for period handling."""

import pytest

from disclosure_filing_resolver.exceptions import UnsupportedPeriodError
from disclosure_filing_resolver.resolver import resolve_filing_package


class TestPeriodValidation:
    def test_resolve_rejects_unsupported_period(self):
        """v0.1.0 only supports period=latest."""
        with pytest.raises(UnsupportedPeriodError) as exc_info:
            resolve_filing_package(ticker="TOYO", period="2026Q1", download=False)
        assert "2026Q1" in str(exc_info.value)
        assert "v0.1.0" in str(exc_info.value)

    def test_resolve_accepts_latest(self):
        """period=latest is accepted (though actual SEC call may fail in test)."""
        # This will fail at the SEC resolution step, not the period check
        with pytest.raises(Exception) as exc_info:
            resolve_filing_package(ticker="NONEXISTENT123", period="latest", download=False)
        # Should NOT be UnsupportedPeriodError
        assert not isinstance(exc_info.value, UnsupportedPeriodError)

    @pytest.mark.parametrize(
        "period",
        ["2026Q1", "2025", "2026-01-15", "Q3", "2025Q4"],
    )
    def test_various_periods_are_rejected(self, period):
        with pytest.raises(UnsupportedPeriodError):
            resolve_filing_package(ticker="TOYO", period=period, download=False)
