"""Simple file cache for filing packages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from disclosure_filing_resolver.models import FilingPackage


class FilingCache:
    """Simple file-based cache for resolved filing packages."""

    def __init__(self, cache_dir: str = ".cache") -> None:
        self.cache_dir = Path(cache_dir)

    def _key_path(self, ticker: str, intent: str, period: str) -> Path:
        """Get cache file path for a request combination."""
        safe_key = f"{ticker}_{intent}_{period}".replace("/", "_").replace("\\", "_")
        return self.cache_dir / "filings" / safe_key / "manifest.json"

    def get(self, ticker: str, intent: str, period: str) -> Optional[FilingPackage]:
        """Try to get a cached filing package."""
        path = self._key_path(ticker, intent, period)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return FilingPackage(**data)
            except (json.JSONDecodeError, Exception):
                return None
        return None

    def set(self, package: FilingPackage) -> None:
        """Cache a filing package."""
        if not package.request.ticker:
            return
        path = self._key_path(
            package.request.ticker,
            package.request.intent,
            package.request.period,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(package.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def clear(self) -> None:
        """Clear all cached data."""
        if self.cache_dir.exists():
            import shutil
            shutil.rmtree(self.cache_dir)
