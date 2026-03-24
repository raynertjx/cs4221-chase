.PHONY: install test demo bench web docker clean help

# Internal variables
PYTHON = python3
PORT = 8080

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	$(PYTHON) -m pip install -r requirements.txt

test: ## Run all tests using pytest
	$(PYTHON) -m pytest -v

demo: ## Run the CLI demo walkthrough
	$(PYTHON) examples/demo.py

bench: ## Run performance benchmarks
	$(PYTHON) examples/benchmark_runner.py

web: ## Start web app at http://localhost:8080
	PORT=$(PORT) $(PYTHON) web/app.py

docker: ## Build and run with Docker (Port 8080)
	docker rm -f chase-v2 || true
	docker build -t chase-app .
	docker run -d --name chase-v2 -p $(PORT):$(PORT) chase-app
	@echo "App running at http://localhost:$(PORT)"

clean: ## Remove all cache and build artifacts
	rm -rf build/ dist/ *.egg-info .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -name "*.pyc" -delete