# ctxledger

Durable Workflow Runtime and Multi-Layer Memory for AI Agents.

`ctxledger` is a remote MCP server that provides:

- durable workflow control
- multi-layer agent memory
- PostgreSQL-backed persistence
- MCP 2025-03-26 compatibility
- Docker-based deployment

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
  - Streamable HTTP
  - stdio
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

### Workflow tools
- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_resume`
- `workflow_complete`

### Memory tools
- `memory_remember_episode`
- `memory_search`
- `memory_get_context`

Some memory APIs may remain stubbed in `v0.1.0` while the workflow subsystem is completed first.

### Resources
- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`
- `memory://episode/{episode_id}`
- `memory://summary/{scope}`

---

## Workflow Model Highlights

`ctxledger` separates:

- planning identity
- execution identity
- operational attempts
- resumable snapshots

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
- `CTXLEDGER_ENABLE_STDIO`
- `CTXLEDGER_HOST`
- `CTXLEDGER_PORT`
- `CTXLEDGER_HTTP_PATH`
- `CTXLEDGER_REQUIRE_AUTH`
- `CTXLEDGER_AUTH_BEARER_TOKEN`
- `CTXLEDGER_PROJECTION_ENABLED`
- `CTXLEDGER_PROJECTION_DIRECTORY`
- `CTXLEDGER_PROJECTION_WRITE_JSON`
- `CTXLEDGER_PROJECTION_WRITE_MARKDOWN`
- `CTXLEDGER_LOG_LEVEL`
- `CTXLEDGER_LOG_STRUCTURED`

### Typical local example

```/dev/null/.env.example#L1-13
CTXLEDGER_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ctxledger
CTXLEDGER_TRANSPORT=http
CTXLEDGER_ENABLE_HTTP=true
CTXLEDGER_ENABLE_STDIO=false
CTXLEDGER_HOST=0.0.0.0
CTXLEDGER_PORT=8080
CTXLEDGER_HTTP_PATH=/mcp
CTXLEDGER_REQUIRE_AUTH=false
CTXLEDGER_PROJECTION_ENABLED=true
CTXLEDGER_PROJECTION_DIRECTORY=.agent
CTXLEDGER_PROJECTION_WRITE_JSON=true
CTXLEDGER_PROJECTION_WRITE_MARKDOWN=true
CTXLEDGER_LOG_LEVEL=info
```

---

## Local Startup

The recommended local path is Docker-based.

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
docker run --rm -p 8080:8080 -e CTXLEDGER_DATABASE_URL=postgresql://ctxledger:ctxledger@host.docker.internal:5432/ctxledger -e CTXLEDGER_TRANSPORT=http -e CTXLEDGER_ENABLE_HTTP=true -e CTXLEDGER_ENABLE_STDIO=false -e CTXLEDGER_HOST=0.0.0.0 -e CTXLEDGER_PORT=8080 -e CTXLEDGER_HTTP_PATH=/mcp ctxledger:local
```

If your Docker environment does not support `host.docker.internal`, use an address appropriate for your host networking setup.

#### 5. Verify endpoint availability

Expected local MCP endpoint:

```/dev/null/txt#L1-1
http://localhost:8080/mcp
```

### Option C: Python direct startup

If you are running from Python directly, a typical command shape is:

```/dev/null/sh#L1-1
python -m ctxledger serve
```

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

For more detail, see `docs/deployment.md`.

---

## Security Notes

In `v0.1.0`, the primary formal security boundary is:

- bearer token authentication

Fine-grained authorization is intentionally deferred.

Recommended production posture:

- put the service behind a reverse proxy
- use TLS
- inject secrets through environment variables or secret-management tooling
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
- `docs/design-principles.md`
- `docs/roadmap.md`

---

## License

See `LICENSE`.