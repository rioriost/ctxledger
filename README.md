# ctxledger

Durable Workflow Runtime and Multi-Layer Memory for AI Agents.

`ctxledger` is a remote MCP server that provides:

- durable workflow control
- multi-layer agent memory
- PostgreSQL-backed persistence
- a minimal HTTP MCP surface at `/mcp`
- Docker-based deployment

For `v0.1.0`, the repository now evidences a minimal HTTP MCP path over `/mcp` for:

- `initialize`
- `tools/list`
- `tools/call`

The release remains HTTP-first.  
Broader protocol-scope claims beyond that minimal path should be treated carefully until they are explicitly verified and documented.

---

## Overview

`ctxledger` is designed for AI-agent development workflows that must survive:

- process restarts
- cross-session continuation
- long-running task execution
- verification and checkpointing
- future memory-based recall and retrieval

The system is built on a simple architectural principle:

- **canonical state lives in PostgreSQL**
- repository files such as `.agent/resume.json` are **derived projections**
- MCP is the **public interface**
- workflow control and memory retrieval are **separate subsystems**

Near-term roadmap emphasis is also important to read correctly:

- `0.4.0` is intended to focus on operator-facing observability
  - CLI inspection/reporting for workflow and memory state
  - optional deployable Grafana-based dashboard support
- broader hierarchical memory retrieval is planned later in `0.5.0`

Current observability surfaces now include:

- CLI:
  - `ctxledger stats`
  - `ctxledger workflows`
  - `ctxledger memory-stats`
  - `ctxledger failures`
- optional Grafana dashboard deployment:
  - runtime overview
  - memory overview
  - failure overview

In `v0.1.0`, the primary focus is the durable workflow control layer.

---

## Prerequisites

Before you start `ctxledger`, prepare the following:

- Docker and Docker Compose
- a local network port available for:
  - PostgreSQL on `5432`
  - Traefik HTTPS entrypoint on `8443`
- an MCP client that can connect to a remote MCP server over HTTPS, such as:
  - VS Code
  - Zed

For the recommended local path, you do **not** need to install PostgreSQL separately.  
The provided Docker Compose setup starts PostgreSQL plus the proxy-protected `ctxledger` deployment for you.

If you already have durable local history in PostgreSQL, note that the repository’s PostgreSQL integration tests are intended to avoid mutating that existing working history directly.  
The current integration-test approach uses a temporary PostgreSQL schema per test run, applies the bundled schema there, and drops that temporary schema afterward instead of truncating long-lived tables in `public`.

You should also know the current local MCP endpoint exposed for operator use:

```/dev/null/txt#L1-1
https://localhost:8443/mcp
```

If you want to use authenticated access, prepare a bearer token for the proxy layer and use the small-pattern Traefik/auth deployment described below.

---

## Quick Start

The repository supports two HTTPS-based local startup paths for operator testing with clients such as Zed:

- **A. start `ctxledger` without authentication over HTTPS** on port `8444`
- **B. start `ctxledger` with proxy authentication over HTTPS** on port `8443`

Both paths require local certificate files for Traefik at:

- `docker/traefik/certs/localhost.crt`
- `docker/traefik/certs/localhost.key`

For the verified working local path with Zed on macOS, use `mkcert` so the `localhost` certificate is trusted by the local machine. A practical local setup is:

```/dev/null/sh#L1-3
mkdir -p docker/traefik/certs
mkcert -install
mkcert -cert-file docker/traefik/certs/localhost.crt -key-file docker/traefik/certs/localhost.key localhost 127.0.0.1 ::1
```

### A. Start `ctxledger` without authentication over HTTPS

Use this mode when you want the simplest HTTPS path for local Zed testing without proxy-side auth.

#### 1. Start the no-auth HTTPS stack

From the repository root, start the base compose file plus the no-auth HTTPS overlay:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.https-no-auth.yml up -d --build --force-recreate
```

For a normal restart after the stack already exists, you can usually omit `--force-recreate`:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.https-no-auth.yml up -d
```

#### 2. Access the HTTPS MCP endpoint
After startup, the HTTPS MCP endpoint is:

```/dev/null/txt#L1-1
https://localhost:8444/mcp
```

If the certificate is self-signed or otherwise not trusted by your machine, local validation commands may need an insecure mode.

