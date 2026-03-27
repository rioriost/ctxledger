# ctxledger

Durable workflow runtime and memory system for AI agents.

`ctxledger` is a remote MCP server for teams that want agent work to be:

- resumable across sessions
- durable across process restarts
- recorded in PostgreSQL as canonical state
- searchable and inspectable later
- observable through CLI and Grafana

It provides:

- workflow lifecycle control
- automatic and explicit memory capture
- bounded historical recall
- file-work metadata capture
- PostgreSQL-backed persistence
- HTTPS-friendly local deployment
- operator-facing observability
- optional derived Apache AGE graph support in the default local stack

---

## For users

### What you get

The default local setup gives you:

- MCP endpoint:
  - `https://localhost:8443/mcp`
- Grafana:
  - `http://localhost:3000`
- authenticated HTTPS access
- PostgreSQL 17 with the repository-owned local image path
- Docker Compose startup for the full local stack

### Quick start

#### 1. Create local TLS certificates

`ctxledger` expects local certificates for `localhost`.

A practical setup with `mkcert`:

```/dev/null/sh#L1-3
mkdir -p docker/traefik/certs
mkcert -install
mkcert -cert-file docker/traefik/certs/localhost.crt -key-file docker/traefik/certs/localhost.key localhost 127.0.0.1 ::1
```

#### 2. Provide required environment variables

Create a `.env` file in the repository root:

```/dev/null/dotenv#L1-5
CTXLEDGER_SMALL_AUTH_TOKEN=replace-me-with-a-strong-secret
CTXLEDGER_GRAFANA_ADMIN_USER=admin
CTXLEDGER_GRAFANA_ADMIN_PASSWORD=replace-with-a-strong-admin-password
CTXLEDGER_GRAFANA_POSTGRES_USER=ctxledger_grafana
CTXLEDGER_GRAFANA_POSTGRES_PASSWORD=replace-with-a-strong-secret
```

#### 3. Start the stack

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build
```

#### 4. Verify the endpoint

Without auth, the endpoint should reject the request:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://localhost:8443 --expect-http-status 401 --expect-auth-failure --insecure
```

With auth, the workflow scenario should succeed:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://localhost:8443 --bearer-token YOUR_TOKEN_HERE --scenario workflow --workflow-resource-read --insecure
```

Replace `YOUR_TOKEN_HERE` with the value of `CTXLEDGER_SMALL_AUTH_TOKEN`.

#### 5. Connect your MCP client

Example client configuration:

```/dev/null/json#L1-7
{
  "ctxledger": {
    "url": "https://localhost:8443/mcp",
    "headers": {
      "Authorization": "Bearer YOUR_TOKEN_HERE"
    }
  }
}
```

### What you can do with it

An MCP client or agent can:

- register a workspace
- start a workflow
- checkpoint progress
- resume work from durable state
- complete a workflow with verification status
- record explicit high-signal episodes
- search memory
- inspect workflow, memory, and failure state

Useful CLI commands:

- `ctxledger stats`
- `ctxledger workflows`
- `ctxledger memory-stats`
- `ctxledger failures`

---

## Options

### Use secret injection instead of `.env`

If you use `envrcctl`, you can inject the same values at runtime:

```/dev/null/sh#L1-1
envrcctl exec -- docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build
```

### Check stack health

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml ps
```

### Open Grafana

Grafana is available at:

```/dev/null/txt#L1-1
http://localhost:3000
```

Log in with:

- username:
  - `CTXLEDGER_GRAFANA_ADMIN_USER`
- password:
  - `CTXLEDGER_GRAFANA_ADMIN_PASSWORD`

### Build an episode summary explicitly

```/dev/null/sh#L1-4
python -m ctxledger.__init__ build-episode-summary \
  --episode-id <episode-uuid> \
  --summary-kind episode_summary \
  --format json
```

### Check or refresh derived AGE graph state

Readiness:

```/dev/null/sh#L1-1
ctxledger age-graph-readiness
```

Refresh derived summary graph:

```/dev/null/sh#L1-1
ctxledger refresh-age-summary-graph
```

Bootstrap the constrained graph explicitly:

```/dev/null/sh#L1-1
ctxledger bootstrap-age-graph
```

### Current local deployment mode

The supported local deployment mode in this repository is:

- `small`
  - HTTPS
  - proxy-layer authentication
  - Grafana enabled
  - Apache AGE enabled
  - repository-owned PostgreSQL image path

---

## For developers

If you need the current system shape, start with:

- product overview:
  - `docs/project/product/specification.md`
  - `docs/project/product/architecture.md`
  - `docs/project/product/mcp-api.md`
  - `docs/project/product/memory-model.md`
- operations:
  - `docs/operations/README.md`
- memory docs:
  - `docs/memory/README.md`
- release state:
  - `docs/project/releases/CHANGELOG.md`
  - `docs/project/releases/0.9.0_acceptance_review.md`
  - `docs/project/releases/0.9.0_closeout.md`

Useful repository scripts:

- `scripts/apply_schema.py`
- `scripts/ensure_age_extension.py`
- `scripts/mcp_http_smoke.py`
- `scripts/setup_grafana_observability.py`

Core local startup files:

- `docker/docker-compose.yml`
- `docker/docker-compose.small-auth.yml`

Current development posture:

- PostgreSQL state is canonical
- workflow, checkpoint, and projection state remain canonical-first
- summaries, rankings, and graph-backed structures are derived support layers
- file-work metadata is stored without broad file-content indexing
- the README is intentionally brief; use the docs above for details

---

## License

Licensed under the Apache License, Version 2.0.
See `LICENSE`.