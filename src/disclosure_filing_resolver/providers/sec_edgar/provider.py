"""SEC EDGAR provider implementation."""

from __future__ import annotations

from disclosure_filing_resolver.config import SECConfig, get_sec_config
from disclosure_filing_resolver.models import (
    CompanyIdentity,
    FilingCandidate,
    FilingDocument,
    ResolveRequest,
)
from disclosure_filing_resolver.providers.base import FilingProvider
from disclosure_filing_resolver.providers.sec_edgar.client import SECEdgarClient
from disclosure_filing_resolver.providers.sec_edgar.downloader import download_documents
from disclosure_filing_resolver.providers.sec_edgar.exhibit_classifier import classify_documents
from disclosure_filing_resolver.providers.sec_edgar.exhibit_parser import parse_filing_index
from disclosure_filing_resolver.providers.sec_edgar.filing_selector import select_filing
from disclosure_filing_resolver.providers.sec_edgar.ticker_resolver import TickerResolver


class SECEdgarProvider(FilingProvider):
    """SEC EDGAR filing acquisition provider."""

    def __init__(self, config: SECConfig | None = None) -> None:
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
    ) -> list[FilingDocument]:
        """Get documents for the selected filing, including exhibits.

        For 6-K filings, always parse the filing index to get exhibits.
        For other filings, return the primary document.
        """
        documents: list[FilingDocument] = []

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
        self, documents: list[FilingDocument], out_dir: str, filing: FilingCandidate,
        company: CompanyIdentity,
    ) -> list[FilingDocument]:
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