#### 3. Optional validation

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://localhost:8444 --scenario workflow --workflow-resource-read
```

#### 4. Configure Zed

```/dev/null/json#L1-6
{
  "ctxledger": {
    "url": "https://localhost:8444/mcp"
  }
}
```

This no-auth HTTPS path was verified against a trusted `mkcert`-generated `localhost` certificate.

### B. Start `ctxledger` with authentication (recommended)

Use this mode when you want the documented proxy-first deployment shape for local development, operator validation, and IDE clients that can send bearer headers.

Run either A or B as a local stack, not both at the same time.

#### 1. Choose a bearer token

You will use the same token in all three places:

- as `CTXLEDGER_SMALL_AUTH_TOKEN` in the startup command
- as the bearer token passed to smoke validation commands
- as the `Authorization: Bearer ...` header in your MCP client configuration

A practical shell pattern is:

```/dev/null/sh#L1-2
export CTXLEDGER_SMALL_AUTH_TOKEN="$(openssl rand -hex 32)"
echo "$CTXLEDGER_SMALL_AUTH_TOKEN"
```

#### 2. Start the auth-enabled HTTPS stack

From the repository root, start the base compose file plus the auth overlay with a shared bearer token.

For a **first start** or a deliberate clean rebuild of the stack, use:

```/dev/null/sh#L1-1
CTXLEDGER_SMALL_AUTH_TOKEN=replace-me-with-a-strong-secret docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build --force-recreate
```

For a **normal restart after the stack has already been created**, you usually do **not** need `--force-recreate`:

```/dev/null/sh#L1-1
CTXLEDGER_SMALL_AUTH_TOKEN=replace-me-with-a-strong-secret docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d
```

If you exported `CTXLEDGER_SMALL_AUTH_TOKEN` in your shell first, you can also run:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d
```

#### 3. Access the authenticated HTTPS MCP endpoint

```/dev/null/txt#L1-1
https://127.0.0.1:8443/mcp
```

Every MCP client request to this endpoint must include the same bearer token you chose above.

#### 4. Optional validation

Missing token should be rejected with `401`:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://localhost:8443 --expect-http-status 401 --expect-auth-failure
```

A valid token should pass and the workflow/resource smoke should succeed:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://localhost:8443 --bearer-token "$CTXLEDGER_SMALL_AUTH_TOKEN" --scenario workflow --workflow-resource-read
```

#### 5. Configure Zed

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

Unfortunately, Zed does not expand environment variables in its MCP configuration file, so `YOUR_TOKEN_HERE` must be replaced with the actual token value.

When using the HTTPS local path, keep the same bearer token header and ensure the client trusts the local certificate chain or is explicitly configured for local self-signed testing.

#### Optional: use `envrcctl` to manage the token

