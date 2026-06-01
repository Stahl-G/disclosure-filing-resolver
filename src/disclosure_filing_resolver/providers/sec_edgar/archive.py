"""SEC archive URL construction."""

from __future__ import annotations


def strip_leading_zeros(cik: str) -> str:
    """Remove leading zeros from CIK for archive URLs."""
    return str(int(cik))


def strip_dashes(accession: str) -> str:
    """Remove dashes from accession number."""
    return accession.replace("-", "")


def build_archive_url(cik: str, accession: str, filename: str) -> str:
    """Build SEC archive URL for a document.

    https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{filename}
    """
    cik_clean = strip_leading_zeros(cik)
    acc_clean = strip_dashes(accession)
    return f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{acc_clean}/{filename}"


def build_filing_index_url(cik: str, accession: str) -> str:
    """Build filing index URL.

    https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{accession_no_dashes}-index.html
    """
    cik_clean = strip_leading_zeros(cik)
    acc_clean = strip_dashes(accession)
    return f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{acc_clean}/{acc_clean}-index.html"


def build_primary_url(cik: str, accession: str, primary_doc: str) -> str:
    """Build URL for the primary document."""
    return build_archive_url(cik, accession, primary_doc)
