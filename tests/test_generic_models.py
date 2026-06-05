"""Tests for generic disclosure models and legacy conversion helpers."""

from disclosure_filing_resolver.models import (
    CompanyIdentity,
    FilingCandidate,
    FilingDocument,
    FilingPackage,
    ResolveRequest,
)


def test_company_identity_to_entity_identity():
    company = CompanyIdentity(
        name="TOYO Co., Ltd",
        ticker="TOYO",
        cik="1985273",
        cik10="0001985273",
    )

    entity = company.to_entity_identity()

    assert entity.legal_name == "TOYO Co., Ltd"
    assert entity.identifiers["ticker"] == "TOYO"
    assert entity.identifiers["cik"] == "1985273"
    assert entity.listings[0]["ticker"] == "TOYO"
    assert entity.provider == "sec_edgar"


def test_filing_candidate_to_disclosure_record():
    filing = FilingCandidate(
        form="6-K",
        filing_date="2026-05-18",
        report_date="2026-03-31",
        accession_number="0001213900-26-058577",
        primary_document="ea0290593-6k_toyo.htm",
        primary_doc_description="Quarterly results",
        primary_url="https://example.com/primary.htm",
        index_url="https://example.com/index.html",
        score=51.0,
        reasons=["6-K filing"],
    )

    disclosure = filing.to_disclosure_record()

    assert disclosure.disclosure_type == "filing"
    assert disclosure.form == "6-K"
    assert disclosure.source_url == "https://example.com/primary.htm"
    assert disclosure.identifiers["accession_number"] == "0001213900-26-058577"
    assert disclosure.reasons == ["6-K filing"]


def test_filing_document_to_artifact():
    document = FilingDocument(
        role="financial_statements",
        priority=100,
        description="Financial statements",
        document_type="EX-99.1",
        sequence="2",
        filename="ex99-1.htm",
        sec_url="https://example.com/ex99-1.htm",
        local_path="/tmp/ex99-1.htm",
        download_status="downloaded",
    )

    artifact = document.to_artifact()

    assert artifact.role == "financial_statements"
    assert artifact.source_url == "https://example.com/ex99-1.htm"
    assert artifact.local_path == "/tmp/ex99-1.htm"
    assert artifact.raw["sequence"] == "2"


def test_filing_package_to_evidence_package():
    package = FilingPackage(
        request=ResolveRequest(ticker="TOYO", intent="quarterly"),
        company=CompanyIdentity(
            name="TOYO Co., Ltd",
            ticker="TOYO",
            cik="1985273",
            cik10="0001985273",
        ),
        selected_filing=FilingCandidate(
            form="6-K",
            filing_date="2026-05-18",
            accession_number="0001213900-26-058577",
            primary_document="ea0290593-6k_toyo.htm",
            primary_url="https://example.com/primary.htm",
            index_url="https://example.com/index.html",
        ),
        documents=[
            FilingDocument(
                role="cover",
                filename="ea0290593-6k_toyo.htm",
                sec_url="https://example.com/primary.htm",
            )
        ],
        warnings=["6-K primary document may be a cover page"],
    )

    evidence = package.to_evidence_package()

    assert evidence.schema_version == "2.0"
    assert evidence.request["ticker"] == "TOYO"
    assert evidence.entity.legal_name == "TOYO Co., Ltd"
    assert evidence.disclosures[0].form == "6-K"
    assert evidence.artifacts[0].role == "cover"
    assert evidence.warnings == ["6-K primary document may be a cover page"]
