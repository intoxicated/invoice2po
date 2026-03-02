# KpopNara Invoice Automation — Complete Workflow Documentation

This document describes the end-to-end workflow for product identification, from Discord invoice messages to normalized catalog results.

> **See [PRODUCT_ONTOLOGY.md](PRODUCT_ONTOLOGY.md)** for product/variant/SKU definitions and naming rules.

---

## 1. Overview

```
Discord (invoice image/Excel)
    → Bot (webhook)
        → n8n (invoice-parse workflow)
            → LLM parse items from attachments
            → Cloud Function: identify_and_generate
                → [Vendor Cache] → [Research] → [Judge] → [Formatter]
            ← Response (line_items, catalog)
        ← Bot callback
    ← Bot reply with results (✅/❌ for approval)
```

**Core principle**: Research → Facts → Catalog. Research outputs a **fact sheet** only; the Judge transforms facts into catalog entries. No variants are invented outside the fact sheet.

---

## 2. High-Level Pipeline

```
Invoice Line Item (vendor_notation, quantity, unit_price, …)
        │
        ▼
┌───────────────────────────────────────────────────────┐
│  1. Vendor Cache Lookup (BigQuery: vendor_product_map) │
│     Key: standard_vendor_id + vendor_notation          │
└───────────────────────────────────────────────────────┘
        │
        │  HIT → return cached mapping + line_items (skip steps 2–5)
        │  MISS
        ▼
┌───────────────────────────────────────────────────────┐
│  2. Research → FACT SHEET                             │
│     Provider: manual | duckduckgo | perplexity        │
│     Output: artist, album, versions, packaging, evidence │
└───────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────┐
│  3. Judge (Catalog Normalizer)                        │
│     Input: FACT SHEET + vendor_notation               │
│     Output: catalog_entries + is_invoice_item         │
│     Rule: Never create variants not in fact sheet     │
└───────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────┐
│  4. Formatter                                         │
│     - Enforce canonical naming (UPPERCASE)            │
│     - Derive deterministic SKUs (sku_formatter)       │
│     - Derive standard_product_id from matched_sku     │
│     - Build line_items, split quantity when multiple │
└───────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────┐
│  5. Persist Learning (if confidence ≥ 0.7, not draft)  │
│     Insert into vendor_product_map                    │
└───────────────────────────────────────────────────────┘
        │
        ▼
   Return JSON (line_items, catalog_entries, etc.)
```

---

## 3. Component Details

### 3.1 Vendor Cache (`cache.py`)

| What | Details |
|------|---------|
| Table | `etl_data.vendor_product_map` |
| Key | `standard_vendor_id` + `vendor_notation` (lowercase, trimmed) |
| Returns | `standard_product_id`, `sku`, `product_name`, `variant_name` |
| Purpose | Skip research/judge for known mappings |

`standard_vendor_id` is derived from `vendor_name` via SHA256 hash. No BigQuery lookup for dim_vendor in current impl.

### 3.2 Research (`research_providers.py`)

Abstract layer that produces a **fact sheet**. Provider is selected by `research_provider` in the request (default: `duckduckgo`).

| Provider | Behavior |
|----------|----------|
| **manual** | Use `fact_sheet` from request body. Requires `fact_sheet` to be provided. |
| **duckduckgo** | Web search (DuckDuckGo, max 2 queries). Returns legacy evidence → converted to fact sheet shape. |
| **perplexity** | Perplexity Sonar API. Returns structured fact sheet (artist, album, versions, packaging, evidence). Requires `PERPLEXITY_API_KEY`. |

**Fact sheet schema** (`fact_sheet.py`):

```json
{
  "artist": "IVE",
  "album": "REVIVE+",
  "release_type": "2ND ALBUM",
  "packaging": ["DIGIPACK", "STANDARD ALBUM"],
  "versions": ["BANGERS VER.", "CHALLENGERS VER.", "GAEUL", "REI", …],
  "official_versions": [],
  "retailer_sources": ["ktown4u", "musicplaza"],
  "evidence": "Search results confirm…"
}
```

