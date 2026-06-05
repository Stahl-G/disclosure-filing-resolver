"""Configuration for disclosure-filing-resolver."""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass


@dataclass
class SECConfig:
    """SEC EDGAR client configuration."""

    user_agent: str = ""
    base_url: str = "https://data.sec.gov"
    archive_base: str = "https://www.sec.gov/Archives/edgar/data"
    tickers_url: str = "https://www.sec.gov/files/company_tickers.json"
    rate_limit: float = 5.0  # max requests per second
    timeout: float = 30.0
    max_retries: int = 3
    cache_dir: str = ".cache"

    def __post_init__(self) -> None:
        if not self.user_agent:
            env_ua = os.environ.get("SEC_USER_AGENT", "")
            if env_ua:
                self.user_agent = env_ua
            else:
                self.user_agent = "disclosure-filing-resolver/0.3.0 (https://github.com/Stahl-G/disclosure-filing-resolver)"
                warnings.warn(
                    "SEC_USER_AGENT not set. Using default user agent. "
                    "Set SEC_USER_AGENT='your_email@example.com disclosure-filing-resolver' "
                    "for SEC fair access compliance.",
                    UserWarning,
                    stacklevel=2,
                )


def get_sec_config(**overrides: object) -> SECConfig:
    """Get SEC configuration with optional overrides."""
    return SECConfig(**{k: v for k, v in overrides.items() if v is not None})  # type: ignore[arg-type]
