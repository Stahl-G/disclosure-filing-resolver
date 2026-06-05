"""Example: Agent workflow using disclosure-filing-resolver.

This shows how an AI agent would use the resolver to acquire SEC filings
and pass them to a downstream analysis tool.
"""

import json
from pathlib import Path

from disclosure_filing_resolver import resolve_filing_package


def agent_workflow(company_query: str, intent: str = "quarterly"):
    """Simulate an agent workflow:

    1. User asks for a company's filing
    2. Resolver acquires and classifies documents
    3. Agent reads manifest and provides analysis
    """
    print(f"User request: '{company_query}' (intent: {intent})")
    print()

    # Step 1: Resolve the filing
    ticker = company_query.upper().split()[0]  # simple extraction
    package = resolve_filing_package(
        ticker=ticker,
        intent=intent,
        download=True,
        out_dir=f"artifacts/{ticker.lower()}",
    )

    # Step 2: Read manifest
    manifest_path = Path(package.request.out_dir) / "manifest.json"
    manifest = json.loads(manifest_path.read_text())

    # Step 3: Identify useful documents
    financial_docs = [
        d for d in manifest["documents"]
        if d["role"] in ("financial_statements", "operating_review")
    ]

    print(f"Resolved: {manifest['company']['name']}")
    print(
        f"Filing: {manifest['selected_filing']['form']} "
        f"({manifest['selected_filing']['filing_date']})"
    )
    print(f"Useful documents for analysis: {len(financial_docs)}")
    for doc in financial_docs:
        print(f"  - {doc['role']}: {doc.get('local_path', doc['sec_url'])}")

    # Step 4: In a real agent, you would now:
    # - Read the downloaded HTML files
    # - Pass them to an LLM for analysis
    # - Generate a report or answer the user's question

    return package


if __name__ == "__main__":
    agent_workflow("TOYO quarterly", "quarterly")
    print()
    agent_workflow("TSLA annual", "annual")
