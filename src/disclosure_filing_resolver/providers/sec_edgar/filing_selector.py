"""Select the best filing from SEC submissions based on intent."""

from __future__ import annotations

from typing import Dict, List

from disclosure_filing_resolver.exceptions import FilingNotFoundError
from disclosure_filing_resolver.models import FilingCandidate, ResolveRequest
from disclosure_filing_resolver.providers.sec_edgar.archive import (
    build_filing_index_url,
    build_primary_url,
)
from disclosure_filing_resolver.providers.sec_edgar.client import SECEdgarClient
from disclosure_filing_resolver.providers.sec_edgar.submissions import (
    get_filings_as_rows,
    get_recent_filings,
)

# Annual form priority (higher = better)
ANNUAL_FORM_PRIORITY: Dict[str, int] = {
    "10-K": 100,
    "20-F": 95,
    "40-F": 90,
    "10-K/A": 80,
    "20-F/A": 75,
    "40-F/A": 70,
}

# Quarterly form priority
QUARTERLY_FORM_PRIORITY: Dict[str, int] = {
    "10-Q": 100,
    "10-Q/A": 80,
}

# Semiannual/interim keywords for 6-K scoring
SEMIANNUAL_KEYWORDS = [
    "interim",
    "half year",
    "h1",
    "six months ended",
    "unaudited interim",
    "interim financial statements",
    "first half",
    "semiannual",
    "semi-annual",
]

QUARTERLY_6K_KEYWORDS = [
    "quarterly results",
    "quarter",
    "q1",
    "q2",
    "q3",
    "three months ended",
    "interim financial statements",
    "unaudited interim",
    "financial results",
    "earnings release",
    "operating and financial review",
    "results of operations",
]


def _score_text_match(text: str, keywords: List[str]) -> float:
    """Score how well text matches a set of keywords."""
    text_lower = text.lower()
    score = 0.0
    for kw in keywords:
        if kw.lower() in text_lower:
            score += 1.0
    return min(score, 3.0)  # cap at 3


def select_filing(
    client: SECEdgarClient,
    cik: str,
    cik10: str,
    request: ResolveRequest,
) -> FilingCandidate:
    """Select the best filing for the given intent from SEC submissions.

    Args:
        client: SEC EDGAR client
        cik: CIK without leading zeros
        cik10: CIK padded to 10 digits
        request: The resolve request

    Returns:
        Best FilingCandidate

    Raises:
        FilingNotFoundError: if no suitable filing found
    """
    from disclosure_filing_resolver.providers.sec_edgar.submissions import get_submissions

    submissions = get_submissions(client, cik10)
    recent = get_recent_filings(submissions)
    rows = get_filings_as_rows(recent, num_filings=100)

    if not rows:
        raise FilingNotFoundError(
            ticker=request.ticker or request.company_name or request.cik or "unknown",
            intent=request.intent,
            tried_forms=["any"],
            period=request.period,
        )

    intent = request.intent

    if intent == "specific_form" and request.form_hint:
        candidates = _filter_by_form(rows, request.form_hint, cik, cik10, request)
        if not candidates:
            raise FilingNotFoundError(
                ticker=request.ticker or "unknown",
                intent=intent,
                tried_forms=[request.form_hint],
                period=request.period,
            )
        return max(candidates, key=lambda c: c.filing_date)

    if intent == "annual":
        return _select_annual(rows, cik, cik10, request)

    if intent == "quarterly":
        return _select_quarterly(rows, cik, cik10, request, client)

    if intent in ("semiannual", "interim"):
        return _select_semiannual(rows, cik, cik10, request, client)

    if intent == "earnings_release":
        return _select_quarterly(rows, cik, cik10, request, client)

    raise FilingNotFoundError(
        ticker=request.ticker or "unknown",
        intent=intent,
        tried_forms=["unknown intent"],
        period=request.period,
    )


def _make_candidate(
    row: Dict[str, str], cik: str, cik10: str, request: ResolveRequest
) -> FilingCandidate:
    """Create a FilingCandidate from a submissions row."""
    accession = row.get("accessionNumber", "")
    primary_doc = row.get("primaryDocument", "")
    return FilingCandidate(
        form=row.get("form", ""),
        filing_date=row.get("filingDate", ""),
        report_date=row.get("reportDate") or None,
        accession_number=accession,
        primary_document=primary_doc,
        primary_doc_description=row.get("primaryDocDescription") or None,
        primary_url=build_primary_url(cik, accession, primary_doc),
        index_url=build_filing_index_url(cik, accession),
    )


