# OpsIQ — Self-Improving Operational Intelligence Agent
# Usage: make start | make test | make reset | make seed

.PHONY: start backend frontend test reset seed clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

start: ## Start backend + frontend (use Ctrl+C to stop)
	@echo "Starting OpsIQ..."
	@python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 & \
	sleep 2 && python -m streamlit run frontend/streamlit_app.py --server.port 8501
	@echo "OpsIQ stopped."

backend: ## Start backend only
	python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

frontend: ## Start frontend only
	python -m streamlit run frontend/streamlit_app.py --server.port 8501

test: ## Run full test suite
	python -m pytest tests/ -v

reset: ## Reset demo state via API
	@curl -s -X POST http://localhost:8000/demo/reset | python3 -m json.tool

seed: ## Regenerate CSV seed data
	python data/seed_data.py

clean: ## Remove __pycache__, .pytest_cache, and runtime DB
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -f storage/opsiq.db

install: ## Install dependencies
	pip install -r requirements.txt
