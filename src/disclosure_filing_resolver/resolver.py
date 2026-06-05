"""Main resolver entry point."""

from __future__ import annotations

from typing import List, Optional

from disclosure_filing_resolver.config import SECConfig, get_sec_config
from disclosure_filing_resolver.exceptions import (
    CompanyNotFoundError,
    FilingNotFoundError,
    UnsupportedMarketError,
    UnsupportedPeriodError,
)
from disclosure_filing_resolver.manifest import (
    write_evidence_manifest,
    write_manifest,
    write_sources_json,
)
from disclosure_filing_resolver.models import (
    Artifact,
    DisclosureRecord,
    DisclosureRequest,
    EntityQuery,
    EvidencePackage,
    FilingPackage,
    ResolveRequest,
)
from disclosure_filing_resolver.providers.registry import ProviderRegistry
from disclosure_filing_resolver.providers.sec_edgar.provider import (
    SECEdgarDisclosureProvider,
    SECEdgarIdentityProvider,
    SECEdgarProvider,
)


def create_default_registry(config: Optional[SECConfig] = None) -> ProviderRegistry:
    """Create the default provider registry."""
    from disclosure_filing_resolver.providers.sec_edgar.xbrl import SECXBRLProvider

    registry = ProviderRegistry()
    registry.register_identity("sec_edgar", SECEdgarIdentityProvider(config))
    registry.register_disclosure("sec_edgar", SECEdgarDisclosureProvider(config))
    registry.register_enrichment("sec_edgar_xbrl", SECXBRLProvider(config))
    return registry


def _close_registry_providers(registry: ProviderRegistry) -> None:
    """Close providers that expose a close method."""
    provider_names = registry.list_providers()
    providers = []
    for name in provider_names["identity"]:
        providers.append(registry.get_identity(name))
    for name in provider_names["disclosure"]:
        providers.append(registry.get_disclosure(name))
    for name in provider_names["enrichment"]:
        providers.append(registry.get_enrichment(name))

    for provider in providers:
        close = getattr(provider, "close", None)
        if callable(close):
            close()


def _build_generic_warnings(
    disclosures: List[DisclosureRecord],
    artifacts: List[Artifact],
    file_format: str,
) -> List[str]:
    """Build warnings for a generic evidence package."""
    warnings: List[str] = []
    if any(disclosure.form.upper() in ("6-K", "6K") for disclosure in disclosures):
        warnings.append(
            "Foreign private issuer quarterly materials may be filed under Form 6-K "
            "rather than Form 10-Q."
        )
        warnings.append(
            "The 6-K primary document may be a cover page; use exhibits for analysis."
        )

    if file_format == "pdf":
        has_pdf = any(artifact.file_format == "pdf" for artifact in artifacts)
        if not has_pdf:
            warnings.append("No PDF documents found. HTML alternatives have been included.")

    failed = [artifact for artifact in artifacts if artifact.download_status == "failed"]
    if failed:
        warnings.append(
            f"{len(failed)} artifact(s) failed to download. "
            "See manifest artifact download_error fields."
        )
        important_roles = {
            "financial_statements",
            "annual_report",
            "quarterly_report",
            "operating_review",
        }
        for artifact in failed:
            if artifact.role in important_roles:
                warnings.append(
                    f"Important analysis artifact failed to download: "
                    f"{artifact.role} ({artifact.filename})"
                )

    return warnings


def resolve_disclosure(
    ticker: Optional[str] = None,
    company_name: Optional[str] = None,
    cik: Optional[str] = None,
    intent: str = "quarterly",
    period: str = "latest",
    form: Optional[str] = None,
    file_format: str = "html",
    download: bool = True,
    include_exhibits: bool = True,
    out_dir: Optional[str] = None,
    market: str = "us",
    registry: Optional[ProviderRegistry] = None,
    config: Optional[SECConfig] = None,
) -> EvidencePackage:
    """Resolve a disclosure into a generic EvidencePackage.

    This is the generic disclosure-resolution entry point. For now, the default
    registry supports SEC EDGAR only.
    """
    if market != "us":
        raise UnsupportedMarketError(market)

    if period != "latest":
        raise UnsupportedPeriodError(period)

    provider_name = "sec_edgar"
    owns_registry = registry is None
    active_registry = registry or create_default_registry(config)

    try:
        query = EntityQuery(
            ticker=ticker,
            company_name=company_name,
            cik=cik,
            market=market,
        )
        identities = active_registry.get_identity(provider_name).resolve(query)
        if not identities:
            raise CompanyNotFoundError(ticker or company_name or cik or "unknown")

        entity = identities[0]
        request = DisclosureRequest(
            entity=entity,
            intent=intent,
            period=period,
            form_hint=form,
            file_format=file_format,
            download=download,
            include_exhibits=include_exhibits,
            out_dir=out_dir,
        )

        disclosure_provider = active_registry.get_disclosure(provider_name)
        disclosures = disclosure_provider.list_disclosures(entity, request)
        if not disclosures:
            raise FilingNotFoundError(
                ticker=entity.identifiers.get("ticker") or entity.legal_name,
                intent=intent,
                tried_forms=[form or "any"],
                period=period,
            )

        artifacts: List[Artifact] = []
        for disclosure in disclosures:
            artifacts.extend(disclosure_provider.fetch_artifacts(disclosure, request))

        package = EvidencePackage(
            request={
                "ticker": ticker,
                "company_name": company_name,
                "cik": cik,
                "market": market,
                "intent": intent,
                "period": period,
                "form_hint": form,
                "file_format": file_format,
                "download": download,
                "include_exhibits": include_exhibits,
                "out_dir": out_dir,
            },
            entity=entity,
            disclosures=disclosures,
            artifacts=artifacts,
            warnings=_build_generic_warnings(disclosures, artifacts, file_format),
            provenance=[{"provider": provider_name}],
        )

        if out_dir:
            write_evidence_manifest(package, out_dir)
            write_sources_json(package, out_dir)

        return package
    finally:
        if owns_registry:
            _close_registry_providers(active_registry)


def resolve_filing_package(
    ticker: Optional[str] = None,
    company_name: Optional[str] = None,
    cik: Optional[str] = None,
    intent: str = "quarterly",
    period: str = "latest",
    form: Optional[str] = None,
    file_format: str = "html",
    download: bool = True,
    include_exhibits: bool = True,
    out_dir: Optional[str] = None,
    market: str = "us",
    config: Optional[SECConfig] = None,
) -> FilingPackage:
    """Resolve and optionally download a filing package.

    This is the main Python API entry point.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL", "MSFT")
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
        warnings: List[str] = []
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
