# n8n Workflows

## invoice-parse-phase1.json

Phase 1 workflow: Webhook → Download attachments → Claude Vision parse → Aggregate line items → BigQuery cache lookup → Respond.

### Import

1. In n8n: **Workflows** → **Import from File** → select `invoice-parse-phase1.json`
2. Or CLI: `n8n import:workflow --input=workflows/invoice-parse-phase1.json`

### Required Credentials

| Credential | Node | Setup |
|------------|------|-------|
| **Anthropic API** | Claude Parse Invoice | Create **HTTP Header Auth** credential. Header name: `x-api-key`, Value: your Anthropic API key |
| **BigQuery** | BigQuery Cache Lookup | Create **Google BigQuery OAuth2** credential |

### Webhook URL

After activating the workflow, the webhook URL will be:
`https://<your-n8n-host>/webhook/invoice`

Configure the Discord bot's `N8N_WEBHOOK_URL` to this URL.

### Expected Payload (from Discord bot)

```json
{
  "attachments": [
    { "attachment_url": "https://...", "filename": "invoice.pdf", "content_type": "application/pdf", "file_size": 12345 }
  ],
  "channel_id": "...",
  "message_id": "...",
  "author": "...",
  "message_content": ""
}
```

### Phase 2: AI Identify Product

- Replace `IDENTIFY_FUNCTION_URL` in the "AI Identify Product" node with your Cloud Function URL (e.g. `us-central1-PROJECT_ID.cloudfunctions.net` for 1st gen, or `identify-and-generate-XXXXX.run.app` for 2nd gen)
- Deploy the Cloud Function: `cd cloud_function && gcloud functions deploy identify_and_generate --gen2 --runtime python311 --trigger-http --allow-unauthenticated --set-env-vars GCP_PROJECT=YOUR_PROJECT`

### invoice-approve.json (Phase 2 — Discord Review)

Webhook for approval flow. When user reacts ✅ to the bot's reply, the bot calls this webhook.

**Import**: Same as above. Path: `invoice-approve`

**Bot config**: Set `N8N_APPROVE_WEBHOOK_URL` to the approval webhook URL (e.g. `https://your-n8n.com/webhook/invoice-approve`).

**Payload** (sent by bot on ✅ reaction):
```json
{
  "approved": true,
  "line_items": [...],
  "standard_vendor_id": "...",
  "vendor_name": "..."
}
```

### Phase 4: PO Generation

After approval, the workflow calls the PO Generator Cloud Function to create a docx. Deploy:
`gcloud functions deploy generate_po --gen2 --runtime python311 --trigger-http --allow-unauthenticated --source=cloud_function`

Replace `PO_GENERATOR_URL` in the "Generate PO Document" node with your function URL.

### Phase 3: Thrive Sync

After BigQuery insert, the workflow calls the Thrive Sync Cloud Function to create products in Thrive and update `fact_purchase_order_item` with `thrive_product_id`, `thrive_variant_id`. Replace `THRIVE_SYNC_URL` in the "Thrive Sync Product" node. If Thrive is not configured, deploy the function without `THRIVE_API_URL` — it will no-op and return success.

### Prerequisites

- Create `etl_data.vendor_product_map` table (run `bigquery/create_vendor_product_map.sql`)
- Ensure `etl_data.dim_vendor` has vendor records for cache lookup
