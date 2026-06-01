"""Tests for filing index parsing."""

from pathlib import Path

from disclosure_filing_resolver.providers.sec_edgar.exhibit_parser import parse_filing_index

FIXTURES = Path(__file__).parent / "fixtures"


class TestParseFilingIndex:
    def test_parse_toyo_index(self):
        html = (FIXTURES / "toyo_filing_index_sample.html").read_text()
        docs = parse_filing_index(html, "1985273", "0001213900-26-058577")

        assert len(docs) == 5
        assert docs[0].filename == "ea0290593-6k_toyo.htm"
        assert docs[0].file_format == "html"
        assert docs[1].filename == "ea029059301ex99-1.htm"

    def test_parse_csiq_index(self):
        """CSIQ 6-K filing index with Exhibit 99.x documents."""
        html = (FIXTURES / "csiq_filing_index_sample.html").read_text()
        docs = parse_filing_index(html, "1375877", "0001104659-26-060672")

        assert len(docs) == 4
        assert docs[0].filename == "tm2614624d1_6k.htm"
        assert docs[1].filename == "tm2614624d1ex99-1.htm"
        # Verify SEC URLs use correct CIK
        for doc in docs:
            assert "sec.gov/Archives/edgar/data/1375877" in doc.sec_url

    def test_urls_are_correct(self):
        html = (FIXTURES / "toyo_filing_index_sample.html").read_text()
        docs = parse_filing_index(html, "1985273", "0001213900-26-058577")

        for doc in docs:
            assert "sec.gov/Archives/edgar/data/1985273" in doc.sec_url

    def test_empty_html(self):
        docs = parse_filing_index("<HTML><BODY></BODY></HTML>", "0000000", "0000000000")
        assert len(docs) == 0

    def test_pdf_detection(self):
        html = """
        <TABLE>
        <TR><TD>EX-99.1</TD><TD><A HREF="report.pdf">report.pdf</A></TD></TR>
        </TABLE>
        """
        docs = parse_filing_index(html, "12345", "0001234500000001")
        pdf_docs = [d for d in docs if d.file_format == "pdf"]
        assert len(pdf_docs) == 1
