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

If you want to use authenticated access, prepare a bearer token for the proxy layer and use the small-pattern Traefik/auth deployment described below.

---

## Quick Start

The recommended local operator path is the **authenticated small-pattern deployment** through Traefik on port `8091`.  
The direct unauthenticated path on port `8080` is still available for isolated local development and debugging.

### Option A. Start `ctxledger` without authentication

Use this mode when you want the simplest direct local path to the backend.

#### 1. Start PostgreSQL and the direct MCP server

From the repository root, start PostgreSQL and the remote MCP server:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml up -d --build
```

After startup, the direct MCP endpoint is:

```/dev/null/txt#L1-1
http://127.0.0.1:8080/mcp
```

You can optionally verify that the local server is up by checking the runtime debug endpoint:

```/dev/null/sh#L1-1
curl http://127.0.0.1:8080/debug/runtime
```

#### 2. Configure your MCP client for the unauthenticated local endpoint

##### VS Code

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

##### Zed

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

Once configured, your MCP client should be able to reach `ctxledger` directly over HTTP and use the workflow and memory tool surfaces exposed at `/mcp`.

### Option B. Start `ctxledger` with authentication (recommended)

Use this mode when you want the documented proxy-first deployment shape for local development, operator validation, and IDE clients that can send bearer headers.

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

#### 1. Start PostgreSQL, the private backend, auth service, and Traefik

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

After startup, the recommended authenticated MCP endpoint is:

```/dev/null/txt#L1-1
http://127.0.0.1:8091/mcp
```

Every MCP client request to this endpoint must include the same bearer token you chose above.

#### 2. Verify authentication behavior

First, confirm that requests without a token are rejected. This shows that proxy-side authentication is actually active.

Missing token should be rejected with `401`:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8091 --expect-http-status 401 --expect-auth-failure
```

Then confirm that a request with the same token used at startup is accepted.

A valid token should pass and the workflow/resource smoke should succeed:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8091 --bearer-token replace-me-with-a-strong-secret --scenario workflow --workflow-resource-read
```

If you exported `CTXLEDGER_SMALL_AUTH_TOKEN` already, you can keep the smoke command aligned with the startup token like this:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8091 --bearer-token "$CTXLEDGER_SMALL_AUTH_TOKEN" --scenario workflow --workflow-resource-read
```

#### 3. Configure your MCP client for the authenticated endpoint

Use the same token value you set in `CTXLEDGER_SMALL_AUTH_TOKEN`. If the token in your MCP client differs from the startup token, the client will receive `401` responses from the proxy.

##### VS Code

Add a remote MCP server entry in your VS Code MCP client configuration.

A representative authenticated shape is:

```/dev/null/json#L1-11
{
  "mcpServers": {
    "ctxledger": {
      "url": "http://127.0.0.1:8091/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN_HERE"
      }
    }
  }
}
```

##### Zed

Add a remote MCP server entry in your Zed MCP configuration.

A representative authenticated shape is:

```/dev/null/json#L1-11
{
  "mcp_servers": {
    "ctxledger": {
      "url": "http://127.0.0.1:8091/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN_HERE"
      }
    }
  }
}
```

Unfortunately, Zed does not expand environment variables in its MCP configuration file, so `YOUR_TOKEN_HERE` must be replaced with the actual token value.

Once configured, your MCP client should be able to reach `ctxledger` through the proxy-protected MCP endpoint and use the workflow and memory tool surfaces exposed at `/mcp`.

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

```/dev/null/sh#L1-1
envrcctl exec -- python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8091 --bearer-token "$CTXLEDGER_SMALL_AUTH_TOKEN" --scenario workflow --workflow-resource-read
```

Because Zed does not expand environment variables in its MCP configuration file, you must still retrieve the token and paste it into `YOUR_TOKEN_HERE` manually:

```/dev/null/sh#L1-1
envrcctl secret get CTXLEDGER_SMALL_AUTH_TOKEN
```

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

The intended staged roadmap is:

- `0.2`: episodic memory, with `memory_remember_episode` as the most direct fit and `memory_get_context` potentially gaining an initial episode-oriented form
- `0.3`: semantic search, with `memory_search` as the most direct fit and `memory_get_context` potentially gaining stronger relevance-based retrieval
- `0.4`: hierarchical memory retrieval, where `memory_get_context` may evolve into a more multi-layer context assembly surface

This is a roadmap-oriented interpretation of the current architecture and planning documents, not a guarantee that every memory tool will be fully complete at the start of its corresponding version.

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

#### 7. Run the proxy-authenticated smoke validation

If you want to validate authenticated access, use the small-pattern Traefik/auth deployment. Authentication is expected to be enforced at the proxy layer rather than inside `ctxledger`.

Start the stack with a shared token for the proxy/auth layer.

For a first start or an intentional clean rebuild:

```/dev/null/sh#L1-1
CTXLEDGER_SMALL_AUTH_TOKEN=replace-me-with-a-strong-secret docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build --force-recreate
```

For a normal restart of an already-created stack:

```/dev/null/sh#L1-1
CTXLEDGER_SMALL_AUTH_TOKEN=replace-me-with-a-strong-secret docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d
```

Then run the smoke client with the matching bearer token through the proxy endpoint:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8091 --bearer-token replace-me-with-a-strong-secret --scenario workflow --workflow-resource-read
```

This validates that the proxy-protected remote MCP server still supports:

- `initialize`
- `tools/list`
- `tools/call`
- `resources/list`
- `resources/read`
- workflow mutation and resume flows

#### 8. Run the small Traefik auth pattern

If you want to validate the small pattern described in `docs/plans/auth_proxy_scaling_plan.md`, run the stack with the Traefik/auth overlay.

For a step-by-step operator procedure covering startup, auth verification, client targeting, shutdown, and common failure modes, see `docs/small_auth_operator_runbook.md`.

This setup is intended to keep the MCP backend private behind the proxy:

- `traefik` is the only host-exposed entrypoint
- `auth-small` validates `Authorization: Bearer <token>` with Traefik ForwardAuth
- the private MCP backend service runs without direct host port exposure
- PostgreSQL remains internal to the compose network

Start the stack with a shared token for the proxy/auth layer.

For a first start or an intentional clean rebuild:

```/dev/null/sh#L1-1
CTXLEDGER_SMALL_AUTH_TOKEN=replace-me-with-a-strong-secret docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build --force-recreate
```

For a normal restart of an already-created stack:

```/dev/null/sh#L1-1
CTXLEDGER_SMALL_AUTH_TOKEN=replace-me-with-a-strong-secret docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d
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

- authentication happens at the proxy boundary, before requests reach the private MCP backend
- the compose override is `docker/docker-compose.small-auth.yml`
- the documented intent is a private backend service behind Traefik, not direct host exposure of the MCP backend itself
- the lightweight auth service is expected to return `200` for valid tokens and `401` for missing or invalid tokens
- `ctxledger` no longer relies on app-layer bearer authentication in the documented deployment path

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
