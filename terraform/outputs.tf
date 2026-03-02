output "dataset_id" {
  description = "BigQuery dataset ID"
  value       = google_bigquery_dataset.catalog.dataset_id
}

output "dataset_full_id" {
  description = "Full dataset ID (project.dataset)"
  value       = "${var.project_id}.${google_bigquery_dataset.catalog.dataset_id}"
}

output "vendor_product_map_table_id" {
  description = "Full table ID for vendor_product_map"
  value       = google_bigquery_table.dim_vendor_product_map.id
}

output "product_catalog_cache_table_id" {
  description = "Full table ID for product_catalog_cache"
  value       = google_bigquery_table.dim_product_catalog_cache.id
}

# ---------------------------------------------------------------------------
# Cloud Function outputs
# ---------------------------------------------------------------------------
output "cf_identify_url" {
  description = "URL for identify_and_generate Cloud Function"
  value       = google_cloudfunctions2_function.identify_and_generate.service_config[0].uri
}

output "cf_generate_po_url" {
  description = "URL for generate_po Cloud Function"
  value       = google_cloudfunctions2_function.generate_po.service_config[0].uri
}

output "cf_sync_to_thrive_url" {
  description = "URL for sync_to_thrive Cloud Function"
  value       = google_cloudfunctions2_function.sync_to_thrive.service_config[0].uri
}
