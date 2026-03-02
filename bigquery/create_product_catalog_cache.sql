-- Create product_catalog_cache table in etl_data dataset
-- Stores full catalog entries per (vendor, artist, album). Used when vendor_notation implies multiple variants.
-- Run: bq query --use_legacy_sql=false < bigquery/create_product_catalog_cache.sql

CREATE TABLE IF NOT EXISTS `etl_data.product_catalog_cache` (
  standard_vendor_id  STRING      NOT NULL,
  artist              STRING      NOT NULL,
  album               STRING      NOT NULL,
  catalog_entries     JSON        NOT NULL,
  created_at         TIMESTAMP   NOT NULL,
  updated_at         TIMESTAMP
);

-- Key: (standard_vendor_id, LOWER(artist), LOWER(album))
-- catalog_entries: [{sku, product_name, variant_name, standard_product_id}]
