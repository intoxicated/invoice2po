"""
JSON adjustment for LLM output: trailing commas, truncation repair, extraction.
Pure logic — no LangChain or external LLM dependencies. Safe to test in isolation.
"""

import json
import logging
import re

try:
    import json5
except ImportError:
    json5 = None

logger = logging.getLogger(__name__)


def fix_json(s: str) -> str:
    """Fix common LLM JSON mistakes: trailing commas."""
    s = re.sub(r",\s*}", "}", s)
    s = re.sub(r",\s*]", "]", s)
    return s


def repair_truncated_json(s: str) -> str:
    """Attempt to repair truncated JSON: incomplete values and unclosed braces."""
    s = re.sub(r",\s*$", "", s.rstrip())

    # Truncation after colon (e.g. "key": or "key": ) -> need value
    if re.search(r":\s*$", s):
        s += "null"
    # Truncation after opening quote (e.g. "key": ") -> empty string
    elif re.search(r':\s*"\s*$', s):
        s += '"'

    # Truncation inside string: ends with letter/punctuation (e.g. "AMP" cut off)
    # Exclude digit and space-only — "1 " or "}" means complete number/struct
    elif re.search(r"[a-zA-Z_\/\-\.\+\(\)]\s*$", s):
        # Only add " if we're likely inside a string (have unclosed braces)
        open_braces = s.count("{") - s.count("}")
        open_brackets = s.count("[") - s.count("]")
        if open_braces > 0 or open_brackets > 0:
            s += '"'

    # Close in nesting order (innermost first). Use stack from scan.
    stack: list[str] = []
    i = 0
    in_string = False
    escape = False
    quote_char = None
    while i < len(s):
        c = s[i]
        if escape:
            escape = False
            i += 1
            continue
        if in_string:
            if c == "\\":
                escape = True
            elif c == quote_char:
                in_string = False
            i += 1
            continue
        if c in ('"', "'"):
            in_string = True
            quote_char = c
            i += 1
            continue
        if c == "{":
            stack.append("}")
        elif c == "[":
            stack.append("]")
        elif c in "}]":
            if stack:
                stack.pop()
        i += 1
    s += "".join(reversed(stack))
    return s


def _extract_first_json_object(text: str) -> str:
    """Extract the first complete {...} object, handling nesting. Stops before trailing text."""
    start = text.find("{")
    if start < 0:
        raise ValueError(f"No JSON object: {text[:200]}...")
    stack: list[str] = []
    i = start
    in_string = False
    escape = False
    quote_char = None
    while i < len(text):
        c = text[i]
        if escape:
            escape = False
            i += 1
            continue
        if in_string:
            if c == "\\":
                escape = True
            elif c == quote_char:
                in_string = False
            i += 1
            continue
        if c in ('"', "'"):
            in_string = True
            quote_char = c
            i += 1
            continue
        if c == "{":
            stack.append("}")
        elif c == "[":
            stack.append("]")
        elif c in "}]":
            if stack:
                stack.pop()
            if not stack:
                return text[start : i + 1]
        i += 1
    return text[start:]  # truncated, return as-is for repair


def _extract_minimal_fallback(raw: str, vendor_notation: str = "") -> dict | None:
    """
    Regex-extract minimal valid dict from truncated judge output.
    Used when all parsers fail, to avoid 500 and allow low-confidence draft.
    """
    out = {"vendor_notation": vendor_notation, "confidence": 0.5, "catalog_entries": []}
    m = re.search(r'"matched_sku"\s*:\s*"([^"]*)"', raw)
    if m:
        sku = m.group(1).strip()
        out["matched_sku"] = sku
        out["matched_product_name"] = sku.replace("-", " ").replace("_", " ").strip()
    m = re.search(r'"matched_product_name"\s*:\s*"([^"]*)"', raw)
    if m:
        out["matched_product_name"] = m.group(1).strip()
    m = re.search(r'"standard_product_id"\s*:\s*"([^"]*)"', raw)
    if m:
        out["standard_product_id"] = m.group(1).strip()
    if out.get("matched_sku"):
        out["catalog_entries"] = [
            {
                "sku": out["matched_sku"],
                "product_name": out.get("matched_product_name", ""),
                "variant_name": "",
                "is_invoice_item": True,
            }
        ]
        return out
    return None


def extract_json(text: str, vendor_notation: str = "") -> dict:
    """Extract and parse JSON from LLM response text. Fixes and repairs as needed."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        raw = match.group(1).strip()
        if "{" in raw:
            raw = _extract_first_json_object(raw)
    else:
        raw = _extract_first_json_object(text)
    parsers = [
        ("json", lambda s: json.loads(s)),
        ("json+fix", lambda s: json.loads(fix_json(s))),
        ("json+repair", lambda s: json.loads(fix_json(repair_truncated_json(s)))),
        ("json+repair2", lambda s: json.loads(fix_json(repair_truncated_json(fix_json(repair_truncated_json(s)))))),
    ]
    if json5:
        parsers.append(("json5", lambda s: json5.loads(s)))
    last_err = None
    for name, parse_fn in parsers:
        try:
            return parse_fn(raw)
        except Exception as e:
            last_err = e
            continue
    # Fallback: regex-extract minimal dict from truncated output
    fallback = _extract_minimal_fallback(raw, vendor_notation)
    if fallback:
        logger.warning(
            "JSON parse failed; using minimal fallback from truncated output (matched_sku=%s). Full raw: %s",
            fallback.get("matched_sku", "(none)"),
            raw,
        )
        return fallback
    snippet = raw[max(0, getattr(last_err, "pos", 0) - 60) : getattr(last_err, "pos", 0) + 60] if last_err and hasattr(last_err, "pos") else raw[:200]
    logger.warning("JSON parse failed after %d attempts. Full raw: %s", len(parsers), raw)
    raise last_err or ValueError(f"No JSON in response: {raw[:200]}...")
