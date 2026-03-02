# KpopNara Cloud Functions

## identify_and_generate

Product identification: cache lookup + Claude web search. Called by n8n for each invoice line item.

**Deploy:**
```bash
gcloud functions deploy identify_and_generate \
  --gen2 \
  --runtime python311 \
  --trigger-http \
  --allow-unauthenticated \
  --set-env-vars GCP_PROJECT=YOUR_PROJECT_ID,ANTHROPIC_API_KEY=YOUR_KEY
```

**Entry point:** `main.identify_and_generate`

## generate_po

PO document (docx) generation. Called by n8n after approval.

**Deploy:**
```bash
gcloud functions deploy generate_po \
  --gen2 \
  --runtime python311 \
  --trigger-http \
  --allow-unauthenticated \
  --entry-point generate_po
```

Deploy from the cloud_function directory:
```bash
cd cloud_function
gcloud functions deploy generate_po --gen2 --runtime python311 --trigger-http --allow-unauthenticated --entry-point generate_po
```

## sync_to_thrive (Phase 3)

Creates products in Thrive via internal API and updates `fact_purchase_order_item` with `thrive_product_id`, `thrive_variant_id`.

**Deploy:**
```bash
cd cloud_function
gcloud functions deploy sync_to_thrive \
  --gen2 \
  --runtime python311 \
  --trigger-http \
  --allow-unauthenticated \
  --entry-point sync_to_thrive \
  --set-env-vars GCP_PROJECT=YOUR_PROJECT,THRIVE_API_URL=https://your-thrive-api/products,THRIVE_USERNAME=xxx,THRIVE_PASSWORD=xxx
```

**Entry point:** `thrive_sync.sync_to_thrive`

If `THRIVE_API_URL` is not set, the function returns success without calling Thrive (no-op).
