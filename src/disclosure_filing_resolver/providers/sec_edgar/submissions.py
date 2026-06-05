"""Parse SEC submissions JSON for a company."""

from __future__ import annotations

from typing import Any, Dict, List

from disclosure_filing_resolver.providers.sec_edgar.client import SECEdgarClient


def get_submissions(client: SECEdgarClient, cik10: str) -> Dict[str, Any]:
    """Fetch the submissions JSON for a company CIK.

    Returns the full submissions data dict.
    """
    url = f"{client.config.base_url}/submissions/CIK{cik10}.json"
    return client.get_json(url, use_cache=True)


def get_recent_filings(submissions: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the recent filings dict from submissions JSON.

    SEC submissions JSON has structure:
    {
      "filings": {
        "recent": {
          "form": [...],
          "filingDate": [...],
          ...
        },
        "files": [...]  # older filing chunks
      }
    }
    """
    return submissions.get("filings", {}).get("recent", {})


def get_filing_lists(submissions: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get list of filing chunk file references for older filings."""
    return submissions.get("filings", {}).get("files", [])


def get_filings_as_rows(recent: Dict[str, Any], num_filings: int) -> List[Dict[str, str]]:
    """Convert the columnar recent filings dict to a list of row dicts.

    recent is like:
    {
      "form": ["10-K", "10-Q", ...],
      "filingDate": ["2026-03-01", "2025-12-01", ...],
      ...
    }

    Returns list of dicts, one per filing.
    """
    if not recent:
        return []

    # Get the number of entries from the first key
    first_key = next(iter(recent), None)
    if first_key is None:
        return []

    n = len(recent[first_key])
    rows: List[Dict[str, str]] = []
    for i in range(min(n, num_filings)):
        row: Dict[str, str] = {}
        for key, values in recent.items():
            if isinstance(values, list) and i < len(values):
                row[key] = str(values[i]) if values[i] is not None else ""
            else:
                row[key] = ""
        rows.append(row)
    return rows
