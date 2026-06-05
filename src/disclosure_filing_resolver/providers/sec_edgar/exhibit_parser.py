"""Parse filing index HTML to extract document list."""

from __future__ import annotations

from typing import List

from bs4 import BeautifulSoup

from disclosure_filing_resolver.models import FilingDocument
from disclosure_filing_resolver.providers.sec_edgar.archive import build_archive_url


def parse_filing_index(html: str, cik: str, accession: str) -> List[FilingDocument]:
    """Parse a filing index HTML page to extract document rows.

    Looks for the Document Format Files table which contains columns like:
    Document Type, Description, Filename, etc.
    """
    soup = BeautifulSoup(html, "html.parser")
    documents: List[FilingDocument] = []

    # Find the table with document format files
    tables = soup.find_all("table")
    doc_table = None
    for table in tables:
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if any("document" in h or "filename" in h or "description" in h for h in headers):
            doc_table = table
            break

    if doc_table is None:
        # Try to find any table with links to .htm/.html/.pdf files
        for table in tables:
            links = table.find_all("a", href=True)
            doc_links = [a for a in links if a["href"].endswith((".htm", ".html", ".pdf"))]
            if doc_links:
                doc_table = table
                break

    if doc_table is None:
        return documents

    rows = doc_table.find_all("tr")
    for row in rows:
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue

        # Find the document link
        link = row.find("a", href=True)
        if not link:
            continue

        href = link.get("href", "")
        if not href.endswith((".htm", ".html", ".pdf")):
            continue

        # Extract filename from href
        filename = href.split("/")[-1]
        if not filename or filename.endswith("-index.html"):
            continue

        # Extract text from cells for description
        cell_texts = [c.get_text(strip=True) for c in cells]

        # Try to identify document type and description
        doc_type = ""
        description = ""
        for text in cell_texts:
            if text and text != filename and not text.startswith("http"):
                if not doc_type:
                    doc_type = text
                elif not description:
                    description = text

        # Build URL
        sec_url = build_archive_url(cik, accession, filename)

        # Determine file format
        file_format = "html"
        if filename.endswith(".pdf"):
            file_format = "pdf"
        elif filename.endswith(".xml"):
            file_format = "xml"

        documents.append(
            FilingDocument(
                filename=filename,
                sec_url=sec_url,
                file_format=file_format,
                document_type=doc_type or None,
                description=description or None,
                confidence=0.8,
            )
        )

    return documents
