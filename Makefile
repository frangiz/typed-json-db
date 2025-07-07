.PHONY: help test build clean

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

test: ## Run tests with coverage
	uv run pytest --cov=src --cov-report=html --cov-report=term-missing

format: ## Format code with ruff
	uv run ruff format src tests

format-check: ## Check if code is properly formatted
	uv run ruff format --check src tests

check: ## Lint code with ruff
	uv run ruff check src tests

install: ## Install dependencies
	uv sync

build: ## Build the package
	uv build

clean: ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -delete
	find . -name "*.pyc" -delete

publish-test: ## Publish to test PyPI
	uv publish --publish-url https://test.pypi.org/legacy/

publish: ## Publish to PyPI
	uv publish
