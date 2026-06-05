"""SEC EDGAR provider implementation."""

from __future__ import annotations

from typing import List, Optional

from disclosure_filing_resolver.config import SECConfig, get_sec_config
from disclosure_filing_resolver.models import (
    Artifact,
    CompanyIdentity,
    DisclosureRecord,
    DisclosureRequest,
    EntityIdentity,
    EntityQuery,
    FilingCandidate,
    FilingDocument,
    ResolveRequest,
)
from disclosure_filing_resolver.providers.base import (
    DisclosureProvider,
    FilingProvider,
    IdentityProvider,
)
from disclosure_filing_resolver.providers.sec_edgar.client import SECEdgarClient
from disclosure_filing_resolver.providers.sec_edgar.downloader import download_documents
from disclosure_filing_resolver.providers.sec_edgar.exhibit_classifier import classify_documents
from disclosure_filing_resolver.providers.sec_edgar.exhibit_parser import parse_filing_index
from disclosure_filing_resolver.providers.sec_edgar.filing_selector import select_filing
from disclosure_filing_resolver.providers.sec_edgar.ticker_resolver import TickerResolver


def _query_to_resolve_request(query: EntityQuery) -> ResolveRequest:
    """Convert a generic entity query to the legacy SEC resolve request."""
    return ResolveRequest(
        ticker=query.ticker or query.identifiers.get("ticker"),
        company_name=query.company_name,
        cik=query.cik or query.identifiers.get("cik"),
        market=query.market,
    )


def _request_to_resolve_request(request: DisclosureRequest) -> ResolveRequest:
    """Convert a generic disclosure request to the legacy SEC resolve request."""
    identifiers = request.entity.identifiers
    return ResolveRequest(
        ticker=identifiers.get("ticker"),
        company_name=request.entity.legal_name,
        cik=identifiers.get("cik"),
        market="us",
        intent=request.intent,
        period=request.period,
        form_hint=request.form_hint,
        file_format=request.file_format,
        download=request.download,
        include_exhibits=request.include_exhibits,
        out_dir=request.out_dir,
    )


def _entity_to_company(entity: EntityIdentity) -> CompanyIdentity:
    """Convert a generic entity identity to the legacy SEC company identity."""
    identifiers = entity.identifiers
    cik = identifiers.get("cik", "")
    cik10 = identifiers.get("cik10") or cik.zfill(10)
    return CompanyIdentity(
        name=entity.legal_name,
        ticker=identifiers.get("ticker"),
        cik=cik,
        cik10=cik10,
        provider=entity.provider or "sec_edgar",
    )


def _disclosure_to_filing(disclosure: DisclosureRecord) -> FilingCandidate:
    """Convert a generic disclosure record to the legacy SEC filing model."""
    raw_candidate = disclosure.raw.get("filing_candidate")
    if raw_candidate:
        return FilingCandidate(**raw_candidate)

    primary_document = disclosure.identifiers.get("primary_document")
    if not primary_document:
        primary_document = disclosure.source_url.rstrip("/").split("/")[-1]

    return FilingCandidate(
        form=disclosure.form,
        filing_date=disclosure.filing_date,
        report_date=disclosure.report_date,
        accession_number=disclosure.identifiers.get("accession_number", ""),
        primary_document=primary_document,
        primary_doc_description=disclosure.description,
        primary_url=disclosure.source_url,
        index_url=disclosure.index_url or "",
        score=disclosure.score,
        reasons=list(disclosure.reasons),
    )


class SECEdgarIdentityProvider(IdentityProvider):
    """SEC EDGAR identity provider adapter."""

    def __init__(self, config: Optional[SECConfig] = None) -> None:
        self.config = config or get_sec_config()
        self._client = SECEdgarClient(self.config)
        self._ticker_resolver = TickerResolver(self._client)

    def resolve(self, query: EntityQuery) -> List[EntityIdentity]:
        """Resolve a generic entity query using SEC ticker/CIK data."""
        company = self._ticker_resolver.resolve(_query_to_resolve_request(query))
        return [company.to_entity_identity()]

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()


