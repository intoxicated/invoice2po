# KpopNara Product Ontology

Clear and concise definitions for product generation.

> **Judge system message** is derived from this ontology: `cloud_function/judge_prompt.py`

---

## 1. Core Entities

```
Product (canonical)
    │
    └── Variant (sellable unit)
            │
            └── SKU (identifier)
```

| Entity | Definition | Example |
|--------|------------|---------|
| **Product** | Base identity: artist + album + optional release/format metadata. One product can have many variants. | `IVE - REVIVE+ (2ND ALBUM)` |
| **Variant** | Sellable differentiation within a product. Same product, different packaging/version/member. | `BANGERS VER.`, `YUJIN VER.` |
| **SKU** | Deterministic identifier for a specific variant. Format: `{ARTIST}-{PRODUCT}-{VARIANT}` | `IVE-REVIVE2ALBUM-BANGERSV` |
| **standard_product_id** | Deterministic hash of SKU. Same SKU → same ID. Format: `std_product_{16 hex}` | `std_product_0f977a94561522b2` |

---

## 2. Canonical Product Name

**Pattern**: `ARTIST - PRODUCT_NAME (VERSIONING) [FORMAT]`

| Part | Required | Description | Examples |
|------|----------|-------------|----------|
| ARTIST | Yes | Official promoted name | `IVE`, `BTS`, `AMPERS&ONE` |
| PRODUCT_NAME | Yes | Base album/product. No variants. | `REVIVE+`, `IVE SWITCH` |
| VERSIONING | No | Release classification | `2ND ALBUM`, `3RD MINI ALBUM`, `1ST EP` |
| FORMAT | No | Packaging type in brackets | `[DIGIPACK]`, `[PHOTOBOOK]`, `[JEWEL CASE]` |

**Rules**:
- product_name must NOT contain variant names, member names, or packaging words.
- Format (e.g. DIGIPACK) goes in brackets; it is NOT a variant.
- For member releases: `GROUP: MEMBER - PRODUCT_NAME` (e.g. `EXO: BAEKHYUN - BAMBI (3RD MINI ALBUM)`)

---

## 3. Variant Name

**Purpose**: Distinguish sellable units within a product.

| Type | Examples |
|------|----------|
| VERSION | `A VER`, `B VER`, `LIMITED VER`, `PHOTOBOOK VER` |
| MEMBER | `YUJIN VER`, `WONYOUNG VER`, `JUNGKOOK VER` |
| PACKAGE | `DIGIPACK VER`, `JEWEL CASE VER` |
| CONTENT | `POSTER VER`, `KIWEE` |
| RANDOM | `[RANDOM]` — only when physically indistinguishable |

**Rules**:
- variant_name must NOT appear inside product_name.
- UPPERCASE for member names; Title Case for versions.
- Append "Ver" when appropriate.
- Use `[RANDOM]` only when variants cannot be distinguished by barcode/packaging.

---

## 4. Vendor Notation Parsing

**Typical structure**: `ARTIST - VERSIONING [ALBUM_NAME] (VARIANT VER.)`

| Notation Part | Maps To | Example |
|---------------|---------|---------|
| `[ALBUM_NAME]` (e.g. [FOCUS], [REVIVE+]) | product_name | Album identifier; goes in product_name |
| `(X VER.)` or `(X VER)` at end | variant_name | Sellable variant; e.g. "RULE BOOK VER" |
| `[FORMAT]` | product_name (optional) | ONLY [DIGIPACK], [PHOTOBOOK], [JEWEL CASE] — packaging type |
| Rule Book, Heart Locket, Photo Book (as version types) | variant_name | Variants, NOT in brackets in product_name |

**Wrong**: `HEARTS2HEARTS - FOCUS (1ST MINI ALBUM) [RULE BOOK]` — RULE BOOK is a variant, not format.

**Correct**: product_name=`HEARTS2HEARTS - FOCUS (1ST MINI ALBUM)`, variant_name=`RULE BOOK VER`

---

## 5. SKU Derivation

**Formula**: `{ARTIST_CODE}-{PRODUCT_CODE}-{VARIANT_CODE}`

**Process**:
1. Parse product_name on ` - ` → (artist, product)
2. Apply abbreviations (Mini Album→MA, Version→V, Postcard→PC, etc.)
3. Normalize: alphanumeric only, uppercase, no spaces
4. Variant empty → use `STD`

| Input | Output |
|-------|--------|
| `IVE - REVIVE+ (2ND ALBUM)`, `BANGERS VER.` | `IVE-REVIVE2ALBUM-BANGERSV` |
| `IVE - IVE SWITCH`, `YUJIN VER` | `IVE-IVESWITCH-YUJINV` |

**standard_product_id**:
```
MD5("product_" + SKU_UPPERCASE)[:16] → "std_product_" + hex
```
Same SKU always yields the same standard_product_id.

---

## 6. Identifiers Summary

| Identifier | Scope | Deterministic | Source |
|------------|-------|---------------|--------|
| product_name | Product (base) | Yes (canonical rules) | Judge + Formatter |
| variant_name | Variant | Yes (canonical rules) | Judge + Formatter |
| sku | Variant | Yes (derive_sku) | sku_formatter |
| standard_product_id | Product/Variant | Yes (hash of SKU) | generate_standard_product_id |
| standard_vendor_id | Vendor | Yes (hash of name) | cache.resolve_vendor_id |

---

## 7. Data Model (BigQuery)

| Table | Key Fields | Purpose |
|-------|------------|---------|
| dim_product | standard_product_id, product_name, variant_name, sku | Canonical product catalog |
| vendor_product_map | standard_vendor_id, vendor_notation → standard_product_id, sku, product_name, variant_name; optional artist, album, invoice_entry_skus for multi-variant | Vendor notation → catalog mapping (cache) |
| dim_product_catalog_cache | standard_vendor_id, artist, album, sku (one row per entry) | Full catalog per product; latest catalog_generation wins; used when notation implies multiple variants |
| dim_vendor | standard_vendor_id | Vendor master |

**vendor_product_map** is the learned cache. Single-variant: returns sku, product_name, variant_name directly. Multi-variant: stores pointer (artist, album, invoice_entry_skus) and fetches catalog from **product_catalog_cache** for quantity splitting.

---

## 8. Invoice Match Semantics

| Mode | Meaning | is_invoice_item |
|------|---------|-----------------|
| EXACT | Invoice names specific version | Only that variant = true |
| SELLER_RANDOM | Vendor ships one of N; we don't know which | All N variants = true |
| PACKAGING_RANDOM | Manufacturer ships randomly; indistinguishable | All variants = true |
| UNKNOWN | Cannot determine | Single [RANDOM] variant = true |

---

## 9. Ontology Diagram

```
                    vendor_notation (input)
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      PRODUCT (canonical)                     │
│  product_name: "ARTIST - PRODUCT_NAME (VERSIONING) [FORMAT]"│
│  standard_product_id: std_product_{hash}                    │
└─────────────────────────────┬───────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│     VARIANT 1    │ │     VARIANT 2    │ │     VARIANT 3    │
│ variant_name     │ │ variant_name     │ │ variant_name     │
│ sku              │ │ sku              │ │ sku              │
│ is_invoice_item  │ │ is_invoice_item  │ │ is_invoice_item  │
└──────────────────┘ └──────────────────┘ └──────────────────┘
```
