#!/bin/sh
set -eu

log() {
  printf '%s\n' "$*"
}

fail() {
  printf '%s\n' "$*" >&2
  exit 1
}

require_env() {
  var_name="$1"
  eval "var_value=\${$var_name:-}"
  if [ -z "$var_value" ]; then
    fail "Required environment variable is missing: $var_name"
  fi
}

bool_is_true() {
  case "${1:-}" in
    1|true|TRUE|True|yes|YES|Yes|on|ON|On)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

resolve_python() {
  if command -v python3 >/dev/null 2>&1; then
    printf '%s\n' "python3"
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    printf '%s\n' "python"
    return 0
  fi
  fail "Python interpreter was not found in PATH."
}

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
PYTHON_BIN=$(resolve_python)

AZURE_AI_SCRIPT="$PROJECT_ROOT/scripts/bootstrap_azure_ai.py"
SCHEMA_SCRIPT="$PROJECT_ROOT/scripts/bootstrap_schema.py"
SCHEMA_PATH="$PROJECT_ROOT/schemas/postgres.sql"

[ -f "$AZURE_AI_SCRIPT" ] || fail "Azure AI bootstrap script not found: $AZURE_AI_SCRIPT"
[ -f "$SCHEMA_SCRIPT" ] || fail "Schema bootstrap script not found: $SCHEMA_SCRIPT"
[ -f "$SCHEMA_PATH" ] || fail "Schema file not found: $SCHEMA_PATH"

require_env CTXLEDGER_DATABASE_URL
require_env AZURE_OPENAI_ENDPOINT
require_env AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME
require_env AZURE_OPENAI_EFFECTIVE_AUTH_MODE

DB_CONNECT_TIMEOUT_SECONDS="${CTXLEDGER_DB_CONNECT_TIMEOUT_SECONDS:-5}"
WAIT_TIMEOUT_SECONDS="${CTXLEDGER_BOOTSTRAP_WAIT_TIMEOUT_SECONDS:-300}"
WAIT_INTERVAL_SECONDS="${CTXLEDGER_BOOTSTRAP_WAIT_INTERVAL_SECONDS:-5}"
EMBEDDING_DIMENSIONS="${CTXLEDGER_EMBEDDING_DIMENSIONS:-1536}"
DB_AGE_ENABLED="${CTXLEDGER_DB_AGE_ENABLED:-true}"
EMBEDDING_ENABLED="${CTXLEDGER_EMBEDDING_ENABLED:-true}"
AZURE_OPENAI_AUTH_MODE="${AZURE_OPENAI_EFFECTIVE_AUTH_MODE}"

log "Starting Azure-side ctxledger bootstrap"
log "Project root: $PROJECT_ROOT"
log "Using Python: $PYTHON_BIN"
log "Azure OpenAI auth mode: $AZURE_OPENAI_AUTH_MODE"

set -- \
  "$PYTHON_BIN" "$AZURE_AI_SCRIPT" \
  --database-url "$CTXLEDGER_DATABASE_URL" \
  --azure-openai-endpoint "$AZURE_OPENAI_ENDPOINT" \
  --azure-openai-auth-mode "$AZURE_OPENAI_AUTH_MODE" \
  --embedding-deployment "$AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME" \
  --embedding-dimensions "$EMBEDDING_DIMENSIONS" \
  --wait-timeout-seconds "$WAIT_TIMEOUT_SECONDS" \
  --wait-interval-seconds "$WAIT_INTERVAL_SECONDS" \
  --connect-timeout-seconds "$DB_CONNECT_TIMEOUT_SECONDS"

if [ "$AZURE_OPENAI_AUTH_MODE" = "subscription_key" ]; then
  require_env CTXLEDGER_AZURE_OPENAI_SUBSCRIPTION_KEY
  set -- "$@" \
    --azure-openai-subscription-key "$CTXLEDGER_AZURE_OPENAI_SUBSCRIPTION_KEY"
fi

if ! bool_is_true "$DB_AGE_ENABLED"; then
  set -- "$@" --skip-age
fi

if bool_is_true "$EMBEDDING_ENABLED"; then
  set -- "$@" --validate-embeddings
fi

log "Running Azure AI bootstrap"
"$@"

set -- \
  "$PYTHON_BIN" "$SCHEMA_SCRIPT" \
  --database-url "$CTXLEDGER_DATABASE_URL" \
  --schema-path "$SCHEMA_PATH" \
  --wait-timeout-seconds "$WAIT_TIMEOUT_SECONDS" \
  --wait-interval-seconds "$WAIT_INTERVAL_SECONDS" \
  --connect-timeout-seconds "$DB_CONNECT_TIMEOUT_SECONDS"

if bool_is_true "$DB_AGE_ENABLED"; then
  set -- "$@" --ensure-age
fi

log "Running schema bootstrap"
"$@"

log "Azure-side ctxledger bootstrap completed successfully"
