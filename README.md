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

In `v0.1.0`, the primary focus is the durable workflow control layer.

---

## Prerequisites

Before you start `ctxledger`, prepare the following:

- Docker and Docker Compose
- a local network port available for:
  - PostgreSQL on `5432`
  - `ctxledger` on `8080`
- an MCP client that can connect to a remote HTTP MCP server, such as:
  - VS Code
  - Zed

For the recommended local path, you do **not** need to install PostgreSQL separately.  
The provided Docker Compose setup starts both PostgreSQL and the `ctxledger` server for you.

You should also know the local MCP endpoint that the default Docker setup exposes:

```/dev/null/txt#L1-1
http://127.0.0.1:8080/mcp
```

If you want to use authenticated access later, also prepare a bearer token and use the authenticated Docker Compose override described below.

---

## Quick Start

### 1. Start `ctxledger` with Docker Compose

From the repository root, start PostgreSQL and the remote MCP server:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml up -d --build
```

After startup, the primary MCP endpoint is:

```/dev/null/txt#L1-1
http://127.0.0.1:8080/mcp
```

You can optionally verify that the local server is up by checking the runtime debug endpoint:

```/dev/null/sh#L1-1
curl http://127.0.0.1:8080/debug/runtime
```

### 2. Configure your MCP client to use `ctxledger`

#### VS Code

Add a remote MCP server entry in your VS Code MCP client configuration.

A representative configuration shape is:

```/dev/null/json#L1-8
{
  "mcpServers": {
    "ctxledger": {
      "url": "http://127.0.0.1:8080/mcp"
    }
  }
}
```

If you are using bearer authentication, include the same bearer token that the server expects. A representative authenticated shape is:

```/dev/null/json#L1-11
{
  "mcpServers": {
    "ctxledger": {
      "url": "http://127.0.0.1:8080/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN_HERE"
      }
    }
  }
}
```

#### Zed

Add a remote MCP server entry in your Zed MCP configuration.

A representative configuration shape is:

```/dev/null/json#L1-8
{
  "mcp_servers": {
    "ctxledger": {
      "url": "http://127.0.0.1:8080/mcp"
    }
  }
}
```

If bearer authentication is enabled, provide the token in the request headers. A representative authenticated shape is:

```/dev/null/json#L1-11
{
  "mcp_servers": {
    "ctxledger": {
      "url": "http://127.0.0.1:8080/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN_HERE"
      }
    }
  }
}
```

Once configured, your MCP client should be able to reach `ctxledger` as a remote HTTP MCP server and use the workflow and memory tool surfaces exposed at `/mcp`.

---

## Current Scope (`v0.1.0`)

The initial release is centered on the workflow kernel.

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

### Architecturally defined, but may still be partial or stubbed
- episodic memory
- semantic memory
- embedding-backed retrieval
- hierarchical summaries
- relation-aware memory retrieval

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

Some memory APIs may remain stubbed in `v0.1.0` while the workflow subsystem is completed first.

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
- `CTXLEDGER_TRANSPORT`
- `CTXLEDGER_ENABLE_HTTP`

- `CTXLEDGER_HOST`
- `CTXLEDGER_PORT`
- `CTXLEDGER_HTTP_PATH`
- `CTXLEDGER_REQUIRE_AUTH`
- `CTXLEDGER_AUTH_BEARER_TOKEN`
- `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS`
- `CTXLEDGER_PROJECTION_ENABLED`
- `CTXLEDGER_PROJECTION_DIRECTORY`
- `CTXLEDGER_PROJECTION_WRITE_JSON`
- `CTXLEDGER_PROJECTION_WRITE_MARKDOWN`
- `CTXLEDGER_LOG_LEVEL`
- `CTXLEDGER_LOG_STRUCTURED`

### Configuration notes

- `CTXLEDGER_REQUIRE_AUTH=true` enables bearer token authentication for protected HTTP endpoints
- `CTXLEDGER_AUTH_BEARER_TOKEN` is required when `CTXLEDGER_REQUIRE_AUTH=true`
- `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS=false` removes `/debug/*` routes from the HTTP runtime entirely
- when bearer auth is enabled, `/debug/*` follows the same authentication boundary as other protected HTTP endpoints
- for internet-exposed production deployments, prefer:
  - `CTXLEDGER_REQUIRE_AUTH=true`
  - `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS=false`

### Typical local example

See `./.env.example` for a committed local-development configuration template.

```/dev/null/.env.example#L1-12
CTXLEDGER_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ctxledger
CTXLEDGER_TRANSPORT=http
CTXLEDGER_ENABLE_HTTP=true
CTXLEDGER_HOST=0.0.0.0
CTXLEDGER_PORT=8080
CTXLEDGER_HTTP_PATH=/mcp
CTXLEDGER_REQUIRE_AUTH=false
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
CTXLEDGER_TRANSPORT=http
CTXLEDGER_ENABLE_HTTP=true
CTXLEDGER_HOST=0.0.0.0
CTXLEDGER_PORT=8080
CTXLEDGER_HTTP_PATH=/mcp
CTXLEDGER_REQUIRE_AUTH=true
CTXLEDGER_AUTH_BEARER_TOKEN=replace-me-with-a-strong-secret
CTXLEDGER_ENABLE_DEBUG_ENDPOINTS=false
CTXLEDGER_PROJECTION_ENABLED=true
CTXLEDGER_PROJECTION_DIRECTORY=.agent
CTXLEDGER_PROJECTION_WRITE_JSON=true
CTXLEDGER_PROJECTION_WRITE_MARKDOWN=true
CTXLEDGER_LOG_LEVEL=info
```

In production-like environments, also prefer TLS termination and reverse-proxy access in front of the HTTP service.

---

## Local Startup

The recommended local path is Docker-based.

On successful startup, `ctxledger` also prints a short runtime summary to stderr so you can quickly verify the active transport wiring.

### Option A: Docker Compose

#### 1. Start PostgreSQL and application services

From the repository root:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml up --build
```

#### 2. Verify endpoint availability

Expected local MCP endpoint:

```/dev/null/txt#L1-1
http://localhost:8080/mcp
```

The Docker Compose path now runs `ctxledger` as a FastAPI application served by `uvicorn`, while preserving the existing MCP and debug dispatch behavior.

#### 3. Verify runtime wiring

You can verify that the server is up and exposing the expected HTTP surface:

```/dev/null/sh#L1-1
curl http://localhost:8080/debug/runtime
```

A typical response shape is:

```/dev/null/json#L1-18
{
  "runtime": [
    {
      "transport": "http",
      "routes": [
        "mcp_rpc",
        "projection_failures_ignore",
        "projection_failures_resolve",
        "runtime_introspection",
        "runtime_routes",
        "runtime_tools",
        "workflow_closed_projection_failures",
        "workflow_resume"
      ],
      "tools": ["memory_get_context", "memory_remember_episode", "memory_search", "projection_failures_ignore", "projection_failures_resolve", "workflow_checkpoint", "workflow_complete", "workflow_resume", "workflow_start", "workspace_register"],
      "resources": ["workspace://{workspace_id}/resume", "workspace://{workspace_id}/workflow/{workflow_instance_id}"]
    }
  ]
}
```

#### 4. Run the minimum MCP smoke validation

A repository-provided smoke client is available for remote MCP validation:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8080 --tool-name memory_get_context
```

This validates the minimum confirmed HTTP MCP path for `v0.1.0`:

- `initialize`
- `tools/list`
- `tools/call`
- `resources/list`

The default smoke call uses `memory_get_context`, which is currently a safe stubbed memory tool in `v0.1.0`. The call itself succeeds over MCP HTTP even though the underlying feature remains intentionally unimplemented.

#### 5. Run workflow-oriented smoke validation

If you also want to validate the workflow tool path against the real Dockerized PostgreSQL instance, use the workflow scenario:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8080 --scenario workflow
```

This scenario performs:

- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_resume`
- `workflow_complete`

against the live server.

#### 6. Run workflow resource-read validation

If you also want to validate workflow resource reads against the live server, enable resource reads in the workflow scenario:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8080 --scenario workflow --workflow-resource-read
```

This extends the workflow validation with:

- `resources/read` for `workspace://{workspace_id}/resume`
- `resources/read` for `workspace://{workspace_id}/workflow/{workflow_instance_id}`

#### 7. Run authenticated smoke validation

If you want to validate the same remote MCP path with bearer authentication enabled, use the authenticated Docker Compose override:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.auth.yml up -d --build --force-recreate
```

Then run the smoke client with the matching bearer token:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8080 --bearer-token smoke-test-secret-token --scenario workflow --workflow-resource-read
```

This validates that the authenticated remote MCP server still supports:

- `initialize`
- `tools/list`
- `tools/call`
- `resources/list`
- `resources/read`
- workflow mutation and resume flows

#### 8. Run the small Traefik auth pattern

If you want to validate the small pattern described in `docs/plans/auth_proxy_scaling_plan.md`, run the stack with the Traefik/auth overlay.

This setup is intended to keep the MCP backend private behind the proxy:

- `traefik` is the only host-exposed entrypoint
- `auth-small` validates `Authorization: Bearer <token>` with Traefik ForwardAuth
- the private MCP backend service runs without direct host port exposure
- PostgreSQL remains internal to the compose network

Start the stack with a shared token for the proxy/auth layer:

```/dev/null/sh#L1-1
CTXLEDGER_SMALL_AUTH_TOKEN=replace-me-with-a-strong-secret docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build --force-recreate
```

Then point your MCP client or smoke client at the Traefik endpoint and send the same bearer token:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8091 --bearer-token replace-me-with-a-strong-secret --scenario workflow --workflow-resource-read
```

You can also validate proxy rejection behavior before the happy path.

Missing token should be rejected by Traefik ForwardAuth with `401`:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8091 --expect-http-status 401 --expect-auth-failure
```

An invalid token should also be rejected with `401`:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8091 --bearer-token wrong-token --expect-http-status 401 --expect-auth-failure
```

Then confirm that a valid token is allowed through the proxy and that the workflow/resource smoke still passes:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8091 --bearer-token replace-me-with-a-strong-secret --scenario workflow --workflow-resource-read
```

Operational notes for this mode:

- `ctxledger` app-layer bearer auth should stay disabled in this overlay
- authentication happens at the proxy boundary, before requests reach the private MCP backend
- the compose override is `docker/docker-compose.small-auth.yml`
- the documented intent is a private backend service behind Traefik, not direct host exposure of the MCP backend itself
- the lightweight auth service is expected to return `200` for valid tokens and `401` for missing or invalid tokens

This small-pattern deployment is the recommended stepping stone for:

- one trusted operator
- local development
- a tightly controlled private environment
- IDE clients such as Zed or VS Code that can send bearer headers

#### 9. Shut down the local stack

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml down
```

### Option B: Dockerfile-based startup

You can also build and run the application image directly from the repository root.

#### 1. Build the image

```/dev/null/sh#L1-1
docker build -t ctxledger:local .
```

#### 2. Start PostgreSQL separately

Example shape:

```/dev/null/sh#L1-1
docker run --name ctxledger-postgres -e POSTGRES_DB=ctxledger -e POSTGRES_USER=ctxledger -e POSTGRES_PASSWORD=ctxledger -p 5432:5432 -d pgvector/pgvector:pg16
```

#### 3. Apply the schema explicitly

`ctxledger` is designed so that schema bootstrap/migration is an **explicit operational step**.

Use:

- `schemas/postgres.sql`

Apply it with your preferred PostgreSQL client after the database is up.

Example shape:

```/dev/null/sh#L1-1
psql postgresql://ctxledger:ctxledger@localhost:5432/ctxledger -f schemas/postgres.sql
```

#### 4. Run the application container

Example shape:

```/dev/null/sh#L1-1
docker run --rm -p 8080:8080 -e CTXLEDGER_DATABASE_URL=postgresql://ctxledger:ctxledger@host.docker.internal:5432/ctxledger -e CTXLEDGER_TRANSPORT=http -e CTXLEDGER_ENABLE_HTTP=true -e CTXLEDGER_HOST=0.0.0.0 -e CTXLEDGER_PORT=8080 -e CTXLEDGER_HTTP_PATH=/mcp ctxledger:local
```

If you are running the image directly with the current repository layout, make sure the container starts the FastAPI app through `uvicorn`. A typical command shape is:

```/dev/null/sh#L1-1
uvicorn ctxledger.http_app:app --host 0.0.0.0 --port 8080
```

If your Docker environment does not support `host.docker.internal`, use an address appropriate for your host networking setup.

#### 5. Verify endpoint availability

Expected local MCP endpoint:

```/dev/null/txt#L1-1
http://localhost:8080/mcp
```

#### 6. Inspect startup summary and debug surfaces

A typical startup summary shape is:

```/dev/null/txt#L1-6
ctxledger 0.1.0 started
health=ok
readiness=ready
runtime=[{'transport': 'http', 'routes': ['mcp_rpc', 'projection_failures_ignore', 'projection_failures_resolve', 'runtime_introspection', 'runtime_routes', 'runtime_tools', 'workflow_closed_projection_failures', 'workflow_resume'], 'tools': ['memory_get_context', 'memory_remember_episode', 'memory_search', 'projection_failures_ignore', 'projection_failures_resolve', 'workflow_checkpoint', 'workflow_complete', 'workflow_resume', 'workflow_start', 'workspace_register'], 'resources': ['workspace://{workspace_id}/resume', 'workspace://{workspace_id}/workflow/{workflow_instance_id}']}]
mcp_endpoint=http://localhost:8080/mcp
```

You can then inspect the same runtime wiring through:

- `/debug/runtime`
- `/debug/routes`
- `/debug/tools`

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
- bearer token authentication strategy
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

- bearer token authentication

Fine-grained authorization is intentionally deferred.

Recommended production posture:

- put the service behind a reverse proxy
- use TLS
- set `CTXLEDGER_REQUIRE_AUTH=true` for HTTP deployments that are not fully private
- provide `CTXLEDGER_AUTH_BEARER_TOKEN` through environment variables or secret-management tooling
- set `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS=false` for internet-exposed production deployments unless operator access to `/debug/*` is explicitly required
- if `/debug/*` must remain enabled in production, keep it behind the same bearer auth boundary and restrict access to trusted operators
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

- `docs/specification.md`
- `docs/architecture.md`
- `docs/workflow-model.md`
- `docs/mcp-api.md`
- `docs/memory-model.md`
- `docs/deployment.md`
- `docs/SECURITY.md`
- `docs/design-principles.md`
- `docs/roadmap.md`

---

## License

See `LICENSE`.