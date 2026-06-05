"""Tests for CLI."""

import json
from unittest.mock import MagicMock, patch

from disclosure_filing_resolver.cli import run


def _make_mock_package():
    """Create a mock FilingPackage."""
    pkg = MagicMock()
    pkg.schema_version = "1.0"
    pkg.request.ticker = "TOYO"
    pkg.request.intent = "quarterly"
    pkg.request.out_dir = None
    pkg.request.file_format = "html"
    pkg.company.ticker = "TOYO"
    pkg.company.cik = "1985273"
    pkg.company.name = "TOYO Co., Ltd"
    pkg.selected_filing.form = "6-K"
    pkg.selected_filing.filing_date = "2026-05-18"
    pkg.selected_filing.accession_number = "0001213900-26-058577"
    pkg.documents = [
        MagicMock(
            role="financial_statements",
            priority=100,
            local_path="test.htm",
            sec_url="https://example.com",
            file_format="html",
        ),
    ]
    pkg.warnings = ["6-K primary document may be a cover page"]

    pkg.model_dump.return_value = {
        "schema_version": "1.0",
        "request": {"ticker": "TOYO", "intent": "quarterly"},
        "company": {"ticker": "TOYO", "cik": "1985273", "name": "TOYO Co., Ltd"},
        "selected_filing": {"form": "6-K", "filing_date": "2026-05-18"},
        "documents": [],
        "warnings": [],
    }
    return pkg


class TestCLI:
    """Tests for the official CLI contract: filing-resolver resolve ..."""

    @patch("disclosure_filing_resolver.cli.resolve_filing_package")
    def test_resolve_with_ticker(self, mock_resolve):
        mock_resolve.return_value = _make_mock_package()
        assert run(["resolve", "--ticker", "TOYO", "--no-download"]) == 0

    @patch("disclosure_filing_resolver.cli.resolve_filing_package")
    def test_resolve_json_output(self, mock_resolve, capsys):
        mock_resolve.return_value = _make_mock_package()
        assert run(["resolve", "--ticker", "TOYO", "--no-download", "--json"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["company"]["ticker"] == "TOYO"

    @patch("disclosure_filing_resolver.cli.resolve_filing_package")
    def test_resolve_no_input_shows_error(self, mock_resolve):
        assert run(["resolve"]) == 1

    @patch("disclosure_filing_resolver.cli.resolve_filing_package")
    def test_resolve_with_company(self, mock_resolve):
        mock_resolve.return_value = _make_mock_package()
        assert run(["resolve", "--company", "Tesla", "--no-download"]) == 0

    @patch("disclosure_filing_resolver.cli.resolve_filing_package")
    def test_resolve_with_cik(self, mock_resolve):
        mock_resolve.return_value = _make_mock_package()
        assert run(["resolve", "--cik", "1985273", "--no-download"]) == 0

    @patch("disclosure_filing_resolver.cli.resolve_filing_package")
    def test_resolve_error_handling(self, mock_resolve, capsys):
        from disclosure_filing_resolver.exceptions import CompanyNotFoundError

        mock_resolve.side_effect = CompanyNotFoundError("XYZ")
        assert run(["resolve", "--ticker", "XYZ"]) == 1
        assert "Error" in capsys.readouterr().err

    def test_help_shows_resolve_command(self, capsys):
        """filing-resolver --help must list 'resolve' as a command."""
        try:
            run(["--help"])
        except SystemExit as exc:
            assert exc.code == 0
        assert "resolve" in capsys.readouterr().out.lower()

    def test_resolve_help_contains_options(self, capsys):
        """filing-resolver resolve --help must show all option flags."""
        try:
            run(["resolve", "--help"])
        except SystemExit as exc:
            assert exc.code == 0
        output = capsys.readouterr().out
        assert "--ticker" in output
        assert "--intent" in output
        assert "--period" in output
        assert "--format" in output
        assert "--download" in output
        assert "--out" in output
        assert "--json" in output

    @patch("disclosure_filing_resolver.cli.resolve_filing_package")
    def test_non_latest_period_is_rejected(self, mock_resolve, capsys):
        from disclosure_filing_resolver.exceptions import UnsupportedPeriodError

        mock_resolve.side_effect = UnsupportedPeriodError("2026Q1")
        assert run(["resolve", "--ticker", "TOYO", "--period", "2026Q1"]) == 1
        output = capsys.readouterr().err
        assert "Error" in output
        assert "2026Q1" in output
