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
- default Grafana dashboard deployment in the authenticated local stack
- a constrained Apache AGE prototype path for graph-backed `supports` lookup plus a narrow derived-summary traversal read path, with explicit CLI bootstrap/readiness/refresh support, using a repository-owned PostgreSQL image path and now enabled by default in the `small` stack

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

Current PostgreSQL/graph setup commands:

- `ctxledger print-schema-path`
- `ctxledger apply-schema`
- `ctxledger bootstrap-age-graph`
- `ctxledger age-graph-readiness`
- `ctxledger refresh-age-summary-graph`

Current hierarchy build command:

- `ctxledger build-episode-summary`

---

## Quick Start

`ctxledger` now has two deployment patterns:

1. `small` (default)
   - HTTPS
   - proxy-layer authentication
   - Grafana enabled
   - Apache AGE enabled
   - repository-owned PostgreSQL 17 image with AGE + pgvector
2. `large` (future plan; not implemented yet)
   - HTTPS
   - proxy-layer authentication
   - Grafana enabled
   - Azure Database for PostgreSQL

This Quick Start is for the **default `small` deployment**.

### What you will get

When you finish the steps below, you will have:

- an authenticated MCP endpoint at:
  - `https://localhost:8443/mcp`
- Grafana at:
  - `http://localhost:3000`
- PostgreSQL 17 through the repository-owned AGE-capable image path
- the default local development stack running through Docker Compose

### Before you start

You need:

- Docker and Docker Compose
- a local certificate for `localhost`
- either:
  - a `.env` file workflow
  - or `envrcctl exec`
- an MCP client that can talk to a remote MCP server over HTTPS
  - for example: Zed or VS Code

### Step 1 — Create local TLS certificates

`ctxledger` uses Traefik for local HTTPS.

Create local certs first so your client does not fail on TLS.

A practical local setup with `mkcert`:

```/dev/null/sh#L1-3
mkdir -p docker/traefik/certs
mkcert -install
mkcert -cert-file docker/traefik/certs/localhost.crt -key-file docker/traefik/certs/localhost.key localhost 127.0.0.1 ::1
```

Files expected by the default local stack:

- `docker/traefik/certs/localhost.crt`
- `docker/traefik/certs/localhost.key`

### Step 2 — Choose how you want to pass environment variables

The default `small` deployment expects values for:

- `CTXLEDGER_SMALL_AUTH_TOKEN`
- `CTXLEDGER_GRAFANA_ADMIN_USER`
- `CTXLEDGER_GRAFANA_ADMIN_PASSWORD`
- `CTXLEDGER_GRAFANA_POSTGRES_USER`
- `CTXLEDGER_GRAFANA_POSTGRES_PASSWORD`

You can provide these either through a `.env` file or through `envrcctl exec`.

#### Option A: use a `.env` file

Create a `.env` file in the repository root with values like:

```/dev/null/dotenv#L1-5
CTXLEDGER_SMALL_AUTH_TOKEN=replace-me-with-a-strong-secret
CTXLEDGER_GRAFANA_ADMIN_USER=admin
CTXLEDGER_GRAFANA_ADMIN_PASSWORD=replace-with-a-strong-admin-password
CTXLEDGER_GRAFANA_POSTGRES_USER=ctxledger_grafana
CTXLEDGER_GRAFANA_POSTGRES_PASSWORD=replace-with-a-strong-secret
```

#### Option B: use `envrcctl exec`

You can store the same values as secrets instead.

Example:

```/dev/null/sh#L1-5
echo -n "$(openssl rand -hex 32)" | envrcctl secret set CTXLEDGER_SMALL_AUTH_TOKEN --account 'ctxledger_auth' --stdin
echo -n "admin" | envrcctl secret set CTXLEDGER_GRAFANA_ADMIN_USER --account 'ctxledger_grafana_admin' --stdin
echo -n "$(openssl rand -hex 32)" | envrcctl secret set CTXLEDGER_GRAFANA_ADMIN_PASSWORD --account 'ctxledger_grafana_pass' --stdin
echo -n "ctxledger_grafana" | envrcctl secret set CTXLEDGER_GRAFANA_POSTGRES_USER --account 'ctxledger_pgsql_admin' --stdin
echo -n "$(openssl rand -hex 32)" | envrcctl secret set CTXLEDGER_GRAFANA_POSTGRES_PASSWORD --account 'ctxledger_pgsql_pass' --stdin
```

