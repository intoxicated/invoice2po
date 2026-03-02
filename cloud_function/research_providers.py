"""
Product Identification — Research Abstraction
Per kpop_product_normalization_architecture.md: Research → FACT SHEET only.

Providers: manual (pass-through), duckduckgo, perplexity.
"""

import logging

from fact_sheet import normalize_fact_sheet

logger = logging.getLogger(__name__)


def run_research(
    vendor_notation: str,
    vendor_name: str = "",
    fact_sheet: dict | None = None,
    provider: str | None = None,
) -> dict:
    """
    Get fact sheet for product research.
    Provider: manual | duckduckgo | perplexity
    """
    provider = (provider or "duckduckgo").lower()

    # Manual: fact_sheet must be provided in request
    if provider == "manual":
        if fact_sheet and isinstance(fact_sheet, dict):
            logger.info("research: manual fact_sheet provided")
            return normalize_fact_sheet(fact_sheet)
        raise ValueError("research_provider=manual requires fact_sheet in request body")

    if fact_sheet and isinstance(fact_sheet, dict):
        logger.info("research: fact_sheet provided (overrides provider)")
        return normalize_fact_sheet(fact_sheet)

    if provider == "perplexity":
        return _run_perplexity_research(vendor_notation, vendor_name)
    if provider == "duckduckgo":
        return _run_duckduckgo_research(vendor_notation)

    raise ValueError(f"Unknown research provider: {provider}. Use manual, duckduckgo, or perplexity.")


def _run_perplexity_research(vendor_notation: str, vendor_name: str) -> dict:
    """Perplexity agent: web search → fact sheet only."""
    try:
        from research_agent_perplexity import run_perplexity_research

        sheet = run_perplexity_research(vendor_notation, vendor_name)
        return normalize_fact_sheet(sheet)
    except ImportError as e:
        logger.warning("Perplexity research not available: %s", e)
        raise ValueError(
            "research_provider=perplexity requires research_agent_perplexity and PERPLEXITY_API_KEY"
        )


def _run_duckduckgo_research(vendor_notation: str) -> dict:
    """DuckDuckGo: web search → legacy evidence format (converted to fact sheet)."""
    from research import run_research_worker

    raw = run_research_worker(vendor_notation)
    # Convert to fact sheet shape (legacy)
    return normalize_fact_sheet({
        "artist": "",
        "album": raw.get("album", ""),
        "release_type": "",
        "packaging": [],
        "versions": raw.get("variants_found", []),
        "official_versions": [],
        "retailer_sources": [],
        "evidence": raw.get("evidence", ""),
    })
