"""Ticker to CIK resolution using SEC company_tickers.json."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Union

from disclosure_filing_resolver.exceptions import (
    AmbiguousCompanyError,
    CompanyNotFoundError,
)
from disclosure_filing_resolver.models import CompanyIdentity, ResolveRequest
from disclosure_filing_resolver.providers.sec_edgar.client import SECEdgarClient


def _pad_cik(cik: Union[int, str]) -> str:
    """Pad CIK to 10 digits with leading zeros."""
    return str(cik).zfill(10)


def _strip_cik(cik: Union[int, str]) -> str:
    """Remove leading zeros from CIK for archive URLs."""
    return str(int(cik))


class TickerResolver:
    """Resolve ticker/company name to CIK using SEC data."""

    def __init__(self, client: SECEdgarClient) -> None:
        self._client = client
        self._tickers: Optional[Dict[str, dict]] = None

    def _load_tickers(self) -> Dict[str, dict]:
        """Load company_tickers.json from SEC."""
        if self._tickers is None:
            data = self._client.get_json(self._client.config.tickers_url)
            # data is keyed by string integer: {"1": {"ticker": "AAPL", ...}, ...}
            self._tickers = {}
            for _key, entry in data.items():
                ticker = entry.get("ticker", "")
                if ticker:
                    self._tickers[ticker.upper()] = entry
        return self._tickers

    def resolve(self, request: ResolveRequest) -> CompanyIdentity:
        """Resolve company identity from request.

        Priority: CIK > ticker > company_name.
        """
        if request.cik:
            return self._resolve_by_cik(request.cik)

        if request.ticker:
            return self._resolve_by_ticker(request.ticker.upper())

        if request.company_name:
            return self._resolve_by_name(request.company_name)

        raise CompanyNotFoundError(
            query="empty request (no ticker, company, or CIK)", provider="sec_edgar"
        )

    def _resolve_by_cik(self, cik: str) -> CompanyIdentity:
        """Resolve directly by CIK."""
        cik10 = _pad_cik(cik)
        cik_clean = _strip_cik(cik)
        # Look up name from tickers data
        tickers = self._load_tickers()
        for _ticker, entry in tickers.items():
            if str(entry.get("cik_str", "")) == cik_clean:
                return CompanyIdentity(
                    name=entry.get("title", "Unknown"),
                    ticker=entry.get("ticker"),
                    cik=cik_clean,
                    cik10=cik10,
                )
        # CIK found but not in tickers file - use a placeholder name
        return CompanyIdentity(
            name=f"Company CIK {cik_clean}",
            ticker=None,
            cik=cik_clean,
            cik10=cik10,
        )

    def _resolve_by_ticker(self, ticker: str) -> CompanyIdentity:
        """Resolve by ticker symbol."""
        tickers = self._load_tickers()
        if ticker not in tickers:
            raise CompanyNotFoundError(query=ticker, provider="sec_edgar")
        entry = tickers[ticker]
        cik = entry.get("cik_str", 0)
        return CompanyIdentity(
            name=entry.get("title", "Unknown"),
            ticker=ticker,
            cik=_strip_cik(cik),
            cik10=_pad_cik(cik),
        )

    def _resolve_by_name(self, name: str) -> CompanyIdentity:
        """Resolve by company name (case-insensitive substring match)."""
        tickers = self._load_tickers()
        name_upper = name.upper()
        matches: List[Tuple[str, dict]] = []
        for ticker, entry in tickers.items():
            entry_name = entry.get("title", "").upper()
            if name_upper in entry_name or entry_name in name_upper:
                matches.append((ticker, entry))
            elif any(word in entry_name for word in name_upper.split() if len(word) > 3):
                matches.append((ticker, entry))

        if not matches:
            raise CompanyNotFoundError(query=name, provider="sec_edgar")
        if len(matches) > 2:
            raise AmbiguousCompanyError(
                query=name, candidates=[f"{t} ({e.get('title', '')})" for t, e in matches[:5]]
            )

        # If exactly 1 or 2 matches, pick the best
        ticker, entry = matches[0]
        cik = entry.get("cik_str", 0)
        return CompanyIdentity(
            name=entry.get("title", "Unknown"),
            ticker=ticker,
            cik=_strip_cik(cik),
            cik10=_pad_cik(cik),
        )
