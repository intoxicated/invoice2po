-- Migration: add columns for multi-variant pointer to product_catalog_cache
-- Run: bq query --use_legacy_sql=false < bigquery/alter_vendor_product_map_add_multi_variant.sql
-- Note: BigQuery ALTER TABLE ADD COLUMN adds to end. Run each statement separately if needed.

ALTER TABLE `etl_data.vendor_product_map`
ADD COLUMN IF NOT EXISTS artist STRING,
ADD COLUMN IF NOT EXISTS album STRING,
ADD COLUMN IF NOT EXISTS invoice_entry_skus ARRAY<STRING>;
