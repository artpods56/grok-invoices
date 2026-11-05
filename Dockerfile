FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/apps/api/src \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies come first so feature pushes reuse this layer and build in seconds.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .

RUN useradd --system --uid 10001 --no-create-home app \
    && mkdir /data \
    && chown app /data
USER app

EXPOSE 8000

# Bots authenticate with a token in the URL, so request URLs must stay out of logs.
CMD ["uvicorn", "grok_invoices.entrypoints.http:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-access-log"]
