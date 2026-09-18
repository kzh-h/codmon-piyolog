# AGENTS.md

## Test Commands

### Unit Tests
```bash
uv run python -m pytest tests/ -v --ignore=tests/e2e/
```

### E2E Tests (requires credentials)
```bash
CODMON_EMAIL=xxx CODMON_PASSWORD=xxx PIYOLOG_FEED_URL=xxx uv run python -m pytest tests/e2e/ -v
```

### All Tests
```bash
uv run python -m pytest tests/ -v
```

## Linting & Type Checking
```bash
uv run ruff check .
uv run mypy src/
```

## Code Formatting
```bash
uv run ruff format .
```