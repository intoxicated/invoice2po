"""
KpopNara Invoice Automation — Cloud Functions
- identify_and_generate: Product identification (cache + research + judge pipeline)
- generate_po: PO document generation (docx) — see po_generator.py
- sync_to_thrive: Thrive sync — see thrive_sync.py

Model config: LLM_PROVIDER (anthropic|openai|google), LLM_MODEL (model name)
Architecture: PRODUCT_IDENTIFICATION_ARCHITECTURE.md
"""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def _save_research_to_disk(vendor_notation: str, fact_sheet: dict, decision: dict | None = None) -> None:
    """
    Save research (fact_sheet) and optionally decision to disk for judge validation.
    Enable with SAVE_RESEARCH_TO_DISK=1.
    Writes to output/research/ — in Docker, use volume mount ./output:/app/output so files persist on host.
    """
    if not os.environ.get("SAVE_RESEARCH_TO_DISK"):
        return
    try:
        # Prefer OUTPUT_DIR env (e.g. /app/output in Docker when mounted); else project root / output / research
        base = Path(os.environ.get("OUTPUT_DIR", Path(__file__).resolve().parent.parent / "output"))
        out_dir = base / "research"
        out_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^\w\-]", "_", vendor_notation[:60]).strip("_") or "unknown"
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = out_dir / f"research_{ts}_{slug}.json"
        payload = {"vendor_notation": vendor_notation, "fact_sheet": fact_sheet}
        if decision is not None:
            payload["decision"] = decision
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        logger.info("research saved to %s", path)
    except Exception as e:
        logger.warning("save research to disk failed: %s", e)


def _save_result_to_disk(result: dict, vendor_notation: str) -> None:
    """
    Save cloud function result to output/result/ when SAVE_RESEARCH_TO_DISK=1.
    Each identify_and_generate response is written as result_{timestamp}_{slug}.json.
    """
    if not os.environ.get("SAVE_RESEARCH_TO_DISK"):
        return
    try:
        base = Path(os.environ.get("OUTPUT_DIR", Path(__file__).resolve().parent.parent / "output"))
        out_dir = base / "result"
        out_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^\w\-]", "_", vendor_notation[:60]).strip("_") or "unknown"
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = out_dir / f"result_{ts}_{slug}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.info("result saved to %s", path)
    except Exception as e:
        logger.warning("save result to disk failed: %s", e)

import functions_framework

from cache import check_vendor_cache, get_bq_client, resolve_vendor_id, save_vendor_mapping
from formatter import format_output
from judge import run_judge_model
from research_providers import run_research


