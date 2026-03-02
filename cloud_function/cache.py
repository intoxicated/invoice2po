"""
Product Identification — Cache layer
- Vendor cache (vendor_product_map): vendor_notation → product mapping (single or pointer to product_catalog_cache)
- product_catalog_cache: (vendor_id, artist, album) → full catalog_entries (multi-variant only)
- Variant knowledge cache (album_variant_knowledge): artist+album → variants (optional)
"""

import hashlib
import json
import logging

from google.cloud import bigquery

logger = logging.getLogger(__name__)


def get_bq_client():
    project = __import__("os").environ.get("GCP_PROJECT") or "kpn-platform"
    return bigquery.Client(project=project)

def generate_standard_vendor_id(name: str) -> str:
    """Generate standardized vendor ID."""
    if not name or name == "Unknown Vendor":
        return "UNKNOWN_VENDOR"
    return hashlib.sha256(f"VENDOR_{name}".encode("utf-8")).hexdigest()

def resolve_vendor_id(client: bigquery.Client, vendor_name: str) -> str | None:
    """Resolve vendor_name to standard_vendor_id from dim_vendor."""
    return generate_standard_vendor_id(vendor_name)
    # query = """
    # SELECT standard_vendor_id FROM `etl_data.dim_vendor`
    # WHERE LOWER(TRIM(vendor_name)) = LOWER(TRIM(@name))
    # LIMIT 1
    # """
    # job_config = bigquery.QueryJobConfig(
    #     query_parameters=[bigquery.ScalarQueryParameter("name", "STRING", vendor_name)]
    # )
    # rows = list(client.query(query, job_config=job_config).result())
    # return rows[0].standard_vendor_id if rows else 


def check_product_catalog_cache(
    client: bigquery.Client,
    standard_vendor_id: str,
    artist: str,
    album: str,
) -> list[dict] | None:
    """Fetch catalog_entries from product_catalog_cache. Returns list or None."""
    project = __import__("os").environ.get("GCP_PROJECT") or "kpn-platform"
    try:
        query = """
        SELECT catalog_entries
        FROM `{project}.etl_data.product_catalog_cache`
        WHERE standard_vendor_id = @vendor_id
          AND LOWER(TRIM(artist)) = LOWER(TRIM(@artist))
          AND LOWER(TRIM(album)) = LOWER(TRIM(@album))
        LIMIT 1
        """.format(project=project)
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("vendor_id", "STRING", standard_vendor_id),
                bigquery.ScalarQueryParameter("artist", "STRING", artist or ""),
                bigquery.ScalarQueryParameter("album", "STRING", album or ""),
            ]
        )
        rows = list(client.query(query, job_config=job_config).result())
        if not rows:
            return None
        raw = rows[0].catalog_entries
        if isinstance(raw, str):
            raw = json.loads(raw)
        return list(raw) if raw else None
    except Exception as e:
        logger.debug("product_catalog_cache lookup skipped: %s", e)
        return None


def _parse_invoice_entry_skus(val) -> list[str]:
    """Parse invoice_entry_skus from row (ARRAY<STRING>, JSON string, or None)."""
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x) for x in val]
    if isinstance(val, str):
        try:
            arr = json.loads(val)
            return [str(x) for x in arr] if isinstance(arr, list) else []
        except json.JSONDecodeError:
            return []
    return []


