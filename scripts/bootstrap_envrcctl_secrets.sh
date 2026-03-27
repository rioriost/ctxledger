#!/usr/bin/env sh
set -eu

usage() {
  cat <<'EOF'
Usage:
  sh scripts/bootstrap_envrcctl_secrets.sh

This script generates local ctxledger secrets and stores them in envrcctl by piping
each generated value through stdin.

It sets:

- CTXLEDGER_SMALL_AUTH_TOKEN          -> account: ctxledger_auth_token
- CTXLEDGER_GRAFANA_ADMIN_USER        -> account: ctxledger_gf_admin_user
- CTXLEDGER_GRAFANA_ADMIN_PASSWORD    -> account: ctxledger_gf_admin_pass
- CTXLEDGER_GRAFANA_POSTGRES_USER     -> account: ctxledger_gf_pg_user
- CTXLEDGER_GRAFANA_POSTGRES_PASSWORD -> account: ctxledger_gf_pg_pass

Notes:
- OPENAI_API_KEY is not generated here. Store that separately with envrcctl.
- The Grafana admin password is generated in a form that should satisfy Grafana's
  password policy.
EOF
}

if [ "$#" -gt 0 ]; then
  case "$1" in
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "error: this script does not accept options" >&2
      usage >&2
      exit 2
      ;;
  esac
fi

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "error: required command not found: $1" >&2
    exit 1
  fi
}

require_command envrcctl
require_command openssl

set_secret() {
  value="$1"
  var="$2"
  account="$3"

  printf '%s' "$value" | envrcctl secret set "$var" \
    --account "$account" \
    --stdin
}

generate_base64_secret() {
  openssl rand -base64 24 | tr -d '\n'
}

generate_grafana_admin_password() {
  hex="$(openssl rand -hex 16 | tr -d '\n')"
  printf 'Admin-%sA1!' "$hex"
}

small_auth_token="$(generate_base64_secret)"
grafana_admin_user="admin"
grafana_admin_password="$(generate_grafana_admin_password)"
grafana_pg_user="ctxledger_grafana"
grafana_pg_password="$(generate_base64_secret)"

set_secret "$small_auth_token" "CTXLEDGER_SMALL_AUTH_TOKEN" "ctxledger_auth_token"
set_secret "$grafana_admin_user" "CTXLEDGER_GRAFANA_ADMIN_USER" "ctxledger_gf_admin_user"
set_secret "$grafana_admin_password" "CTXLEDGER_GRAFANA_ADMIN_PASSWORD" "ctxledger_gf_admin_pass"
set_secret "$grafana_pg_user" "CTXLEDGER_GRAFANA_POSTGRES_USER" "ctxledger_gf_pg_user"
set_secret "$grafana_pg_password" "CTXLEDGER_GRAFANA_POSTGRES_PASSWORD" "ctxledger_gf_pg_pass"

cat <<'EOF'
Stored ctxledger local secrets in envrcctl.

Stored variables:
- CTXLEDGER_SMALL_AUTH_TOKEN
- CTXLEDGER_GRAFANA_ADMIN_USER
- CTXLEDGER_GRAFANA_ADMIN_PASSWORD
- CTXLEDGER_GRAFANA_POSTGRES_USER
- CTXLEDGER_GRAFANA_POSTGRES_PASSWORD

Still required separately:
- OPENAI_API_KEY

Example:
  envrcctl secret set --account 'ctxledger_openai_api_key' OPENAI_API_KEY
EOF
