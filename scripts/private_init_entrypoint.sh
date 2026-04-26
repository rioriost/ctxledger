#!/bin/sh
# Entrypoint for the `ctxledger-private-init` service.
#
# This script is the extracted form of what was previously a single very long
# `sh -lc '...'` payload embedded in `docker/docker-compose.small-auth.yml`.
# Embedding that payload inline made the compose file fragile under
# `podman-compose`, where shell quoting and `$${VAR}` double-escaping behave
# slightly differently from `docker compose`. Moving the logic into a real
# script lets the compose file simply reference this file by path.
#
# Responsibilities, in order:
#   1. Apply the relational schema (`ctxledger apply-schema`).
#   2. Ensure the AGE PostgreSQL extension is loaded.
#   3. Optionally bootstrap or rebuild the AGE summary graph, gated by env.
#   4. Optionally configure Grafana observability (best-effort; non-fatal).
#
# Environment variables consumed:
#   CTXLEDGER_DATABASE_URL
#       Database URL used for schema apply, AGE extension setup, and AGE
#       graph bootstrap. Falls back to the in-stack default if unset so the
#       script keeps working when invoked without an explicit override.
#   CTXLEDGER_DB_AGE_GRAPH_NAME
#       AGE graph name. Defaults to `ctxledger_memory`.
#   CTXLEDGER_PRIVATE_INIT_REBUILD_AGE_GRAPH
#       When `true`, run `bootstrap-age-graph --rebuild`.
#   CTXLEDGER_PRIVATE_INIT_BOOTSTRAP_AGE_GRAPH
#       When `true` (and rebuild is not requested), run `bootstrap-age-graph`
#       without `--rebuild`. Default behavior is to skip AGE graph bootstrap.

set -eu

log() {
    printf 'private-init: %s\n' "$*"
}

PYTHON_BIN="${PYTHON_BIN:-/opt/ctxledger-venv/bin/python}"
DATABASE_URL="${CTXLEDGER_DATABASE_URL:-postgresql://ctxledger:ctxledger@postgres:5432/ctxledger}"
AGE_GRAPH_NAME="${CTXLEDGER_DB_AGE_GRAPH_NAME:-ctxledger_memory}"
REBUILD_AGE_GRAPH="${CTXLEDGER_PRIVATE_INIT_REBUILD_AGE_GRAPH:-false}"
BOOTSTRAP_AGE_GRAPH="${CTXLEDGER_PRIVATE_INIT_BOOTSTRAP_AGE_GRAPH:-false}"

if [ ! -x "$PYTHON_BIN" ]; then
    log "Python interpreter not found or not executable: $PYTHON_BIN"
    exit 1
fi

log "Applying relational schema"
"$PYTHON_BIN" -m ctxledger.__init__ apply-schema

log "Ensuring AGE extension is installed"
"$PYTHON_BIN" scripts/ensure_age_extension.py \
    --database-url "$DATABASE_URL"

if [ "$REBUILD_AGE_GRAPH" = "true" ]; then
    log "Running explicit AGE graph rebuild (graph=$AGE_GRAPH_NAME)"
    "$PYTHON_BIN" -m ctxledger.__init__ bootstrap-age-graph \
        --database-url "$DATABASE_URL" \
        --graph-name "$AGE_GRAPH_NAME" \
        --rebuild
elif [ "$BOOTSTRAP_AGE_GRAPH" = "true" ]; then
    log "Running opt-in AGE graph bootstrap (graph=$AGE_GRAPH_NAME)"
    "$PYTHON_BIN" -m ctxledger.__init__ bootstrap-age-graph \
        --database-url "$DATABASE_URL" \
        --graph-name "$AGE_GRAPH_NAME"
else
    log "Skipping AGE graph bootstrap (private init bootstrap disabled by default)"
fi

log "Attempting Grafana observability setup (non-fatal)"
if "$PYTHON_BIN" scripts/setup_grafana_observability.py; then
    log "Grafana observability setup completed"
else
    log "Skipping Grafana observability setup because credentials are not configured or setup failed"
fi

log "Private init completed successfully"
