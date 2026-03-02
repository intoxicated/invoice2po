"""
KpopNara Thrive Sync — Cloud Function
Creates products in Thrive via internal API and updates BigQuery with thrive_product_id, thrive_variant_id.
Called by n8n after BigQuery insert of approved invoice items.
"""

import os
import json
import base64
import functions_framework
import requests
from google.cloud import bigquery

def get_bq_client():
    project = os.environ.get("GCP_PROJECT") or "kpn-platform"
    return bigquery.Client(project=project)


def update_po_item_thrive_ids(
    client: bigquery.Client,
    po_item_id: str,
    thrive_product_id: str,
    thrive_variant_id: str,
) -> None:
    """Update fact_purchase_order_item with Thrive IDs."""
    project = os.environ.get("GCP_PROJECT", client.project)
    query = f"""
    UPDATE `{project}.etl_data.fact_purchase_order_item`
    SET thrive_product_id = @thrive_product_id,
        thrive_variant_id = @thrive_variant_id,
        updated_at = CURRENT_TIMESTAMP()
    WHERE po_item_id = @po_item_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("po_item_id", "STRING", po_item_id),
            bigquery.ScalarQueryParameter("thrive_product_id", "STRING", thrive_product_id),
            bigquery.ScalarQueryParameter("thrive_variant_id", "STRING", thrive_variant_id),
        ]
    )
    client.query(query, job_config=job_config).result()


@functions_framework.http
def sync_to_thrive(request):
    """
    POST with JSON: {
      po_item_id, standard_product_id, product_name, sku, upc, variation_name, ...
    }
    Calls Thrive API to create product, then updates BigQuery with thrive IDs.
    """
    if request.method != "POST":
        return (json.dumps({"error": "Method not allowed"}), 405, {"Content-Type": "application/json"})

    thrive_url = os.environ.get("THRIVE_API_URL")
    if not thrive_url:
        return (
            json.dumps({"error": "THRIVE_API_URL not configured", "skipped": True}),
            200,
            {"Content-Type": "application/json"},
        )

    try:
        data = request.get_json(silent=True) or {}
        po_item_id = data.get("po_item_id")
        standard_product_id = data.get("standard_product_id")
        product_name = data.get("product_name") or data.get("matched_product_name")
        sku = data.get("sku") or data.get("matched_sku")
        upc = data.get("upc", "")

        if not po_item_id or not product_name or not sku:
            return (
                json.dumps({"error": "po_item_id, product_name, sku required"}),
                400,
                {"Content-Type": "application/json"},
            )

        username = os.environ.get("THRIVE_USERNAME", "")
        password = os.environ.get("THRIVE_PASSWORD", "")
        auth = base64.b64encode(f"{username}:{password}".encode()).decode() if username else None

        headers = {"Content-Type": "application/json"}
        if auth:
            headers["Authorization"] = f"Basic {auth}"

        payload = {
            "name": product_name,
            "sku": sku,
            "upc": upc or sku,
            "standard_product_id": standard_product_id,
        }

        resp = requests.post(
            thrive_url,
            json=payload,
            headers=headers,
            timeout=30,
        )

        if resp.status_code >= 400:
            return (
                json.dumps({
                    "error": f"Thrive API error: {resp.status_code}",
                    "response": resp.text[:500],
                }),
                resp.status_code,
                {"Content-Type": "application/json"},
            )

        result = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        thrive_product_id = result.get("thrive_product_id") or result.get("id") or str(result)
        thrive_variant_id = result.get("thrive_variant_id") or result.get("variant_id", "")

        if thrive_product_id:
            bq = get_bq_client()
            update_po_item_thrive_ids(bq, po_item_id, str(thrive_product_id), str(thrive_variant_id))

        return (
            json.dumps({
                "success": True,
                "po_item_id": po_item_id,
                "thrive_product_id": thrive_product_id,
                "thrive_variant_id": thrive_variant_id,
            }),
            200,
            {"Content-Type": "application/json"},
        )

    except Exception as e:
        return (
            json.dumps({"error": str(e), "type": type(e).__name__}),
            500,
            {"Content-Type": "application/json"},
        )
