# ctxledger

Durable Workflow Runtime and Multi-Layer Memory for AI Agents.

`ctxledger` is a remote MCP server for teams that want agent work to be:

- resumable across sessions
- durable across process restarts
- recorded in PostgreSQL as canonical state
- inspectable through operator-facing observability tools

It provides:

- workflow lifecycle control
- episodic memory capture
- initial semantic memory search
- PostgreSQL-backed persistence
- HTTPS-friendly local deployment
- operator-facing CLI observability
- optional Grafana dashboard deployment

---

## What you can do with it

With `ctxledger`, an MCP client or agent can:

- register a repository workspace
- start a workflow for a ticket or task
- checkpoint progress during work
- resume the latest known workflow state later
- complete a workflow with final verification state
- remember episodes as durable memory
- search stored memory items
- inspect workflow, memory, and failure state from the CLI

Current observability commands:

- `ctxledger stats`
- `ctxledger workflows`
- `ctxledger memory-stats`
- `ctxledger failures`

---

## Quick Start

If you want the fastest reliable local setup, use the authenticated HTTPS path.

### Before you start

You need:

- Docker and Docker Compose
- a local certificate for `localhost`
- an MCP client that can talk to a remote MCP server over HTTPS
  - for example: Zed or VS Code

The recommended local endpoint is:

```/dev/null/txt#L1-1
https://localhost:8443/mcp
```

### 1. Create local TLS certificates

`ctxledger` uses Traefik for local HTTPS.  
Create local certs first so your client does not fail on TLS.

A practical local setup with `mkcert`:

```/dev/null/sh#L1-3
mkdir -p docker/traefik/certs
mkcert -install
mkcert -cert-file docker/traefik/certs/localhost.crt -key-file docker/traefik/certs/localhost.key localhost 127.0.0.1 ::1
```

Files expected by the local stack:

- `docker/traefik/certs/localhost.crt`
- `docker/traefik/certs/localhost.key`

### 2. Choose an auth token

The authenticated local stack expects one bearer token shared across:

- startup environment
- smoke tests
- your MCP client configuration

Example:

```/dev/null/sh#L1-2
export CTXLEDGER_SMALL_AUTH_TOKEN="$(openssl rand -hex 32)"
echo "$CTXLEDGER_SMALL_AUTH_TOKEN"
```

If you use `envrcctl`, you can store it as a secret instead:

```/dev/null/sh#L1-1
echo -n "$(openssl rand -hex 32)" | envrcctl secret set CTXLEDGER_SMALL_AUTH_TOKEN --account 'ctxledger' --stdin
```

### 3. Start the authenticated local stack

Standard shell:

```/dev/null/sh#L1-1
CTXLEDGER_SMALL_AUTH_TOKEN=replace-me-with-a-strong-secret docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build --force-recreate
```

If you already exported the token:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build
```

If you use `envrcctl`:

```/dev/null/sh#L1-1
envrcctl exec -- docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build
```

### 4. Verify the server is reachable

Expected MCP endpoint:

```/dev/null/txt#L1-1
https://localhost:8443/mcp
```

Check that missing auth is rejected:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://localhost:8443 --expect-http-status 401 --expect-auth-failure --insecure
```

Check that valid auth works:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://localhost:8443 --bearer-token "$CTXLEDGER_SMALL_AUTH_TOKEN" --scenario workflow --workflow-resource-read --insecure
```

### 5. Configure your MCP client

Representative Zed configuration:

```/dev/null/json#L1-11
{
  "ctxledger": {
    "url": "https://localhost:8443/mcp",
    "headers": {
      "Authorization": "Bearer YOUR_TOKEN_HERE"
    }
  }
}
```

Replace `YOUR_TOKEN_HERE` with the actual token.

### 6. If you want observability dashboards, add Grafana

First apply the observability SQL views:

```/dev/null/sh#L1-1
docker exec -i ctxledger-postgres psql -U ctxledger -d ctxledger < docs/sql/observability_views.sql
```

Create a read-only PostgreSQL role for Grafana.

Open a PostgreSQL shell in the running container:

```/dev/null/sh#L1-1
docker exec -it ctxledger-postgres psql -U ctxledger -d ctxledger
```

Then run:

```/dev/null/sql#L1-11
CREATE ROLE ctxledger_grafana
LOGIN
PASSWORD 'replace-with-a-strong-secret';

