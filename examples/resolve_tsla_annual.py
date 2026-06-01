"""Example: Resolve TSLA latest annual filing."""

from disclosure_filing_resolver import resolve_filing_package

def main():
    package = resolve_filing_package(
        ticker="TSLA",
        intent="annual",
        period="latest",
        file_format="html",
        download=True,
        out_dir="artifacts/tsla",
    )

    print(f"Company: {package.company.name} (CIK {package.company.cik})")
    print(f"Filing: {package.selected_filing.form} filed {package.selected_filing.filing_date}")
    print(f"Documents: {len(package.documents)}")

    for doc in package.documents:
        print(f"  [{doc.role}] {doc.filename}")


if __name__ == "__main__":
    main()
