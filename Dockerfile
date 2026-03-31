FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY schemas ./schemas
COPY scripts ./scripts
RUN chmod +x /app/scripts/run_azure_bootstrap.sh /app/scripts/start_with_bootstrap.sh

RUN pip install --upgrade pip \
    && pip install .

EXPOSE 8080

CMD ["/app/scripts/start_with_bootstrap.sh"]
