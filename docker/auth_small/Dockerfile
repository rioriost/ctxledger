# syntax=docker/dockerfile:1.7

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/opt/auth-small-venv/bin:${PATH}"

WORKDIR /app

# `curl` is included so the compose-level healthcheck can use a real HTTP
# client instead of an ad-hoc `python -c` urllib invocation.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Build a self-contained virtualenv so the runtime container never has to
# reach out to PyPI on start. Pinning to compatible-release specifiers keeps
# the image reproducible while still allowing security patch uptake on
# rebuild.
RUN python -m venv /opt/auth-small-venv \
    && /opt/auth-small-venv/bin/pip install --upgrade pip \
    && /opt/auth-small-venv/bin/pip install \
        "fastapi~=0.115" \
        "uvicorn[standard]~=0.30"

COPY docker/auth_small/src /app/src

ENV PYTHONPATH=/app/src

EXPOSE 8090

HEALTHCHECK --interval=10s --timeout=5s --retries=10 --start-period=10s \
    CMD curl -fsS http://127.0.0.1:8090/healthz > /dev/null || exit 1

CMD ["python", "-m", "uvicorn", "auth_small_app:app", \
     "--app-dir", "/app/src", \
     "--host", "0.0.0.0", \
     "--port", "8090"]