GRANT CONNECT ON DATABASE ctxledger TO ctxledger_grafana;
GRANT USAGE ON SCHEMA observability TO ctxledger_grafana;
GRANT SELECT ON ALL TABLES IN SCHEMA observability TO ctxledger_grafana;

ALTER DEFAULT PRIVILEGES IN SCHEMA observability
GRANT SELECT ON TABLES TO ctxledger_grafana;
```

You can verify the role works with:

```/dev/null/sh#L1-1
docker exec -it ctxledger-postgres psql -h 127.0.0.1 -U ctxledger_grafana -d ctxledger -c "SELECT * FROM observability.memory_overview;"
```

Set Grafana-related environment values, then start the overlay.

Standard shell example:

```/dev/null/sh#L1-4
export CTXLEDGER_GRAFANA_ADMIN_USER=admin
export CTXLEDGER_GRAFANA_ADMIN_PASSWORD='replace-with-a-strong-admin-password'
export CTXLEDGER_GRAFANA_POSTGRES_USER=ctxledger_grafana
export CTXLEDGER_GRAFANA_POSTGRES_PASSWORD='replace-with-a-strong-secret'
```

Example with `envrcctl`:

```/dev/null/sh#L1-4
echo -n "admin" | envrcctl secret set CTXLEDGER_GRAFANA_ADMIN_USER --account 'ctxledger' --stdin
echo -n "replace-with-a-strong-admin-password" | envrcctl secret set CTXLEDGER_GRAFANA_ADMIN_PASSWORD --account 'ctxledger' --stdin
echo -n "ctxledger_grafana" | envrcctl secret set CTXLEDGER_GRAFANA_POSTGRES_USER --account 'ctxledger' --stdin
echo -n "replace-with-a-strong-secret" | envrcctl secret set CTXLEDGER_GRAFANA_POSTGRES_PASSWORD --account 'ctxledger' --stdin
```

Then start the stack with Grafana:

```/dev/null/sh#L1-1
envrcctl exec -- docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml -f docker/docker-compose.observability.yml up -d --build
```

Grafana is available at:

```/dev/null/txt#L1-1
http://localhost:3000
```

Log in with:

- username:
  - `CTXLEDGER_GRAFANA_ADMIN_USER`
- password:
  - `CTXLEDGER_GRAFANA_ADMIN_PASSWORD`

Initial dashboards:

- `ctxledger Runtime Overview`
- `ctxledger Memory Overview`
- `ctxledger Failure Overview`

If Grafana starts but dashboards are empty, the two most common causes are:

1. the observability SQL views were not applied
2. the Grafana PostgreSQL role does not have read access to the `observability` schema

Useful checks:

```/dev/null/sh#L1-2
docker exec -it ctxledger-postgres psql -U ctxledger -d ctxledger -c "SELECT * FROM observability.memory_overview;"
docker exec -it ctxledger-postgres psql -h 127.0.0.1 -U ctxledger_grafana -d ctxledger -c "SELECT * FROM observability.memory_overview;"
```

---

## Alternative local startup: HTTPS without authentication

If you want a simpler local HTTPS path for quick experiments, use the no-auth overlay instead.

Start it:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.https-no-auth.yml up -d --build --force-recreate
```

Endpoint:

```/dev/null/txt#L1-1
https://localhost:8444/mcp
```

Representative Zed config:

```/dev/null/json#L1-6
{
  "ctxledger": {
    "url": "https://localhost:8444/mcp"
  }
}
```

Use this only for local, controlled testing.

---

## Common places people get stuck

### TLS errors
Usually means:

- the local cert files do not exist, or
- your machine/client does not trust the certificate

Start with the `mkcert` setup shown above.

### Auth failures (`401`)
Usually means the bearer token does not match between:

