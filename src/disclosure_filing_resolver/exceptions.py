"""Agent-friendly exceptions for disclosure-filing-resolver."""


class ResolverError(Exception):
    """Base exception for resolver errors."""


class CompanyNotFoundError(ResolverError):
    """Could not resolve a company identity from the given input."""

    def __init__(self, query: str, provider: str = "sec_edgar") -> None:
        self.query = query
        self.provider = provider
        super().__init__(
            f"Could not find company for '{query}' using provider '{provider}'. "
            "Check ticker, company name, or CIK."
        )


class AmbiguousCompanyError(ResolverError):
    """Multiple companies matched the input."""

    def __init__(self, query: str, candidates: list[str]) -> None:
        self.query = query
        self.candidates = candidates
        super().__init__(
            f"Ambiguous company match for '{query}'. "
            f"Candidates: {', '.join(candidates)}. "
            "Provide a more specific input (CIK or exact name)."
        )


class FilingNotFoundError(ResolverError):
    """No filing matched the requested intent and period."""

    def __init__(
        self,
        ticker: str,
        intent: str,
        tried_forms: list[str],
        period: str = "latest",
    ) -> None:
        self.ticker = ticker
        self.intent = intent
        self.tried_forms = tried_forms
        self.period = period
        super().__init__(
            f"Could not find a {intent} filing for '{ticker}' (period={period}). "
            f"Tried forms: {', '.join(tried_forms)}. "
            "Try --intent annual, --form 6-K, or check the ticker."
        )


class DocumentNotFoundError(ResolverError):
    """A specific document could not be found or downloaded."""

    def __init__(self, document: str, url: str | None = None) -> None:
        self.document = document
        self.url = url
        msg = f"Document not found: {document}"
        if url:
            msg += f" (URL: {url})"
        super().__init__(msg)


class SECRequestError(ResolverError):
    """An HTTP request to SEC EDGAR failed."""

    def __init__(self, url: str, status: int | None = None, detail: str = "") -> None:
        self.url = url
        self.status = status
        msg = f"SEC request failed for {url}"
        if status:
            msg += f" (status {status})"
        if detail:
            msg += f": {detail}"
        super().__init__(msg)


class UnsupportedMarketError(ResolverError):
    """The requested market is not supported in this version."""

    def __init__(self, market: str) -> None:
        self.market = market
        super().__init__(
            f"Market '{market}' is not supported in v0.1.0. "
            "Supported markets: us (SEC EDGAR)."
        )


class UnsupportedPeriodError(ResolverError):
    """The requested period is not supported in this version."""

    def __init__(self, period: str) -> None:
        self.period = period
        super().__init__(
            f"v0.1.0 currently supports only --period latest. "
            f"Received: {period}. "
            "Specific period filtering is planned for v0.2.0."
        )
