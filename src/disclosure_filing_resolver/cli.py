"""CLI for disclosure-filing-resolver."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, List, Optional

from disclosure_filing_resolver.manifest import evidence_to_sources
from disclosure_filing_resolver.resolver import resolve_disclosure, resolve_filing_package


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        prog="filing-resolver",
        description="Deterministic SEC filing acquisition and exhibit classification.",
    )
    subparsers = parser.add_subparsers(dest="command")

    resolve_parser = subparsers.add_parser(
        "resolve",
        help="Resolve a SEC filing and optionally download documents.",
        description="Resolve a SEC filing and optionally download documents.",
    )
    resolve_parser.add_argument("--ticker", "-t", help="Stock ticker symbol")
    resolve_parser.add_argument("--company", "-c", help="Company name")
    resolve_parser.add_argument("--cik", help="SEC CIK number")
    resolve_parser.add_argument(
        "--intent",
        "-i",
        default="quarterly",
        help="annual, quarterly, semiannual, interim, earnings_release, specific_form",
    )
    resolve_parser.add_argument(
        "--period",
        "-p",
        default="latest",
        help="Period: latest or specific date",
    )
    resolve_parser.add_argument(
        "--form",
        "-f",
        help="Form type for --intent specific_form",
    )
    resolve_parser.add_argument(
        "--format",
        dest="file_format",
        default="html",
        help="File format: html, pdf, any",
    )
    resolve_parser.add_argument(
        "--download",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Download documents",
    )
    resolve_parser.add_argument(
        "--include-exhibits",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include exhibits",
    )
    resolve_parser.add_argument("--out", "-o", help="Output directory")
    resolve_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output manifest JSON to stdout",
    )
    resolve_parser.add_argument(
        "--sources-json",
        dest="sources_json",
        action="store_true",
        help="Output sources.json to stdout (for multi-agent-brief-workflow)",
    )
    resolve_parser.set_defaults(func=_resolve_cmd)

    # enrich subcommand
    enrich_parser = subparsers.add_parser(
        "enrich",
        help="Enrich an entity with XBRL financial facts from SEC companyfacts.",
        description="Enrich an entity with XBRL financial facts from SEC companyfacts.",
    )
    enrich_parser.add_argument("--ticker", "-t", help="Stock ticker symbol")
    enrich_parser.add_argument("--company", "-c", help="Company name")
    enrich_parser.add_argument("--cik", help="SEC CIK number")
    enrich_parser.add_argument(
        "--max-facts",
        type=int,
        default=30,
        help="Maximum number of facts to extract (default: 30)",
    )
    enrich_parser.set_defaults(func=_enrich_cmd)

    return parser


def _resolve_cmd(args: argparse.Namespace) -> int:
    """Resolve command implementation."""
    if not args.ticker and not args.company and not args.cik:
        print("Error: Provide at least one of --ticker, --company, or --cik.", file=sys.stderr)
        return 1

    try:
        # Use the generic resolver when sources-json is requested
        if args.sources_json:
            evidence = resolve_disclosure(
                ticker=args.ticker,
                company_name=args.company,
                cik=args.cik,
                intent=args.intent,
                period=args.period,
                form=args.form,
                file_format=args.file_format,
                download=args.download,
                include_exhibits=args.include_exhibits,
                out_dir=args.out,
            )
            sources = evidence_to_sources(evidence)
            print(json.dumps(sources, ensure_ascii=False, indent=2))
            return 0

        package = resolve_filing_package(
            ticker=args.ticker,
            company_name=args.company,
            cik=args.cik,
            intent=args.intent,
            period=args.period,
            form=args.form,
            file_format=args.file_format,
            download=args.download,
            include_exhibits=args.include_exhibits,
            out_dir=args.out,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json_output:
        print(json.dumps(package.model_dump(), ensure_ascii=False, indent=2))
        return 0

    _print_summary(package)
    return 0


def _enrich_cmd(args: argparse.Namespace) -> int:
    """Enrich command implementation."""
    if not args.ticker and not args.company and not args.cik:
        print("Error: Provide at least one of --ticker, --company, or --cik.", file=sys.stderr)
        return 1

    try:
        from disclosure_filing_resolver.providers.sec_edgar.ticker_resolver import TickerResolver
        from disclosure_filing_resolver.providers.sec_edgar.client import SECEdgarClient
        from disclosure_filing_resolver.providers.sec_edgar.xbrl import (
            SECXBRLProvider,
            fetch_companyfacts,
            extract_observations,
        )
        from disclosure_filing_resolver.config import get_sec_config

        config = get_sec_config()
        client = SECEdgarClient(config)

        try:
            # Resolve company identity
            from disclosure_filing_resolver.models import ResolveRequest
            request = ResolveRequest(
                ticker=args.ticker,
                company_name=args.company,
                cik=args.cik,
            )
            resolver = TickerResolver(client)
            company = resolver.resolve(request)
            cik10 = company.cik10

            # Fetch and extract XBRL facts
            companyfacts = fetch_companyfacts(client, cik10)
            observations = extract_observations(companyfacts, max_facts=args.max_facts)

            # Output as JSON
            result = {
                "entity": {
                    "name": company.name,
                    "ticker": company.ticker,
                    "cik": company.cik,
                    "cik10": company.cik10,
                },
                "observations": [obs.model_dump() for obs in observations],
                "count": len(observations),
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
        finally:
            client.close()

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


def _print_summary(package: Any) -> None:
    """Print a human-readable summary of the resolved package."""
    print()
    print(
        f"Resolved {package.company.ticker or package.company.name} "
        f"/ CIK {package.company.cik}"
    )
    print(
        f"Selected filing: {package.selected_filing.form} "
        f"filed {package.selected_filing.filing_date}, "
        f"accession {package.selected_filing.accession_number}"
    )

    if package.documents:
        downloaded = sum(1 for d in package.documents if d.download_status == "downloaded")
        failed = sum(1 for d in package.documents if d.download_status == "failed")
        total = len(package.documents)
        status_parts = [f"{total} total", f"{downloaded} downloaded"]
        if failed:
            status_parts.append(f"{failed} failed")
        print(f"Documents: {', '.join(status_parts)}")

    if package.request.out_dir:
        print(f"Output: {package.request.out_dir}")
        print(f"Manifest: {package.request.out_dir}/manifest.json")

    useful = [d for d in package.documents if d.role not in ("unknown", "cover")]
    if useful:
        print()
        print("Recommended analysis documents:")
        for doc in sorted(useful, key=lambda d: -d.priority):
            path = doc.local_path or doc.sec_url
            print(f"  - {doc.role}: {path}")

    failed_docs = [d for d in package.documents if d.download_status == "failed"]
    if failed_docs:
        print()
        print("Failed downloads:")
        for doc in failed_docs:
            error = doc.download_error or "unknown error"
            print(f"  - {doc.role}: {doc.sec_url} - {error}")

    if package.warnings:
        print()
        print("Warnings:")
        for warning in package.warnings:
            print(f"  - {warning}")

    print()


def run(argv: Optional[List[str]] = None) -> int:
    """Run the CLI and return an exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return args.func(args)


def main(argv: Optional[List[str]] = None) -> None:
    """Entry point for both CLI names."""
    raise SystemExit(run(argv))


if __name__ == "__main__":
    main()
