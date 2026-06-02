# disclosure-filing-resolver

Deterministic SEC filing acquisition and exhibit classification layer for AI agent workflows.

**This project is not a financial analysis engine. It is a deterministic public disclosure acquisition and classification layer for agent workflows.**

## What It Does

- Resolves company identity from ticker, name, or CIK
- Locates the right SEC filing (10-K, 10-Q, 6-K, 20-F, 40-F)
- Downloads `.htm`/`.html` documents by default
- Expands and classifies 6-K exhibits (critical for foreign private issuers)
- Generates a machine-readable `manifest.json` for downstream LLM analysis
- Retries on transient SEC errors (429, 500, 502, 503, 504) with exponential backoff
- Tracks download status per document in the manifest

## What It Does Not Do

- Financial analysis or valuation
- Legal risk analysis
- LLM summarization
- XBRL parsing
- PDF OCR
- Web scraping or browser automation
- HKEX, CNINFO, ASX filings

## Why Deterministic SEC Resolution

Web search is unreliable for SEC filings. Links break, search results vary, and agents can hallucinate URLs. This project uses SEC EDGAR's deterministic data sources:

- `company_tickers.json` for ticker-to-CIK resolution
- `submissions/CIK*.json` for filing metadata
- Archive URLs constructed from accession numbers

Every URL in the output is a real, verifiable SEC link.

## Why 6-K Matters

Foreign private issuers (companies like TOYO, CSIQ listed on US exchanges but incorporated outside the US) file quarterly and annual reports under Form 6-K, not 10-Q or 10-K. The 6-K primary document is often just a cover page — the actual financial statements live in Exhibit 99.x files.

This resolver automatically:

1. Detects when a filing is a 6-K
2. Parses the filing index to find all exhibits
3. Classifies exhibits by role (financial statements, operating review, press release, etc.)
4. Downloads all relevant documents

**Note:** Exhibit expansion depends on SEC EDGAR filing index availability. If the filing index page is temporarily unavailable, the resolver will download the primary document only and continue without exhibits. Check the `documents` array in `manifest.json` for what was actually retrieved.

## Installation

```bash
pip install -e .

# or with dev dependencies
pip install -e ".[dev]"
```

## CLI Usage

```bash
# Set your SEC user agent (required for fair access)
export SEC_USER_AGENT="your_email@example.com disclosure-filing-resolver"

# Resolve latest quarterly filing for TOYO
filing-resolver resolve --ticker TOYO --intent quarterly --out artifacts/toyo

# Resolve latest annual report for Tesla
filing-resolver resolve --ticker TSLA --intent annual --out artifacts/tsla

# Resolve latest quarterly for Canadian Solar
filing-resolver resolve --ticker CSIQ --intent quarterly --out artifacts/csiq

# Get JSON output
filing-resolver resolve --ticker TOYO --intent quarterly --json

# Download without exhibits
filing-resolver resolve --ticker TOYO --intent quarterly --no-include-exhibits --out artifacts/toyo

# Find a specific form
filing-resolver resolve --ticker TOYO --intent specific_form --form 6-K --out artifacts/toyo
```

Both CLI entry points work:

```bash
filing-resolver resolve ...
disclosure-filing-resolver resolve ...
```

**Note:** v0.2.0 supports `--period latest` only. Specific year/quarter/date selection is planned for v0.3.0.

## Python API

```python
from disclosure_filing_resolver import resolve_filing_package

package = resolve_filing_package(
    ticker="TOYO",
    intent="quarterly",
    period="latest",
    file_format="html",
    download=True,
    out_dir="artifacts/toyo",
)

print(f"Company: {package.company.name}")
print(f"Filing: {package.selected_filing.form} filed {package.selected_filing.filing_date}")
print(f"Documents: {len(package.documents)}")

for doc in package.documents:
    status = doc.download_status or "unknown"
    print(f"  - {doc.role} [{status}]: {doc.local_path or doc.sec_url}")
```

## Agent Workflow Example

```python
from disclosure_filing_resolver import resolve_filing_package

# Agent receives user request: "Download TOYO latest quarterly report"
package = resolve_filing_package(
    ticker="TOYO",
    intent="quarterly",
    download=True,
    out_dir="artifacts/toyo",
)

# Check for failed downloads
failed = [d for d in package.documents if d.download_status == "failed"]
if failed:
    print(f"Warning: {len(failed)} document(s) failed to download")

# Read manifest for downstream analysis
manifest_path = f"{package.request.out_dir}/manifest.json"

# Pass to sec-filing-legal-decoder or other analysis tool
# downstream_project.analyze(manifest_path)
```

## Manifest Schema

The `manifest.json` output contains:

```json
{
  "schema_version": "1.0",
  "request": { "ticker": "TOYO", "intent": "quarterly", ... },
  "company": { "name": "TOYO Co., Ltd", "ticker": "TOYO", "cik": "1985273", ... },
  "selected_filing": {
    "form": "6-K",
    "filing_date": "2026-05-18",
    "accession_number": "0001213900-26-058577",
    ...
  },
  "documents": [
    {
      "role": "financial_statements",
      "priority": 100,
      "filename": "...",
      "sec_url": "...",
      "local_path": "...",
      "file_format": "html",
      "confidence": 0.98,
      "download_status": "downloaded",
      "download_error": null
    }
  ],
  "warnings": ["6-K primary document may be a cover page; use exhibits for analysis."]
}
```

### Download Status Values

| Status | Meaning |
|---|---|
| `downloaded` | Document downloaded successfully |
| `failed` | Download failed; see `download_error` for details |
| `skipped` | Download was not requested (`--no-download`) |
| `null` | Status not yet determined |

## Smoke Test Results

Tested against live SEC EDGAR (2026-06-01):

| Ticker | Intent | Form | Result |
|---|---|---|---|
| TSLA | annual | 10-K | ✅ Resolved, downloaded primary HTML |
| TOYO | quarterly | 6-K | ✅ Resolved, downloaded cover page |
| CSIQ | quarterly | 6-K | ✅ Resolved, downloaded cover page |

**Note:** SEC filing index pages were temporarily unavailable during testing, so exhibit expansion returned only the primary document. This is expected SEC infrastructure behavior — the resolver handles it gracefully.

## SEC User-Agent and Fair Access

SEC EDGAR requires a declared User-Agent. Set it before running:

```bash
export SEC_USER_AGENT="your_email@example.com disclosure-filing-resolver"
```

If not set, a default user agent is used with a warning. SEC expects reasonable rate limits (max 10 requests/second, we default to 5).

The client automatically retries on transient errors (429, 500, 502, 503, 504) with exponential backoff. Non-retryable errors (400, 401, 403, 404) raise `SECRequestError` immediately with an agent-friendly message.

## Roadmap

### v0.2.0 (current)

- [x] SEC EDGAR provider with retry/backoff
- [x] Ticker/CIK/name resolution
- [x] Filing selection (annual, quarterly, semiannual, interim, specific form)
- [x] 6-K exhibit parsing and classification
- [x] HTML download with status tracking
- [x] Manifest generation with download_status fields
- [x] CLI (`filing-resolver resolve ...`) and Python API
- [x] Period validation (v0.2.0: `latest` only)

### v0.3.0

- [ ] Optional `fetch` adapter for `sec-filing-legal-decoder`
- [ ] Period filtering (YYYY, YYYYQ1-Q4, YYYY-MM-DD)
- [ ] XBRL data extraction
- [ ] Full-text search within filings

### v0.4.0

- [ ] HKEX provider
- [ ] CNINFO provider
- [ ] PDF OCR fallback
- [ ] MCP server interface

## License

MIT
