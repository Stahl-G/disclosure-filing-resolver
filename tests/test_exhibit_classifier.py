"""Tests for exhibit classification."""

from disclosure_filing_resolver.models import FilingDocument
from disclosure_filing_resolver.providers.sec_edgar.exhibit_classifier import (
    classify_document,
    classify_documents,
)


class TestClassifyDocument:
    def test_financial_statements(self):
        doc = FilingDocument(
            filename="ea029059301ex99-1.htm",
            sec_url="https://example.com/ea029059301ex99-1.htm",
            description="Unaudited interim consolidated financial statements",
            document_type="EX-99.1",
        )
        result = classify_document(doc, is_primary=False)
        assert result.role == "financial_statements"
        assert result.priority == 100

    def test_operating_review(self):
        doc = FilingDocument(
            filename="ea029059302ex99-2.htm",
            sec_url="https://example.com/ea029059302ex99-2.htm",
            description="Operating and financial review",
            document_type="EX-99.2",
        )
        result = classify_document(doc, is_primary=False)
        assert result.role == "operating_review"
        assert result.priority == 90

    def test_press_release(self):
        doc = FilingDocument(
            filename="ea029059304ex99-4.htm",
            sec_url="https://example.com/ea029059304ex99-4.htm",
            description="Press release - quarterly results",
            document_type="EX-99.4",
        )
        result = classify_document(doc, is_primary=False)
        assert result.role == "press_release"
        assert result.priority == 70

    def test_presentation(self):
        doc = FilingDocument(
            filename="ea029059303ex99-3.htm",
            sec_url="https://example.com/ea029059303ex99-3.htm",
            description="Investor presentation",
            document_type="EX-99.3",
        )
        result = classify_document(doc, is_primary=False)
        assert result.role == "presentation"
        assert result.priority == 60

    def test_cover_page(self):
        doc = FilingDocument(
            filename="ea0290593-6k_toyo.htm",
            sec_url="https://example.com/ea0290593-6k_toyo.htm",
            description="6-K cover page",
            document_type="6-K",
        )
        result = classify_document(doc, is_primary=True)
        assert result.role == "cover"
        assert result.priority == 10

    def test_cover_page_with_financials(self):
        """Primary document that contains financial statements."""
        doc = FilingDocument(
            filename="ea0290593-6k_toyo.htm",
            sec_url="https://example.com/ea0290593-6k_toyo.htm",
            description="Financial statements and results of operations",
            document_type="6-K",
        )
        result = classify_document(doc, is_primary=True)
        # Should get operating_review or financial_statements if keywords match
        assert result.priority > 10

    def test_unknown_exhibit(self):
        doc = FilingDocument(
            filename="ea029059305ex99-5.htm",
            sec_url="https://example.com/ea029059305ex99-5.htm",
            description="Some random document",
            document_type="EX-99.5",
        )
        result = classify_document(doc, is_primary=False)
        assert result.role == "unknown"


class TestClassifyDocuments:
    def test_classify_all(self):
        docs = [
            FilingDocument(
                filename="cover.htm",
                sec_url="https://example.com/cover.htm",
                description="6-K cover page",
            ),
            FilingDocument(
                filename="ex99-1.htm",
                sec_url="https://example.com/ex99-1.htm",
                description="Unaudited interim consolidated financial statements",
            ),
            FilingDocument(
                filename="ex99-2.htm",
                sec_url="https://example.com/ex99-2.htm",
                description="Operating and financial review",
            ),
        ]
        result = classify_documents(docs)
        assert result[0].role == "cover"
        assert result[1].role == "financial_statements"
        assert result[2].role == "operating_review"
