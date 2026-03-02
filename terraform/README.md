# Terraform: BigQuery Catalog + Cloud Functions

Creates the BigQuery dataset, catalog cache tables, and Cloud Functions for the invoice normalization flow.

## Resources

### BigQuery
- **Dataset**: `catalog` (or `var.dataset_id`)
- **Tables**:
  - `dim_vendor_product_map` — Vendor notation → SKU mapping cache
  - `dim_product_catalog_cache` — Full catalog entries per (vendor, artist, album)

### Cloud Functions (Gen 2)
- `invoice-identify-and-generate` — Product identification (cache + research + judge)
- `invoice-generate-po` — PO document (docx) generation
- `invoice-sync-to-thrive` — Thrive API sync + BigQuery update

## Usage

```bash
cd terraform

# Initialize
terraform init

# Plan (set project_id via -var or tfvars)
terraform plan -var="project_id=kpn-platform"

# Apply (set secrets via cf_env or TF_VAR_cf_env)
terraform apply -var="project_id=kpn-platform"
```

## Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `project_id` | GCP project ID | `kpn-platform` |
| `dataset_id` | BigQuery dataset ID | `catalog` |
| `region` | GCP region | `us-central1` |
| `cf_memory` | Cloud Function memory | `512M` |
| `cf_timeout` | Cloud Function timeout (s) | `300` |
| `cf_env` | Env vars (PERPLEXITY_API_KEY, THRIVE_*, etc.) | `{}` |

## Secrets (cf_env)

Pass via variable or `terraform.tfvars` (gitignored):

```hcl
cf_env = {
  PERPLEXITY_API_KEY   = "pplx-..."
  THRIVE_API_URL       = "https://..."
  THRIVE_USERNAME      = "..."
  THRIVE_PASSWORD      = "..."
  LLM_PROVIDER         = "google"   # or anthropic, openai
  LLM_MODEL            = "gemini-1.5-flash"
}
```

`GCP_PROJECT` and `GCP_BQ_DATASET` (catalog) are set automatically from Terraform variables.

## IAM

Ensure the Cloud Function service account has:
- `roles/bigquery.user` for BigQuery
- `roles/bigquery.dataEditor` if writing to tables

The default compute service account usually has these in the same project.
