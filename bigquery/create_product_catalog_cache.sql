-- Create dim_product_catalog_cache table in catalog dataset
-- One row per catalog entry (vendor+artist+album+sku). Latest catalog_generation wins.
-- Run: bq query --use_legacy_sql=false < bigquery/create_product_catalog_cache.sql

CREATE TABLE IF NOT EXISTS `catalog.dim_product_catalog_cache` (
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

-- Key: (standard_vendor_id, artist, album). Latest catalog_generation per key = current catalog.
-- One row per variant/SKU.
