"""
Deterministic SKU derivation from product_name + variant_name.
Parse artist/product, apply abbreviations, normalize to alphanumeric uppercase.
Deterministic standard_product_id from SKU.
"""

import hashlib
import re

# Abbreviation substitutions (case-insensitive); apply in order
_ABBREVS = [
    (r"\bMini Album\b", "MA"),
    (r"\bSingle Album\b", "SA"),
    (r"\bFull Album\b", "FA"),
    (r"\bVersion\b", "V"),
    (r"\bVer\.\b", "V"),
    (r"\bVer\b", "V"),
    (r"\bPostcard\b", "PC"),
    (r"\bLimited\b", "LTD"),
    (r"\b1st\b", "1"),
    (r"\b2nd\b", "2"),
    (r"\b3rd\b", "3"),
    (r"\b4th\b", "4"),
    (r"\b5th\b", "5"),
    (r"\b6th\b", "6"),
    (r"\b7th\b", "7"),
    (r"\b8th\b", "8"),
    (r"\b9th\b", "9"),
]


def parse_product_name(product_name: str) -> tuple[str, str]:
    """
    Split product_name on first ' - ' (space-hyphen-space).
    Returns (artist, product) where product is album name + version/format, kept as-is.
    """
    if not product_name or " - " not in product_name:
        return ("", product_name or "")
    parts = product_name.split(" - ", 1)
    artist = parts[0].strip()
    product = parts[1].strip()
    return (artist, product)


def _apply_abbreviations(text: str) -> str:
    """Apply deterministic abbreviation substitutions (case-insensitive)."""
    for pattern, repl in _ABBREVS:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    return text


def normalize_to_sku(text: str) -> str:
    """
    Normalize text for SKU: apply abbreviations, keep alphanumeric only,
    remove spaces (concatenate), uppercase.
    """
    if not text or not str(text).strip():
        return ""
    t = str(text).strip()
    t = _apply_abbreviations(t)
    t = re.sub(r"[^A-Za-z0-9]", "", t)
    return t.upper()


def derive_sku(product_name: str, variant_name: str) -> str:
    """
    Deterministic SKU: {ARTIST}-{PRODUCT}-{VARIANT}
    All parts uppercase, alphanumeric only, with abbreviations applied.
    """
    artist, product = parse_product_name(product_name or "")
    a = normalize_to_sku(artist)
    p = normalize_to_sku(product)
    v = normalize_to_sku(variant_name or "")
    if not v:
        v = "STD"
    parts = [a or "UNK", p or "XX", v]
    return "-".join(parts)


def generate_standard_product_id(sku: str) -> str | None:
    """
    Generate deterministic standard_product_id from SKU.
    Same SKU always yields the same standard_product_id.
    """
    if not sku or sku.strip() == "":
        return None
    sku_normalized = sku.upper().strip()
    hash_object = hashlib.md5(f"product_{sku_normalized}".encode())
    hash_hex = hash_object.hexdigest()[:16]
    return f"std_product_{hash_hex}"