- startup
- smoke test
- client config

Use one token everywhere.

### Grafana shows no data
Usually means one of:

- `docs/sql/observability_views.sql` was not applied
- Grafana is not using the intended read-only DB role
- the observability role cannot read the `observability` schema

Use the Grafana runbook for the exact checks.

### MCP client config does not expand environment variables
Some editors do not expand them in MCP config files.  
Paste the actual token if needed.

---

## Day-to-day operator commands

Once the system is running, these are the quickest ways to inspect state.

### High-level summary
```/dev/null/sh#L1-1
ctxledger stats
```

### Recent workflows
```/dev/null/sh#L1-1
ctxledger workflows --limit 10
```

### Memory summary
```/dev/null/sh#L1-1
ctxledger memory-stats
```

### Failure summary
```/dev/null/sh#L1-1
ctxledger failures --limit 20
```

These are operator-facing inspection tools.  
They summarize canonical PostgreSQL state.

---

## What is canonical, and what is derived?

The most important design rule in `ctxledger` is:

- PostgreSQL is the source of truth
- projection files are derived artifacts

Examples of derived artifacts include historical resume projection outputs and other non-canonical repository-facing files.

As of `v0.5.3`, local repository `.agent/resume.json` and `.agent/resume.md` files are no longer a supported user-facing feature.

This means:

- resume and workflow state must be reconstructable from PostgreSQL
- canonical resume inspection should happen through supported service interfaces
- projection failures do not redefine truth
- Grafana should read PostgreSQL directly, not projection files
- CLI observability commands also summarize PostgreSQL-backed state

---

## Current capability summary

### Workflow
Implemented:

- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_resume`
- `workflow_complete`

### Memory
Implemented:

- `memory_remember_episode`
- `memory_search`
- initial `memory_get_context`

Current memory state should be read as:

- episodic memory is real
- semantic search is present in an initial form
- hierarchical retrieval is future work

### Observability
Implemented:

- CLI inspection:
  - `stats`
  - `workflows`
  - `memory-stats`
  - `failures`
- optional Grafana deployment:
  - runtime dashboard
  - memory dashboard
  - failure dashboard

---

## Security posture

For normal local or production-like deployment:

- put `ctxledger` behind a reverse proxy
- terminate TLS at the proxy
- enforce authentication at the proxy layer
- do not expose broad debug/operator surfaces publicly
- do not give Grafana write-capable DB credentials
- use a dedicated read-only Grafana role

For more detail, see:

- `docs/SECURITY.md`
- `docs/deployment.md`

---

## Where to go next

If you are trying to **use** `ctxledger`, go here first:

- local auth HTTPS runbook:
  - `docs/small_auth_operator_runbook.md`
- deployment guidance:
  - `docs/deployment.md`
- Grafana runbook:
  - `docs/grafana_operator_runbook.md`

If you are trying to **understand the model**, start here:

- architecture:
  - `docs/architecture.md`
- workflow model:
  - `docs/workflow-model.md`
- MCP API:
  - `docs/mcp-api.md`
- memory model:
  - `docs/memory-model.md`
- roadmap:
  - `docs/roadmap.md`

If you are trying to **develop on the repository**, use:

- contribution guide:
  - `docs/CONTRIBUTING.md`

---

## Documentation index

Core references:

- `docs/specification.md`
- `docs/architecture.md`
- `docs/workflow-model.md`
- `docs/mcp-api.md`
- `docs/memory-model.md`
- `docs/deployment.md`
- `docs/SECURITY.md`
- `docs/design-principles.md`
- `docs/roadmap.md`

Operator runbooks:

- `docs/small_auth_operator_runbook.md`
- `docs/grafana_operator_runbook.md`

Planning docs:

- `docs/plans/observability_0_4_0_plan.md`
- `docs/plans/auth_planning_index.md`
- `docs/plans/auth_proxy_scaling_plan.md`
- `docs/plans/auth_large_gateway_evaluation_memo.md`
- `docs/plans/auth_large_gateway_shortlist_example.md`

---

## License

See `LICENSE`.