def check_vendor_cache(
    client: bigquery.Client, standard_vendor_id: str, vendor_notation: str
) -> dict | None:
    """
    Look up vendor_product_map. Returns mapping dict or None if miss.
    Single variant: returns {sku, product_name, variant_name, standard_product_id}.
    Multi variant: returns {catalog_entries, ...} after fetching product_catalog_cache.
    """
    if not standard_vendor_id:
        return None
    project = __import__("os").environ.get("GCP_PROJECT") or "kpn-platform"
    query = f"""
    SELECT standard_product_id, sku, product_name, variant_name,
           artist, album, invoice_entry_skus
    FROM `{project}.etl_data.vendor_product_map`
    WHERE standard_vendor_id = @vendor_id
      AND LOWER(TRIM(vendor_notation)) = LOWER(TRIM(@notation))
    LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("vendor_id", "STRING", standard_vendor_id),
            bigquery.ScalarQueryParameter("notation", "STRING", vendor_notation),
        ]
    )
    try:
        rows = list(client.query(query, job_config=job_config).result())
    except Exception as e:
        query_legacy = f"""
        SELECT standard_product_id, sku, product_name, variant_name
        FROM `{project}.etl_data.vendor_product_map`
        WHERE standard_vendor_id = @vendor_id
          AND LOWER(TRIM(vendor_notation)) = LOWER(TRIM(@notation))
        LIMIT 1
        """
        job_config_legacy = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("vendor_id", "STRING", standard_vendor_id),
                bigquery.ScalarQueryParameter("notation", "STRING", vendor_notation),
            ]
        )
        rows = list(client.query(query_legacy, job_config=job_config_legacy).result())
        if not rows:
            return None
        r = rows[0]
        return {
            "standard_product_id": r.standard_product_id,
            "sku": r.sku,
            "product_name": r.product_name.upper(),
            "variant_name": (getattr(r, "variant_name", None) or "").upper(),
        }

    if not rows:
        return None
    r = rows[0]
    invoice_skus = _parse_invoice_entry_skus(getattr(r, "invoice_entry_skus", None))
    artist = getattr(r, "artist", None) or ""
    album = getattr(r, "album", None) or ""

    if len(invoice_skus) < 2:
        return {
            "standard_product_id": r.standard_product_id,
            "sku": r.sku,
            "product_name": r.product_name.upper(),
            "variant_name": (getattr(r, "variant_name", None) or "").upper(),
        }

    catalog_entries = check_product_catalog_cache(client, standard_vendor_id, artist, album)
    if not catalog_entries:
        logger.warning("multi-variant cache: product_catalog_cache miss for artist=%r album=%r", artist, album)
        return {
            "standard_product_id": r.standard_product_id,
            "sku": r.sku,
            "product_name": r.product_name.upper(),
            "variant_name": (getattr(r, "variant_name", None) or "").upper(),
        }

    invoice_entries = [e for e in catalog_entries if e.get("sku") in invoice_skus]
    if not invoice_entries:
        invoice_entries = catalog_entries[:1]
    return {
        "catalog_entries": invoice_entries,
        "standard_product_id": invoice_entries[0].get("standard_product_id", r.standard_product_id),
        "sku": invoice_entries[0].get("sku", r.sku),
        "product_name": (invoice_entries[0].get("product_name") or r.product_name).upper(),
        "variant_name": (invoice_entries[0].get("variant_name") or "").upper(),
        "_multi_variant": True,
    }


def get_variant_knowledge(
    client: bigquery.Client, artist: str, album: str
) -> dict | None:
    """
    Look up album_variant_knowledge. Returns {artist, album, variants} or None.
    Table is optional; returns None if table doesn't exist or no match.
    """
    try:
        project = __import__("os").environ.get("GCP_PROJECT") or "kpn-platform"
        query = """
        SELECT artist, album, variants
        FROM `{project}.etl_data.album_variant_knowledge`
        WHERE LOWER(TRIM(artist)) = LOWER(TRIM(@artist))
          AND LOWER(TRIM(album)) = LOWER(TRIM(@album))
        LIMIT 1
        """.format(project=project)
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("artist", "STRING", artist or ""),
                bigquery.ScalarQueryParameter("album", "STRING", album or ""),
            ]
        )
        rows = list(client.query(query, job_config=job_config).result())
        if not rows:
            return None
        r = rows[0]
        variants = list(r.variants) if r.variants else []
        return {"artist": r.artist, "album": r.album, "variants": variants}
    except Exception as e:
        logger.debug("variant knowledge lookup skipped: %s", e)
        return None


def save_product_catalog_cache(
    client: bigquery.Client,
    standard_vendor_id: str,
    artist: str,
    album: str,
    catalog_entries: list[dict],
) -> None:
    """Upsert catalog_entries into product_catalog_cache."""
    project = __import__("os").environ.get("GCP_PROJECT", client.project)
    table_id = f"{project}.etl_data.product_catalog_cache"
    entries_json = json.dumps(catalog_entries)
    query = f"""
    MERGE `{table_id}` T
    USING (
        SELECT @vendor_id AS standard_vendor_id, @artist AS artist, @album AS album,
               PARSE_JSON(@entries) AS catalog_entries
    ) S
    ON T.standard_vendor_id = S.standard_vendor_id
      AND LOWER(TRIM(T.artist)) = LOWER(TRIM(S.artist))
      AND LOWER(TRIM(T.album)) = LOWER(TRIM(S.album))
    WHEN MATCHED THEN UPDATE SET
        catalog_entries = S.catalog_entries,
        updated_at = CURRENT_TIMESTAMP()
    WHEN NOT MATCHED THEN INSERT (
        standard_vendor_id, artist, album, catalog_entries, created_at, updated_at
    ) VALUES (
        S.standard_vendor_id, S.artist, S.album, S.catalog_entries,
        CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP()
    )
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("vendor_id", "STRING", standard_vendor_id),
            bigquery.ScalarQueryParameter("artist", "STRING", (artist or "").strip()),
            bigquery.ScalarQueryParameter("album", "STRING", (album or "").strip()),
            bigquery.ScalarQueryParameter("entries", "STRING", entries_json),
        ]
    )
    client.query(query, job_config=job_config).result()


