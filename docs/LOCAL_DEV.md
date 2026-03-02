# Local Development — KpopNara Invoice Automation

Run the full stack locally in Docker: n8n, Discord bot, and Cloud Functions.

## Prerequisites

- Docker & Docker Compose
- GCP credentials for BigQuery (service account JSON)
- Anthropic API key (for Claude invoice parse)
- Discord bot token

## Quick Start

### 1. Configure environment

```bash
cp .env.local.example .env.local
# Edit .env.local: DISCORD_BOT_TOKEN, INVOICE_CHANNEL_NAME, ANTHROPIC_API_KEY, GCP_PROJECT

# GCP credentials for BigQuery (mounts ~/.config/gcloud)
gcloud auth application-default login
```

### 2. Start all services

```bash
docker compose -f docker-compose.local.yml up -d
```

- **n8n**: http://localhost:5678
- **Cloud Functions**: http://localhost:8080 (research+judge)
- **Cloud Functions Perplexity**: http://localhost:8081 (Perplexity Sonar)
- **Bot**: runs in Docker, forwards to n8n

### 3. Import workflows into n8n

1. Open http://localhost:5678
2. **Workflows** → **Import from File**
3. Import:
   - `workflows/invoice-parse-phase1.local.json` (research+judge pipeline)
   - `workflows/invoice-parse-phase1-perplexity.local.json` (Perplexity Sonar pipeline)
   - `workflows/invoice-approve.local.json`
4. **Activate** the workflow you want (only one invoice-parse workflow at a time) and invoice-approve

The `.local` workflows use `http://cloud-functions:8080` (research+judge) or `http://cloud-functions-perplexity:8081` (Perplexity) via the Docker network.

**Perplexity pipeline**: Set `PERPLEXITY_API_KEY` in `.env.local`. Import `invoice-parse-phase1-perplexity.local.json` and activate it (deactivate the research+judge workflow).

### 4. Configure n8n credentials

- **Anthropic API**: Settings → Credentials → Add "Header Auth"
  - Name: `Anthropic API`
  - Header: `x-api-key`, Value: your `ANTHROPIC_API_KEY`
- **BigQuery**: Add Google BigQuery OAuth2 credentials (for approve workflow)

## Makefile shortcuts

```bash
make up    # Start n8n + bot + Cloud Functions (Docker)
make down  # Stop all services
make help  # List commands
```

## Architecture (Local)

```
Discord → Bot (Docker) → n8n (Docker) → Cloud Functions (Docker)
                              ↓
                         BigQuery (GCP)
                         Anthropic API
```

All services run in Docker. n8n reaches Cloud Functions at `http://cloud-functions:8080` (research+judge) or `http://cloud-functions-perplexity:8081` (Perplexity).

## Troubleshooting

### BigQuery / GCP credentials

Run `gcloud auth application-default login` before starting. The compose file mounts `~/.config/gcloud` into the Cloud Functions container.

### n8n can't reach Cloud Functions

- Ensure all services are up: `docker compose -f docker-compose.local.yml ps`
- Cloud Functions should be reachable at `http://cloud-functions:8080` from n8n (same network)

### BigQuery errors

- Ensure `gcp-credentials.json` is valid and has BigQuery access
- Run `bigquery/create_vendor_product_map.sql` to create the cache table

### Claude parse fails

- Check Anthropic credential in n8n
- Verify `ANTHROPIC_API_KEY` is set in `.env.local`

### Thrive sync no-op

- If `THRIVE_API_URL` is not set, the function returns success without calling Thrive (safe for local testing)
