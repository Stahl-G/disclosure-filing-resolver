"""Tests for sources.json export."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from disclosure_filing_resolver.manifest import evidence_to_sources, write_sources_json
from disclosure_filing_resolver.models import (
    Artifact,
    DisclosureRecord,
    EntityIdentity,
    EvidencePackage,
)


def _make_test_evidence() -> EvidencePackage:
    """Create a test EvidencePackage with artifacts."""
    entity = EntityIdentity(
        legal_name="TOYO Co., Ltd",
        identifiers={"ticker": "TOYO", "cik": "1985273", "cik10": "0001985273"},
        provider="sec_edgar",
    )
    disclosure = DisclosureRecord(
        disclosure_type="filing",
        form="6-K",
        filing_date="2026-03-15",
        title="6-K filing",
        source_url="https://www.sec.gov/Archives/edgar/data/1985273/000121390026058577/ea0290593-6k_toyo.htm",
        identifiers={
            "accession_number": "0001213900-26-058577",
            "primary_document": "ea0290593-6k_toyo.htm",
        },
        provider="sec_edgar",
    )
    artifacts = [
        Artifact(
            role="financial_statements",
            priority=100,
            filename="ea029059301ex99-1.htm",
            source_url="https://www.sec.gov/Archives/edgar/data/1985273/000121390026058577/ea029059301ex99-1.htm",
            file_format="html",
            confidence=0.9,
            provider="sec_edgar",
            raw={"accession_number": "0001213900-26-058577"},
        ),
        Artifact(
            role="operating_review",
            priority=90,
            filename="ea029059301ex99-2.htm",
            source_url="https://www.sec.gov/Archives/edgar/data/1985273/000121390026058577/ea029059301ex99-2.htm",
            file_format="html",
            confidence=0.85,
            provider="sec_edgar",
            raw={"accession_number": "0001213900-26-058577"},
        ),
    ]
    return EvidencePackage(
        entity=entity,
        disclosures=[disclosure],
        artifacts=artifacts,
    )


class TestEvidenceToSources:
    def test_basic_conversion(self):
        evidence = _make_test_evidence()
        sources = evidence_to_sources(evidence)

        assert len(sources) == 2

    def test_source_has_required_fields(self):
        evidence = _make_test_evidence()
        sources = evidence_to_sources(evidence)

        for source in sources:
            assert "title" in source
            assert "url" in source
            assert "source_type" in source
            assert "date" in source
            assert "provider" in source
            assert "metadata" in source

    def test_source_type_is_filing(self):
        evidence = _make_test_evidence()
        sources = evidence_to_sources(evidence)

        for source in sources:
            assert source["source_type"] == "filing"

    def test_source_date_from_disclosure(self):
        evidence = _make_test_evidence()
        sources = evidence_to_sources(evidence)

        for source in sources:
            assert source["date"] == "2026-03-15"

    def test_source_title_includes_entity_name(self):
        evidence = _make_test_evidence()
        sources = evidence_to_sources(evidence)

        for source in sources:
            assert "TOYO Co., Ltd" in source["title"]

    def test_source_title_includes_form(self):
        evidence = _make_test_evidence()
        sources = evidence_to_sources(evidence)

        for source in sources:
            assert "6-K" in source["title"]

    def test_source_metadata_has_form(self):
        evidence = _make_test_evidence()
        sources = evidence_to_sources(evidence)

        for source in sources:
            assert source["metadata"]["form"] == "6-K"

    def test_source_metadata_has_role(self):
        evidence = _make_test_evidence()
        sources = evidence_to_sources(evidence)

        roles = {s["metadata"]["role"] for s in sources}
        assert "financial_statements" in roles
        assert "operating_review" in roles

    def test_content_included_when_present(self):
        evidence = _make_test_evidence()
        evidence.artifacts[0].content_text = "Financial statements content..."
        sources = evidence_to_sources(evidence)

        fs_source = next(s for s in sources if s["metadata"]["role"] == "financial_statements")
        assert fs_source["content"] == "Financial statements content..."

    def test_content_not_included_when_absent(self):
        evidence = _make_test_evidence()
        sources = evidence_to_sources(evidence)

        for source in sources:
            assert "content" not in source

    def test_local_path_included_when_present(self):
        evidence = _make_test_evidence()
        evidence.artifacts[0].local_path = "/tmp/financial.htm"
        sources = evidence_to_sources(evidence)

        fs_source = next(s for s in sources if s["metadata"]["role"] == "financial_statements")
        assert fs_source["local_path"] == "/tmp/financial.htm"

    def test_no_artifacts_uses_disclosure(self):
        evidence = _make_test_evidence()
        evidence.artifacts = []
        sources = evidence_to_sources(evidence)

        assert len(sources) == 1
        assert "6-K" in sources[0]["title"]
        assert sources[0]["source_type"] == "filing"

    def test_empty_evidence_returns_empty(self):
        entity = EntityIdentity(legal_name="Empty Corp")
        evidence = EvidencePackage(entity=entity)
        sources = evidence_to_sources(evidence)

        assert sources == []


class TestWriteSourcesJson:
    def test_writes_file(self):
        evidence = _make_test_evidence()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_sources_json(evidence, tmpdir)
            assert path.exists()
            assert path.name == "sources.json"

    def test_file_is_valid_json(self):
        evidence = _make_test_evidence()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_sources_json(evidence, tmpdir)
            data = json.loads(path.read_text(encoding="utf-8"))
            assert isinstance(data, list)

    def test_file_contains_sources(self):
        evidence = _make_test_evidence()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_sources_json(evidence, tmpdir)
            data = json.loads(path.read_text(encoding="utf-8"))
            assert len(data) == 2

    def test_creates_output_dir(self):
        evidence = _make_test_evidence()
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = str(Path(tmpdir) / "nested" / "dir")
            path = write_sources_json(evidence, out_dir)
            assert path.exists()
