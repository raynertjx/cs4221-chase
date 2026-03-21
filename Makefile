.PHONY: install test demo bench web docker clean help

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## Install deps
	pip install -r requirements.txt

test:  ## Run all tests
	python tests/test_chase.py

demo:  ## Run the CLI demo
	python examples/demo.py

bench:  ## Run benchmarks
	python examples/benchmark_runner.py

web:  ## Start web app at http://localhost:5000
	python web/app.py

docker:  ## Build and run with Docker
	docker build -t chase-algorithm .
	docker run -p 5000:5000 chase-algorithm

clean:  ## Remove build artifacts
	rm -rf build/ dist/ *.egg-info __pycache__ chase/__pycache__ tests/__pycache__
	find . -name '*.pyc' -delete
