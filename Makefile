.PHONY: format
format:
	uv run ruff format .
	uv run ruff check . --fix

.PHONY: lint
lint:
	uv run ruff check .

.PHONY: type
type:
	uv run mypy .

.PHONY: test
test:
	uv run pytest

.PHONY: secrets
secrets:
	detect-secrets scan

.PHONY: check
check:
	uv run ruff format . --check
	uv run ruff check .
	uv run mypy .
	uv run pytest