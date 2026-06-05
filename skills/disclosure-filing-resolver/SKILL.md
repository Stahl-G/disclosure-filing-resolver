# disclosure-filing-resolver Skill

Use this skill when the user asks to find, download, or locate SEC filings for a public company.

## When to Use

- "Download the latest quarterly report for AAPL"
- "Find the 10-K filing for Microsoft"
- "Get the latest SEC filing for a public company"
- "Resolve the latest quarterly filing for a public company"

## How to Use

### CLI (preferred)

```bash
filing-resolver resolve --ticker <TICKER> --intent <INTENT> --out <DIR>
```

### Python API

```python
from disclosure_filing_resolver import resolve_filing_package
package = resolve_filing_package(ticker="<TICKER>", intent="<INTENT>", out_dir="<DIR>")
```

## Intent Options

- `annual` — latest 10-K, 20-F, or 40-F
- `quarterly` — latest 10-Q, falling back to 6-K
- `semiannual` / `interim` — 6-K with interim financial data
- `earnings_release` — 6-K with earnings/financial results
- `specific_form` — use `--form` to specify exact form type

## Important Notes

1. **Always read `manifest.json` before answering.** The manifest tells you which documents are available and their roles.
2. **6-K filings need exhibit expansion.** The primary 6-K document is often just a cover page. The actual financial data is in Exhibit 99.x files.
3. **Do not invent SEC links.** Use the URLs from the manifest.
4. **Prefer HTML/HTM for LLM analysis.** PDFs are harder to process.
5. **This tool does not analyze filings.** It only acquires and classifies them. Pass the manifest to a downstream analysis tool.

## Output

The resolver creates:

- `<out_dir>/manifest.json` — structured metadata about the filing
- `<out_dir>/*.htm` — downloaded documents
- Console summary with recommended analysis documents
