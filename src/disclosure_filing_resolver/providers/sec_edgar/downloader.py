"""Download filing documents to local filesystem."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

from disclosure_filing_resolver.models import FilingDocument
from disclosure_filing_resolver.providers.sec_edgar.client import SECEdgarClient


def _sanitize_filename(name: str) -> str:
    """Make a filename safe for filesystem."""
    # Replace problematic characters
    safe = re.sub(r'[<>:"/\\|?*]', "_", name)
    # Collapse multiple underscores
    safe = re.sub(r"_+", "_", safe)
    return safe.strip("_")


def _make_local_name(
    doc: FilingDocument,
    company_ticker: str,
    filing_date: str,
    form: str,
    index: int,
) -> str:
    """Generate a readable local filename.

    Example: acme_2026_q1_6k_cover.htm
    """
    # Parse year and quarter from filing date
    year = filing_date[:4] if filing_date else "unknown"
    month = filing_date[5:7] if len(filing_date) >= 7 else "00"
    quarter = f"q{(int(month) - 1) // 3 + 1}" if month.isdigit() and month != "00" else "q?"

    ticker = company_ticker.lower() if company_ticker else "unknown"
    form_slug = form.lower().replace("-", "").replace("/", "")
    role_slug = _sanitize_filename(doc.role)

    # Get file extension
    ext = Path(doc.filename).suffix or ".htm"

    if doc.role == "cover":
        return f"{ticker}_{year}_{quarter}_{form_slug}_cover{ext}"

    # For exhibits, include the exhibit number if available
    ex_match = re.search(r"ex(?:hibit)?[\s-]*99[\s.-]*(\d+)", doc.filename, re.IGNORECASE)
    ex_num = f"ex99-{ex_match.group(1)}" if ex_match and ex_match.group(1) else f"doc{index}"

    return f"{ticker}_{year}_{quarter}_{form_slug}_{ex_num}_{role_slug}{ext}"


def download_documents(
    client: SECEdgarClient,
    documents: List[FilingDocument],
    out_dir: str,
    company_ticker: str,
    filing_date: str,
    form: str,
) -> List[FilingDocument]:
    """Download documents to local filesystem.

    Updates each document's local_path.
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    for i, doc in enumerate(documents):
        local_name = _make_local_name(doc, company_ticker, filing_date, form, i)
        local_path = out_path / local_name

        try:
            client.download(doc.sec_url, local_path)
            doc.local_path = str(local_path)
            doc.download_status = "downloaded"
        except Exception as exc:
            # Don't fail the whole package for one document
            doc.local_path = None
            doc.download_status = "failed"
            doc.download_error = str(exc)[:200]

    return documents
