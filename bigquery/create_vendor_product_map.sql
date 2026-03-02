-- Create dim_vendor_product_map table in catalog dataset
-- Cache for vendor notation -> SKU mappings to avoid repeated AI lookups
-- Run: bq query --use_legacy_sql=false < bigquery/create_vendor_product_map.sql
-- Or execute in BigQuery Console

CREATE TABLE IF NOT EXISTS `catalog.dim_vendor_product_map` (
  standard_vendor_id  STRING      NOT NULL,
  vendor_notation     STRING      NOT NULL,
  standard_product_id STRING      NOT NULL,
  sku                 STRING      NOT NULL,
  product_name        STRING      NOT NULL,
  confidence          FLOAT64,
  verified_by         STRING      NOT NULL,
  created_at          TIMESTAMP   NOT NULL,
  updated_at          TIMESTAMP
);

-- Composite unique constraint: one mapping per vendor + notation
-- BigQuery doesn't support UNIQUE, so enforce in application or use MERGE with dedup
