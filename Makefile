.PHONY: help install build clean publish-test publish

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

test:
	uv run pytest --cov=src --cov-report=html --cov-report=term-missing

format:
	uv run ruff format src tests

check:
	uv run ruff check src tests

install:
	uv sync

build:
	uv build

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -delete
	find . -name "*.pyc" -delete

publish-test:
	uv publish --publish-url https://test.pypi.org/legacy/

publish:
	uv publish
