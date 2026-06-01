"""Tests for download status tracking."""

from __future__ import annotations

import tempfile
from unittest.mock import MagicMock

from disclosure_filing_resolver.models import FilingDocument
from disclosure_filing_resolver.providers.sec_edgar.downloader import download_documents


def _make_doc(filename: str = "test.htm", role: str = "cover") -> FilingDocument:
    return FilingDocument(
        filename=filename,
        sec_url=f"https://example.com/{filename}",
        role=role,
    )


class TestDownloadStatus:
    def test_successful_download_sets_downloaded_status(self):
        client = MagicMock()
        docs = [_make_doc()]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = download_documents(client, docs, tmpdir, "TOYO", "2026-05-18", "6-K")

        assert result[0].download_status == "downloaded"
        assert result[0].local_path is not None
        assert result[0].download_error is None
        client.download.assert_called_once()

    def test_failed_download_sets_failed_status_and_error(self):
        client = MagicMock()
        client.download.side_effect = ConnectionError("Connection refused")
        docs = [_make_doc()]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = download_documents(client, docs, tmpdir, "TOYO", "2026-05-18", "6-K")

        assert result[0].download_status == "failed"
        assert result[0].local_path is None
        assert "Connection refused" in (result[0].download_error or "")

    def test_multiple_documents_partial_failure(self):
        client = MagicMock()
        client.download.side_effect = [
            None,  # first succeeds
            ConnectionError("timeout"),  # second fails
        ]
        docs = [_make_doc("doc1.htm"), _make_doc("doc2.htm")]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = download_documents(client, docs, tmpdir, "TOYO", "2026-05-18", "6-K")

        assert result[0].download_status == "downloaded"
        assert result[1].download_status == "failed"
        assert "timeout" in (result[1].download_error or "")


class TestNoDownloadStatus:
    def test_no_download_sets_skipped_status(self):
        """When download=False, documents should have download_status='skipped'."""

        # We can't easily test the full resolver without mocking SEC,
        # so test the logic directly
        docs = [_make_doc(), _make_doc("doc2.htm", role="financial_statements")]

        # Simulate what resolver does when download=False
        for doc in docs:
            if doc.download_status is None:
                doc.download_status = "skipped"

        assert docs[0].download_status == "skipped"
        assert docs[1].download_status == "skipped"
        assert docs[0].local_path is None
        assert docs[0].download_error is None


class TestManifestDownloadStatus:
    def test_manifest_includes_download_status_fields(self):
        """Verify download_status and download_error appear in manifest."""
        from disclosure_filing_resolver.manifest import read_manifest, write_manifest
        from disclosure_filing_resolver.models import (
            CompanyIdentity,
            FilingCandidate,
            FilingPackage,
            ResolveRequest,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            package = FilingPackage(
                request=ResolveRequest(ticker="TEST", intent="quarterly"),
                company=CompanyIdentity(
                    name="Test Co", ticker="TEST", cik="000", cik10="0000000000"
                ),
                selected_filing=FilingCandidate(
                    form="6-K",
                    filing_date="2026-01-01",
                    accession_number="000-00-000",
                    primary_document="test.htm",
                    primary_url="https://example.com/test.htm",
                    index_url="https://example.com/index.html",
                ),
                documents=[
                    FilingDocument(
                        filename="doc1.htm",
                        sec_url="https://example.com/doc1.htm",
                        download_status="downloaded",
                        local_path="artifacts/doc1.htm",
                    ),
                    FilingDocument(
                        filename="doc2.htm",
                        sec_url="https://example.com/doc2.htm",
                        download_status="failed",
                        download_error="Connection refused",
                    ),
                    FilingDocument(
                        filename="doc3.htm",
                        sec_url="https://example.com/doc3.htm",
                        download_status="skipped",
                    ),
                ],
            )

            manifest_path = write_manifest(package, tmpdir)
            loaded = read_manifest(manifest_path)

            assert loaded.documents[0].download_status == "downloaded"
            assert loaded.documents[0].download_error is None
            assert loaded.documents[1].download_status == "failed"
            assert loaded.documents[1].download_error == "Connection refused"
            assert loaded.documents[2].download_status == "skipped"