def _filter_by_form(
    rows: List[Dict[str, str]], form: str, cik: str, cik10: str, request: ResolveRequest
) -> List[FilingCandidate]:
    """Filter rows by form type (exact match, case-insensitive)."""
    form_upper = form.upper()
    candidates = []
    for row in rows:
        row_form = row.get("form", "").upper()
        if row_form == form_upper:
            candidates.append(_make_candidate(row, cik, cik10, request))
    return candidates


def _select_annual(
    rows: List[Dict[str, str]], cik: str, cik10: str, request: ResolveRequest
) -> FilingCandidate:
    """Select latest annual filing."""
    tried_forms = []
    for form, _priority in sorted(ANNUAL_FORM_PRIORITY.items(), key=lambda x: -x[1]):
        tried_forms.append(form)
        candidates = _filter_by_form(rows, form, cik, cik10, request)
        if candidates:
            best = max(candidates, key=lambda c: c.filing_date)
            best.score = ANNUAL_FORM_PRIORITY.get(form, 50)
            best.reasons = [f"Latest {form} filing"]
            if "/A" in form:
                best.reasons.append(f"Warning: selected amended filing {form}")
            return best

    raise FilingNotFoundError(
        ticker=request.ticker or "unknown",
        intent="annual",
        tried_forms=tried_forms,
        period=request.period,
    )


def _select_quarterly(
    rows: List[Dict[str, str]],
    cik: str,
    cik10: str,
    request: ResolveRequest,
    client: SECEdgarClient,
) -> FilingCandidate:
    """Select latest quarterly filing, falling back to 6-K."""
    # Try 10-Q first
    tried_forms = ["10-Q"]
    candidates_10q = _filter_by_form(rows, "10-Q", cik, cik10, request)
    if not candidates_10q:
        candidates_10q = _filter_by_form(rows, "10-Q/A", cik, cik10, request)
        tried_forms.append("10-Q/A")

    if candidates_10q:
        best = max(candidates_10q, key=lambda c: c.filing_date)
        best.score = 100
        best.reasons = ["Latest 10-Q quarterly filing"]
        return best

    # Fall back to 6-K
    tried_forms.append("6-K")
    candidates_6k = _filter_by_form(rows, "6-K", cik, cik10, request)
    if not candidates_6k:
        raise FilingNotFoundError(
            ticker=request.ticker or "unknown",
            intent="quarterly",
            tried_forms=tried_forms,
            period=request.period,
        )

    # Score 6-K candidates by description relevance
    for c in candidates_6k:
        desc = f"{c.primary_doc_description or ''}"
        c.score = 50 + _score_text_match(desc, QUARTERLY_6K_KEYWORDS)
        c.reasons = [f"6-K filing ({c.filing_date})"]

    best = max(candidates_6k, key=lambda c: c.score)
    best.reasons.append("Foreign private issuer quarterly material may be filed as 6-K")
    return best


def _select_semiannual(
    rows: List[Dict[str, str]],
    cik: str,
    cik10: str,
    request: ResolveRequest,
    client: SECEdgarClient,
) -> FilingCandidate:
    """Select latest semiannual/interim filing, typically a 6-K."""
    tried_forms = ["6-K"]
    candidates_6k = _filter_by_form(rows, "6-K", cik, cik10, request)

    if not candidates_6k:
        # Try 20-F (annual may contain semiannual info)
        tried_forms.append("20-F")
        candidates_20f = _filter_by_form(rows, "20-F", cik, cik10, request)
        if candidates_20f:
            best = max(candidates_20f, key=lambda c: c.filing_date)
            best.score = 40
            best.reasons = ["No 6-K interim filing found; using 20-F annual"]
            return best

        raise FilingNotFoundError(
            ticker=request.ticker or "unknown",
            intent=request.intent,
            tried_forms=tried_forms,
            period=request.period,
        )

    for c in candidates_6k:
        desc = f"{c.primary_doc_description or ''}"
        c.score = 50 + _score_text_match(desc, SEMIANNUAL_KEYWORDS)
        c.reasons = [f"6-K filing ({c.filing_date})"]

    best = max(candidates_6k, key=lambda c: c.score)
    best.reasons.append("6-K semiannual/interim filing for foreign private issuer")
    return best
