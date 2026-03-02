# KpopNara Invoice Automation — Local Development

.PHONY: up up-build down help

# Start all services (n8n + Discord bot + Cloud Functions)
up:
	docker compose -f docker-compose.local.yml up -d
	@echo "n8n: http://localhost:5678"
	@echo "Cloud Functions: http://localhost:8080 (research+judge)"
	@echo "Cloud Functions Perplexity: http://localhost:8081 (Perplexity Sonar)"
	@echo "Import workflows: invoice-parse-phase1.local.json, invoice-parse-phase1-perplexity.local.json, invoice-approve.local.json"

# Start with rebuild (use after code changes)
up-build:
	docker compose -f docker-compose.local.yml up -d --build
	@echo "n8n: http://localhost:5678"
	@echo "Cloud Functions: http://localhost:8080 (research+judge)"
	@echo "Cloud Functions Perplexity: http://localhost:8081 (Perplexity Sonar)"
	@echo "Import workflows: invoice-parse-phase1.local.json, invoice-parse-phase1-perplexity.local.json, invoice-approve.local.json"

# Stop services
down:
	docker compose -f docker-compose.local.yml down

help:
	@echo "Local development commands:"
	@echo "  make up       - Start n8n + bot + Cloud Functions (Docker, both pipelines)"
	@echo "  make up-build - Rebuild images and start (use after code changes)"
	@echo "  make down     - Stop all services"
