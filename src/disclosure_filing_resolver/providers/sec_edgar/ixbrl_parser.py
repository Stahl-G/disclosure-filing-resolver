"""iXBRL parser for extracting structured facts from Inline XBRL HTML documents."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

# Common XBRL namespace prefixes
XBRL_NAMESPACES = {
    "ix": "http://www.xbrl.org/2013/inlineXBRL",
    "ixt": "http://www.xbrl.org/inlineXBRL/transformation/2015-02-26",
    "dei": "http://xbrl.sec.gov/dei/2024",
    "us-gaap": "http://fasb.org/us-gaap/2024",
    "ifrs": "http://xbrl.ifrs.org/taxonomy/2024",
}


def _parse_numeric_value(text: str) -> Optional[float]:
    """Parse a numeric value from iXBRL text, handling negatives and formatting."""
    if not text:
        return None

    text = text.strip()

    # Handle parenthetical negatives: (1,234) -> -1234
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]

    # Remove commas and currency symbols
    text = re.sub(r"[,$€£¥]", "", text)

    # Handle explicit negative sign
    text = text.replace("−", "-")  # Unicode minus

    try:
        return float(text)
    except ValueError:
        return None


def _extract_context_periods(soup: BeautifulSoup) -> Dict[str, Dict[str, str]]:
    """Extract XBRL context periods from the document.

    Returns a dict mapping context IDs to their period info.
    """
    contexts: Dict[str, Dict[str, str]] = {}

    for ctx in soup.find_all("xbrli:context"):
        ctx_id = ctx.get("id", "")
        if not ctx_id:
            continue

        period_info: Dict[str, str] = {}

        instant = ctx.find("xbrli:instant")
        if instant:
            period_info["instant"] = instant.get_text(strip=True)

        start_date = ctx.find("xbrli:startdate")
        end_date = ctx.find("xbrli:enddate")
        if start_date and end_date:
            period_info["start"] = start_date.get_text(strip=True)
            period_info["end"] = end_date.get_text(strip=True)

        if period_info:
            contexts[ctx_id] = period_info

    return contexts


def extract_ixbrl_facts(html: str, max_facts: int = 100) -> List[Dict[str, Any]]:
    """Extract structured facts from an Inline XBRL HTML document.

    Args:
        html: The HTML content of an iXBRL document.
        max_facts: Maximum number of facts to extract.

    Returns:
        List of fact dicts with keys: name, value, unit, period, context_ref, format.
    """
    soup = BeautifulSoup(html, "html.parser")
    contexts = _extract_context_periods(soup)
    facts: List[Dict[str, Any]] = []

    # Find all ix:nonNumeric and ix:nonFraction elements
    for tag_name in ["ix:nonnumeric", "ix:nonfraction"]:
        for element in soup.find_all(tag_name):
            if len(facts) >= max_facts:
                break

            name = element.get("name", "")
            context_ref = element.get("contextref", "")
            unit_ref = element.get("unitref", "")
            format_ref = element.get("format", "")
            sign = element.get("sign", "")

            if not name:
                continue

            # Get the text value
            text_value = element.get_text(strip=True)

            # Parse numeric value for nonFraction elements
            numeric_value: Optional[float] = None
            if tag_name == "ix:nonfraction":
                numeric_value = _parse_numeric_value(text_value)
                if numeric_value is not None and sign == "-":
                    numeric_value = -numeric_value

            # Get period info from context
            period_info = contexts.get(context_ref, {})

            fact: Dict[str, Any] = {
                "name": name,
                "text": text_value,
                "value": numeric_value,
                "unit": unit_ref,
                "context_ref": context_ref,
                "format": format_ref,
                "period": period_info,
            }

            facts.append(fact)

    return facts


def extract_key_financials(html: str) -> List[Dict[str, Any]]:
    """Extract key financial facts from an iXBRL document.

    Filters to commonly-used GAAP/IFRS concepts and returns structured data.
    """
    all_facts = extract_ixbrl_facts(html)

    key_prefixes = [
        "us-gaap/Revenue",
        "us-gaap/NetIncomeLoss",
        "us-gaap/OperatingIncomeLoss",
        "us-gaap/GrossProfit",
        "us-gaap/Assets",
        "us-gaap/Liabilities",
        "us-gaap/StockholdersEquity",
        "us-gaap/EarningsPerShare",
        "us-gaap/CashAndCashEquivalents",
        "us-gaap/LongTermDebt",
        "ifrs-full/Revenue",
        "ifrs-full/ProfitLoss",
        "ifrs-full/TotalAssets",
        "dei/EntityRegistrantName",
        "dei/TradingSymbol",
        "dei/CurrentFiscalYearEndDate",
    ]

    key_facts = []
    for fact in all_facts:
        name = fact["name"]
        # iXBRL uses ":" separator (us-gaap:Revenues), normalize to "/" for matching
        normalized = name.replace(":", "/")
        if any(normalized.startswith(prefix) or normalized == prefix for prefix in key_prefixes):
            key_facts.append(fact)

    return key_facts
