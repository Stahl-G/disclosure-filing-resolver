"""Example: Resolve CSIQ latest quarterly filing."""

from disclosure_filing_resolver import resolve_filing_package


def main():
    package = resolve_filing_package(
        ticker="CSIQ",
        intent="quarterly",
        period="latest",
        file_format="html",
        download=True,
        out_dir="artifacts/csiq",
    )

    print(f"Company: {package.company.name} (CIK {package.company.cik})")
    print(f"Filing: {package.selected_filing.form} filed {package.selected_filing.filing_date}")
    print(f"Documents: {len(package.documents)}")

    # Show recommended analysis documents
    useful = [d for d in package.documents if d.role not in ("unknown", "cover")]
    if useful:
        print("\nRecommended for analysis:")
        for doc in sorted(useful, key=lambda d: -d.priority):
            print(f"  - {doc.role}: {doc.local_path or doc.sec_url}")


if __name__ == "__main__":
    main()
