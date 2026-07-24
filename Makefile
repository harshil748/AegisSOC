.DEFAULT_GOAL := help
COMPOSE ?= docker compose
# Prefer the project venv when present (avoids Homebrew python3 missing deps).
PY ?= $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)
GATEWAY_URL ?= http://localhost:8080

.PHONY: help up up-observability down restart logs ps build seed replay demo \
        sync-gateway test test-unit test-integration lint load-test load-test-locust \
        samples clean nuke evaluate

help: ## Show this help
	@echo "AegisSOC — common developer commands"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

up: ## Start the full stack in the background (docker compose up -d --build)
	$(COMPOSE) up -d --build
	@echo "Waiting for core services to become healthy..."
	@sleep 5
	@$(MAKE) ps

up-observability: ## Start the stack plus Grafana/otel-collector (observability profile)
	$(COMPOSE) --profile observability up -d --build

down: ## Stop and remove all containers (keeps named volumes)
	$(COMPOSE) down

nuke: ## Stop containers AND delete all volumes (full reset, destroys data)
	$(COMPOSE) down -v

restart: down up ## Restart the full stack

ps: ## Show container status
	$(COMPOSE) ps

logs: ## Tail logs for all services (Ctrl-C to stop)
	$(COMPOSE) logs -f --tail=200

build: ## Rebuild all service images without starting them
	$(COMPOSE) build

samples: ## Regenerate the synthetic benign background corpus (data/samples/)
	$(PY) scripts/generate_samples.py --out-dir data/samples --seed 1337

seed: ## Seed threat intel + replay all 3 canonical demo scenarios end-to-end
	$(PY) scripts/seed_demo.py --api-url $(GATEWAY_URL)

replay: ## Replay every scenario in data/scenarios/ with realistic pacing
	$(PY) scripts/replay_scenario.py data/scenarios/*.json --api-url $(GATEWAY_URL) --speed 200

demo: seed ## Alias for `make seed` — the one-command demo entrypoint
	@echo "Demo seeded. Open http://localhost:3000 (analyst/analyst123, senior/senior123, admin/admin123)."

sync-gateway: ## Run gateway alone in AEGIS_SYNC_MODE (no Kafka/Postgres/Neo4j)
	AEGIS_SYNC_MODE=true $(PY) scripts/run_sync_gateway.py

test: test-unit ## Run the default test suite (unit tests across the monorepo)

test-unit: ## Run unit tests (packages/common + any service-local tests)
	$(PY) -m pytest packages/common/tests tests/unit -v

test-integration: ## Run integration tests against a running stack
	$(PY) -m pytest tests/integration -v

lint: ## Lint Python sources with ruff (if installed) and frontend with eslint
	-ruff check packages/common services scripts
	-cd frontend && npm run lint

load-test: ## Threaded load test against ingestion (see docs/EVALUATION.md)
	$(PY) scripts/load_test_ingest.py --rate 500 --duration 30 --api-url $(GATEWAY_URL)

load-test-locust: ## Alternative Locust-based load test (requires `pip install locust`)
	locust -f tests/load/locustfile.py --headless -u 200 -r 20 -t 5m --host http://localhost:8001

evaluate: ## Run detection + LLM groundedness evaluation scripts
	$(PY) scripts/evaluate_detection.py --include-samples
	$(PY) scripts/evaluate_llm_groundedness.py --reports-dir eval/reports/ || true

clean: ## Remove Python/Node caches and build artifacts (safe, no data loss)
	find . -type d -name '__pycache__' -not -path './.venv/*' -exec rm -rf {} +
	find . -type d -name '.pytest_cache' -exec rm -rf {} +
	rm -rf frontend/dist
