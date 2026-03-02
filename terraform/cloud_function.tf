# ---------------------------------------------------------------------------
# Cloud Functions (Gen 2) for KpopNara Invoice Automation
# - identify_and_generate: Product identification (cache + research + judge)
# - generate_po: PO document (docx) generation
# - sync_to_thrive: Thrive API sync + BigQuery update
# ---------------------------------------------------------------------------

# Enable required APIs
resource "google_project_service" "cloudfunctions" {
  project            = var.project_id
  service            = "cloudfunctions.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloudbuild" {
  project            = var.project_id
  service            = "cloudbuild.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "run" {
  project            = var.project_id
  service            = "run.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "storage" {
  project            = var.project_id
  service            = "storage.googleapis.com"
  disable_on_destroy = false
}

# GCS bucket for Cloud Function source archives (unique name for global uniqueness)
resource "random_id" "cf_bucket_suffix" {
  byte_length = 4
}

resource "google_storage_bucket" "cf_source" {
  name     = "${replace(var.project_id, ".", "-")}-invoice2po-cf-${random_id.cf_bucket_suffix.hex}"
  project  = var.project_id
  location = var.region

  uniform_bucket_level_access = true

  depends_on = [google_project_service.storage]
}

# Zip cloud_function source and upload to GCS (md5 in object name triggers redeploy on code change)
data "archive_file" "cf_source" {
  type        = "zip"
  output_path = "${path.module}/.terraform/cf-source.zip"
  source_dir  = "${path.module}/../cloud_function"
  excludes    = ["__pycache__", "*.pyc", ".venv", "venv", "*.zip"]
}

resource "google_storage_bucket_object" "cf_source" {
  name   = "source-${data.archive_file.cf_source.output_md5}.zip"
  bucket = google_storage_bucket.cf_source.name
  source = data.archive_file.cf_source.output_path

  depends_on = [google_project_service.storage]
}

# ---------------------------------------------------------------------------
# Cloud Function: identify_and_generate
# ---------------------------------------------------------------------------
resource "google_cloudfunctions2_function" "identify_and_generate" {
  name     = "invoice-identify-and-generate"
  location = var.region
  project  = var.project_id

  build_config {
    runtime     = "python311"
    entry_point = "main.identify_and_generate"
    source {
      storage_source {
        bucket = google_storage_bucket.cf_source.name
        object = google_storage_bucket_object.cf_source.name
      }
    }
  }

  service_config {
    available_memory   = var.cf_memory
    timeout_seconds    = var.cf_timeout
    max_instance_count = var.cf_max_instances
    min_instance_count = var.cf_min_instances

    environment_variables = merge(var.cf_env, {
      GCP_PROJECT = var.project_id
    })

    ingress_settings               = "ALLOW_INTERNAL_AND_GCLB"
    all_traffic_on_latest_revision  = true
  }

  depends_on = [
    google_project_service.cloudfunctions,
    google_project_service.cloudbuild,
    google_project_service.run,
  ]
}

# ---------------------------------------------------------------------------
# Cloud Function: generate_po
# ---------------------------------------------------------------------------
resource "google_cloudfunctions2_function" "generate_po" {
  name     = "invoice-generate-po"
  location = var.region
  project  = var.project_id

  build_config {
    runtime     = "python311"
    entry_point = "po_generator.generate_po"
    source {
      storage_source {
        bucket = google_storage_bucket.cf_source.name
        object = google_storage_bucket_object.cf_source.name
      }
    }
  }

  service_config {
    available_memory   = var.cf_memory
    timeout_seconds    = var.cf_timeout
    max_instance_count = var.cf_max_instances
    min_instance_count = var.cf_min_instances

    environment_variables = merge(var.cf_env, {
      GCP_PROJECT = var.project_id
    })

    ingress_settings              = "ALLOW_INTERNAL_AND_GCLB"
    all_traffic_on_latest_revision = true
  }

  depends_on = [
    google_project_service.cloudfunctions,
    google_project_service.cloudbuild,
    google_project_service.run,
  ]
}

# ---------------------------------------------------------------------------
# Cloud Function: sync_to_thrive
# ---------------------------------------------------------------------------
resource "google_cloudfunctions2_function" "sync_to_thrive" {
  name     = "invoice-sync-to-thrive"
  location = var.region
  project  = var.project_id

  build_config {
    runtime     = "python311"
    entry_point = "thrive_sync.sync_to_thrive"
    source {
      storage_source {
        bucket = google_storage_bucket.cf_source.name
        object = google_storage_bucket_object.cf_source.name
      }
    }
  }

  service_config {
    available_memory   = var.cf_memory
    timeout_seconds    = var.cf_timeout
    max_instance_count = var.cf_max_instances
    min_instance_count = var.cf_min_instances

    environment_variables = merge(var.cf_env, {
      GCP_PROJECT = var.project_id
    })

    ingress_settings              = "ALLOW_INTERNAL_AND_GCLB"
    all_traffic_on_latest_revision = true
  }

  depends_on = [
    google_project_service.cloudfunctions,
    google_project_service.cloudbuild,
    google_project_service.run,
  ]
}
