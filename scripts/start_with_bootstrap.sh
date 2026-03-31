#!/bin/sh
set -eu

log() {
  printf '%s\n' "$*"
}

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

resolve_python() {
  if command -v python3 >/dev/null 2>&1; then
    printf '%s\n' "python3"
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    printf '%s\n' "python"
    return 0
  fi
  log "Python interpreter was not found in PATH."
  exit 1
}

PYTHON_BIN=$(resolve_python)
BOOTSTRAP_SCRIPT="$PROJECT_ROOT/scripts/run_azure_bootstrap.sh"

log "ctxledger startup wrapper: bootstrap-first mode"
log "Project root: $PROJECT_ROOT"
log "Using Python: $PYTHON_BIN"

if [ ! -f "$BOOTSTRAP_SCRIPT" ]; then
  log "Bootstrap script not found: $BOOTSTRAP_SCRIPT"
  exit 1
fi

log "Running bootstrap script: $BOOTSTRAP_SCRIPT"
"$BOOTSTRAP_SCRIPT"

log "Bootstrap completed successfully"
log "Starting uvicorn server"

exec python3 -m uvicorn ctxledger.http_app:app --host 0.0.0.0 --port 8080
