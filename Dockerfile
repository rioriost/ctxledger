FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    PATH="/root/.local/bin:/opt/ctxledger-venv/bin:${PATH}"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
COPY schemas ./schemas
COPY scripts ./scripts
RUN chmod +x /app/scripts/run_azure_bootstrap.sh /app/scripts/start_with_bootstrap.sh

RUN uv venv /opt/ctxledger-venv
RUN cd /app && \
    VIRTUAL_ENV=/opt/ctxledger-venv PATH="/opt/ctxledger-venv/bin:/root/.local/bin:${PATH}" \
    uv sync --frozen --active

EXPOSE 8080

CMD ["/app/scripts/start_with_bootstrap.sh"]
