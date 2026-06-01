# AGENTS.md

## Project Rules

- Do not commit confidential company documents, private filings, credentials, or raw logs.
- Use public SEC filings and synthetic fixtures only.
- Keep source acquisition separate from analysis.
- Do not provide legal, investment, accounting, audit, or professional conclusions.
- Prefer deterministic SEC EDGAR data over web search.
- Do not use browser automation in v0.1.0.
- Respect SEC fair access expectations.
- Run tests or at least a smoke test before completion.

## v0.1.0 Scope

This version implements SEC EDGAR only. It resolves company identity, locates public filings, downloads HTML documents, classifies exhibits, and generates a machine-readable manifest.

Non-goals for this version: HKEX, CNINFO, ASX, PDF OCR, XBRL parsing, valuation, LLM summarization, legal analysis, MCP server.

## Key Design Decisions

- Deterministic SEC data sources over web scraping.
- 6-K exhibit expansion is a first-class feature (foreign private issuers).
- File-level cache for repeat requests.
- Manifest is the contract between resolver and downstream analyzers.
