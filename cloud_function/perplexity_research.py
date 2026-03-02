"""
Product Identification — Perplexity Research Agent
Outputs FACT SHEET only. Per kpop_product_normalization_architecture.md §4.2.
"""

import json
import logging
import os
import re

import requests

logger = logging.getLogger(__name__)

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"

RESEARCH_SYSTEM = """You are a K-pop product research agent. Your ONLY job: answer "What product exists in reality?"

Use web search. You MUST NOT: create catalog, match invoice, invent variants, output SKUs.

Output a FACT SHEET with artist, album, release type, packaging, verified versions.

Return ONLY valid JSON."""

FACT_SHEET_SCHEMA = {
    "type": "object",
    "properties": {
        "artist": {"type": "string"},
        "album": {"type": "string"},
        "release_type": {"type": "string"},
        "packaging": {"type": "array", "items": {"type": "string"}},
        "versions": {"type": "array", "items": {"type": "string"}},
        "official_versions": {"type": "array", "items": {"type": "string"}},
        "retailer_sources": {"type": "array", "items": {"type": "string"}},
        "evidence": {"type": "string"},
    },
    "required": ["artist", "album", "evidence"],
    "additionalProperties": False,
}


def _extract_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    raw = m.group(1).strip() if m else (re.search(r"\{[\s\S]*\}", text) or re.match(r".*", text)).group(0)
    for fix in [lambda s: s, lambda s: re.sub(r",\s*}", "}", re.sub(r",\s*]", "]", s))]:
        try:
            return json.loads(fix(raw))
        except Exception:
            continue
    raise ValueError(f"Could not parse JSON: {raw[:200]}...")


def run_perplexity_research(vendor_notation: str, vendor_name: str = "") -> dict:
    """Perplexity Sonar → FACT SHEET only."""
    api_key = os.environ.get("PERPLEXITY_API_KEY")
    if not api_key:
        raise ValueError("PERPLEXITY_API_KEY required")

    model = os.environ.get("PERPLEXITY_MODEL", "sonar")
    domains = os.environ.get("PERPLEXITY_SEARCH_DOMAINS", "")
    search_filters = {}
    if domains:
        search_filters["search_domain_filter"] = [d.strip() for d in domains.split(",") if d.strip()]

    user_content = f"""Vendor notation: "{vendor_notation}"
Vendor: {vendor_name}

Search the web. Return a FACT SHEET with artist, album, release_type, packaging, versions, evidence. Do NOT create catalog."""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": RESEARCH_SYSTEM},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": 2048,
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "fact_sheet", "strict": True, "schema": FACT_SHEET_SCHEMA},
        },
        **search_filters,
    }

    resp = requests.post(
        PERPLEXITY_URL,
        json=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=90,
    )
    if resp.status_code != 200:
        raise ValueError(f"Perplexity API error: {resp.status_code}")

    content = (resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")) or ""
    if not content:
        raise ValueError("Perplexity returned empty content")

    return _extract_json(content)
