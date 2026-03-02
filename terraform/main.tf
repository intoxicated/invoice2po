provider "google" {
  project = var.project_id
  region  = var.region
}

# BigQuery dataset for catalog cache tables
resource "google_bigquery_dataset" "catalog" {
  dataset_id  = var.dataset_id
  description = var.dataset_description
  location    = var.region
}

resource "google_bigquery_table" "dim_vendor_product_map" {
  dataset_id = var.dataset_id
  table_id   = "dim_vendor_product_map"
  project    = var.project_id

  description = "Mapping of vendor product notation to standard product (vendor invoice description -> KpopNara product)"

  schema = file("${path.module}/../schemas/dim_vendor_product_map.json")

  clustering = ["standard_vendor_id", "standard_product_id"]

  deletion_protection = false

  labels = {
    environment = var.environment
    project     = var.project_id
    table_type  = "dimension"
  }

  depends_on = [google_bigquery_dataset.catalog]
}

resource "google_bigquery_table" "dim_product_catalog_cache" {
  dataset_id = var.dataset_id
  table_id   = "dim_product_catalog_cache"
  project    = var.project_id

  description = "Product catalog cache keyed by vendor + artist/album for product family lookup"

  schema = file("${path.module}/../schemas/dim_product_catalog_cache.json")

  clustering = ["standard_vendor_id", "artist", "album"]

  deletion_protection = false

  labels = {
    environment = var.environment
    project     = var.project_id
    table_type  = "dimension"
  }

  depends_on = [google_bigquery_dataset.catalog]
}