def save_vendor_mapping(
    client: bigquery.Client,
    standard_vendor_id: str,
    vendor_notation: str,
    standard_product_id: str,
    sku: str,
    product_name: str,
    variant_name: str,
    confidence: float,
    verified_by: str = "ai",
    *,
    artist: str | None = None,
    album: str | None = None,
    invoice_entry_skus: list[str] | None = None,
    catalog_entries: list[dict] | None = None,
) -> None:
    """
    Insert new mapping into vendor_product_map.
    Single variant: legacy columns only.
    Multi variant: also saves to product_catalog_cache and stores artist, album, invoice_entry_skus.
    """
    project = __import__("os").environ.get("GCP_PROJECT", client.project)
    table_id = f"{project}.etl_data.vendor_product_map"
    is_multi = bool(
        invoice_entry_skus
        and len(invoice_entry_skus) >= 2
        and artist
        and album
        and catalog_entries
    )
    if is_multi:
        try:
            save_product_catalog_cache(client, standard_vendor_id, artist, album, catalog_entries)
        except Exception as e:
            logger.warning("save_product_catalog_cache failed (table may not exist): %s", e)
        try:
            query = f"""
            INSERT INTO `{table_id}` (
                standard_vendor_id, vendor_notation, standard_product_id, sku,
                product_name, variant_name, confidence, verified_by,
                artist, album, invoice_entry_skus, created_at, updated_at
            )
            VALUES (
                @vendor_id, @notation, @product_id, @sku,
                @product_name, @variant_name, @confidence, @verified_by,
                @artist, @album, @skus, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP()
            )
            """
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("vendor_id", "STRING", standard_vendor_id),
                    bigquery.ScalarQueryParameter("notation", "STRING", vendor_notation.strip()),
                    bigquery.ScalarQueryParameter("product_id", "STRING", standard_product_id),
                    bigquery.ScalarQueryParameter("sku", "STRING", sku),
                    bigquery.ScalarQueryParameter("product_name", "STRING", product_name),
                    bigquery.ScalarQueryParameter("variant_name", "STRING", variant_name or None),
                    bigquery.ScalarQueryParameter("confidence", "FLOAT64", confidence),
                    bigquery.ScalarQueryParameter("verified_by", "STRING", verified_by),
                    bigquery.ScalarQueryParameter("artist", "STRING", artist.strip()),
                    bigquery.ScalarQueryParameter("album", "STRING", album.strip()),
                    bigquery.ArrayQueryParameter("skus", "STRING", invoice_entry_skus),
                ]
            )
            client.query(query, job_config=job_config).result()
            return
        except Exception as e:
            logger.warning("multi-variant insert failed (columns may not exist), falling back to single: %s", e)
            is_multi = False

    if not is_multi:
        query = f"""
        INSERT INTO `{table_id}` (
            standard_vendor_id, vendor_notation, standard_product_id, sku,
            product_name, variant_name, confidence, verified_by, created_at, updated_at
        )
        VALUES (
            @vendor_id, @notation, @product_id, @sku,
            @product_name, @variant_name, @confidence, @verified_by,
            CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP()
        )
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("vendor_id", "STRING", standard_vendor_id),
                bigquery.ScalarQueryParameter("notation", "STRING", vendor_notation.strip()),
                bigquery.ScalarQueryParameter("product_id", "STRING", standard_product_id),
                bigquery.ScalarQueryParameter("sku", "STRING", sku),
                bigquery.ScalarQueryParameter("product_name", "STRING", product_name),
                bigquery.ScalarQueryParameter("variant_name", "STRING", variant_name or None),
                bigquery.ScalarQueryParameter("confidence", "FLOAT64", confidence),
                bigquery.ScalarQueryParameter("verified_by", "STRING", verified_by),
            ]
        )
    client.query(query, job_config=job_config).result()
