FROM mcr.microsoft.com/playwright/python:v1.63.0-noble

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    HEADLESS=true \
    PLAYWRIGHT_CHROMIUM_ARGS="--enable-features=UseOzonePlatform --ozone-platform=wayland --no-sandbox --disable-setuid-sandbox"

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && \
    uv sync --frozen --no-dev

COPY src/ ./src/

ENTRYPOINT ["/app/.venv/bin/python", "-m", "src.main_morning"]