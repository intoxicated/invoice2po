
# K-Pop Product Normalization System
## Production Architecture & Implementation Plan

---

# 1. Objective

Build a **deterministic K-Pop product normalization system** that converts messy vendor invoice items into:

- Canonical catalog products
- Complete variant structures
- Accurate invoice matching
- Non-hallucinated catalog entries

Primary goals:

- Zero invented products
- Stable catalog ontology
- Controlled web research
- Reduced API cost
- Continuous learning system

---

# 2. Core Problem

Vendor invoices contain inconsistent naming:

IVE REVIVE+ DIGITPACK RANDOM  
IVE REVIVE PLUS  
IVE 2ND ALBUM DP RND  
IVE REVIVE+ ANYUJIN

Challenges:

- Distributor shorthand
- Typos
- Packaging aliases
- Random shipment wording
- Missing variant information
- Multiple locations processing invoices simultaneously

LLMs fail when asked to:
- research
- design catalog
- interpret invoice

in one step.

---

# 3. High-Level Architecture

Invoice
→ Alias Normalizer  
→ Research Agent (Perplexity)  
→ FACT SHEET (Source of Truth)  
→ Catalog Normalizer (LLM)  
→ Catalog Database  
→ Invoice Matching Result

---

# 4. System Components

## 4.1 Alias Normalization Layer

### Purpose
Normalize vendor shorthand BEFORE AI reasoning.

### Examples

| Vendor Text | Normalized |
|-------------|------------|
| digitpack | digipack |
| dp | digipack |
| rnd | random |
| random ver | random |

### Storage

BigQuery Table:

alias_dictionary  
alias_text  
canonical_text  
confidence  
last_seen  

### Process
1. lowercase text
2. remove punctuation
3. apply alias mapping
4. send cleaned query downstream

---

## 4.2 Research Agent (Perplexity)

### Responsibility

ONLY answer:

“What product exists in reality?”

### Forbidden
- No catalog creation
- No invoice decisions
- No invented variants

### Model
Perplexity Sonar

### Query Template

{invoice_item} kpop album version  
-site:youtube.com  
-site:tiktok.com  
-site:pinterest.com  
-site:reddit.com

### Output = FACT SHEET

Example:

{
  "artist": "IVE",
  "album": "IVE SWITCH",
  "release_type": "2ND EP",
  "packaging": ["DIGIPACK"],
  "versions": [
    "ANYUJIN",
    "GAEUL",
    "REI",
    "JANGWONYOUNG",
    "LIZ",
    "LEESEO"
  ],
  "official_versions": [],
  "retailer_sources": ["ktown4u", "yes24"]
}

---

## 4.3 Fact Sheet Cache (Cost Optimization)

### Why
Multiple stores receive identical albums.

### Strategy
Cache research permanently.

### Cache Key
artist + album + packaging

Example:
IVE|IVE SWITCH|DIGIPACK

### Storage
BigQuery or Firestore

Result:
- Skip web search for known products
- Reduce API cost by ~70–90%

---

## 4.4 Catalog Normalization Agent

### Responsibility
Transform FACT SHEET into canonical catalog structure.

### Model
GPT‑5 Mini or Claude Sonnet

### Canonical Naming Rule

ARTIST - ALBUM (RELEASE_TYPE) [PACKAGING]

Example:
IVE - IVE SWITCH (2ND EP) [DIGIPACK]

### Variant Rules

OFFICIAL_VARIANT → verified version  
MEMBER_VARIANT → member digipack/jewel  
SELLER_RANDOM → vendor-only wording  
PACKAGING_RANDOM → random shipment  
UNKNOWN_ALIAS → insufficient evidence

### Critical Rule
Never create variants not present in FACT SHEET.

---

## 4.5 Invoice Matching

Mark is_invoice_item = true when:

- exact version named
- RANDOM indicated
- seller random mapped

Never match invented variants.

---

# 5. Database Design

## products
product_id  
artist  
album  
release_type  
packaging  

## variants
variant_id  
product_id  
variant_name  
variant_class  
barcode  
confidence  

## alias_dictionary
alias_text  
canonical_text  

## research_cache
cache_key  
fact_sheet_json  
created_at  

---

# 6. Processing Flow (Implemented)

See **[docs/WORKFLOW.md](docs/WORKFLOW.md)** for complete documentation.

1. Receive invoice (vendor_notation, vendor_name, quantity, etc.)
2. Check vendor cache (vendor_product_map)
3. If cache miss:
   a. **Research** (manual | duckduckgo | perplexity) → **FACT SHEET**
   b. **Judge** (Catalog Normalizer): FACT SHEET → catalog_entries + is_invoice_item
   c. Formatter: enforce naming, derive SKUs, build line_items
4. Save to vendor cache when confidence ≥ 0.7

## Research Abstraction

- **manual**: `fact_sheet` provided in request body (pass-through)
- **duckduckgo**: Web search → legacy evidence → fact sheet shape
- **perplexity**: Perplexity Sonar → structured fact sheet

## API Request (optional params)

- `research_provider`: "manual" | "duckduckgo" | "perplexity"
- `fact_sheet`: for manual mode or to override provider

---

# 7. Cost Optimization Strategy

- Cache research forever
- Separate research from normalization
- Use small model for catalog logic
- Avoid repeated searches across locations

Expected outcome:
Massive cost reduction and stable outputs.

---

# 8. Future Extensions

- Barcode knowledge graph
- Distributor catalog ingestion
- Self-learning alias expansion
- Confidence auto-adjustment
- Multi-language vendor support

---

# 9. Guiding Principle

Do NOT build an invoice parser.

Build a **K‑Pop Product Knowledge System**.

Research → Facts  
Facts → Catalog  
Catalog → Automation
