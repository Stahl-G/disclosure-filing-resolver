"""Tests for SEC archive URL construction."""

from disclosure_filing_resolver.providers.sec_edgar.archive import (
    build_archive_url,
    build_filing_index_url,
    build_primary_url,
    strip_dashes,
    strip_leading_zeros,
)


class TestStripFunctions:
    def test_strip_leading_zeros(self):
        assert strip_leading_zeros("0001985273") == "1985273"

    def test_strip_leading_zeros_no_zeros(self):
        assert strip_leading_zeros("1985273") == "1985273"

    def test_strip_dashes(self):
        assert strip_dashes("0001213900-26-058577") == "000121390026058577"

    def test_strip_dashes_no_dashes(self):
        assert strip_dashes("000121390026058577") == "000121390026058577"


class TestArchiveURLs:
    def test_build_archive_url(self):
        url = build_archive_url("1985273", "0001213900-26-058577", "ea0290593-6k_toyo.htm")
        assert url == (
            "https://www.sec.gov/Archives/edgar/data/1985273/"
            "000121390026058577/ea0290593-6k_toyo.htm"
        )

    def test_build_filing_index_url(self):
        url = build_filing_index_url("1985273", "0001213900-26-058577")
        assert url == (
            "https://www.sec.gov/Archives/edgar/data/1985273/"
            "000121390026058577/000121390026058577-index.html"
        )

    def test_build_primary_url(self):
        url = build_primary_url("1318605", "0001318605-26-000012", "tsla-20260331.htm")
        assert url == (
            "https://www.sec.gov/Archives/edgar/data/1318605/"
            "000131860526000012/tsla-20260331.htm"
        )
