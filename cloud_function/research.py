"""
Product Identification — Research Worker
Gathers evidence via web search. Max 2 searches. Never chooses SKU.
"""

import logging

logger = logging.getLogger(__name__)
MAX_SEARCHES = 2


def normalize_query(text: str) -> str:
    return (
        text.lower()
        .replace("ver.", "version")
        .replace("digip", "digipack")
        .replace("rnd", "random")
        .replace("+", " plus ")
    )


def _web_search(query: str) -> str:
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        search = DuckDuckGoSearchRun()
        return search.run(query)
    except Exception as e:
        logger.warning("web_search failed: %s", e)
        return f"[Search unavailable: {str(e)[:100]}]"


def run_research_worker(vendor_notation: str) -> dict:
    base = normalize_query(vendor_notation)

    queries = [
        base,
        (
            f"{base} kpop album versions digipack photobook member "
            "cover image site:ktown4u.com OR site:musicplaza.com OR site:yesasia.com"
        ),
    ]

    results = []

    for q in queries[:MAX_SEARCHES]:
        results.append(_web_search(q))

    # fail-safe retry
    if len(results[0]) < 200:
        results[0] = _web_search(base + " kpop album")

    evidence = "\n\n--- IDENTITY ---\n\n"
    evidence += results[0]
    evidence += "\n\n--- VARIANTS ---\n\n"
    evidence += results[1]

    return {
        "album": "",
        "variants_found": [],
        "evidence": evidence,
        "search_count": len(results),
    }