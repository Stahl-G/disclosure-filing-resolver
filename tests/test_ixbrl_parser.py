"""Tests for iXBRL parser."""

from __future__ import annotations

from disclosure_filing_resolver.providers.sec_edgar.ixbrl_parser import (
    _parse_numeric_value,
    extract_ixbrl_facts,
    extract_key_financials,
)


class TestParseNumericValue:
    def test_simple_integer(self):
        assert _parse_numeric_value("1234") == 1234.0

    def test_negative_with_parens(self):
        assert _parse_numeric_value("(1234)") == -1234.0

    def test_negative_with_minus(self):
        assert _parse_numeric_value("-1234") == -1234.0

    def test_with_commas(self):
        assert _parse_numeric_value("1,234,567") == 1234567.0

    def test_with_currency_symbol(self):
        assert _parse_numeric_value("$1,234") == 1234.0

    def test_decimal(self):
        assert _parse_numeric_value("12.34") == 12.34

    def test_empty_string(self):
        assert _parse_numeric_value("") is None

    def test_none_returns_none(self):
        assert _parse_numeric_value(None) is None

    def test_non_numeric(self):
        assert _parse_numeric_value("abc") is None

    def test_unicode_minus(self):
        assert _parse_numeric_value("−1234") == -1234.0


# Sample iXBRL HTML for testing
SAMPLE_IXBRL_HTML = """
<html>
<head><title>TOYO 6-K</title></head>
<body>
<xbrli:context id="ctx1">
    <xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/cik">1985273</xbrli:identifier></xbrli:entity>
    <xbrli:period>
        <xbrli:startDate>2025-01-01</xbrli:startDate>
        <xbrli:endDate>2025-12-31</xbrli:endDate>
    </xbrli:period>
</xbrli:context>
<xbrli:context id="ctx2">
    <xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/cik">1985273</xbrli:identifier></xbrli:entity>
    <xbrli:period>
        <xbrli:instant>2025-12-31</xbrli:instant>
    </xbrli:period>
</xbrli:context>

<p>Revenue:
<ix:nonFraction name="us-gaap:Revenues" contextRef="ctx1"
  unitRef="USD">150,000,000</ix:nonFraction>
</p>

<p>Net Income:
<ix:nonFraction name="us-gaap:NetIncomeLoss" contextRef="ctx1"
  unitRef="USD">25,000,000</ix:nonFraction>
</p>

<p>Total Assets:
<ix:nonFraction name="us-gaap:Assets" contextRef="ctx2"
  unitRef="USD">500,000,000</ix:nonFraction>
</p>

<p>EPS:
<ix:nonFraction name="us-gaap:EarningsPerShareBasic" contextRef="ctx1"
  unitRef="USD/shares">1.25</ix:nonFraction>
</p>

<p>Company Name:
<ix:nonNumeric name="dei:EntityRegistrantName" contextRef="ctx1">TOYO Co., Ltd</ix:nonNumeric>
</p>

<p>Trading Symbol:
<ix:nonNumeric name="dei:TradingSymbol" contextRef="ctx1">TOYO</ix:nonNumeric>
</p>
</body>
</html>
"""


class TestExtractIXBRLFacts:
    def test_extracts_facts(self):
        facts = extract_ixbrl_facts(SAMPLE_IXBRL_HTML)

        assert len(facts) > 0

    def test_fact_has_name(self):
        facts = extract_ixbrl_facts(SAMPLE_IXBRL_HTML)

        names = {f["name"] for f in facts}
        assert "us-gaap:Revenues" in names

    def test_fact_has_numeric_value(self):
        facts = extract_ixbrl_facts(SAMPLE_IXBRL_HTML)

        revenue = next(f for f in facts if f["name"] == "us-gaap:Revenues")
        assert revenue["value"] == 150000000.0

    def test_fact_has_unit(self):
        facts = extract_ixbrl_facts(SAMPLE_IXBRL_HTML)

        revenue = next(f for f in facts if f["name"] == "us-gaap:Revenues")
        assert revenue["unit"] == "USD"

    def test_fact_has_period(self):
        facts = extract_ixbrl_facts(SAMPLE_IXBRL_HTML)

        revenue = next(f for f in facts if f["name"] == "us-gaap:Revenues")
        assert revenue["period"]["end"] == "2025-12-31"

    def test_non_numeric_facts(self):
        facts = extract_ixbrl_facts(SAMPLE_IXBRL_HTML)

        company = next(f for f in facts if f["name"] == "dei:EntityRegistrantName")
        assert company["text"] == "TOYO Co., Ltd"
        assert company["value"] is None  # non-fraction has no numeric value

    def test_max_facts_limit(self):
        facts = extract_ixbrl_facts(SAMPLE_IXBRL_HTML, max_facts=2)
        assert len(facts) <= 2

    def test_empty_html(self):
        facts = extract_ixbrl_facts("<html><body></body></html>")
        assert facts == []


class TestExtractKeyFinancials:
    def test_extracts_key_facts(self):
        key_facts = extract_key_financials(SAMPLE_IXBRL_HTML)

        assert len(key_facts) > 0

    def test_includes_revenue(self):
        key_facts = extract_key_financials(SAMPLE_IXBRL_HTML)

        names = {f["name"] for f in key_facts}
        assert "us-gaap:Revenues" in names

    def test_includes_entity_name(self):
        key_facts = extract_key_financials(SAMPLE_IXBRL_HTML)

        names = {f["name"] for f in key_facts}
        assert "dei:EntityRegistrantName" in names

    def test_includes_trading_symbol(self):
        key_facts = extract_key_financials(SAMPLE_IXBRL_HTML)

        names = {f["name"] for f in key_facts}
        assert "dei:TradingSymbol" in names

    def test_filters_non_key_facts(self):
        key_facts = extract_key_financials(SAMPLE_IXBRL_HTML)

        # All returned facts should be from our key concepts list
        # iXBRL uses ":" separator, normalize to "/" for checking
        for fact in key_facts:
            name = fact["name"].replace(":", "/")
            is_key = any(
                name.startswith(p)
                for p in [
                    "us-gaap/Revenue",
                    "us-gaap/NetIncomeLoss",
                    "us-gaap/Assets",
                    "us-gaap/EarningsPerShare",
                    "dei/",
                    "ifrs-full/",
                ]
            )
            assert is_key, f"Unexpected fact: {fact['name']}"