@functions_framework.http
def identify_and_generate(request):
    """
    Called by n8n for each invoice line item.
    Checks cache first; if miss, uses Claude web search to identify product.
    """
    if request.method != "POST":
        return (json.dumps({"error": "Method not allowed"}), 405, {"Content-Type": "application/json"})

    try:
        data = request.get_json(silent=True) or {}
        if isinstance(data.get("body"), dict):
            data = data["body"]
        vendor_notation = data.get("vendor_notation", "").strip()
        vendor_name = data.get("vendor_name", "").strip()
        quantity = data.get("quantity")
        unit_price = data.get("unit_price")
        total_price = data.get("total_price")

        logger.info(
            "identify request: vendor_notation=%r vendor_name=%r quantity=%s",
            vendor_notation[:80] + "..." if len(vendor_notation) > 80 else vendor_notation,
            vendor_name,
            quantity,
        )

        if not vendor_notation:
            return (
                json.dumps({"error": "vendor_notation is required"}),
                400,
                {"Content-Type": "application/json"},
            )

        bq = get_bq_client()
        standard_vendor_id = resolve_vendor_id(bq, vendor_name)
        logger.info("vendor lookup: vendor_name=%r -> standard_vendor_id=%s", vendor_name, standard_vendor_id or "(none)")

        # [1] Vendor cache lookup
        if standard_vendor_id:
            cached = check_vendor_cache(bq, standard_vendor_id, vendor_notation)
            if cached:
                logger.info("cache HIT: vendor_notation=%r -> sku=%s", vendor_notation[:60], cached.get("sku"))
                qty = quantity if quantity is not None else 0
                try:
                    qty = int(qty) if isinstance(qty, (int, float)) else 0
                except (ValueError, TypeError):
                    qty = 0
                vn_cap = (vendor_notation or "").strip().upper()
                if cached.get("_multi_variant") and len(cached.get("catalog_entries", [])) > 1:
                    entries = cached["catalog_entries"]
                    n = len(entries)
                    base = qty // n
                    remainder = qty % n
                    line_items = []
                    for i, entry in enumerate(entries):
                        split_qty = base + (1 if i < remainder else 0)
                        unit = unit_price or 0
                        total = split_qty * unit if isinstance(unit, (int, float)) else 0
                        line_items.append({
                            "sku": entry.get("sku", ""),
                            "product_name": (entry.get("product_name", "") or "").strip().upper(),
                            "variant_name": (entry.get("variant_name", "") or "").strip().upper(),
                            "quantity": split_qty,
                            "unit_price": unit_price,
                            "total_price": total,
                            "standard_product_id": entry.get("standard_product_id", cached.get("standard_product_id")),
                            "vendor_notation": vn_cap,
                            "vendor_name": vendor_name,
                            "standard_vendor_id": standard_vendor_id,
                            "is_draft": False,
                        })
                    total = sum(li.get("total_price") or 0 for li in line_items)
                    resp = {
                        "standard_product_id": cached.get("standard_product_id"),
                        "sku": entries[0].get("sku", cached.get("sku")),
                        "product_name": (entries[0].get("product_name", "") or "").strip().upper(),
                        "variant_name": (entries[0].get("variant_name", "") or "").strip().upper(),
                        "vendor_notation": vn_cap,
                        "matched_product_name": (entries[0].get("product_name", "") or "").strip().upper(),
                        "vendor_name": vendor_name,
                        "standard_vendor_id": standard_vendor_id,
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "total_price": total if total else total_price,
                        "from_cache": True,
                        "line_items": line_items,
                    }
                    _save_result_to_disk(resp, vendor_notation)
                    return (json.dumps(resp), 200, {"Content-Type": "application/json"})
                pn_cap = (cached.get("product_name", "") or "").strip().upper()
                vrn_cap = (cached.get("variant_name", "") or "").strip().upper()
                resp = {
                    **{k: v for k, v in cached.items() if not k.startswith("_")},
                    "product_name": pn_cap,
                    "variant_name": vrn_cap,
                    "vendor_notation": vn_cap,
                    "matched_product_name": pn_cap,
                    "vendor_name": vendor_name,
                    "standard_vendor_id": standard_vendor_id,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total_price": total_price,
                    "from_cache": True,
                    "line_items": [{
                        "sku": cached.get("sku", ""),
                        "product_name": pn_cap,
                        "variant_name": vrn_cap,
                        "quantity": qty,
                        "unit_price": unit_price,
                        "total_price": total_price,
                        "standard_product_id": cached.get("standard_product_id"),
                        "vendor_notation": vn_cap,
                        "vendor_name": vendor_name,
                        "standard_vendor_id": standard_vendor_id,
                        "is_draft": False,
                    }],
                }
                _save_result_to_disk(resp, vendor_notation)
                return (json.dumps(resp), 200, {"Content-Type": "application/json"})
            else:
                logger.info("cache MISS: vendor_notation=%r", vendor_notation[:60])
        else:
            logger.info("cache SKIP: no standard_vendor_id (vendor not in dim_vendor)")

        # [2–4] Cache miss — Research → Fact Sheet → Judge (facts→catalog) → Formatter
        research_provider = data.get("research_provider") or "perplexity"
        fact_sheet = data.get("fact_sheet")
        logger.info("cache MISS: running research (provider=%s) + judge pipeline", research_provider)
        fact_sheet = run_research(
            vendor_notation,
            vendor_name=vendor_name,
            fact_sheet=fact_sheet,
            provider=research_provider,
        )
        logger.info("research done: artist=%r album=%r versions=%d", fact_sheet.get("artist"), fact_sheet.get("album"), len(fact_sheet.get("versions", [])))

        decision = run_judge_model(vendor_notation, fact_sheet, vendor_name)
        _save_research_to_disk(vendor_notation, fact_sheet, decision)
        logger.info(
            "judge done: matched_sku=%s confidence=%.2f catalog_entries=%d",
            decision.get("matched_sku", "")[:40],
            decision.get("confidence", 0),
            len(decision.get("catalog_entries", [])),
        )

        result = format_output(
            decision,
            vendor_notation=vendor_notation,
            vendor_name=vendor_name,
            standard_vendor_id=standard_vendor_id,
            quantity=quantity,
            unit_price=unit_price,
            total_price=total_price,
        )

        # [6] Persist learning (save to vendor cache when high confidence)
        if standard_vendor_id and not result.get("is_draft") and result.get("confidence", 0) >= 0.7:
            invoice_entries_for_cache = [e for e in result.get("catalog_entries", []) if e.get("is_invoice_item")]
            entry = invoice_entries_for_cache[0] if invoice_entries_for_cache else {}
            cache_product_name = entry.get("product_name", result.get("matched_product_name", ""))
            cache_variant_name = entry.get("variant_name", "")
            logger.info("cache INSERT: vendor_notation=%r sku=%s", vendor_notation[:60], result.get("matched_sku", "")[:40])
            try:
                if len(invoice_entries_for_cache) >= 2:
                    artist = fact_sheet.get("artist", "")
                    album = fact_sheet.get("album", "")
                    invoice_skus = [e.get("sku", "") for e in invoice_entries_for_cache if e.get("sku")]
                    all_entries = result.get("catalog_entries", [])
                    save_vendor_mapping(
                        bq,
                        standard_vendor_id=standard_vendor_id,
                        vendor_notation=vendor_notation,
                        standard_product_id=result["standard_product_id"],
                        sku=result.get("matched_sku", result["standard_product_id"]),
                        product_name=cache_product_name,
                        variant_name=cache_variant_name,
                        confidence=float(result.get("confidence", 0.9)),
                        artist=artist,
                        album=album,
                        invoice_entry_skus=invoice_skus,
                        catalog_entries=all_entries,
                    )
                else:
                    save_vendor_mapping(
                        bq,
                        standard_vendor_id=standard_vendor_id,
                        vendor_notation=vendor_notation,
                        standard_product_id=result["standard_product_id"],
                        sku=result.get("matched_sku", result["standard_product_id"]),
                        product_name=cache_product_name,
                        variant_name=cache_variant_name,
                        confidence=float(result.get("confidence", 0.9)),
                    )
            except Exception as e:
                logger.warning("cache insert failed: %s", e)
        else:
            logger.info("cache SKIP: not saving (is_draft=%s confidence=%.2f)", result.get("is_draft"), result.get("confidence", 0))
        logger.info("identify success: from_cache=false matched_sku=%s", result.get("matched_sku", "")[:40])
        _save_result_to_disk(result, vendor_notation)
        return (json.dumps(result), 200, {"Content-Type": "application/json"})
        # out = {**result, "fact_sheet": fact_sheet}
        # return (json.dumps(out), 200, {"Content-Type": "application/json"})

    except json.JSONDecodeError as e:
        logger.warning("identify error: JSONDecodeError %s", e)
        return (
            json.dumps({"error": f"Invalid request JSON: {e}"}),
            400,
            {"Content-Type": "application/json"},
        )
    except ValueError as e:
        logger.warning("identify error: ValueError %s", e)
        return (
            json.dumps({"error": str(e)}),
            500,
            {"Content-Type": "application/json"},
        )
    except Exception as e:
        logger.exception("identify error: %s", e)
        return (
            json.dumps({"error": str(e), "type": type(e).__name__}),
            500,
            {"Content-Type": "application/json"},
        )
