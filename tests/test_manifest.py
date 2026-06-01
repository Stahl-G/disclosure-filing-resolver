"""Tests for manifest writing."""

import json
import tempfile

from disclosure_filing_resolver.manifest import read_manifest, write_manifest
from disclosure_filing_resolver.models import (
    CompanyIdentity,
    FilingCandidate,
    FilingDocument,
    FilingPackage,
    ResolveRequest,
)


def _make_test_package() -> FilingPackage:
    """Create a test filing package."""
    return FilingPackage(
        request=ResolveRequest(
            ticker="TOYO",
            intent="quarterly",
            period="latest",
            file_format="html",
            download=True,
        ),
        company=CompanyIdentity(
            name="TOYO Co., Ltd",
            ticker="TOYO",
            cik="1985273",
            cik10="0001985273",
        ),
        selected_filing=FilingCandidate(
            form="6-K",
            filing_date="2026-05-18",
            report_date="2026-03-31",
            accession_number="0001213900-26-058577",
            primary_document="ea0290593-6k_toyo.htm",
            primary_url="https://example.com/ea0290593-6k_toyo.htm",
            index_url="https://example.com/index.html",
        ),
        documents=[
            FilingDocument(
                role="cover",
                priority=10,
                filename="ea0290593-6k_toyo.htm",
                sec_url="https://example.com/ea0290593-6k_toyo.htm",
                local_path="artifacts/toyo/toyo_2026_q1_6k_cover.htm",
            ),
            FilingDocument(
                role="financial_statements",
                priority=100,
                filename="ea029059301ex99-1.htm",
                sec_url="https://example.com/ea029059301ex99-1.htm",
                local_path="artifacts/toyo/toyo_2026_q1_ex99-1_financial_statements.htm",
            ),
        ],
        warnings=["6-K primary document may be a cover page"],
    )


class TestManifestWriteRead:
    def test_write_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            package = _make_test_package()
            path = write_manifest(package, tmpdir)

            assert path.exists()
            assert path.name == "manifest.json"

            data = json.loads(path.read_text())
            assert data["schema_version"] == "1.0"
            assert data["company"]["ticker"] == "TOYO"
            assert len(data["documents"]) == 2

    def test_read_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            package = _make_test_package()
            path = write_manifest(package, tmpdir)

            loaded = read_manifest(path)
            assert loaded.company.ticker == "TOYO"
            assert loaded.selected_filing.form == "6-K"
            assert len(loaded.documents) == 2

    def test_manifest_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            package = _make_test_package()
            path = write_manifest(package, tmpdir)
            loaded = read_manifest(path)

            # Verify all fields survive roundtrip
            assert loaded.request.ticker == package.request.ticker
            assert loaded.request.intent == package.request.intent
            assert loaded.company.cik == package.company.cik
            sel_acc = loaded.selected_filing.accession_number
            pkg_acc = package.selected_filing.accession_number
            assert sel_acc == pkg_acc
            assert loaded.warnings == package.warnings
