"""Main resolver entry point."""

from __future__ import annotations

from disclosure_filing_resolver.config import SECConfig, get_sec_config
from disclosure_filing_resolver.exceptions import UnsupportedMarketError, UnsupportedPeriodError
from disclosure_filing_resolver.manifest import write_manifest
from disclosure_filing_resolver.models import (
    FilingPackage,
    ResolveRequest,
)
from disclosure_filing_resolver.providers.sec_edgar import SECEdgarProvider


def resolve_filing_package(
    ticker: str | None = None,
    company_name: str | None = None,
    cik: str | None = None,
    intent: str = "quarterly",
    period: str = "latest",
    form: str | None = None,
    file_format: str = "html",
    download: bool = True,
    include_exhibits: bool = True,
    out_dir: str | None = None,
    market: str = "us",
    config: SECConfig | None = None,
) -> FilingPackage:
    """Resolve and optionally download a filing package.

    This is the main Python API entry point.

    Args:
        ticker: Stock ticker symbol (e.g., "TOYO", "CSIQ", "TSLA")
        company_name: Company name for fuzzy matching
        cik: SEC CIK number
        intent: Filing intent (annual, quarterly, semiannual, interim,
            earnings_release, specific_form)
        period: Time period (latest, or specific date)
        form: Specific form type for intent=specific_form
        file_format: Output format (html, pdf, any)
        download: Whether to download documents
        include_exhibits: Whether to include exhibits
        out_dir: Output directory for downloads
        market: Market identifier (us for SEC EDGAR)
        config: Optional SEC configuration override

    Returns:
        FilingPackage with all resolved filing information

    Raises:
        UnsupportedMarketError: If market is not supported
        CompanyNotFoundError: If company cannot be resolved
        FilingNotFoundError: If no suitable filing found
    """
    if market != "us":
        raise UnsupportedMarketError(market)

    if period != "latest":
        raise UnsupportedPeriodError(period)

    request = ResolveRequest(
        ticker=ticker,
        company_name=company_name,
        cik=cik,
        market=market,
        intent=intent,
        period=period,
        form_hint=form,
        file_format=file_format,
        download=download,
        include_exhibits=include_exhibits,
        out_dir=out_dir,
    )

    provider = SECEdgarProvider(config or get_sec_config())

    try:
        # 1. Resolve company identity
        company = provider.resolve_company(request)

        # 2. Select filing
        filing = provider.select_filing(company, request)

        # 3. Get documents (and classify exhibits)
        documents = provider.get_documents(company, filing, request)

        # 4. Build warnings
        warnings: list[str] = []
        is_6k = filing.form.upper() in ("6-K", "6K")
        if is_6k:
            warnings.append(
                "Foreign private issuer quarterly materials may be filed under Form 6-K "
                "rather than Form 10-Q."
            )
            warnings.append(
                "The 6-K primary document may be a cover page; use exhibits for analysis."
            )

        # 5. Check for PDF fallback
        if file_format == "pdf":
            has_pdf = any(d.file_format == "pdf" for d in documents)
            if not has_pdf:
                warnings.append(
                    "No PDF documents found. HTML alternatives have been included."
                )

        # 6. Download if requested
        if download and out_dir:
            documents = provider.download_documents(documents, out_dir, filing, company)
        else:
            # Mark all documents as skipped when not downloading
            for doc in documents:
                if doc.download_status is None:
                    doc.download_status = "skipped"

        # 7. Add warnings for failed downloads
        failed = [d for d in documents if d.download_status == "failed"]
        if failed:
            warnings.append(
                f"{len(failed)} document(s) failed to download. "
                "See manifest document download_error fields."
            )
            # Stronger warning for important document types
            important_roles = {
                "financial_statements",
                "annual_report",
                "quarterly_report",
                "operating_review",
            }
            for doc in failed:
                if doc.role in important_roles:
                    warnings.append(
                        f"Important analysis document failed to download: "
                        f"{doc.role} ({doc.filename})"
                    )

        # 8. Build package
        package = FilingPackage(
            request=request,
            company=company,
            selected_filing=filing,
            documents=documents,
            warnings=warnings,
        )

        # 8. Write manifest
        if out_dir:
            write_manifest(package, out_dir)

        return package

    finally:
        provider.close()
