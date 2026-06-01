"""Core data models for disclosure-filing-resolver."""

from __future__ import annotations

from enum import Enum

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

    ticker: str | None = None
    company_name: str | None = None
    cik: str | None = None
    market: str = "us"
    intent: str = "quarterly"
    period: str = "latest"
    form_hint: str | None = None
    file_format: str = "html"
    download: bool = True
    include_exhibits: bool = True
    out_dir: str | None = None


class CompanyIdentity(BaseModel):
    """Resolved company identity."""

    name: str
    ticker: str | None = None
    cik: str
    cik10: str
    provider: str = "sec_edgar"


class FilingCandidate(BaseModel):
    """A candidate filing from SEC submissions."""

    form: str
    filing_date: str
    report_date: str | None = None
    accession_number: str
    primary_document: str
    primary_doc_description: str | None = None
    primary_url: str
    index_url: str
    score: float = 0.0
    reasons: list[str] = Field(default_factory=list)


class FilingDocument(BaseModel):
    """A document within a filing, potentially an exhibit."""

    role: str = "unknown"
    priority: int = 0
    description: str | None = None
    document_type: str | None = None
    sequence: str | None = None
    filename: str
    sec_url: str
    local_path: str | None = None
    file_format: str = "html"
    confidence: float = 0.5
    download_status: str | None = None  # "downloaded", "failed", "skipped"
    download_error: str | None = None


class FilingPackage(BaseModel):
    """Complete output package from filing resolution."""

    schema_version: str = "1.0"
    request: ResolveRequest
    company: CompanyIdentity
    selected_filing: FilingCandidate
    documents: list[FilingDocument] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
