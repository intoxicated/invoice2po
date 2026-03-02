# Invoice Approval Workflow — Data Flow Analysis

## 1. Where/How Does It Retrieve Invoice Data?

### Source: Webhook POST

The workflow is triggered by **Webhook Approve** (`POST /webhook/invoice-approve`). The Discord bot calls this when a user reacts ✅ or ❌ to the bot's reply.

**Bot → Webhook payload** (from `bot.py` lines 147–153):

```json
{
  "approved": true,
  "line_items": [...],
  "standard_vendor_id": "...",
  "vendor_name": "..."
}
```

`line_items` comes from the **parse workflow** response. The bot stores it in `_pending_approvals` when the parse webhook returns (lines 108–112).

### Extraction: Prepare Approval Data (Code node)

```javascript
const body = $input.first().json.body || $input.first().json;
```

- n8n webhooks may put the body in `json.body` or directly in `json`; this handles both.
- Expects: `approved`, `line_items`, `standard_vendor_id`, `vendor_name`.
- Outputs one item with: `approved`, `po_id`, `po_number`, `vendor_name`, `standard_vendor_id`, `location_id`, `total_amount`, `currency`, `line_items` (each with `po_item_id`, `po_id`).

---

## 2. Data Flow Between Nodes

### Flow Diagram

```
Webhook Approve
    ↓
Prepare Approval Data  (1 item: { approved, po_id, line_items, ... })
    ↓
IF Approved
    ├─ TRUE  → BigQuery Insert PO (1 item)
    │              ├─→ Split Line Items (N items, one per line)
    │              │       ↓
    │              │   BigQuery Insert PO Items (N executions)
    │              │       ↓
    │              │   Thrive Sync (N executions)  ← N items to Respond OK
    │              │       ↓
    │              │   Respond OK
    │              │
    │              └─→ Generate PO Document (1 item, no outgoing connection)
    │
    └─ FALSE → Respond Reject
```

### Issues

#### 1. Respond OK receives N items (one per line item)

- **Split Line Items** turns 1 item into N.
- Each line item goes through BigQuery Insert PO Items → Thrive Sync.
- Thrive Sync outputs N items, all connected to Respond OK.
- Respond to Webhook should run once per webhook; multiple executions can cause “already responded” errors or duplicate responses.

**Fix:** Add a Merge or Code node before Respond OK that aggregates all items into one, then connect that to Respond OK.

#### 2. Generate PO Document is disconnected

- Connected from BigQuery Insert PO.
- `"Generate PO Document": { "main": [[]] }` — no outgoing connections.
- The PO doc is generated but not used or returned.
- BigQuery Insert PO passes through its input, so `$json` includes `po_id`, `po_number`, `vendor_name`, `line_items`, `total_amount` — correct for the PO generator.

#### 3. IF node data passing

- IF node passes the same item(s) to the true/false branches.
- True branch receives the full prepared object; false branch receives `{ approved: false }`.
- Data structure is preserved.

#### 4. Split Line Items → downstream

- Splits `line_items` into N items.
- Each item has: `po_item_id`, `po_id`, `standard_product_id`, `product_name`, `sku`, `quantity`, etc.
- BigQuery Insert PO Items and Thrive Sync use `$json` correctly.

---

## 3. Summary

| Aspect | Status |
|--------|--------|
| Data source | Webhook POST from bot |
| Prepare node | Correctly reads body and builds payload |
| IF node | Correctly branches and passes data |
| BigQuery Insert PO | Receives full object, inserts PO header |
| Split Line Items | Correctly splits `line_items` |
| BigQuery Insert PO Items | Correct per-line-item mapping |
| Thrive Sync | Correct per-line-item mapping |
| Generate PO Document | Receives correct data; output unused |
| Respond OK | Receives N items; should receive 1 |
