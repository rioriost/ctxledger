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

COPY pyproject.toml README.md ./
COPY src ./src
COPY schemas ./schemas

RUN pip install --upgrade pip \
    && pip install .

EXPOSE 8080

CMD ["python", "-m", "ctxledger", "serve", "--transport", "http", "--host", "0.0.0.0", "--port", "8080"]
