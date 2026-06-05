# disclosure-filing-resolver

Deterministic SEC filing acquisition and exhibit classification layer for AI agent workflows.

**This project is not a financial analysis engine. It is a deterministic public disclosure acquisition and classification layer for agent workflows.**

## What It Does

- Resolves company identity from ticker, name, or CIK
- Locates the right SEC filing (10-K, 10-Q, 6-K, 20-F, 40-F)
- Downloads `.htm`/`.html` documents by default
- Expands and classifies 6-K exhibits (critical for foreign private issuers)
- Generates a machine-readable `manifest.json` for downstream LLM analysis
- Exports `sources.json` for integration with [multi-agent-brief-workflow](https://github.com/Stahl-G/multi-agent-brief-workflow)
- Enriches entities with XBRL financial facts from SEC companyfacts API
- Parses Inline XBRL (iXBRL) facts from filing HTML documents
- Retries on transient SEC errors (429, 500, 502, 503, 504) with exponential backoff
- Tracks download status per document in the manifest

## What It Does Not Do

- Financial analysis or valuation
- Legal risk analysis
- LLM summarization
- PDF OCR
- Web scraping or browser automation
- HKEX, CNINFO, ASX filings

## What's New in v0.3.0

v0.2.0 was a **SEC-only tool** — one hardcoded path from ticker to filing download.
v0.3.0 is a **pluggable disclosure resolution layer** with provider abstraction, structured data extraction, and agent-workflow integration.

### Architecture shift

```
v0.2.0:  ticker → SECEdgarProvider → FilingPackage (SEC-specific)

v0.3.0:  ticker → IdentityProvider    → EntityIdentity    (generic entity)
              → DisclosureProvider   → EvidencePackage   (generic evidence bundle)
              → EnrichmentProvider   → Observation[]      (structured facts)
```

### New in v0.3.0

| Feature | Description |
|---------|-------------|
| **Generic data models** | `EntityIdentity`, `DisclosureRecord`, `Artifact`, `EvidencePackage`, `Observation` — provider-agnostic |
| **Provider registry** | `IdentityProvider`, `DisclosureProvider`, `EnrichmentProvider` abstract base classes — register any data source |
| **`resolve_disclosure()`** | New generic entry point returning `EvidencePackage` |
| **`sources.json` export** | `--sources-json` CLI flag — output consumable by [multi-agent-brief-workflow](https://github.com/Stahl-G/multi-agent-brief-workflow) |
| **XBRL enrichment** | `enrich` CLI subcommand — extract revenue, net income, assets, EPS from SEC companyfacts API |
| **iXBRL parser** | Extract Inline XBRL facts from filing HTML documents |
| **argparse CLI** | Python 3.9+ compatible (replaces typer dependency) |

### Backward compatibility

All v0.2.0 APIs are preserved — zero breaking changes:

- `resolve_filing_package()` still returns `FilingPackage`
- `CompanyIdentity`, `FilingCandidate`, `FilingDocument` still work
- `filing-resolver resolve --ticker TOYO` behaves identically
- Legacy models have `.to_entity_identity()`, `.to_disclosure_record()`, `.to_artifact()` conversion methods

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

# Export sources.json for multi-agent-brief-workflow
filing-resolver resolve --ticker TOYO --intent quarterly --sources-json

# Download without exhibits
filing-resolver resolve --ticker TOYO --intent quarterly --no-include-exhibits --out artifacts/toyo

# Find a specific form
filing-resolver resolve --ticker TOYO --intent specific_form --form 6-K --out artifacts/toyo

# Enrich with XBRL financial facts
filing-resolver enrich --ticker TOYO
filing-resolver enrich --ticker TSLA --max-facts 50
```

Both CLI entry points work:

```bash
filing-resolver resolve ...
disclosure-filing-resolver resolve ...
```

**Note:** v0.3.0 supports `--period latest` only. Specific year/quarter/date selection is planned for v0.4.0.

## Python API

### Legacy API (SEC-specific)

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

### Generic API (provider-agnostic)

```python
from disclosure_filing_resolver import resolve_disclosure, evidence_to_sources

# Returns a generic EvidencePackage
evidence = resolve_disclosure(
    ticker="TOYO",
    intent="quarterly",
    download=True,
    out_dir="artifacts/toyo",
)

# Convert to sources.json format for multi-agent-brief-workflow
sources = evidence_to_sources(evidence)
for source in sources:
    print(f"{source['title']} — {source['url']}")
```

### XBRL Enrichment

```python
from disclosure_filing_resolver import resolve_disclosure, create_default_registry

registry = create_default_registry()
evidence = resolve_disclosure(ticker="TOYO", registry=registry)

# The evidence package includes observations from XBRL enrichment
for obs in evidence.observations:
    print(f"{obs.category}: {obs.value} {obs.unit} ({obs.period})")
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

## Multi-Agent Brief Workflow Integration

This project integrates with [multi-agent-brief-workflow](https://github.com/Stahl-G/multi-agent-brief-workflow) as a source provider, enabling SEC filing data to flow directly into audit-ready executive briefs.

### How It Works

```text
multi-agent-brief sources decide  →  generates filing_sources candidates
                                    ↓
source_candidates.yaml            →  user reviews tickers, enables/disables
                                    ↓
sources decide --merge            →  enables filing_resolver in sources.yaml
                                    ↓
FilingResolverProvider            →  calls resolve_disclosure() per ticker
                                    ↓
EvidencePackage → SourceItems     →  enters Scout → Screener → Claim Ledger
XBRL observations → claims        →  structured financial facts in brief
```

### What the Integration Provides

| Feature | Description |
|---------|-------------|
| SEC filing sources | 10-K, 10-Q, 8-K, 6-K documents automatically fetched as source material |
| XBRL financial claims | Revenue, net income, assets, EPS extracted as structured Claim Ledger entries |
| Source traceability | Every claim carries a SEC EDGAR URL for audit |
| 6-K exhibit expansion | Foreign private issuer filings expanded to include actual financial statements |

### Configuration in multi-agent-brief-workflow

Add to `sources.yaml`:

```yaml
filing_resolver:
  enabled: true
  tickers:
    - TOYO
    - TSLA
  filing_types:
    - 10-K
    - 10-Q
    - 8-K
  xbrl: true
```

Or auto-discover via `sources decide`:

```bash
# Generate candidates (includes SEC filing suggestions)
multi-agent-brief sources decide --config workspace/config.yaml

# Review and merge
multi-agent-brief sources decide --config workspace/config.yaml --merge
```

### CLI Integration

The `--sources-json` flag outputs a `sources.json` file consumable by multi-agent-brief-workflow:

```bash
filing-resolver resolve --ticker TOYO --intent quarterly --sources-json
```

This generates `sources.json` with structured entries that can be imported into a multi-agent-brief-workflow workspace.

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

### v0.3.0 (current)

- [x] SEC EDGAR provider with retry/backoff
- [x] Ticker/CIK/name resolution
- [x] Filing selection (annual, quarterly, semiannual, interim, specific form)
- [x] 6-K exhibit parsing and classification
- [x] HTML download with status tracking
- [x] Manifest generation with download_status fields
- [x] CLI (`filing-resolver resolve ...`) and Python API
- [x] Period validation (`latest` only)
- [x] Generic data models: EntityIdentity, DisclosureRecord, Artifact, EvidencePackage, Observation
- [x] Provider registry with IdentityProvider, DisclosureProvider, EnrichmentProvider abstractions
- [x] Generic `resolve_disclosure()` entry point
- [x] `sources.json` export for multi-agent-brief-workflow integration
- [x] SEC XBRL enrichment via companyfacts API
- [x] Inline XBRL (iXBRL) fact extraction from filing HTML
- [x] argparse CLI (Python 3.9+ compatible)

### v0.4.0

- [ ] Period filtering (YYYY, YYYYQ1-Q4, YYYY-MM-DD)
- [ ] Full-text search within filings
- [ ] Optional `fetch` adapter for `sec-filing-legal-decoder`
- [ ] HKEX provider
- [ ] CNINFO provider
- [ ] PDF OCR fallback
- [ ] MCP server interface

## License

MIT
