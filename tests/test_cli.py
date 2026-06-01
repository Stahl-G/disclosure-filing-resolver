"""Tests for CLI."""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from disclosure_filing_resolver.cli import app

runner = CliRunner()


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

    # model_dump for JSON output
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
    @patch("disclosure_filing_resolver.cli.resolve_filing_package")
    def test_resolve_with_ticker(self, mock_resolve):
        mock_resolve.return_value = _make_mock_package()
        result = runner.invoke(app, ["--ticker", "TOYO", "--no-download"])
        assert result.exit_code == 0
        assert "TOYO" in result.output

    @patch("disclosure_filing_resolver.cli.resolve_filing_package")
    def test_resolve_json_output(self, mock_resolve):
        mock_resolve.return_value = _make_mock_package()
        result = runner.invoke(app, ["--ticker", "TOYO", "--no-download", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["company"]["ticker"] == "TOYO"

    @patch("disclosure_filing_resolver.cli.resolve_filing_package")
    def test_resolve_no_input_shows_error(self, mock_resolve):
        result = runner.invoke(app, [])
        assert result.exit_code != 0

    @patch("disclosure_filing_resolver.cli.resolve_filing_package")
    def test_resolve_with_company(self, mock_resolve):
        mock_resolve.return_value = _make_mock_package()
        result = runner.invoke(app, ["--company", "Tesla", "--no-download"])
        assert result.exit_code == 0

    @patch("disclosure_filing_resolver.cli.resolve_filing_package")
    def test_resolve_with_cik(self, mock_resolve):
        mock_resolve.return_value = _make_mock_package()
        result = runner.invoke(app, ["--cik", "1985273", "--no-download"])
        assert result.exit_code == 0

    @patch("disclosure_filing_resolver.cli.resolve_filing_package")
    def test_resolve_error_handling(self, mock_resolve):
        from disclosure_filing_resolver.exceptions import CompanyNotFoundError
        mock_resolve.side_effect = CompanyNotFoundError("XYZ")
        result = runner.invoke(app, ["--ticker", "XYZ"])
        assert result.exit_code == 1
        assert "Error" in result.output
