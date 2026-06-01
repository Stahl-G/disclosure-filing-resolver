"""CLI for disclosure-filing-resolver."""

from __future__ import annotations

import json

import typer
from rich.console import Console

from disclosure_filing_resolver.resolver import resolve_filing_package

# Two-level app: "filing-resolver resolve --ticker TOYO"
app = typer.Typer(
    name="filing-resolver",
    help="Deterministic SEC filing acquisition and exhibit classification.",
    no_args_is_help=True,
    invoke_without_command=True,
)
console = Console()


@app.callback(invoke_without_command=True)
def main_callback() -> None:
    """Deterministic SEC filing acquisition and exhibit classification."""


@app.command(name="resolve")
def resolve_cmd(
    ticker: str | None = typer.Option(None, "--ticker", "-t", help="Stock ticker symbol"),
    company: str | None = typer.Option(None, "--company", "-c", help="Company name"),
    cik: str | None = typer.Option(None, "--cik", help="SEC CIK number"),
    intent: str = typer.Option(
        "quarterly",
        "--intent",
        "-i",
        help="annual, quarterly, semiannual, interim, earnings_release, specific_form",
    ),
    period: str = typer.Option(
        "latest", "--period", "-p", help="Period: latest or specific date"
    ),
    form: str | None = typer.Option(
        None, "--form", "-f", help="Form type for --intent specific_form"
    ),
    file_format: str = typer.Option(
        "html", "--format", help="File format: html, pdf, any"
    ),
    download: bool = typer.Option(
        True, "--download/--no-download", help="Download documents"
    ),
    include_exhibits: bool = typer.Option(
        True, "--include-exhibits/--no-include-exhibits", help="Include exhibits"
    ),
    out: str | None = typer.Option(None, "--out", "-o", help="Output directory"),
    json_output: bool = typer.Option(False, "--json", help="Output manifest JSON to stdout"),
) -> None:
    """Resolve a SEC filing and optionally download documents."""
    if not ticker and not company and not cik:
        console.print(
            "[red]Error: Provide at least one of --ticker, --company, or --cik.[/red]"
        )
        raise typer.Exit(1)

    try:
        package = resolve_filing_package(
            ticker=ticker,
            company_name=company,
            cik=cik,
            intent=intent,
            period=period,
            form=form,
            file_format=file_format,
            download=download,
            include_exhibits=include_exhibits,
            out_dir=out,
        )
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    if json_output:
        console.print(json.dumps(package.model_dump(), ensure_ascii=False, indent=2))
        return

    # Print human-readable summary
    _print_summary(package)


def _print_summary(package: object) -> None:
    """Print a human-readable summary of the resolved package."""
    console.print()
    console.print(
        f"[green]Resolved[/green] {package.company.ticker or package.company.name} "
        f"/ CIK {package.company.cik}"
    )
    console.print(
        f"[green]Selected filing:[/green] {package.selected_filing.form} "
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
        console.print(f"[green]Documents:[/green] {', '.join(status_parts)}")

    if package.request.out_dir:
        console.print(f"[green]Output:[/green] {package.request.out_dir}")
        console.print(f"[green]Manifest:[/green] {package.request.out_dir}/manifest.json")

    # Recommended analysis documents
    useful = [d for d in package.documents if d.role not in ("unknown", "cover")]
    if useful:
        console.print()
        console.print("[bold]Recommended analysis documents:[/bold]")
        for doc in sorted(useful, key=lambda d: -d.priority):
            path = doc.local_path or doc.sec_url
            console.print(f"  - {doc.role}: {path}")

    # Failed downloads
    failed_docs = [d for d in package.documents if d.download_status == "failed"]
    if failed_docs:
        console.print()
        console.print("[red]Failed downloads:[/red]")
        for doc in failed_docs:
            error = doc.download_error or "unknown error"
            console.print(f"  - {doc.role}: {doc.sec_url} — {error}")

    # Warnings
    if package.warnings:
        console.print()
        console.print("[yellow]Warnings:[/yellow]")
        for w in package.warnings:
            console.print(f"  - {w}")

    console.print()


def main() -> None:
    """Entry point for both CLI names."""
    app()


if __name__ == "__main__":
    main()
