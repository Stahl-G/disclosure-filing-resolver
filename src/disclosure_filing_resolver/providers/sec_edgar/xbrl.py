"""SEC XBRL enrichment provider using companyfacts API."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from disclosure_filing_resolver.config import SECConfig
from disclosure_filing_resolver.models import (
    DisclosureRecord,
    DisclosureRequest,
    EntityIdentity,
    Observation,
)
from disclosure_filing_resolver.providers.base import EnrichmentProvider
from disclosure_filing_resolver.providers.sec_edgar.client import SECEdgarClient


# Key financial concepts to extract from companyfacts
# Maps XBRL concept names to human-readable categories
KEY_CONCEPTS: Dict[str, str] = {
    "us-gaap/Revenues": "revenue",
    "us-gaap/RevenueFromContractWithCustomerExcludingAssessedTax": "revenue",
    "us-gaap/RevenueFromContractWithCustomerIncludingAssessedTax": "revenue",
    "us-gaap/SalesRevenueNet": "revenue",
    "us-gaap/NetIncomeLoss": "net_income",
    "us-gaap/OperatingIncomeLoss": "operating_income",
    "us-gaap/GrossProfit": "gross_profit",
    "us-gaap/Assets": "total_assets",
    "us-gaap/Liabilities": "total_liabilities",
    "us-gaap/StockholdersEquity": "stockholders_equity",
    "us-gaap/EarningsPerShareBasic": "eps_basic",
    "us-gaap/EarningsPerShareDiluted": "eps_diluted",
    "us-gaap/OperatingCashFlow": "operating_cash_flow",
    "us-gaap/NetCashProvidedByUsedInOperatingActivities": "operating_cash_flow",
    "us-gaap/CashAndCashEquivalentsAtCarryingValue": "cash",
    "us-gaap/LongTermDebt": "long_term_debt",
    "us-gaap/AccountsReceivableNetCurrent": "accounts_receivable",
    "us-gaap/InventoryNet": "inventory",
}

# XBRL concept names for common non-GAAP or IFRS concepts
IFRS_CONCEPTS: Dict[str, str] = {
    "ifrs-full/Revenue": "revenue",
    "ifrs-full/ProfitLoss": "net_income",
    "ifrs-full/TotalAssets": "total_assets",
    "ifrs-full/TotalLiabilities": "total_liabilities",
    "ifrs-full/Equity": "stockholders_equity",
    "ifrs-full/BasicEarningsLossPerShare": "eps_basic",
    "ifrs-full/DilutedEarningsLossPerShare": "eps_diluted",
    "ifrs-full/CashAndCashEquivalents": "cash",
}


def _parse_concept_name(label: str) -> str:
    """Convert a concept label to a clean key.

    'us-gaap/Revenues' -> 'revenues'
    'us-gaap/NetIncomeLoss' -> 'netincomeloss'
    """
    return label.split("/")[-1].lower()


def _extract_latest_fact(
    concept_data: Dict[str, Any],
    unit_filter: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Extract the most recent fact from a concept's units array.

    Args:
        concept_data: The concept data from companyfacts JSON.
        unit_filter: If set, only consider facts with this unit (e.g., "USD", "USD/shares").

    Returns:
        The most recent fact dict, or None if no facts found.
    """
    units = concept_data.get("units", {})
    if not units:
        return None

    best: Optional[Dict[str, Any]] = None
    best_end = ""

    for unit_name, facts in units.items():
        if unit_filter and unit_name != unit_filter:
            continue

        for fact in facts:
            # Only consider 10-K, 10-Q, 20-F, 40-F, 6-K filings
            form = fact.get("form", "")
            if form not in ("10-K", "10-Q", "20-F", "40-F", "6-K",
                            "10-K/A", "10-Q/A", "20-F/A", "40-F/A", "6-K/A"):
                continue

            end = fact.get("end", "")
            if end > best_end:
                best_end = end
                best = {
                    "value": fact.get("val"),
                    "unit": unit_name,
                    "end": end,
                    "start": fact.get("start", ""),
                    "form": form,
                    "filed": fact.get("filed", ""),
                    "accession": fact.get("accn", ""),
                    "fiscal_year": fact.get("fy"),
                    "fiscal_period": fact.get("fp"),
                }

    return best