### Step 3 — Start the default `small` deployment

The default deployment is now:

- `docker/docker-compose.yml`
- `docker/docker-compose.small-auth.yml`

If you use a `.env` file:
If you already exported the required values:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build
```

If you use `envrcctl`:

```/dev/null/sh#L1-1
envrcctl exec -- docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build
```

This default startup path is intended to bring up:

- authenticated HTTPS access
- PostgreSQL 17 through the repository-owned AGE-capable image path
- AGE enabled by default
- automatic AGE extension setup before graph bootstrap
- automatic AGE graph bootstrap for the default `ctxledger_memory` graph
- the private application service behind auth
- Grafana

### Step 4 — Wait for the stack to become healthy

A successful startup should leave these services healthy or started:

- `ctxledger-postgres`
- `ctxledger-server-private`
- `ctxledger-auth-small`
- `ctxledger-grafana`
- `ctxledger-traefik`

If `ctxledger-postgres` fails immediately after you switched from an older local stack, check whether you still have a PostgreSQL 16-era local volume attached. In that case, follow the PostgreSQL 18 migration note in Step 3 and recreate the local PostgreSQL volume before retrying.

You can inspect the current state with:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml ps
```

### Step 5 — Verify the MCP endpoint

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

If you are using a `.env` file and do not want to export the token into your shell first, pass the actual token value directly.

### Step 5.1 — Optionally build one canonical episode summary explicitly

The current `0.6.0` hierarchy slice includes an explicit episode summary build
command:

- `ctxledger build-episode-summary`

This command builds one canonical relational summary for a selected episode from
that episode's current memory items.

Minimal example:

```/dev/null/sh#L1-4
python -m ctxledger.__init__ build-episode-summary \
  --episode-id <episode-uuid> \
  --summary-kind episode_summary \
  --format json
```

By default, this path uses replace-or-rebuild behavior for the selected
`summary_kind`.

To keep existing summaries of the same kind instead of replacing them:

```/dev/null/sh#L1-4
python -m ctxledger.__init__ build-episode-summary \
  --episode-id <episode-uuid> \
  --summary-kind episode_summary \
  --no-replace-existing
```

### Step 5.2 — Optionally refresh the derived AGE summary graph

If you want the current derived summary graph shape mirrored into AGE for the
narrow graph-backed summary traversal path, refresh it explicitly with:

- `ctxledger refresh-age-summary-graph`

Minimal example:

```/dev/null/sh#L1-3
python -m ctxledger.__init__ refresh-age-summary-graph \
  --database-url "$CTXLEDGER_DATABASE_URL" \
  --graph-name ctxledger_memory
```

This refresh path rebuilds the current derived summary graph shape from the
canonical relational summary tables:

- `memory_summaries`
- `memory_summary_memberships`

The current mirrored shape is intentionally narrow:

- `memory_summary` nodes
- `memory_item` nodes
- `summarizes` edges

This graph state is derived and rebuildable.
Canonical summary ownership remains relational.

### Step 5.3 — Check AGE graph readiness and summary graph observability

You can inspect the current AGE graph readiness state with:

- `ctxledger age-graph-readiness`

Minimal example:

```/dev/null/sh#L1-3
python -m ctxledger.__init__ age-graph-readiness \
  --database-url "$CTXLEDGER_DATABASE_URL" \
  --graph-name ctxledger_memory
```

The current readiness output is intended to help you verify:

- whether AGE is available
- whether the configured graph is ready
- whether derived summary mirroring is in scope for the current environment
- which explicit refresh command is expected for summary graph rebuilding
- whether the current summary graph state should be read as ready, unavailable,
  or degraded-but-non-canonical

If the summary graph is absent, stale, or otherwise degraded, current summary
retrieval should still be read as relationally correct for the supported
`0.6.0` path.

The runtime debug surface also reports AGE prototype details, including summary
graph mirroring observability and the current workflow-completion-oriented
summary automation policy.

When interpreting those details, treat the derived summary graph as:

- optional for the current narrow graph-backed auxiliary read path
- rebuildable through `ctxledger refresh-age-summary-graph`
- not the canonical system of record for summary truth
- a degraded-but-ready concern when relational retrieval remains healthy

### Step 6 — Verify Grafana

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

The default stack is intended to complete the Grafana-related observability setup automatically during startup.

If Grafana starts but dashboards are empty, useful checks are:

```/dev/null/sh#L1-2
docker exec -it ctxledger-postgres psql -U ctxledger -d ctxledger -c "SELECT * FROM observability.memory_overview;"
docker exec -it ctxledger-postgres psql -h 127.0.0.1 -U ctxledger_grafana -d ctxledger -c "SELECT * FROM observability.memory_overview;"
```

### Step 7 — Configure your MCP client

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

Replace `YOUR_TOKEN_HERE` with the actual auth token used by your local stack.

### Step 8 — Know the future `large` direction

A second deployment pattern is planned, but not implemented yet:

- `large`
  - HTTPS
  - proxy-layer authentication
  - Grafana enabled
  - Azure Database for PostgreSQL

Until that work exists, treat the default `small` deployment as the canonical way to run `ctxledger` locally.

---

## Constrained AGE prototype controls

For a practical step-by-step validation procedure for this prototype, see:

- `docs/memory/age_prototype_validation_runbook.md`

For a fill-in template that records one concrete validation pass, see:

- `docs/memory/age_prototype_validation_observation_template.md`

For the repository-owned PostgreSQL 17 AGE image/build path that now underpins
the default local stack, see:

- `docs/memory/age_docker_provisioning_plan.md`
- `docs/memory/age_image_selection_note.md`
- `docs/memory/age_image_selection_decision.md`
- `docs/memory/age_image_candidate_repo_build_record.md`

`ctxledger` now includes a **constrained Apache AGE prototype** for one-hop
`supports` relation lookup.

This prototype is intentionally narrow:

- relational PostgreSQL tables remain canonical
- AGE-backed graph lookup is enabled by default in the `small` stack through the
  repository-owned PostgreSQL image path
- current visible `memory_get_context` behavior is intended to remain unchanged
- relational fallback remains the safe path when AGE is unavailable, unready, or
  not bootstrapped

The current prototype controls are:

- `CTXLEDGER_DB_AGE_ENABLED`
  - enable or disable the AGE-backed prototype path
  - current default in the `small` stack:
    - `true`
- `CTXLEDGER_DB_AGE_GRAPH_NAME`
  - select the named AGE graph used by the prototype
  - default:
    - `ctxledger_memory`

Example shell setup:

```/dev/null/sh#L1-2
export CTXLEDGER_DB_AGE_ENABLED=true
export CTXLEDGER_DB_AGE_GRAPH_NAME=ctxledger_memory
```

### Check constrained AGE graph readiness

If you want a lightweight readiness check for the constrained AGE prototype,
use:

```/dev/null/sh#L1-1
ctxledger age-graph-readiness
```

You can also override the database URL or graph name directly:

```/dev/null/sh#L1-3
ctxledger age-graph-readiness \
  --database-url postgresql://ctxledger:ctxledger@localhost:5432/ctxledger \
  --graph-name ctxledger_memory
```

The command prints a small JSON summary including:

- whether the prototype is enabled
- the configured graph name
- AGE availability
- current graph-readiness status

The current runtime debug surface also exposes the AGE prototype state through:

- `/debug/runtime`
- `/debug/routes`
- `/debug/tools`

Example shape:

```/dev/null/json#L1-6
{
  "age_enabled": true,
  "age_graph_name": "ctxledger_memory",
  "age_available": true,
  "age_graph_status": "graph_ready"
}
```

This is useful as a lightweight operator-facing readiness check before or after
running the explicit bootstrap path.

For the default `small` deployment, the intended AGE operator flow is now:

1. start the stack with:
   - `docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build`
   - or use the equivalent `envrcctl exec -- ...` form
2. let the default startup path do all of the following automatically:
   - apply the canonical PostgreSQL schema
   - ensure the `age` extension exists in the database
   - bootstrap the default AGE graph:
     - `ctxledger_memory`
3. confirm the application has AGE mode enabled:
   - `CTXLEDGER_DB_AGE_ENABLED=true`
   - `CTXLEDGER_DB_AGE_GRAPH_NAME=ctxledger_memory`
4. run `ctxledger age-graph-readiness`
5. inspect `/debug/runtime` if you want the current `age_prototype` payload
6. if summary graph details look absent or degraded, treat that as an
   observability/rebuild signal first rather than as proof that canonical
   summary retrieval is broken
6. use `ctxledger bootstrap-age-graph` only when you explicitly want to rebuild the current constrained graph contents

