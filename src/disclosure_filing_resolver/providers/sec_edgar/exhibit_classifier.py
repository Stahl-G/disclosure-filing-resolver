"""Classify filing documents by role (e.g., financial_statements, press_release)."""

from __future__ import annotations

import re

from disclosure_filing_resolver.models import FilingDocument

# Role definitions with keywords and priority
ROLE_DEFINITIONS: dict[str, dict] = {
    "financial_statements": {
        "keywords": [
            "unaudited interim consolidated financial statements",
            "interim consolidated financial statements",
            "interim financial statements",
            "consolidated financial statements",
            "financial statements",
            "balance sheet",
            "income statement",
            "cash flow statement",
            "statement of operations",
        ],
        "priority": 100,
    },
    "operating_review": {
        "keywords": [
            "operating and financial review",
            "management discussion",
            "md&a",
            "results of operations",
            "liquidity and capital resources",
            "operating review",
            "financial review",
        ],
        "priority": 90,
    },
    "material_contract": {
        "keywords": [
            "material contract",
            "agreement",
            "credit agreement",
            "loan agreement",
            "supply agreement",
            "share purchase agreement",
            "amendment",
        ],
        "priority": 85,
    },
    "subsidiaries": {
        "keywords": [
            "list of subsidiaries",
            "significant subsidiaries",
            "subsidiaries",
        ],
        "priority": 80,
    },
    "press_release": {
        "keywords": [
            "press release",
            "earnings release",
            "financial results",
            "results for the quarter",
            "quarterly results",
            "announcement",
        ],
        "priority": 70,
    },
    "presentation": {
        "keywords": [
            "investor presentation",
            "presentation",
            "earnings presentation",
            "slide",
        ],
        "priority": 60,
    },
    "risk_factors": {
        "keywords": [
            "risk factors",
            "risks",
        ],
        "priority": 50,
    },
    "certification": {
        "keywords": [
            "certification",
            "certified",
            "section 302",
            "section 906",
            "sox",
        ],
        "priority": 40,
    },
    "cover": {
        "keywords": [
            "cover page",
            "cover",
            "form 6-k",
            "exhibit index",
        ],
        "priority": 10,
    },
}

# Exhibit number patterns
EX99_PATTERN = re.compile(r"ex(?:hibit)?[\s-]*99[\s.-]*(\d*)", re.IGNORECASE)


def classify_document(doc: FilingDocument, is_primary: bool = False) -> FilingDocument:
    """Classify a document's role based on its metadata.

    Args:
        doc: The document to classify
        is_primary: Whether this is the primary (cover) document

    Returns:
        Updated document with role, priority, and confidence
    """
    # Build search text from available metadata
    search_parts = [
        doc.document_type or "",
        doc.description or "",
        doc.filename,
    ]
    search_text = " ".join(search_parts).lower()

    # Check exhibit number pattern (Exhibit 99.x)
    ex99_match = EX99_PATTERN.search(doc.filename)
    ex99_num = None
    if ex99_match:
        ex99_num = ex99_match.group(1)

    # If primary document and no strong keyword match, classify as cover
    if is_primary:
        best_role = "cover"
        best_priority = 10
        best_confidence = 0.7
        for role_name, role_def in ROLE_DEFINITIONS.items():
            if role_name == "cover":
                continue
            for keyword in role_def["keywords"]:
                if keyword.lower() in search_text:
                    candidate_priority = role_def["priority"]
                    if candidate_priority > best_priority:
                        best_role = role_name
                        best_priority = candidate_priority
                        best_confidence = 0.9
                    break
        doc.role = best_role
        doc.priority = best_priority
        doc.confidence = best_confidence
        return doc

    # Non-primary: match against role keywords
    best_role = "unknown"
    best_priority = 0
    best_confidence = 0.3

    for role_name, role_def in ROLE_DEFINITIONS.items():
        for keyword in role_def["keywords"]:
            if keyword.lower() in search_text:
                candidate_priority = role_def["priority"]
                if candidate_priority > best_priority:
                    best_role = role_name
                    best_priority = candidate_priority
                    best_confidence = 0.85
                break

    # If still unknown but is an Exhibit 99.x, mark with lower confidence
    if best_role == "unknown" and ex99_num:
        best_role = "unknown"
        best_priority = 5
        best_confidence = 0.4

    doc.role = best_role
    doc.priority = best_priority
    doc.confidence = best_confidence
    return doc


def classify_documents(documents: list[FilingDocument]) -> list[FilingDocument]:
    """Classify all documents in a filing.

    The first document is typically the cover/primary document.
    """
    for i, doc in enumerate(documents):
        is_primary = i == 0
        classify_document(doc, is_primary=is_primary)
    return documents
