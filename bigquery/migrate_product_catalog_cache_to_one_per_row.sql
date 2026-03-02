-- Migration: dim_product_catalog_cache from JSON catalog_entries to one row per entry
-- Run if you have the old schema (catalog_entries JSON).
-- Step 1: Create new table (run create_product_catalog_cache.sql on new table name, then rename)
-- Step 2: Migrate data

-- Option A: Create temp table with new schema, migrate, swap
CREATE TABLE IF NOT EXISTS `catalog.dim_product_catalog_cache_new` (
  standard_vendor_id  STRING      NOT NULL,
  artist              STRING      NOT NULL,
  album               STRING      NOT NULL,
  sku                 STRING      NOT NULL,
  product_name        STRING      NOT NULL,
  variant_name        STRING,
  standard_product_id STRING      NOT NULL,
  catalog_generation  TIMESTAMP   NOT NULL,
  created_at         TIMESTAMP   NOT NULL
);

-- Migrate from old table (catalog_entries JSON) - unnest and insert
INSERT INTO `catalog.dim_product_catalog_cache_new` (
  standard_vendor_id, artist, album, sku, product_name, variant_name,
  standard_product_id, catalog_generation, created_at
)
SELECT
  standard_vendor_id,
  artist,
  album,
  JSON_VALUE(e, '$.sku') AS sku,
  JSON_VALUE(e, '$.product_name') AS product_name,
  JSON_VALUE(e, '$.variant_name') AS variant_name,
  JSON_VALUE(e, '$.standard_product_id') AS standard_product_id,
  COALESCE(updated_at, created_at) AS catalog_generation,
  created_at
FROM `catalog.dim_product_catalog_cache` OLD,
  UNNEST(JSON_QUERY_ARRAY(OLD.catalog_entries)) AS e;

-- Then: DROP OLD table, RENAME new to dim_product_catalog_cache
-- (Run manually: bq rm, bq cp, etc. or use BigQuery Console)
