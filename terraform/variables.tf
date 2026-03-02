variable "project_id" {
  description = "GCP project ID for BigQuery"
  type        = string
  default     = "kpn-platform"
}

variable "dataset_id" {
  description = "BigQuery dataset ID (e.g. catalog or etl_data)"
  type        = string
  default     = "catalog"
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "location" {
  description = "BigQuery dataset location"
  type        = string
  default     = "us-central1"
}

variable "dataset_description" {
  description = "Description for the BigQuery dataset"
  type        = string
  default     = "Vendor notation and product catalog cache tables"
}

variable "environment" {
  description = "Environment"
  type        = string
  default     = "production"
}

# ---------------------------------------------------------------------------
# Cloud Function variables
# ---------------------------------------------------------------------------
variable "cf_memory" {
  description = "Cloud Function memory (e.g. 256M, 512M)"
  type        = string
  default     = "512M"
}

variable "cf_timeout" {
  description = "Cloud Function timeout in seconds"
  type        = number
  default     = 300
}

variable "cf_max_instances" {
  description = "Max Cloud Function instances"
  type        = number
  default     = 10
}

variable "cf_min_instances" {
  description = "Min Cloud Function instances (0 for scale-to-zero)"
  type        = number
  default     = 0
}

variable "cf_env" {
  description = "Environment variables for Cloud Functions (GCP_PROJECT is set automatically)"
  type        = map(string)
  default     = {}
  sensitive   = true
}