The first successful validation target for the default `small` deployment is
that the repository-owned PostgreSQL 17 image builds successfully and the
resulting environment can support:

- `CREATE EXTENSION age;`
- `LOAD 'age';`
- `CREATE EXTENSION vector;`

The second validation target is that the default `small` deployment remains
compatible with the current constrained prototype workflow:

- `ctxledger apply-schema`
- `ctxledger age-graph-readiness`
- `ctxledger bootstrap-age-graph`
- `/debug/runtime`

### Bootstrap the constrained AGE graph

If you want to exercise the constrained AGE prototype in a graph-enabled
environment, the default `small` stack now bootstraps the default graph
automatically during startup.

You can still use the explicit bootstrap command when you want to rebuild the
current constrained graph contents on demand:

```/dev/null/sh#L1-1
ctxledger bootstrap-age-graph
```

You can also override the database URL or graph name directly:

```/dev/null/sh#L1-3
ctxledger bootstrap-age-graph \
  --database-url postgresql://ctxledger:ctxledger@localhost:5432/ctxledger \
  --graph-name ctxledger_memory
```

For the Docker Compose local stack in this repository, the PostgreSQL container
is named `ctxledger-postgres`, but the in-network database host for service-to-
service access is `postgres`.

That means the most useful current Docker-oriented bootstrap patterns are:

From your host, against the published PostgreSQL port:

```/dev/null/sh#L1-3
export CTXLEDGER_DB_AGE_ENABLED=true
export CTXLEDGER_DB_AGE_GRAPH_NAME=ctxledger_memory
ctxledger bootstrap-age-graph --database-url postgresql://ctxledger:ctxledger@localhost:55432/ctxledger
```

From inside the running `ctxledger` service container:

```/dev/null/sh#L1-3
docker exec -it ctxledger-server-private \
  sh -lc 'export CTXLEDGER_DB_AGE_ENABLED=true CTXLEDGER_DB_AGE_GRAPH_NAME=ctxledger_memory && \
  ctxledger bootstrap-age-graph --database-url postgresql://ctxledger:ctxledger@postgres:5432/ctxledger'
```

A practical local Docker sequence is now:

1. start the default stack
2. let startup apply the canonical schema and bootstrap the default AGE graph
3. run `ctxledger age-graph-readiness`
4. only use `ctxledger bootstrap-age-graph` when you want to rebuild the graph intentionally

Current bootstrap behavior is intentionally prototype-grade and constrained. It:

- loads AGE
- creates the named graph if needed
- clears the currently managed prototype graph contents
- repopulates:
  - `memory_item` nodes from canonical `memory_items`
  - `supports` edges from canonical `memory_relations`
- reports a success message of the form:
  - `AGE graph bootstrap completed for 'ctxledger_memory' (memory_item nodes repopulated=123, supports edges repopulated=45).`

Those counts should be read as a lightweight verification summary for the current
bootstrap run.

For the current constrained prototype, the most useful observability routes are:

- `/debug/runtime`
  - includes the `age_prototype` payload with enablement, graph name, AGE
    availability, and graph-readiness status
- `/debug/routes`
  - confirms the currently exposed runtime routes
- `/debug/tools`
  - confirms the currently exposed runtime tools surface

For a fuller operator-facing validation flow that combines readiness checks,
bootstrap counts, and runtime introspection, see:

- `docs/memory/age_prototype_validation_runbook.md`

For a reusable fill-in template for recording one validation pass, see:

- `docs/memory/age_prototype_validation_observation_template.md`

For the planned optional AGE-capable Docker/dev path needed for real graph-enabled
local validation, see:

- `docs/memory/age_docker_provisioning_plan.md`

For the image-selection decision that should precede that provisioning path, see:

- `docs/memory/age_image_selection_note.md`
- `docs/memory/age_image_selection_decision.md`

This means the current command should be read as a rebuild-oriented bootstrap
step for the constrained prototype graph, not as an incremental synchronization
path.

Important current limitations:

- this is not yet a full graph administration framework
- graph population is currently rebuild-first rather than incremental
- the prototype should still be read as an internal, optional graph-backed path
  rather than broad graph adoption

---


Representative Zed config:

```/dev/null/json#L1-8
{
  "ctxledger": {
    "url": "https://localhost:8443/mcp",
    "headers": {
      "Authorization": "Bearer YOUR_TOKEN_HERE"
    }
  }
}
```

Replace `YOUR_TOKEN_HERE` with the actual local auth token.

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
