"""SEC EDGAR HTTP client with rate limiting and caching."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from disclosure_filing_resolver.config import SECConfig


class SECEdgarClient:
    """HTTP client for SEC EDGAR with rate limiting and file caching."""

    def __init__(self, config: SECConfig) -> None:
        self.config = config
        self._last_request_time: float = 0.0
        self._min_interval = 1.0 / config.rate_limit
        self._cache_dir = Path(config.cache_dir)
        self._client: httpx.Client | None = None

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

    def _cache_path(self, url: str) -> Path:
        """Get cache file path for a URL."""
        safe_name = url.replace("https://", "").replace("http://", "").replace("/", "_")
        return self._cache_dir / "sec" / safe_name

    def _get_cached(self, url: str) -> Any | None:
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
        cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_json(self, url: str, use_cache: bool = True) -> Any:
        """GET request that returns parsed JSON."""
        if use_cache:
            cached = self._get_cached(url)
            if cached is not None:
                return cached

        self._rate_limit()
        response = self.client.get(url)
        response.raise_for_status()
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

        self._rate_limit()
        response = self.client.get(url)
        response.raise_for_status()
        text = response.text

        if use_cache:
            cache_file = self._cache_path(url)
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(text, encoding="utf-8")

        return text

    def download(self, url: str, dest: Path) -> Path:
        """Download a file to local path."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        self._rate_limit()
        with self.client.stream("GET", url) as response:
            response.raise_for_status()
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
