"""
Product Identification — Judge Model
Transforms FACT SHEET → catalog. No web search. Ontology-aligned.
See judge_prompt.py and docs/PRODUCT_ONTOLOGY.md.
"""

import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from json_adjust import extract_json
from judge_prompt import JUDGE_SYSTEM
from llm import get_llm

logger = logging.getLogger(__name__)


def run_judge_model(
    vendor_notation: str,
    fact_sheet: dict,
    vendor_name: str = "",
) -> dict:
    """
    Judge transforms FACT SHEET → catalog. No web search.
    Never creates variants not in the fact sheet.
    """
    evidence = fact_sheet.get("evidence", "")
    versions = fact_sheet.get("versions", [])
    official = fact_sheet.get("official_versions", [])
    artist = fact_sheet.get("artist", "")
    album = fact_sheet.get("album", "")
    packaging = fact_sheet.get("packaging", [])
    retailer_sources = fact_sheet.get("retailer_sources", [])

    user_prompt = f"""Vendor notation: "{vendor_notation}"
Vendor: {vendor_name}

FACT SHEET (from research — use ONLY these facts):
- artist: {artist}
- album: {album}
- release_type: {fact_sheet.get('release_type', '')}
- packaging: {packaging}
- versions (verified): {versions}
- official_versions: {official}
- retailer_sources: {retailer_sources}

Evidence:
{evidence[:6000]}
"""

    variants_from_cache = fact_sheet.get("variants", [])
    if variants_from_cache:
        user_prompt += f"\nKnown variants (from cache): {variants_from_cache}"

    user_prompt += "\n\nTransform these FACTS into catalog_entries. Set is_invoice_item=true for variants matching the invoice. NEVER invent variants not in the fact sheet. Return ONLY valid JSON with vendor_notation, matched_sku, matched_product_name, standard_product_id, confidence, evidence, catalog_entries."

    llm = get_llm()
    messages = [
        SystemMessage(content=JUDGE_SYSTEM),
        HumanMessage(content=user_prompt),
    ]

    for attempt in range(2):
        response = llm.invoke(messages)
        # Log truncation diagnostics (finish_reason=MAX_TOKENS means output was cut by token limit)
        meta = getattr(response, "response_metadata", None) or {}
        finish_reason = meta.get("finish_reason", "unknown")
        usage = getattr(response, "usage_metadata", None) or {}
        logger.info(
            "judge response: finish_reason=%s input_tokens=%s output_tokens=%s",
            finish_reason,
            usage.get("input_tokens", "?"),
            usage.get("output_tokens", "?"),
        )
        if str(finish_reason).upper() in ("MAX_TOKENS", "2") or finish_reason == 2:
            logger.warning(
                "judge output TRUNCATED by max_output_tokens limit (finish_reason=%s). "
                "Consider increasing max_output_tokens in llm.py or reducing catalog_entries in prompt.",
                finish_reason,
            )
        content = response.content
        if isinstance(content, list) and content:
            content = content[0].get("text", "") if isinstance(content[0], dict) else str(content[0])
        text = content if isinstance(content, str) else str(content)
        try:
            return extract_json(text, vendor_notation=vendor_notation)
        except ValueError as e:
            if "No JSON" in str(e) and attempt == 0:
                logger.warning("judge returned no JSON, retrying with JSON-only reminder: %s", str(e)[:100])
                messages.append(AIMessage(content=text))
                messages.append(
                    HumanMessage(content="That was not valid JSON. Output ONLY a single JSON object. No reasoning, markdown, or other text.")
                )
                continue
            raise
