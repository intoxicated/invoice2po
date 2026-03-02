"""
Product Identification — Naming Formatter
Enforces catalog naming and builds line_items from catalog_entries.
Uses deterministic SKU derivation (parse + normalize, no mappings).
standard_product_id derived deterministically from matched_sku.
"""

import logging
import uuid

from sku_formatter import derive_sku, generate_standard_product_id

logger = logging.getLogger(__name__)

# Naming convention: vendor_notation, product_name, variant_name = CAP (uppercase)


def format_output(
    decision: dict,
    vendor_notation: str,
    vendor_name: str,
    standard_vendor_id: str | None,
    quantity: int | float | None,
    unit_price: float | None,
    total_price: float | None,
) -> dict:
    """
    Enforce naming and build line_items from catalog_entries.
    Preserves API contract for n8n.
    """
    result = dict(decision)
    result["vendor_notation"] = (vendor_notation or "").strip().upper()
    result["matched_product_name"] = (result.get("matched_product_name", "") or "").strip().upper()
    result["vendor_name"] = vendor_name
    result["standard_vendor_id"] = standard_vendor_id
    result["quantity"] = quantity
    result["unit_price"] = unit_price
    result["total_price"] = total_price
    result["from_cache"] = False

    # Derive is_draft from confidence (deterministic; per architecture doc)
    result["is_draft"] = result.get("confidence", 1) < 0.7

    # Normalize catalog_entries and derive deterministic SKUs
    entries = result.get("catalog_entries", [])
    for e in entries:
        e["product_name"] = (e.get("product_name", result.get("matched_product_name", "")) or "").strip().upper()
        e["variant_name"] = (e.get("variant_name", "") or "").strip().upper()
        e["is_draft"] = result["is_draft"]
        e["sku"] = derive_sku(e["product_name"], e["variant_name"])

    result["catalog_entries"] = entries

    # Override matched_sku with deterministic SKU from invoice item
    if invoice_entries := [x for x in entries if x.get("is_invoice_item")]:
        result["matched_sku"] = invoice_entries[0]["sku"]
    else:
        result["matched_sku"] = derive_sku(result["matched_product_name"], "")

    # Ensure standard_product_id (deterministic from matched_sku)
    matched_sku = result.get("matched_sku", "")
    result["standard_product_id"] = (
        generate_standard_product_id(matched_sku)
        if matched_sku
        else (result.get("standard_product_id") or str(uuid.uuid4()))
    )

    # Build line_items with quantity split
    qty = quantity if quantity is not None else 0
    try:
        qty = int(qty) if isinstance(qty, (int, float)) else 0
    except (ValueError, TypeError):
        qty = 0

    if len(invoice_entries) > 1:
        logger.info(
            "quantity SPLIT: qty=%d variants=%d -> %d line_items",
            qty, len(invoice_entries), len(invoice_entries),
        )
        n = len(invoice_entries)
        base = qty // n
        remainder = qty % n
        line_items = []
        for i, entry in enumerate(invoice_entries):
            split_qty = base + (1 if i < remainder else 0)
            unit = unit_price or 0
            total = split_qty * unit if isinstance(unit, (int, float)) else 0
            line_items.append(_line_item(
                entry, result, split_qty, unit_price, total,
                result["vendor_notation"], vendor_name, standard_vendor_id,
            ))
        result["line_items"] = line_items
    else:
        logger.info("quantity SINGLE: qty=%d -> 1 line_item", qty)
        entry = invoice_entries[0] if invoice_entries else {}
        total = total_price
        if total is None and unit_price is not None:
            total = qty * unit_price
        result["line_items"] = [_line_item(
            entry, result, qty, unit_price, total,
            result["vendor_notation"], vendor_name, standard_vendor_id,
        )]

    return result


def _line_item(
    entry: dict,
    result: dict,
    quantity: int,
    unit_price: float | None,
    total_price: float | None,
    vendor_notation: str,
    vendor_name: str,
    standard_vendor_id: str | None,
) -> dict:
    return {
        "sku": entry.get("sku", result.get("matched_sku", "")),
        "product_name": entry.get("product_name", result.get("matched_product_name", "")),
        "variant_name": entry.get("variant_name", ""),
        "quantity": quantity,
        "unit_price": unit_price,
        "total_price": total_price,
        "standard_product_id": result.get("standard_product_id"),
        "standard_vendor_id": standard_vendor_id,
        "vendor_notation": vendor_notation,
        "vendor_name": vendor_name,
        "is_draft": result["is_draft"],
    }
