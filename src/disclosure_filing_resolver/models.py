"""Core data models for disclosure-filing-resolver."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Intent(str, Enum):
    """Filing intent types."""

    ANNUAL = "annual"
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"
    INTERIM = "interim"
    EARNINGS_RELEASE = "earnings_release"
    SPECIFIC_FORM = "specific_form"


class FileFormat(str, Enum):
    """Output file format preference."""

    HTML = "html"
    PDF = "pdf"
    ANY = "any"


class ResolveRequest(BaseModel):
    """Input request for filing resolution."""

    ticker: Optional[str] = None
    company_name: Optional[str] = None
    cik: Optional[str] = None
    market: str = "us"
    intent: str = "quarterly"
    period: str = "latest"
    form_hint: Optional[str] = None
    file_format: str = "html"
    download: bool = True
    include_exhibits: bool = True
    out_dir: Optional[str] = None


class EntityQuery(BaseModel):
    """Generic entity lookup query."""

    ticker: Optional[str] = None
    company_name: Optional[str] = None
    cik: Optional[str] = None
    market: str = "us"
    identifiers: Dict[str, str] = Field(default_factory=dict)


class EntityIdentity(BaseModel):
    """Generic resolved entity identity."""

    legal_name: str
    aliases: List[str] = Field(default_factory=list)
    jurisdiction: str = ""
    identifiers: Dict[str, str] = Field(default_factory=dict)
    listings: List[Dict[str, str]] = Field(default_factory=list)
    provider: str = ""
    raw: Dict[str, Any] = Field(default_factory=dict)


class DisclosureRequest(BaseModel):
    """Generic request for resolving a disclosure."""

    entity: EntityIdentity
    intent: str = "quarterly"
    period: str = "latest"
    form_hint: Optional[str] = None
    file_format: str = "html"
    download: bool = True
    include_exhibits: bool = True
    out_dir: Optional[str] = None


class DisclosureRecord(BaseModel):
    """Generic disclosure metadata record."""

    disclosure_type: str = "filing"
    form: str = ""
    filing_date: str = ""
    report_date: Optional[str] = None
    title: str = ""
    description: Optional[str] = None
    source_url: str = ""
    index_url: Optional[str] = None
    identifiers: Dict[str, str] = Field(default_factory=dict)
    score: float = 0.0
    reasons: List[str] = Field(default_factory=list)
    provider: str = ""
    raw: Dict[str, Any] = Field(default_factory=dict)


class Artifact(BaseModel):
    """Generic source artifact associated with a disclosure."""

    role: str = "unknown"
    priority: int = 0
    description: Optional[str] = None
    document_type: Optional[str] = None
    filename: str = ""
    source_url: str = ""
    local_path: Optional[str] = None
    file_format: str = "html"
    confidence: float = 0.5
    download_status: Optional[str] = None
    download_error: Optional[str] = None
    content_text: Optional[str] = None
    provider: str = ""
    raw: Dict[str, Any] = Field(default_factory=dict)


class Observation(BaseModel):
    """Generic enriched fact or observation from a disclosure provider."""

    source: str = ""
    category: str = ""
    key: str = ""
    value: Any = None
    unit: Optional[str] = None
    period: Optional[str] = None
    confidence: float = 1.0
    provenance: Dict[str, str] = Field(default_factory=dict)


class EvidencePackage(BaseModel):
    """Generic evidence package produced by the disclosure resolution layer."""

    schema_version: str = "2.0"
    request: Dict[str, Any] = Field(default_factory=dict)
    entity: EntityIdentity
    disclosures: List[DisclosureRecord] = Field(default_factory=list)
    artifacts: List[Artifact] = Field(default_factory=list)
    observations: List[Observation] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    provenance: List[Dict[str, str]] = Field(default_factory=list)


class CompanyIdentity(BaseModel):
    """Resolved company identity."""

    name: str
    ticker: Optional[str] = None
    cik: str
    cik10: str
    provider: str = "sec_edgar"

    def to_entity_identity(self) -> EntityIdentity:
        """Convert the SEC-specific identity to the generic identity model."""
        identifiers = {
            "cik": self.cik,
            "cik10": self.cik10,
        }
        listings: List[Dict[str, str]] = []
        if self.ticker:
            identifiers["ticker"] = self.ticker
            listings.append(
                {
                    "ticker": self.ticker,
                    "exchange": "",
                    "mic": "",
                    "currency": "",
                }
            )
        return EntityIdentity(
            legal_name=self.name,
            identifiers=identifiers,
            listings=listings,
            provider=self.provider,
        )


class FilingCandidate(BaseModel):
    """A candidate filing from SEC submissions."""

    form: str
    filing_date: str
    report_date: Optional[str] = None
    accession_number: str
    primary_document: str
    primary_doc_description: Optional[str] = None
    primary_url: str
    index_url: str
    score: float = 0.0
    reasons: List[str] = Field(default_factory=list)

    def to_disclosure_record(self) -> DisclosureRecord:
        """Convert the SEC-specific filing candidate to a generic disclosure record."""
        return DisclosureRecord(
            disclosure_type="filing",
            form=self.form,
            filing_date=self.filing_date,
            report_date=self.report_date,
            title=self.primary_doc_description or f"{self.form} filing",
            description=self.primary_doc_description,
            source_url=self.primary_url,
            index_url=self.index_url,
            identifiers={
                "accession_number": self.accession_number,
                "primary_document": self.primary_document,
            },
            score=self.score,
            reasons=list(self.reasons),
            provider="sec_edgar",
        )


class FilingDocument(BaseModel):
    """A document within a filing, potentially an exhibit."""

    role: str = "unknown"
    priority: int = 0
    description: Optional[str] = None
    document_type: Optional[str] = None
    sequence: Optional[str] = None
    filename: str
    sec_url: str
    local_path: Optional[str] = None
    file_format: str = "html"
    confidence: float = 0.5
    download_status: Optional[str] = None  # "downloaded", "failed", "skipped"
    download_error: Optional[str] = None

    def to_artifact(self) -> Artifact:
        """Convert the SEC-specific filing document to a generic artifact."""
        return Artifact(
            role=self.role,
            priority=self.priority,
            description=self.description,
            document_type=self.document_type,
            filename=self.filename,
            source_url=self.sec_url,
            local_path=self.local_path,
            file_format=self.file_format,
            confidence=self.confidence,
            download_status=self.download_status,
            download_error=self.download_error,
            provider="sec_edgar",
            raw={"sequence": self.sequence} if self.sequence else {},
        )


class FilingPackage(BaseModel):
    """Complete output package from filing resolution."""

    schema_version: str = "1.0"
    request: ResolveRequest
    company: CompanyIdentity
    selected_filing: FilingCandidate
    documents: List[FilingDocument] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    def to_evidence_package(self) -> EvidencePackage:
        """Convert the legacy filing package to the generic evidence package."""
        return EvidencePackage(
            request=self.request.model_dump(),
            entity=self.company.to_entity_identity(),
            disclosures=[self.selected_filing.to_disclosure_record()],
            artifacts=[document.to_artifact() for document in self.documents],
            warnings=list(self.warnings),
            provenance=[
                {
                    "provider": self.company.provider,
                    "schema_version": self.schema_version,
                }
            ],
        )
