"""
Product Identification — Perplexity Research Agent
Outputs FACT SHEET only. No catalog, no invoice matching.
Per kpop_product_normalization_architecture.md §4.2.
"""

import json
import logging
import os
import re

import requests

try:
    import json5
except ImportError:
    json5 = None

logger = logging.getLogger(__name__)

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"

RESEARCH_SYSTEM_PROMPT = """You are a K-pop product research agent for KpopNara. Your ONLY job is to answer: "What product exists in reality?"

Use web search to find factual information about the product. You MUST NOT:
- Create catalog entries
- Decide which variant matches an invoice
- Invent variants without evidence
- Output SKUs or matched_sku

Output a FACT SHEET: artist, album, release type, packaging formats, and verified version names.

Rules:
- artist: official promoted name (e.g. IVE, BTS, AMPERS&ONE)
- album: product/album name base (e.g. REVIVE+, LOUD & PROUD)
- release_type: 1ST ALBUM, 2ND MINI ALBUM, 3RD SINGLE, etc.
- packaging: list of formats like [DIGIPACK], [PHOTOBOOK], [JEWEL CASE]
- versions: list of verified variant names (member names, version names like BANGERS VER., KIWEE)
- official_versions: variants confirmed from official sources
- retailer_sources: ktown4u, musicplaza, yesasia, etc.
- evidence: brief research reasoning with source references

Return ONLY valid JSON matching the schema."""

FACT_SHEET_SCHEMA = {
    "type": "object",
    "properties": {
        "artist": {"type": "string", "description": "Official artist/group name"},
        "album": {"type": "string", "description": "Album/product name"},
        "release_type": {"type": "string", "description": "1ST ALBUM, 2ND MINI ALBUM, etc."},
        "packaging": {
            "type": "array",
            "items": {"type": "string"},
            "description": "DIGIPACK, PHOTOBOOK, JEWEL CASE, etc.",
        },
        "versions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Verified variant names",
        },
        "official_versions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Officially confirmed variants",
        },
        "retailer_sources": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Source retailers",
        },
        "evidence": {"type": "string", "description": "Research reasoning"},
    },
    "required": ["artist", "album", "evidence"],
    "additionalProperties": False,
}


def _fix_json(s: str) -> str:
    s = re.sub(r",\s*}", "}", s)
    s = re.sub(r",\s*]", "]", s)
    return s


def _extract_json(text: str) -> dict:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        raw = match.group(1).strip()
    else:
        match = re.search(r"\{[\s\S]*\}", text)
        raw = match.group(0) if match else "{}"
    for parse in [lambda s: json.loads(s), lambda s: json.loads(_fix_json(s))]:
        try:
            return parse(raw)
        except Exception:
            continue
    raise ValueError(f"Could not parse JSON from response: {raw[:200]}...")


def run_perplexity_research(vendor_notation: str, vendor_name: str = "") -> dict:
    """
    Call Perplexity Sonar. Returns FACT SHEET only.
    """
    api_key = os.environ.get("PERPLEXITY_API_KEY")
    if not api_key:
        raise ValueError("PERPLEXITY_API_KEY required for Perplexity research")

    model = os.environ.get("PERPLEXITY_MODEL", "sonar")
    domains = os.environ.get("PERPLEXITY_SEARCH_DOMAINS", "")
    search_filters = {}
    if domains:
        search_filters["search_domain_filter"] = [d.strip() for d in domains.split(",") if d.strip()]

    user_content = f"""Vendor notation: "{vendor_notation}"
Vendor: {vendor_name}

Search the web to identify this K-pop product. Return a FACT SHEET with artist, album, release type, packaging, and verified versions. Do NOT create catalog or match invoice."""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": 2048,
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "fact_sheet",
                "strict": True,
                "schema": FACT_SHEET_SCHEMA,
            },
        },
        **search_filters,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    resp = requests.post(PERPLEXITY_URL, json=payload, headers=headers, timeout=90)
    if resp.status_code != 200:
        logger.error("Perplexity API error: %s %s", resp.status_code, resp.text[:300])
        raise ValueError(f"Perplexity API error: {resp.status_code}")

    data = resp.json()
    content = (data.get("choices", [{}])[0].get("message", {}).get("content", "")) or ""
    if not content:
        raise ValueError("Perplexity returned empty content")

    return _extract_json(content)