class SECEdgarDisclosureProvider(DisclosureProvider):
    """SEC EDGAR disclosure provider adapter."""

    def __init__(self, config: Optional[SECConfig] = None) -> None:
        self._legacy = SECEdgarProvider(config)

    def list_disclosures(
        self, entity: EntityIdentity, request: DisclosureRequest
    ) -> List[DisclosureRecord]:
        """Select SEC disclosure records for a generic entity/request pair."""
        company = _entity_to_company(entity)
        resolve_request = _request_to_resolve_request(request)
        filing = self._legacy.select_filing(company, resolve_request)
        disclosure = filing.to_disclosure_record()
        disclosure.raw["filing_candidate"] = filing.model_dump()
        disclosure.raw["company"] = company.model_dump()
        return [disclosure]

    def fetch_artifacts(
        self, disclosure: DisclosureRecord, request: DisclosureRequest
    ) -> List[Artifact]:
        """Fetch and optionally download artifacts for a SEC disclosure."""
        company = _entity_to_company(request.entity)
        filing = _disclosure_to_filing(disclosure)
        resolve_request = _request_to_resolve_request(request)
        documents = self._legacy.get_documents(company, filing, resolve_request)
        if request.download and request.out_dir:
            documents = self._legacy.download_documents(
                documents,
                request.out_dir,
                filing,
                company,
            )
        else:
            for document in documents:
                if document.download_status is None:
                    document.download_status = "skipped"
        return [document.to_artifact() for document in documents]

    def close(self) -> None:
        """Close the underlying SEC EDGAR provider."""
        self._legacy.close()


class SECEdgarProvider(FilingProvider):
    """SEC EDGAR filing acquisition provider."""

    def __init__(self, config: Optional[SECConfig] = None) -> None:
        self.config = config or get_sec_config()
        self._client = SECEdgarClient(self.config)
        self._ticker_resolver = TickerResolver(self._client)

    @property
    def client(self) -> SECEdgarClient:
        return self._client

    def resolve_company(self, request: ResolveRequest) -> CompanyIdentity:
        """Resolve company identity from request."""
        return self._ticker_resolver.resolve(request)

    def select_filing(
        self, company: CompanyIdentity, request: ResolveRequest
    ) -> FilingCandidate:
        """Select the best filing for the given intent."""
        return select_filing(self._client, company.cik, company.cik10, request)

    def get_documents(
        self,
        company: CompanyIdentity,
        filing: FilingCandidate,
        request: ResolveRequest,
    ) -> List[FilingDocument]:
        """Get documents for the selected filing, including exhibits.

        For 6-K filings, always parse the filing index to get exhibits.
        For other filings, return the primary document.
        """
        documents: List[FilingDocument] = []

        # Always add the primary document
        primary = FilingDocument(
            filename=filing.primary_document,
            sec_url=filing.primary_url,
            role="unknown",
            priority=0,
            description=filing.primary_doc_description,
            confidence=0.9,
        )
        documents.append(primary)

        # For 6-K or when includes_exhibits is True, parse filing index
        is_6k = filing.form.upper() in ("6-K", "6K")
        if is_6k or request.include_exhibits:
            try:
                index_html = self._client.get_text(filing.index_url)
                index_docs = parse_filing_index(
                    index_html, company.cik, filing.accession_number
                )
                # Add any documents not already in the list
                existing_filenames = {d.filename for d in documents}
                for doc in index_docs:
                    if doc.filename not in existing_filenames:
                        documents.append(doc)
            except Exception:
                # Filing index may not be parseable; continue with primary doc
                pass

        # Classify all documents
        documents = classify_documents(documents)

        # For 6-K, add standard warnings
        if is_6k:
            pass  # warnings added at package level

        # Filter by file format preference
        if request.file_format == "html":
            # Keep HTML docs, but also keep unknown format docs
            documents = [
                d for d in documents
                if d.file_format in ("html", "unknown") or d.role == "cover"
            ]
        elif request.file_format == "pdf":
            pdf_docs = [d for d in documents if d.file_format == "pdf"]
            if pdf_docs:
                documents = pdf_docs
            # If no PDF, keep all and add warning later

        return documents

    def download_documents(
        self, documents: List[FilingDocument], out_dir: str, filing: FilingCandidate,
        company: CompanyIdentity,
    ) -> List[FilingDocument]:
        """Download documents to local filesystem."""
        return download_documents(
            self._client,
            documents,
            out_dir,
            company.ticker or "unknown",
            filing.filing_date,
            filing.form,
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()