### 3.3 Judge (`judge.py`)

| Role | Transform FACT SHEET → catalog structure |
|------|------------------------------------------|
| Input | `vendor_notation`, `fact_sheet`, `vendor_name` |
| Output | `catalog_entries` with `product_name`, `variant_name`, `is_invoice_item`; `matched_sku`, `confidence`, `evidence` |
| LLM | Configurable via `LLM_PROVIDER` (google, anthropic, openai, perplexity) |
| Critical rule | Never create variants not present in the fact sheet |

Invoice matching modes: **EXACT**, **SELLER_RANDOM**, **PACKAGING_RANDOM**, **INFERRED**, **UNKNOWN**. `is_invoice_item=true` is set for variants matching the invoice.

### 3.4 Formatter (`formatter.py`)

| Role | Canonical naming, SKU derivation, line item building |
|------|------------------------------------------------------|
| Naming | All product/variant names → UPPERCASE |
| SKU | `derive_sku(product_name, variant_name)` → `ARTIST-PRODUCT-VARIANT` (abbreviations applied) |
| standard_product_id | `generate_standard_product_id(matched_sku)` → `std_product_<16-char-hash>` |
| Quantity split | When multiple invoice variants (e.g. SELLER_RANDOM): quantity divided evenly across line_items |
| is_draft | `confidence < 0.7` → `is_draft: true` |

### 3.5 SKU Formatter (`sku_formatter.py`)

Deterministic SKU: `{ARTIST}-{PRODUCT}-{VARIANT}`

- Parse `product_name` on ` - ` → (artist, product)
- Apply abbreviations (Mini Album→MA, Version→V, Postcard→PC, etc.)
- Normalize to alphanumeric uppercase
- `standard_product_id`: MD5(`product_{sku}`)[:16] → `std_product_<hex>`

---

## 4. API Contract

### Request (POST)

```json
{
  "vendor_notation": "IVE - THE 2ND ALBUM [REVIVE+] (BANGERS VER./CHALLENGERS VER.) (2TYPES RANDOM VER.)",
  "vendor_name": "INTERASIA",
  "quantity": 24,
  "unit_price": 17500,
  "total_price": 420000,
  "research_provider": "perplexity",
  "fact_sheet": null
}
```

| Field | Required | Description |
|-------|----------|-------------|
| vendor_notation | Yes | Raw vendor line text |
| vendor_name | Yes | Vendor name (e.g. INTERASIA) |
| quantity | No | Line quantity |
| unit_price | No | Unit price |
| total_price | No | Line total |
| research_provider | No | `manual` \| `duckduckgo` \| `perplexity` (default: duckduckgo) |
| fact_sheet | No | For manual mode; overrides provider when present |

### Response

```json
{
  "vendor_notation": "IVE - THE 2ND ALBUM [REVIVE+] …",
  "matched_sku": "IVE-REVIVE2ALBUM-BANGERSV",
  "matched_product_name": "IVE - REVIVE+ (2ND ALBUM)",
  "standard_product_id": "std_product_0f977a94561522b2",
  "confidence": 0.85,
  "is_draft": false,
  "from_cache": false,
  "line_items": [
    {
      "sku": "IVE-REVIVE2ALBUM-BANGERSV",
      "product_name": "IVE - REVIVE+ (2ND ALBUM)",
      "variant_name": "BANGERS VER.",
      "quantity": 12,
      "unit_price": 17500,
      "total_price": 210000,
      "standard_product_id": "std_product_0f977a94561522b2",
      "standard_vendor_id": "...",
      "vendor_notation": "…",
      "vendor_name": "INTERASIA",
      "is_draft": false
    },
    { "…": "CHALLENGERS VER.", "quantity": 12, … }
  ],
  "catalog_entries": [ … ]
}
```

---

## 5. Environment Variables

