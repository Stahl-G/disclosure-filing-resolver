"""SEC EDGAR HTTP client with rate limiting, caching, and retry/backoff."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

import httpx

from disclosure_filing_resolver.config import SECConfig
from disclosure_filing_resolver.exceptions import SECRequestError

# HTTP status codes that should trigger a retry
RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}
# HTTP status codes that should NOT be retried (client errors except 408/429)
NON_RETRYABLE_STATUSES = {400, 401, 403, 404}


class SECEdgarClient:
    """HTTP client for SEC EDGAR with rate limiting, caching, and retry/backoff."""

    def __init__(self, config: SECConfig) -> None:
        self.config = config
        self._last_request_time: float = 0.0
        self._min_interval = 1.0 / config.rate_limit
        self._cache_dir = Path(config.cache_dir)
        self._client: Optional[httpx.Client] = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                headers={"User-Agent": self.config.user_agent},
                timeout=self.config.timeout,
                follow_redirects=True,
            )
        return self._client

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.monotonic()

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Execute an HTTP request with retry/backoff.

        Retries on: 408, 429, 500, 502, 503, 504, timeouts, transport errors.
        Does not retry on: 400, 401, 403, 404.
        """
        last_exc: Optional[Exception] = None

        for attempt in range(self.config.max_retries):
            self._rate_limit()
            try:
                response = self.client.request(method, url, **kwargs)

                # Check for retryable status codes
                if response.status_code in RETRYABLE_STATUSES:
                    if attempt < self.config.max_retries - 1:
                        sleep_sec = min(2**attempt, 10)
                        time.sleep(sleep_sec)
                        continue
                    # Last attempt — fall through to raise

                # Non-retryable client errors — raise immediately
                if response.status_code in NON_RETRYABLE_STATUSES:
                    detail = response.text[:300] if response.text else ""
                    if response.status_code == 403:
                        raise SECRequestError(
                            url=url,
                            status=403,
                            detail=(
                                f"SEC returned 403 Forbidden. "
                                f"Check that SEC_USER_AGENT is set correctly. "
                                f"SEC fair access requires a valid user agent. "
                                f"Detail: {detail}"
                            ),
                        )
                    raise SECRequestError(
                        url=url, status=response.status_code, detail=detail
                    )

                # Other status codes (2xx, 3xx, etc.) — return as-is
                # If we got here on a retryable status after last attempt, raise
                if response.status_code in RETRYABLE_STATUSES:
                    detail = (
                        f"Retried {self.config.max_retries} times. "
                        f"Last: {response.text[:300]}"
                    )
                    raise SECRequestError(
                        url=url,
                        status=response.status_code,
                        detail=detail,
                    )

                return response

            except SECRequestError:
                raise
            except httpx.TimeoutException as exc:
                last_exc = exc
                if attempt < self.config.max_retries - 1:
                    sleep_sec = min(2**attempt, 10)
                    time.sleep(sleep_sec)
                    continue
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt < self.config.max_retries - 1:
                    sleep_sec = min(2**attempt, 10)
                    time.sleep(sleep_sec)
                    continue

        # All retries exhausted
        raise SECRequestError(
            url=url,
            detail=f"Failed after {self.config.max_retries} attempts. Last error: {last_exc}",
        )

    def _cache_path(self, url: str) -> Path:
        """Get cache file path for a URL."""
        safe_name = url.replace("https://", "").replace("http://", "").replace("/", "_")
        return self._cache_dir / "sec" / safe_name

    def _get_cached(self, url: str) -> Optional[Any]:
        """Try to get cached response."""
        cache_file = self._cache_path(url)
        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def _set_cached(self, url: str, data: Any) -> None:
        """Cache a response."""
        cache_file = self._cache_path(url)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get_json(self, url: str, use_cache: bool = True) -> Any:
        """GET request that returns parsed JSON."""
        if use_cache:
            cached = self._get_cached(url)
            if cached is not None:
                return cached

        response = self._request("GET", url)
        data = response.json()

        if use_cache:
            self._set_cached(url, data)

        return data

    def get_text(self, url: str, use_cache: bool = True) -> str:
        """GET request that returns text content."""
        if use_cache:
            cache_file = self._cache_path(url)
            if cache_file.exists():
                try:
                    return cache_file.read_text(encoding="utf-8")
                except OSError:
                    pass

        response = self._request("GET", url)
        text = response.text

        if use_cache:
            cache_file = self._cache_path(url)
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(text, encoding="utf-8")

        return text

    def download(self, url: str, dest: Path) -> Path:
        """Download a file to local path."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        response = self._request("GET", url, headers={"Accept": "*/*"})
        with open(dest, "wb") as f:
            for chunk in response.iter_bytes(chunk_size=8192):
                f.write(chunk)
        return dest

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            self._client.close()

    def __enter__(self) -> SECEdgarClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
