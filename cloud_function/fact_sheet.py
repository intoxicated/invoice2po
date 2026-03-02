"""
Product Identification — Fact Sheet Schema
Source of truth from research. Per kpop_product_normalization_architecture.md.

Research outputs FACT SHEET only. Judge transforms facts → catalog.
Never create variants not present in fact sheet.
"""

from typing import Any

# Full fact sheet (from Perplexity agent or manual)
FACT_SHEET_SCHEMA = {
    "artist": "str — official artist/group name",
    "album": "str — album/product name",
    "release_type": "str — 1ST ALBUM, 2ND MINI ALBUM, etc.",
    "packaging": "list[str] — [DIGIPACK], [PHOTOBOOK], [JEWEL CASE], etc.",
    "versions": "list[str] — known variants (member names, version names)",
    "official_versions": "list[str] — verified official variant names",
    "retailer_sources": "list[str] — ktown4u, musicplaza, yesasia, etc.",
    "evidence": "str — research reasoning, citations",
}


def is_full_fact_sheet(data: dict) -> bool:
    """True if structured fact sheet with artist/album."""
    return bool(data.get("artist") or data.get("album"))


def normalize_fact_sheet(data: dict) -> dict:
    """Ensure fact sheet has required keys with defaults."""
    return {
        "artist": (data.get("artist") or "").strip(),
        "album": (data.get("album") or "").strip(),
        "release_type": (data.get("release_type") or "").strip(),
        "packaging": list(data.get("packaging") or []),
        "versions": list(data.get("versions") or []),
        "official_versions": list(data.get("official_versions") or []),
        "retailer_sources": list(data.get("retailer_sources") or []),
        "evidence": (data.get("evidence") or "").strip(),
        "_legacy": not is_full_fact_sheet(data),
    }
