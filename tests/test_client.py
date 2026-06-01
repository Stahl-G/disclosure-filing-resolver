"""Tests for SEC EDGAR client retry/backoff behavior."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from disclosure_filing_resolver.config import SECConfig
from disclosure_filing_resolver.exceptions import SECRequestError
from disclosure_filing_resolver.providers.sec_edgar.client import SECEdgarClient


def _make_client(max_retries: int = 3) -> SECEdgarClient:
    """Create a client with fast timeouts for testing."""
    config = SECConfig(
        user_agent="test@example.com test-client",
        rate_limit=100.0,  # fast for tests
        max_retries=max_retries,
        timeout=5.0,
    )
    return SECEdgarClient(config)


class TestRetryOnRetryableStatus:
    def test_get_json_retries_on_429_then_succeeds(self):
        """429 (rate limit) should retry and eventually succeed."""
        client = _make_client(max_retries=3)

        responses = [
            MagicMock(status_code=429, text="Rate limited"),
            MagicMock(status_code=429, text="Rate limited"),
            MagicMock(status_code=200, json=lambda: {"key": "value"}),
        ]

        with patch.object(client, "_rate_limit"):
            with patch.object(client.client, "request", side_effect=responses):
                result = client.get_json("https://example.com/test.json", use_cache=False)

        assert result == {"key": "value"}

    def test_get_text_retries_on_500_then_succeeds(self):
        """500 (server error) should retry and eventually succeed."""
        client = _make_client(max_retries=3)

        responses = [
            MagicMock(status_code=500, text="Internal error"),
            MagicMock(status_code=200, text="OK content"),
        ]

        with patch.object(client, "_rate_limit"):
            with patch.object(client.client, "request", side_effect=responses):
                result = client.get_text("https://example.com/test.htm", use_cache=False)

        assert result == "OK content"


class TestNoRetryOnNonRetryableStatus:
    def test_get_json_404_raises_without_retry(self):
        """404 should raise immediately, no retry."""
        client = _make_client(max_retries=3)

        response = MagicMock(status_code=404, text="Not found")

        with patch.object(client, "_rate_limit"):
            with patch.object(client.client, "request", return_value=response):
                with pytest.raises(SECRequestError) as exc_info:
                    client.get_json("https://example.com/missing.json", use_cache=False)

        assert exc_info.value.status == 404
        assert "Not found" in str(exc_info.value)

    def test_get_json_403_mentions_user_agent(self):
        """403 should raise with a helpful message about SEC_USER_AGENT."""
        client = _make_client(max_retries=3)

        response = MagicMock(status_code=403, text="Forbidden")

        with patch.object(client, "_rate_limit"):
            with patch.object(client.client, "request", return_value=response):
                with pytest.raises(SECRequestError) as exc_info:
                    client.get_json("https://example.com/forbidden.json", use_cache=False)

        assert exc_info.value.status == 403
        assert "SEC_USER_AGENT" in str(exc_info.value)

    def test_get_json_400_raises_without_retry(self):
        """400 should raise immediately."""
        client = _make_client(max_retries=3)

        response = MagicMock(status_code=400, text="Bad request")

        with patch.object(client, "_rate_limit"):
            with patch.object(client.client, "request", return_value=response):
                with pytest.raises(SECRequestError) as exc_info:
                    client.get_json("https://example.com/bad.json", use_cache=False)

        assert exc_info.value.status == 400


class TestTransportErrorRetry:
    def test_transport_error_retries_then_raises(self):
        """Transport errors should retry, then raise SECRequestError."""
        client = _make_client(max_retries=2)

        with patch.object(client, "_rate_limit"):
            with patch.object(
                client.client,
                "request",
                side_effect=httpx.ConnectError("Connection refused"),
            ):
                with pytest.raises(SECRequestError) as exc_info:
                    client.get_json("https://example.com/test.json", use_cache=False)

        assert "Failed after 2 attempts" in str(exc_info.value)

    def test_timeout_retries_then_raises(self):
        """Timeout errors should retry, then raise SECRequestError."""
        client = _make_client(max_retries=2)

        with patch.object(client, "_rate_limit"):
            with patch.object(
                client.client,
                "request",
                side_effect=httpx.TimeoutException("Timed out"),
            ):
                with pytest.raises(SECRequestError) as exc_info:
                    client.get_text("https://example.com/test.htm", use_cache=False)

        assert "Failed after 2 attempts" in str(exc_info.value)


class TestRetryExhaustion:
    def test_retryable_status_exhausted_raises(self):
        """If all retries return 500, should raise SECRequestError."""
        client = _make_client(max_retries=2)

        response = MagicMock(status_code=500, text="Server error")

        with patch.object(client, "_rate_limit"):
            with patch.object(client.client, "request", return_value=response):
                with pytest.raises(SECRequestError) as exc_info:
                    client.get_json("https://example.com/test.json", use_cache=False)

        assert "Retried 2 times" in str(exc_info.value)
