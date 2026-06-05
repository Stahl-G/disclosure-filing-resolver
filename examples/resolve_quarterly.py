"""Example: Resolve a company's latest quarterly filing.

Replace YOUR_TICKER with any SEC-listed ticker (e.g. AAPL, MSFT, GOOG).
"""

import os
import sys

from disclosure_filing_resolver import resolve_filing_package


def main():
    ticker = os.environ.get("EXAMPLE_TICKER", "AAPL")
    if len(sys.argv) > 1:
        ticker = sys.argv[1]

    package = resolve_filing_package(
        ticker=ticker,
        intent="quarterly",
        period="latest",
        file_format="html",
        download=True,
        out_dir=f"artifacts/{ticker.lower()}",
    )

    print(f"Company: {package.company.name} (CIK {package.company.cik})")
    print(f"Filing: {package.selected_filing.form} filed {package.selected_filing.filing_date}")
    print(f"Accession: {package.selected_filing.accession_number}")
    print(f"Documents: {len(package.documents)}")
    print()

    for doc in package.documents:
        status = "downloaded" if doc.local_path else "not downloaded"
        print(f"  [{doc.role}] {doc.filename} ({status})")

    if package.warnings:
        print()
        for w in package.warnings:
            print(f"  Warning: {w}")


if __name__ == "__main__":
    main()