| Variable | Purpose |
|----------|---------|
| GCP_PROJECT | BigQuery project (e.g. `kpn-platform`) |
| LLM_PROVIDER | Judge model: `google`, `anthropic`, `openai`, `perplexity` |
| LLM_MODEL | Model name (e.g. `gemini-3-flash-preview`) |
| PERPLEXITY_API_KEY | For `research_provider=perplexity` |
| PERPLEXITY_MODEL | Perplexity model (default: sonar) |
| PERPLEXITY_SEARCH_DOMAINS | Optional: ktown4u.com,musicplaza.com,etc. |
| THRIVE_API_URL | Optional: Thrive sync |
| THRIVE_USERNAME | Optional |
| THRIVE_PASSWORD | Optional |

---

## 6. File Structure (cloud_function/)

```
cloud_function/
├── main.py                    # identify_and_generate, generate_po, sync_to_thrive
├── cache.py                   # Vendor cache, save_vendor_mapping
├── fact_sheet.py              # Fact sheet schema, normalize_fact_sheet
├── research_providers.py      # run_research (manual|duckduckgo|perplexity)
├── research.py                # DuckDuckGo research worker
├── research_agent_perplexity.py # Perplexity fact-sheet-only research
├── judge.py                   # Judge (fact sheet → catalog)
├── formatter.py               # Naming, SKU, line_items
├── sku_formatter.py           # derive_sku, generate_standard_product_id
├── llm.py                     # LangChain model factory
├── po_generator.py            # PO docx generation
├── thrive_sync.py             # Thrive API sync
├── local_server.py            # Local Flask server
└── requirements.txt
```

---

## 7. n8n Integration

### Invoice Parse Workflow

1. Webhook receives POST from Discord bot (with parsed line items from Claude).
2. For each line item, HTTP Request to `http://cloud-functions:8080/identify` with body:
   - `vendor_notation`, `vendor_name`, `quantity`, `unit_price`, `total_price`
   - Optional: `research_provider`, `fact_sheet`
3. Response aggregated and sent to bot callback.

### Approval Workflow

1. Webhook receives POST when user reacts ✅ or ❌.
2. If ✅: `sync_to_thrive`, `generate_po` via `http://cloud-functions:8080/...`

---

## 8. Docker & Local Dev

```bash
# Start
docker compose -f docker-compose.local.yml up -d

# Services
# - n8n:           http://localhost:5678
# - cloud-functions: http://localhost:8080
# - invoice-bot:   port 9090 (callback)
```

Cloud Functions container mounts `~/.config/gcloud` for BigQuery credentials. Run `gcloud auth application-default login` before starting.

---

## 9. Confidence & Human Review

| Confidence | is_draft | Action |
|------------|----------|--------|
| ≥ 0.7 | false | Auto-save to vendor cache |
| < 0.7 | true | Human review recommended; not saved to cache |

Approval flow: Discord bot stores pending results; user reacts ✅ (approve) or ❌ (reject). Approval webhook triggers Thrive sync and PO generation.

---

## 10. Data Flow Diagram

```
                    ┌─────────────────┐
                    │  Discord Bot    │
                    │  (invoice msg)  │
                    └────────┬────────┘
                             │ POST /webhook/invoice
                             ▼
                    ┌─────────────────┐
                    │      n8n        │
                    │  Parse workflow │
                    └────────┬────────┘
                             │ For each line: POST /identify
                             ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    Cloud Function: identify_and_generate                 │
│                                                                        │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐               │
│  │ Vendor Cache │   │   Research   │   │    Judge     │               │
│  │ (BigQuery)   │──▶│ Fact Sheet   │──▶│ Facts→Catalog│               │
│  └──────────────┘   └──────────────┘   └──────┬───────┘               │
│         │                    │                     │                   │
│         │ HIT                │ miss                 │                   │
│         ▼                    ▼                     ▼                   │
│  ┌──────────────┐     ┌──────────────┐      ┌──────────────┐          │
│  │ Return early │     │  Formatter   │      │ Save to cache│          │
│  └──────────────┘     └──────────────┘      └──────────────┘          │
└────────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  line_items +   │
                    │  catalog_entries│
                    └─────────────────┘
```