def _pick_preferred_unit(concept_data: Dict[str, Any]) -> Optional[str]:
    """Pick the preferred unit for a concept (USD for most, USD/shares for EPS)."""
    units = set(concept_data.get("units", {}).keys())
    if not units:
        return None
    # EPS concepts use per-share units
    for u in units:
        if "shares" in u.lower() or "per" in u.lower():
            return u
    # Prefer USD, then first available
    if "USD" in units:
        return "USD"
    return next(iter(units))


def fetch_companyfacts(client: SECEdgarClient, cik10: str) -> Dict[str, Any]:
    """Fetch companyfacts JSON from SEC API.

    Args:
        client: SEC EDGAR HTTP client.
        cik10: CIK padded to 10 digits.

    Returns:
        Parsed companyfacts JSON.
    """
    url = f"{client.config.base_url}/api/xbrl/companyfacts/CIK{cik10}.json"
    return client.get_json(url, use_cache=True)


def extract_observations(
    companyfacts: Dict[str, Any],
    max_facts: int = 30,
) -> List[Observation]:
    """Extract structured observations from companyfacts data.

    Args:
        companyfacts: Parsed companyfacts JSON from SEC API.
        max_facts: Maximum number of facts to extract.

    Returns:
        List of Observation objects.
    """
    observations: List[Observation] = []
    facts = companyfacts.get("facts", {})

    # Merge GAAP and IFRS concept maps
    all_concepts = {**KEY_CONCEPTS, **IFRS_CONCEPTS}

    for concept_label, category in all_concepts.items():
        taxonomy, concept_name = concept_label.split("/", 1)
        taxonomy_data = facts.get(taxonomy, {})
        concept_data = taxonomy_data.get(concept_name)
        if not concept_data:
            continue

        preferred_unit = _pick_preferred_unit(concept_data)
        if not preferred_unit:
            continue

        fact = _extract_latest_fact(concept_data, unit_filter=preferred_unit)
        if not fact:
            continue

        obs = Observation(
            source="sec_edgar",
            category=category,
            key=concept_name,
            value=fact["value"],
            unit=fact["unit"],
            period=fact["end"],
            confidence=1.0,
            provenance={
                "provider": "sec_edgar",
                "taxonomy": taxonomy,
                "concept": concept_name,
                "form": fact["form"],
                "filed": fact["filed"],
                "accession": fact["accession"],
                "fiscal_year": str(fact.get("fiscal_year", "")),
                "fiscal_period": fact.get("fiscal_period", ""),
            },
        )
        observations.append(obs)

        if len(observations) >= max_facts:
            break

    return observations


class SECXBRLProvider(EnrichmentProvider):
    """SEC XBRL enrichment provider using companyfacts API.

    Extracts structured financial facts (revenue, net income, assets, etc.)
    from SEC EDGAR companyfacts XBRL data.
    """

    def __init__(self, config: Optional[SECConfig] = None) -> None:
        from disclosure_filing_resolver.config import get_sec_config

        self.config = config or get_sec_config()
        self._client = SECEdgarClient(self.config)

    def enrich(
        self,
        entity: EntityIdentity,
        disclosure: Optional[DisclosureRecord],
        request: DisclosureRequest,
    ) -> List[Observation]:
        """Enrich an entity with XBRL financial facts from SEC companyfacts.

        Args:
            entity: The resolved entity identity.
            disclosure: Optional disclosure record (not used for XBRL lookup).
            request: The disclosure request.

        Returns:
            List of financial observations.
        """
        cik = entity.identifiers.get("cik", "")
        if not cik:
            return []

        cik10 = entity.identifiers.get("cik10") or cik.zfill(10)

        try:
            companyfacts = fetch_companyfacts(self._client, cik10)
        except Exception:
            return []

        return extract_observations(companyfacts)

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()