If you use [`envrcctl`](https://github.com/rioriost/homebrew-envrcctl), you can store the token as a managed secret:

```/dev/null/sh#L1-1
echo -n "$(openssl rand -hex 32)" | envrcctl secret set CTXLEDGER_SMALL_AUTH_TOKEN --account 'ctxledger' --stdin
```

You can then run startup and validation commands with the secret injected into the environment.

For a first start or forced clean rebuild:

```/dev/null/sh#L1-1
envrcctl exec -- docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build --force-recreate
```

For a normal restart of an existing stack:

```/dev/null/sh#L1-1
envrcctl exec -- docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d
```

Because Zed does not expand environment variables in its MCP configuration file, you must still retrieve the token and paste it into `YOUR_TOKEN_HERE` manually:

```/dev/null/sh#L1-1
envrcctl secret get CTXLEDGER_SMALL_AUTH_TOKEN
```

### Optional Grafana observability startup

The repository now also includes an optional Grafana overlay for read-only dashboard observability over canonical PostgreSQL state.

Important design expectations:

- Grafana is optional
- Grafana is read-only
- Grafana reads PostgreSQL directly
- Grafana should use a dedicated read-only PostgreSQL role
- Grafana should query `observability` schema views rather than broad raw-table access
- Grafana does **not** depend on shelling out to the CLI observability commands

#### 1. Apply observability SQL views

Before starting Grafana, apply the observability SQL bootstrap:

```/dev/null/sh#L1-1
docker exec -i ctxledger-postgres psql -U ctxledger -d ctxledger < docs/sql/observability_views.sql
```

This creates:

- `observability` schema
- workflow overview views
- memory overview views
- projection failure views
- activity timeline view

#### 2. Create a read-only PostgreSQL role for Grafana

Create a dedicated role such as `ctxledger_grafana` and grant it:

- `CONNECT` on database `ctxledger`
- `USAGE` on schema `observability`
- `SELECT` on observability views

A concrete example is documented in:

- `docs/deployment.md`
- `docs/grafana_operator_runbook.md`
- `docs/sql/observability_views.sql` (commented example)

#### 3. Set Grafana-related environment variables

When using `envrcctl`, a practical local setup is:

```/dev/null/sh#L1-4
echo -n "admin" | envrcctl secret set CTXLEDGER_GRAFANA_ADMIN_USER --account 'ctxledger' --stdin
echo -n "replace-with-a-strong-admin-password" | envrcctl secret set CTXLEDGER_GRAFANA_ADMIN_PASSWORD --account 'ctxledger' --stdin
echo -n "ctxledger_grafana" | envrcctl secret set CTXLEDGER_GRAFANA_POSTGRES_USER --account 'ctxledger' --stdin
echo -n "replace-with-a-strong-secret" | envrcctl secret set CTXLEDGER_GRAFANA_POSTGRES_PASSWORD --account 'ctxledger' --stdin
```

You may also want to set optional values such as:

- `CTXLEDGER_GRAFANA_ROOT_URL`
- `CTXLEDGER_GRAFANA_DOMAIN`
- `CTXLEDGER_GRAFANA_POSTGRES_HOST`
- `CTXLEDGER_GRAFANA_POSTGRES_DB`
- `CTXLEDGER_GRAFANA_POSTGRES_SSLMODE`

For the local Docker path, defaults are normally sufficient for:

- host: `postgres:5432`
- db: `ctxledger`
- sslmode: `disable`

#### 4. Start the stack with the Grafana overlay

If you are already using the authenticated local HTTPS stack, start Grafana by adding the observability overlay:

```/dev/null/sh#L1-1
envrcctl exec -- docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml -f docker/docker-compose.observability.yml up -d --build
```

If you are using the HTTPS no-auth stack instead, the same pattern applies:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.https-no-auth.yml -f docker/docker-compose.observability.yml up -d --build
```

For a forced recreate of the auth-enabled path:

```/dev/null/sh#L1-1
envrcctl exec -- docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml -f docker/docker-compose.observability.yml up -d --build --force-recreate
```

#### 5. Access Grafana

Grafana is exposed locally at:

```/dev/null/txt#L1-1
http://localhost:3000
```

Use the admin credentials provided through the Grafana environment variables above.

#### 6. What should appear

Provisioning should create:

- datasource:
  - `ctxledger-postgres`
- dashboard folder:
  - `ctxledger`

Initial dashboards currently included:

- `ctxledger Runtime Overview`
- `ctxledger Memory Overview`
- `ctxledger Failure Overview`

#### 7. Verify dashboard data

Useful cross-checks:

```/dev/null/sh#L1-3
ctxledger stats
ctxledger memory-stats
ctxledger failures --limit 10
```

Representative expected behavior:

- Runtime dashboard reflects canonical workflow counts and recent activity
- Memory dashboard reflects:
  - episode count
  - memory item count
  - memory embedding count
  - memory relation count
  - provenance breakdown
- Failure dashboard reflects:
  - open / resolved / ignored projection failures
  - recent failure rows
  - failure timeline

For deeper operational guidance, troubleshooting, and security notes, see:

- `docs/grafana_operator_runbook.md`
- `docs/deployment.md`

### Agent workflow usage guidance

If your MCP client hosts an AI agent that follows repository instructions such as `.rules`, you should make workflow tracking part of the agent's normal work loop.

Recommended agent behavior:

- at session start:
  - read `last_session.md`
  - register or confirm the current repository workspace
  - resume the current workflow when continuing existing work
  - start a new workflow when beginning a new task
- during work:
  - record meaningful progress checkpoints after planning, code changes, test updates, and validation/debugging milestones
  - treat `workflow_complete` as a terminal transition, not as a general progress-save operation
  - if more work may still occur in the current work loop, prefer another checkpoint and delay `workflow_complete` until the work is truly done
- at session close or task completion:
  - update `last_session.md`
  - complete the workflow
  - keep resume projections current when they are part of the operating flow

Important workflow lifecycle notes:

- terminal workflow states include `completed`, `failed`, and `cancelled`
- once a workflow is terminal, do not attempt to add more checkpoints to it
- terminal workflows should be inspected, not continued as active work
- if new work appears after a workflow has already become terminal, start a new workflow instead of trying to continue the closed one

For reliable handoff between agent sessions, it is also helpful to keep the current `workspace_id`, `workflow_instance_id`, `attempt_id`, and `ticket_id` in `last_session.md` when they are available.

---

## Current Scope (`v0.1.0`)

The initial release is centered on the workflow kernel, while the memory layer has begun to take shape in a limited but real form.

### Implemented / targeted first
- workspace registration
- workflow start
- workflow checkpoint
- workflow resume
- workflow completion / termination
- PostgreSQL-backed canonical state
- Docker-based local deployment
- structured configuration and startup validation
- health / readiness foundations

### Memory status in the current repository
- `memory_remember_episode` is implemented for append-only episodic recording
  - `attempt_id` is now persisted canonically with the episode record when provided
  - memory-item embeddings may also be generated and stored during episode persistence when embedding storage is configured and enabled
- `memory_get_context` is partially implemented as an episode-oriented retrieval path
  - direct `workflow_instance_id` lookup is supported
  - workflow lookup by `workspace_id` is supported
  - workflow lookup by `ticket_id` is supported
  - `include_episodes=false` is supported
  - `limit` is supported
  - initial lightweight query filtering over episode summary and explicit metadata fields is supported
  - broader retrieval behavior remains early-stage
- `memory_search` is implemented as an initial hybrid lexical and embedding-backed retrieval surface over stored memory items
- semantic memory and embedding-backed retrieval are now present in an initial form
- hierarchical summaries and relation-aware retrieval remain future work

---

## Architecture Summary

At a high level, `ctxledger` is composed of:

- **MCP transport layer**
  - HTTP MCP surface at `/mcp`
- **application services**
  - workflow orchestration
  - resource assembly
  - error normalization
- **PostgreSQL persistence**
  - canonical workflow state
  - verification records
  - projection diagnostics
  - future memory records
- **repository projections**
  - `.agent/resume.json`
  - `.agent/resume.md`

Projection failure lifecycle is tracked canonically as operational metadata, including:

- `open`
- `resolved`
- `ignored`

Repeated failures remain visible as repeated operational events, and `retry_count` distinguishes first failure from subsequent unresolved failures for the same projection stream.

The resume read side now distinguishes:

- open projection failures
- closed projection failures
- warning-level visibility for ignored versus resolved closure

Resume consumers can inspect:

- open failures through projection warning details
- closed failure history through `closed_projection_failures`
- dedicated HTTP history endpoint:
  - `/workflow-resume/{workflow_instance_id}/closed-projection-failures`
- lifecycle-specific warning codes:
  - `open_projection_failure`
  - `ignored_projection_failure`
  - `resolved_projection_failure`

Closed projection failure details may include:

- `projection_type`
- `target_path`
- `attempt_id`
- `error_code`
- `error_message`
- `occurred_at`
- `resolved_at`
- `open_failure_count`
- `retry_count`
- `status`

For detailed design, see:

- `docs/architecture.md`
- `docs/workflow-model.md`
- `docs/mcp-api.md`
- `docs/deployment.md`
- `docs/memory-model.md`
- `docs/specification.md`

---

## Repository Layout

Typical top-level structure:

- `src/ctxledger`
  - application code
- `schemas/postgres.sql`
  - bootstrap schema
- `docker/docker-compose.yml`
  - local deployment scaffold
- `docs/`
  - architecture and design documentation

---

## MCP Surface

### Primary HTTP MCP surface

For `v0.1.0`, the primary MCP acceptance surface is HTTP at:

- `/mcp`

The currently evidenced minimal HTTP MCP path includes:

- `initialize`
- `tools/list`
- `tools/call`

This means repository evidence now supports the claim that a remote MCP client can reach `/mcp` and perform basic MCP session setup, tool discovery, and tool invocation over HTTP.

Acceptance-boundary note for `v0.1.0`:

- the minimal confirmed HTTP MCP path is:
  - `initialize`
  - `tools/list`
  - `tools/call`
- this minimal path should be treated as the strongest current release evidence surface
- broader MCP coverage, such as additional resource-oriented protocol proof, should be treated as a separate closeout question rather than implied by this minimal confirmed path

### Workflow tools
- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_resume`
- `workflow_complete`
  - can auto-create workflow closeout memory when sufficient summary/checkpoint signal exists
  - returns auto-memory outcome details through `auto_memory_details`
  - current closeout duplicate suppression rejects exact duplicates and suppresses near-duplicates only within the same workflow and matching `step_name`, using workflow-local, metadata-aware matching plus weighted similarity over extracted summary fields

Tool argument discovery is available through `tools/list`, and visible tools expose a concrete `inputSchema`.

For example, `workspace_register` exposes:

- required:
  - `repo_url`
  - `canonical_path`
  - `default_branch`
- optional:
  - `workspace_id`
  - `metadata`

This allows MCP clients to discover valid arguments before calling the tool instead of relying on runtime validation errors.

At present, the strongest repository evidence is for the minimal HTTP MCP flow itself plus the concrete tool schema surface.  
If stricter protocol-coverage claims are needed for release closeout, they should be stated separately from this minimal confirmed path.

In other words, the current README should be read as claiming:

- confirmed HTTP MCP initialization
- confirmed HTTP MCP tool discovery
- confirmed HTTP MCP tool invocation

It should not be read as silently claiming full MCP surface completeness beyond what is explicitly evidenced.

### Memory tools
- `memory_remember_episode`
- `memory_search`
- `memory_get_context`

Current implementation status:

- `memory_remember_episode`
  - implemented
  - validates `workflow_instance_id`
  - optionally validates `attempt_id`
  - verifies workflow existence before recording
  - records append-only episode entries
  - persists `attempt_id` canonically when present
- `memory_get_context`
  - partially implemented
  - currently returns episode-oriented context
  - supports direct retrieval by `workflow_instance_id`
  - supports lookup expansion by `workspace_id`
  - supports lookup expansion by `ticket_id`
  - supports `limit`
  - supports `include_episodes`
  - supports initial lightweight query filtering against episode summary and explicit metadata fields
  - broader relevance-based, semantic, summary, and multi-layer retrieval is not implemented yet
- `memory_search`
  - implemented as an initial hybrid lexical and embedding-backed retrieval surface over stored memory items
  - currently supports workspace-scoped search, result limits, and optional structured filters
  - returns lexical score, semantic score, and ranking explanation details for each result
  - falls back to lexical-only behavior when embedding generation or semantic lookup is unavailable
  - validated embedding execution paths now include `openai` in addition to `local_stub` and `custom_http`
  - PostgreSQL-backed vector retrieval now defaults to an HNSW index over stored embeddings
  - workflow completion can now auto-create closeout memory that becomes part of the searchable corpus
  - because HNSW indexes are updated incrementally as new embeddings are inserted, normal writes do not require a separate indexing job, but long-running deployments may still benefit from occasional reindex/rebuild maintenance after substantial growth or distribution drift
  - broader provider-specific integrations and richer multi-layer retrieval remain follow-up work

The intended staged roadmap is still:

- `0.2`: episodic memory, with `memory_remember_episode` implemented and `memory_get_context` now providing an initial episode-oriented form
- `0.3`: semantic search, with `memory_search` now implemented as the primary tool fit and `memory_get_context` still a candidate for stronger relevance-based retrieval over time
- `0.4`: hierarchical memory retrieval, where `memory_get_context` may evolve into a more multi-layer context assembly surface

This is a roadmap-oriented interpretation of the current architecture and planning documents, not a guarantee that every memory tool will be fully complete at the start of its corresponding version.

### Working `0.2.0` memory closeout criteria
The repository should treat `0.2.0` memory closeout as satisfied only when the following are true:

- `memory_remember_episode` is implemented and stores episode records durably in PostgreSQL
- `attempt_id` is canonically persisted on episodes when provided
- `memory_get_context` remains implemented as an episode-oriented retrieval path, not as a stub
- `memory_get_context` supports workflow-linked retrieval through:
  - `workflow_instance_id`
  - `workspace_id`
  - `ticket_id`
- `memory_get_context` supports:
  - `limit`
  - `include_episodes`
  - initial query-aware filtering over episode summary and explicit metadata fields
- `memory_get_context` returns enough response details to explain how context was assembled, including at least:
  - `lookup_scope`
  - `resolved_workflow_count`
  - `resolved_workflow_ids`
  - `query_filter_applied`
  - `episodes_before_query_filter`
  - `matched_episode_count`
  - `episodes_returned`
- unit and PostgreSQL-backed integration coverage exist for the implemented episodic capture and context retrieval paths
- docs clearly distinguish:
  - implemented episodic memory behavior
  - partially implemented context retrieval behavior
  - the earlier `0.2.0` scope boundary where `memory_search` was still stubbed
- semantic retrieval, embeddings, relations, and hierarchical summaries remained explicitly out of scope for `0.2.0` at that time
- TLS / HTTPS deployment work may proceed as part of the broader `0.2.0` stream, but only after the memory-focused closeout work is considered sufficiently complete
- later roadmap framing should continue to distinguish:
  - `0.4.0` observability-oriented operator surfaces
  - `0.5.0` hierarchical memory retrieval expansion

### Workflow HTTP read endpoints
- `/workflow-resume/{workflow_instance_id}`
- `/workflow-resume/{workflow_instance_id}/closed-projection-failures`

The dedicated closed projection failure history endpoint returns:

- `workflow_instance_id`
- `closed_projection_failures`

Each `closed_projection_failures` entry includes:

- `projection_type`
- `target_path`
- `attempt_id`
- `error_code`
- `error_message`
- `occurred_at`
- `resolved_at`
- `open_failure_count`
- `retry_count`
- `status`

### Resources
- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`
- `memory://episode/{episode_id}`
- `memory://summary/{scope}`

### Runtime debug endpoints
- `/debug/runtime`
- `/debug/routes`
- `/debug/tools`

These HTTP debug endpoints expose the currently wired runtime surface.

Typical intent:

- `/debug/runtime` returns transport-level route/tool summary
- `/debug/routes` returns HTTP route registrations only
- `/debug/tools` returns MCP tool registrations only

These endpoints are operational/debug surfaces.  
They should not be treated as equivalent to the MCP protocol surface itself.

For MCP usage, the primary machine-readable source of tool argument requirements is `tools/list` on `/mcp`, not the HTTP debug endpoints above.

Typical payload shapes:

```/dev/null/json#L1-17
{
  "runtime": [
    {
      "transport": "http",
      "routes": [
        "mcp_rpc",
        "runtime_introspection",
        "runtime_routes",
        "runtime_tools",
        "workflow_resume",
        "workflow_closed_projection_failures"
      ],
      "tools": [],
      "resources": []
    }
  ]
}
```

```/dev/null/json#L1-18
{
  "routes": [
    {
      "transport": "http",
      "routes": [
        "runtime_introspection",
        "runtime_routes",
        "runtime_tools",
        "workflow_resume",
        "workflow_closed_projection_failures"
      ]
    }
  ]
}
```

```/dev/null/json#L1-5
{
  "tools": []
}
```

---


## Workflow Model Highlights

`ctxledger` separates:

- planning identity
- execution identity
- operational attempts
- resumable snapshots

The workflow resume contract also surfaces projection lifecycle diagnostics as part of resumable state assembly, including both unresolved open failures and closed failure history.

Core workflow entities:

- `workspace`
- `workflow_instance`
- `workflow_attempt`
- `workflow_checkpoint`
- `verify_report`

### Workflow instance states
- `running`
- `completed`
- `failed`
- `cancelled`

### Workflow attempt states
- `running`
- `succeeded`
- `failed`
- `cancelled`

### Checkpoints
Checkpoints are designed as **resume snapshots**, not just log entries.

They are intended to preserve enough structured state for safe continuation after restart.

---

## Canonical State vs Projection Files

A key design rule is:

- PostgreSQL is the system of record
- repository projection files are derived artifacts

Examples of projections:

- `.agent/resume.json`
- `.agent/resume.md`

Projection failures or staleness should never redefine truth.  
Canonical workflow state must still be reconstructed from PostgreSQL.

### Projection failure lifecycle summary

Projection failure lifecycle is distinct from projection freshness status.

Representative lifecycle states:

- `open`
- `resolved`
- `ignored`

Important distinctions:

- projection status such as `failed` describes the artifact state
- failure lifecycle state describes whether projection failure records are still open
- `ignored` is not the same as successful projection recovery
- repeated failures remain visible as repeated operational events

Representative retry behavior:

- first open failure for a projection stream: `retry_count = 0`
- second consecutive open failure for the same projection stream: `retry_count = 1`

Representative resolution timing behavior:

- `resolved_at` is unset while a failure remains `open`
- `resolved_at` is set when a failure transitions to either `resolved` or `ignored`
- `resolved_at` records when the failure stopped being open; it does not by itself mean the projection artifact became `fresh`

Representative warning behavior:

- `open projection failure` is emitted only when open projection failures exist
- `ignored projection failure` may be emitted when a projection remains `failed` but its failure records are no longer open
- `projection.status = failed` by itself does not necessarily imply an unresolved open failure
- a projection may remain `failed` even when `open_failure_count = 0`

---

## Requirements

At a minimum, you need:

- Python 3.14+
- PostgreSQL
- Docker and Docker Compose for the recommended local setup
- `pgvector` support in PostgreSQL

Project metadata is defined in `pyproject.toml`.

---

## Configuration

`ctxledger` uses startup-validated configuration.

Important environment variables include:

- `CTXLEDGER_DATABASE_URL`
- `CTXLEDGER_DB_SCHEMA_NAME`
- `CTXLEDGER_TRANSPORT`
- `CTXLEDGER_ENABLE_HTTP`

- `CTXLEDGER_HOST`
- `CTXLEDGER_PORT`
- `CTXLEDGER_HTTP_PATH`
- `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS`
- `CTXLEDGER_PROJECTION_ENABLED`
- `CTXLEDGER_PROJECTION_DIRECTORY`
- `CTXLEDGER_PROJECTION_WRITE_JSON`
- `CTXLEDGER_PROJECTION_WRITE_MARKDOWN`
- `CTXLEDGER_LOG_LEVEL`
- `CTXLEDGER_LOG_STRUCTURED`

### Configuration notes

- `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS=false` removes `/debug/*` routes from the HTTP runtime entirely
- for internet-exposed production deployments, prefer:
  - proxy-layer authentication in front of `ctxledger`
  - `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS=false`

### Typical local example

See `./.env.example` for a committed local-development configuration template.

```/dev/null/.env.example#L1-12
CTXLEDGER_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ctxledger
CTXLEDGER_DB_SCHEMA_NAME=public
CTXLEDGER_TRANSPORT=http
CTXLEDGER_ENABLE_HTTP=true
CTXLEDGER_HOST=0.0.0.0
CTXLEDGER_PORT=8080
CTXLEDGER_HTTP_PATH=/mcp
CTXLEDGER_ENABLE_DEBUG_ENDPOINTS=true
CTXLEDGER_PROJECTION_ENABLED=true
CTXLEDGER_PROJECTION_DIRECTORY=.agent
CTXLEDGER_PROJECTION_WRITE_JSON=true
CTXLEDGER_PROJECTION_WRITE_MARKDOWN=true
CTXLEDGER_LOG_LEVEL=info
```

### Production-like example

See `./.env.production.example` for a committed production-oriented configuration template.

```/dev/null/.env.production.example#L1-14
CTXLEDGER_DATABASE_URL=postgresql://ctxledger:replace-me@db.internal:5432/ctxledger
CTXLEDGER_DB_SCHEMA_NAME=public
CTXLEDGER_TRANSPORT=http
CTXLEDGER_ENABLE_HTTP=true
CTXLEDGER_HOST=0.0.0.0
CTXLEDGER_PORT=8080
CTXLEDGER_HTTP_PATH=/mcp
CTXLEDGER_ENABLE_DEBUG_ENDPOINTS=false
CTXLEDGER_PROJECTION_ENABLED=true
CTXLEDGER_PROJECTION_DIRECTORY=.agent
CTXLEDGER_PROJECTION_WRITE_JSON=true
CTXLEDGER_PROJECTION_WRITE_MARKDOWN=true
CTXLEDGER_LOG_LEVEL=info
```

In production-like environments, also prefer TLS termination and reverse-proxy access in front of the HTTP service, with authentication enforced at the proxy layer rather than inside `ctxledger`.

`CTXLEDGER_DB_SCHEMA_NAME` defaults to `public`, which is the normal runtime choice. It can also be set explicitly when you need to target a different PostgreSQL schema, such as an isolated temporary schema for persistence integration tests.

---

## Local Startup

The recommended local path is Docker-based and HTTPS-oriented.

On successful startup, `ctxledger` also prints a short runtime summary to stderr so you can quickly verify the active transport wiring.

### Docker Compose

#### A. HTTPS startup without authentication

Use this when you want the simplest HTTPS path for local client testing without proxy-side auth.

##### 1. Prepare local TLS certificate files

Before starting the stack, create certificate material for Traefik if you do not already have it.

A practical local option is `mkcert`:

```/dev/null/sh#L1-2
mkdir -p docker/traefik/certs
mkcert -cert-file docker/traefik/certs/localhost.crt -key-file docker/traefik/certs/localhost.key localhost 127.0.0.1 ::1
```

##### 2. Start PostgreSQL, the backend, and the HTTPS no-auth proxy

From the repository root:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.https-no-auth.yml up -d --build --force-recreate
```

For a normal restart after the stack has already been created:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.https-no-auth.yml up -d
```

##### 3. Verify endpoint availability

Expected local MCP endpoint:

```/dev/null/txt#L1-1
https://127.0.0.1:8444/mcp
```

This path is HTTPS-only through Traefik and does not require an auth header.

##### 4. Run the minimum MCP smoke validation

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://127.0.0.1:8444 --tool-name memory_get_context --insecure
```

##### 5. Run workflow and resource-read validation

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://127.0.0.1:8444 --scenario workflow --workflow-resource-read --insecure
```

##### 6. Configure Zed for the no-auth HTTPS endpoint

A representative Zed MCP configuration shape is:

```/dev/null/json#L1-6
{
  "ctxledger": {
    "url": "https://127.0.0.1:8444/mcp"
  }
}
```

If your local certificate is not trusted by the client environment, use a trusted local certificate chain before testing from Zed.

#### B. HTTPS startup with authentication (recommended)

Use this when you want the documented proxy-first deployment shape for local development, operator validation, and IDE clients that can send bearer headers.

Before you start this mode, choose a bearer token value. You will use the same token in all three places:

- as `CTXLEDGER_SMALL_AUTH_TOKEN` in the startup command
- as the bearer token passed to smoke validation commands
- as the `Authorization: Bearer ...` header in your MCP client configuration

If these values do not match exactly, authenticated requests will fail with `401`.

For local experiments, the examples below use:

```/dev/null/txt#L1-1
replace-me-with-a-strong-secret
```

To generate a stronger token, you can use either of these examples:

```/dev/null/sh#L1-1
openssl rand -hex 32
```

```/dev/null/sh#L1-1
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

A practical shell pattern is:

```/dev/null/sh#L1-2
export CTXLEDGER_SMALL_AUTH_TOKEN="$(openssl rand -hex 32)"
echo "$CTXLEDGER_SMALL_AUTH_TOKEN"
```

For any shared, persistent, or less-trusted environment, use a strong random secret instead of the example placeholder.

##### 1. Prepare local TLS certificate files

Before starting the stack, create certificate material for Traefik if you do not already have it.

A practical local option is `mkcert`:

```/dev/null/sh#L1-2
mkdir -p docker/traefik/certs
mkcert -cert-file docker/traefik/certs/localhost.crt -key-file docker/traefik/certs/localhost.key localhost 127.0.0.1 ::1
```

##### 2. Start PostgreSQL, the private backend, auth service, and Traefik

From the repository root, start the base compose file plus the auth overlay with a shared bearer token.

For a **first start** or a deliberate clean rebuild of the stack, use:

```/dev/null/sh#L1-1
CTXLEDGER_SMALL_AUTH_TOKEN=replace-me-with-a-strong-secret docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build --force-recreate
```

For a **normal restart after the stack has already been created**, you usually do **not** need `--force-recreate`:

```/dev/null/sh#L1-1
CTXLEDGER_SMALL_AUTH_TOKEN=replace-me-with-a-strong-secret docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d
```

If you exported `CTXLEDGER_SMALL_AUTH_TOKEN` in your shell first, you can also run:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d
```

If you changed code or image inputs and want a normal rebuild without forcibly replacing every container, use:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build
```

Use `--force-recreate` only when you intentionally want to replace existing containers, such as after a major compose/config change or when you want a known-fresh container set.

##### 3. Verify endpoint availability

Expected local MCP endpoint:

```/dev/null/txt#L1-1
https://localhost:8443/mcp
```

Every MCP client request to this endpoint must include the same bearer token you chose above.

##### 4. Verify authentication behavior

First, confirm that requests without a token are rejected. This shows that proxy-side authentication is actually active.

Missing token should be rejected with `401`:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://127.0.0.1:8443 --expect-http-status 401 --expect-auth-failure --insecure
```

Then confirm that a request with the same token used at startup is accepted.

A valid token should pass and the workflow/resource smoke should succeed:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://127.0.0.1:8443 --bearer-token replace-me-with-a-strong-secret --scenario workflow --workflow-resource-read --insecure
```

If you exported `CTXLEDGER_SMALL_AUTH_TOKEN` already, you can keep the smoke command aligned with the startup token like this:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://127.0.0.1:8443 --bearer-token "$CTXLEDGER_SMALL_AUTH_TOKEN" --scenario workflow --workflow-resource-read --insecure
```

The `--insecure` flag is useful for local self-signed certificates. If your certificate is trusted locally, you can omit it.

##### 5. Configure Zed for the authenticated HTTPS endpoint

A representative Zed MCP configuration shape is:

```/dev/null/json#L1-11
{
  "ctxledger": {
    "url": "https://127.0.0.1:8443/mcp",
    "headers": {
         "Authorization": "Bearer YOUR_TOKEN_HERE"
    }
  }
}
```

Unfortunately, Zed does not expand environment variables in its MCP configuration file, so `YOUR_TOKEN_HERE` must be replaced with the actual token value.

When using the HTTPS local path, keep the same bearer token header and ensure the client trusts the local certificate chain or is explicitly configured for local self-signed testing.

#### Shut down the local stack

For the no-auth HTTPS stack:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.https-no-auth.yml down --remove-orphans
```

For the auth-enabled HTTPS stack:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml down --remove-orphans
```

### Container Image Notes

You can still build the application image directly from the repository root:

```/dev/null/sh#L1-1
docker build -t ctxledger:local .
```

However, the current recommended operator-facing deployment path is the HTTPS-terminated Traefik stack rather than direct host exposure of the backend application container.

If you use the image directly for advanced or internal-only experiments, treat that as a backend/runtime detail rather than the primary documented operator path.

### Option C: Python direct startup

If you are running from Python directly, the simplest current path is to run the FastAPI app with `uvicorn`:

```/dev/null/sh#L1-1
uvicorn ctxledger.http_app:app --host 0.0.0.0 --port 8080
```

The older CLI bootstrap path is still useful for package-level operations, but the FastAPI + `uvicorn` path is the current documented route for real remote HTTP MCP serving.

You can also inspect the schema path from the CLI:

```/dev/null/sh#L1-1
python -m ctxledger print-schema-path --absolute
```

---

## Schema Initialization

`ctxledger` is designed so that schema bootstrap/migration is an **explicit operational step**.

Use:

- `schemas/postgres.sql`

Apply it with your preferred PostgreSQL client after the database is up.

Example shape:

```/dev/null/sh#L1-1
psql postgresql://postgres:postgres@localhost:5432/ctxledger -f schemas/postgres.sql
```

---

## Health and Readiness

`ctxledger` distinguishes between:

- **liveness**
- **readiness**

### Liveness
The process is up.

### Readiness
The service is actually safe to handle workflow requests.

Readiness depends on at least:

- valid configuration
- PostgreSQL connectivity
- required schema availability

The service may still be degraded-but-ready if, for example:

- a projection is stale
- projection generation previously failed
- an open projection failure exists
- a projection remains failed after failure records were resolved or ignored
- embedding/indexing work is lagging

---

## Deployment Guidance

For local development, the recommended topology is:

- `postgres`
- `ctxledger`

For production-like environments, the recommended topology is:

- reverse proxy
- TLS termination
- proxy-layer authentication strategy
- `ctxledger`
- PostgreSQL with durable storage

### Important deployment rules
- PostgreSQL persistence is required
- schema changes should be explicit
- projection files are best-effort outputs
- canonical state must survive restarts
- readiness should be tied to DB and schema health

For deployment details, see `docs/deployment.md`.  
For security posture and exposure guidance, see `docs/SECURITY.md`.

---

## Security Notes

In `v0.1.0`, the primary formal security boundary is:

- proxy-layer bearer token authentication

Fine-grained authorization is intentionally deferred.

Recommended production posture:

- put the service behind a reverse proxy
- use TLS
- enforce authentication at the proxy layer for HTTP deployments that are not fully private
- provide proxy bearer tokens through environment variables or secret-management tooling
- set `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS=false` for internet-exposed production deployments unless operator access to `/debug/*` is explicitly required
- if `/debug/*` must remain enabled in production, keep it behind the same proxy auth boundary and restrict access to trusted operators
- do not hardcode credentials in repository files

---

## Development Status

This repository currently contains:

- architecture documentation
- workflow model documentation
- MCP API documentation
- a concrete PostgreSQL foundation schema
- initial Python service/config/bootstrap structure

The project is still in an early implementation phase, but the architectural direction is now aligned around:

- durable workflow control first
- memory subsystem expansion next
- derived retrieval/index layers later

---

## Suggested Development Flow

A practical development sequence is:

1. start PostgreSQL
2. apply `schemas/postgres.sql`
3. boot `ctxledger`
4. register a workspace
5. start a workflow
6. create a checkpoint
7. verify resume behavior
8. terminate the workflow
9. inspect projection behavior and diagnostics

This validates the core promise of the system:

- durable workflow state
- restart-safe continuation
- canonical PostgreSQL-backed recovery

---

## Documentation Index

Core docs:
- `docs/specification.md`
- `docs/architecture.md`
- `docs/workflow-model.md`
- `docs/mcp-api.md`
- `docs/memory-model.md`
- `docs/deployment.md`
- `docs/SECURITY.md`
- `docs/design-principles.md`
- `docs/roadmap.md`

Auth and deployment guidance:
- `docs/small_auth_operator_runbook.md`
- `docs/plans/auth_planning_index.md`
- `docs/plans/auth_proxy_scaling_plan.md`
- `docs/plans/auth_large_gateway_evaluation_memo.md`
- `docs/plans/auth_large_gateway_shortlist_example.md`
- `docs/CONTRIBUTING.md`

---

## License

See `LICENSE`.
