# Deployment

## 1. Purpose

This document describes how to deploy and run `ctxledger` in local and production-like environments.

`ctxledger` is a durable workflow runtime and multi-layer memory system for AI agents.  
Its deployment model is built around the following assumptions:

- canonical state lives in PostgreSQL
- MCP is the public interface
- repository projections are derived artifacts
- workflow control must remain available across process restarts
- schema initialization is an explicit operational step

In `v0.1.0`, the primary deployment target is a local Docker-based environment with:

- one `ctxledger` server
- one PostgreSQL instance

The currently evidenced local deployment path now runs `ctxledger` as a FastAPI application served by `uvicorn`, while preserving the existing MCP and HTTP dispatch behavior behind `/mcp`.

---

## 2. Deployment Principles

The deployment model follows these principles:

1. **PostgreSQL is required**
2. **Database state must persist across container restarts**
3. **Schema bootstrap/migration is an explicit step**
4. **Readiness depends on DB connectivity and schema availability**
5. **Projection failures must not invalidate canonical workflow state**
6. **Production deployments should place the MCP server behind TLS and a reverse proxy**
7. **The `0.2.0` work scope is expected to include an HTTPS/TLS deployment path after the memory workstream is closed out**

---

## 3. Runtime Topology

## 3.1 Minimum Local Topology

Recommended local topology:

- `postgres`
- `ctxledger`

Responsibilities:

### `postgres`
- canonical data store
- workflow state persistence
- verification persistence
- future memory persistence
- projection failure/freshness metadata

### `ctxledger`
- MCP server
- FastAPI/`uvicorn` HTTP application process
- workflow control API
- resource assembly
- projection generation
- readiness/liveness handling

## 3.2 Recommended Production Topology

Recommended production topology:

- reverse proxy
- TLS termination
- proxy-layer authentication handling strategy
- `ctxledger` application container/process
- PostgreSQL with persistent storage
- optional future background workers for embeddings/summaries/indexing

Planned follow-up scope for `0.2.0` after the memory closeout work:

- HTTPS exposure for the MCP endpoint through proxy-side TLS termination
- local operator guidance for certificate and trust handling
- authenticated MCP client compatibility over HTTPS
- explicit documentation for when to use plain local HTTP versus HTTPS-oriented deployment paths

---

## 4. Runtime Modes

`ctxledger` is designed around a shared application core with separate transport adapters.

Supported runtime mode in the repository currently is:

- HTTP MCP at `/mcp`

### 4.1 Primary Runtime Mode

For `v0.1.0`, the primary deployment and acceptance mode is:

- HTTP MCP at `/mcp`

The currently evidenced minimal HTTP MCP path supports:

- `initialize`
- `tools/list`
- `tools/call`

### 4.2 Deployment Recommendation

Use HTTP mode for normal deployment, including Docker-based local operation, and treat `/mcp` as the canonical MCP endpoint for `v0.1.0`.

For the currently evidenced local runtime, the recommended concrete serving shape is:

- FastAPI application wrapper
- `uvicorn` process
- MCP requests routed to `/mcp`
- debug and workflow HTTP routes exposed alongside the MCP endpoint

---

## 5. Canonical Dependencies

## 5.1 PostgreSQL

PostgreSQL is mandatory.

The service is not meaningfully operational without:

- database connectivity
- required schema/tables
- writable canonical storage

## 5.2 pgvector

The schema enables `pgvector` and the current memory-search implementation now uses vector-backed similarity lookup for stored memory embeddings in PostgreSQL.

This should be understood as an initial semantic retrieval layer rather than a claim that all planned memory retrieval behavior is complete. The current `0.3.0`-oriented state is best described as:

- PostgreSQL-backed storage for memory embeddings
- vector similarity lookup used by `memory_search`
- hybrid lexical + embedding-backed ranking over stored memory items
- validated provider-specific embedding support for `openai`, alongside `local_stub`, `custom_http`, and the broader embedding provider scaffolding
- richer multi-layer retrieval still remaining as follow-up work beyond `0.4.0`
- `0.4.0` is instead intended to focus on operator-facing observability surfaces such as CLI inspection and optionally deployable Grafana-based dashboard support

Operators should therefore treat `pgvector` as part of the active memory-search path, not merely as dormant future-proofing infrastructure.

## 5.3 Filesystem Access

Filesystem access may be needed for derived artifacts and other non-canonical operational outputs.

Any such writing is best-effort and must not be treated as canonical persistence.

## 5.4 Observability SQL Views and Grafana Read-only Access

For `0.4.0` observability work, Grafana should be treated as a **read-only PostgreSQL client** over canonical state.

Recommended deployment posture:

- do **not** make Grafana depend on CLI command execution for metrics collection
- do **not** point Grafana at broad write-capable database credentials
- prefer a dedicated observability schema containing stable read-only SQL views
- grant Grafana only:
  - database connect
  - schema usage
  - `SELECT` on observability views

This keeps the CLI and dashboard paths aligned in meaning while avoiding a design where dashboard access can mutate canonical runtime state.

### 5.4.1 Recommended access model

Preferred structure:

- application schema:
  - `public`
- observability schema:
  - `observability`
- Grafana database role:
  - `ctxledger_grafana`

Recommended properties of the Grafana role:

- login-capable
- read-only
- no table ownership
- no schema creation
- no write privileges on canonical tables
- no dependency on broad function execution grants unless explicitly needed

### 5.4.2 Example observability schema bootstrap

The following example creates an observability schema and a minimal set of stable views for Grafana-oriented inspection.

```/dev/null/sql#L1-92
CREATE SCHEMA IF NOT EXISTS observability;

CREATE OR REPLACE VIEW observability.workflow_status_counts AS
SELECT
  status,
  COUNT(*)::bigint AS workflow_count
FROM workflow_instances
GROUP BY status;

CREATE OR REPLACE VIEW observability.workflow_recent AS
SELECT
  wi.workflow_instance_id,
  wi.workspace_id,
  w.canonical_path,
  wi.ticket_id,
  wi.status AS workflow_status,
  wi.updated_at,
  wc.step_name AS latest_step_name,
  wa.verify_status AS latest_verify_status
FROM workflow_instances AS wi
LEFT JOIN workspaces AS w
  ON w.workspace_id = wi.workspace_id
LEFT JOIN LATERAL (
  SELECT
    checkpoint_id,
    step_name,
    created_at
  FROM workflow_checkpoints
  WHERE workflow_instance_id = wi.workflow_instance_id
  ORDER BY created_at DESC
  LIMIT 1
) AS wc ON TRUE
LEFT JOIN LATERAL (
  SELECT
    attempt_id,
    verify_status,
    updated_at
  FROM workflow_attempts
  WHERE workflow_instance_id = wi.workflow_instance_id
  ORDER BY attempt_number DESC, started_at DESC
  LIMIT 1
) AS wa ON TRUE;

CREATE OR REPLACE VIEW observability.memory_overview AS
SELECT
  (SELECT COUNT(*)::bigint FROM episodes) AS episode_count,
  (SELECT COUNT(*)::bigint FROM memory_items) AS memory_item_count,
  (SELECT COUNT(*)::bigint FROM memory_embeddings) AS memory_embedding_count,
  (SELECT COUNT(*)::bigint FROM memory_relations) AS memory_relation_count,
  (SELECT MAX(created_at) FROM episodes) AS latest_episode_created_at,
  (SELECT MAX(created_at) FROM memory_items) AS latest_memory_item_created_at,
  (SELECT MAX(created_at) FROM memory_embeddings) AS latest_memory_embedding_created_at,
  (SELECT MAX(created_at) FROM memory_relations) AS latest_memory_relation_created_at;

CREATE OR REPLACE VIEW observability.memory_item_provenance_counts AS
SELECT
  provenance,
  COUNT(*)::bigint AS memory_item_count
FROM memory_items
GROUP BY provenance;

CREATE OR REPLACE VIEW observability.projection_failures_recent AS
SELECT
  projection_failure_id,
  workspace_id,
  workflow_instance_id,
  attempt_id,
  projection_type,
  target_path,
  error_code,
  error_message,
  status,
  retry_count,
  occurred_at,
  resolved_at
FROM projection_failures;

CREATE OR REPLACE VIEW observability.projection_failure_status_counts AS
SELECT
  status,
  COUNT(*)::bigint AS failure_count
FROM projection_failures
GROUP BY status;
```

These views are intentionally simple:

- aggregate counts
- recent workflow inspection
- memory overview
- provenance breakdown
- projection failure inspection

They are suitable for:

- Grafana panels
- ad hoc operator inspection
- future compatibility hardening through view-level evolution

### 5.4.3 Example Grafana read-only role

The following example shows the intended database privilege shape for a Grafana-specific role.

```/dev/null/sql#L1-23
CREATE ROLE ctxledger_grafana
LOGIN
PASSWORD 'replace-with-a-strong-secret';

GRANT CONNECT ON DATABASE ctxledger TO ctxledger_grafana;

GRANT USAGE ON SCHEMA observability TO ctxledger_grafana;

GRANT SELECT ON ALL TABLES IN SCHEMA observability TO ctxledger_grafana;

ALTER DEFAULT PRIVILEGES IN SCHEMA observability
GRANT SELECT ON TABLES TO ctxledger_grafana;

REVOKE ALL ON SCHEMA public FROM ctxledger_grafana;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM ctxledger_grafana;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM ctxledger_grafana;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM ctxledger_grafana;
```

Operational notes:

- use a real secret, never the placeholder password
- prefer secret injection through deployment configuration rather than hardcoding credentials in dashboard JSON
- if the deployment uses a schema name other than `public` for canonical application tables, adjust the revocation/grant pattern accordingly
- if Grafana only needs selected views, you may grant `SELECT` on those specific views instead of all tables in the `observability` schema

### 5.4.4 SQL injection risk posture

Grafana should not be treated as “safe by default” merely because it is read-oriented.

Important risk controls:

1. **read-only database role**
   - the primary control
   - ensures dashboard-issued SQL cannot mutate canonical state

2. **view-based exposure**
   - reduce direct access to raw tables
   - expose stable, intentionally chosen columns only

3. **restricted dashboard editing**
   - limit who can create or modify SQL-backed panels
   - avoid broad editor/admin access without operational need

4. **careful variable usage**
   - prefer bounded choice variables over free-text interpolation
   - avoid surprising query expansion patterns

5. **statement timeout / connection limits**
   - helps reduce operational blast radius from accidental expensive queries

This means the intended Grafana model is:

- **separate from the CLI implementation path**
- **directly querying PostgreSQL**
- **constrained by a read-only observability role and stable views**

---

## 6. Configuration

`ctxledger` should use a typed configuration boundary with startup validation.

Recommended environment variables include:

- `CTXLEDGER_DATABASE_URL`
- `CTXLEDGER_HOST`
- `CTXLEDGER_PORT`
- `CTXLEDGER_TRANSPORT`
- `CTXLEDGER_ENABLE_HTTP`

- `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS`
- `CTXLEDGER_LOG_LEVEL`

### 6.0 Environment Variable Guidance

The following variables are especially important for deployment and production hardening.

See also:

- `../.env.example`
- `../.env.production.example`
- `SECURITY.md`

| Variable | Default | Purpose | Local / internal recommendation | Internet-exposed production recommendation |
| --- | --- | --- | --- | --- |
| `CTXLEDGER_DATABASE_URL` | none | PostgreSQL connection string for canonical state | set to local or shared development database | required; inject through secret management |
| `CTXLEDGER_TRANSPORT` | `http` | selects the enabled transport mode | keep set to `http` for Docker/local deployment | keep set to `http` for the `v0.1.0` release posture |
| `CTXLEDGER_ENABLE_HTTP` | derived from transport | enables HTTP transport | keep aligned with `CTXLEDGER_TRANSPORT`; expected `true` for normal local deployment | keep aligned with `CTXLEDGER_TRANSPORT`; expected `true` |
| `CTXLEDGER_HOST` | `0.0.0.0` | HTTP bind host | `0.0.0.0` is acceptable in containers/local networks | bind according to network policy, typically behind a reverse proxy |
| `CTXLEDGER_PORT` | `8080` | HTTP listen port | `8080` is a reasonable default | set explicitly to match deployment and proxy routing |
| `CTXLEDGER_HTTP_PATH` | `/mcp` | MCP HTTP endpoint path | keep default unless integration requires a different path | keep stable and document it for proxy configuration |
| `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS` | `true` | controls whether `/debug/*` routes are registered at all | `true` is acceptable for local/operator use | usually `false`; enable only for a clear operational need |
| `CTXLEDGER_LOG_LEVEL` | `info` | log verbosity | `info` or `debug` during development | `info` or stricter, depending on operational policy |

Authentication and debug exposure expectations:

- authentication is expected to be enforced at the reverse-proxy/auth-gateway layer rather than inside `ctxledger`
- keep the `ctxledger` backend private behind the proxy in shared or internet-exposed deployments
- when `/debug/*` is enabled, keep it behind the same proxy-layer authentication boundary as `/mcp`
- `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS=false` removes `/debug/*` from the registered HTTP route surface instead of returning debug-specific responses from still-registered handlers

Optional future variables may include:

- embedding backend settings
- worker mode settings
- summary/indexing configuration
- auth integration settings

## 6.1 Configuration Expectations

At startup, configuration should be validated before the service is considered healthy.

Invalid critical configuration should fail startup early.

Examples of critical configuration:

- missing or invalid database URL
- incompatible transport mode
- invalid host/port configuration
- invalid debug endpoint exposure configuration

## 6.2 Deployment Evidence for Local HTTP Serving

The repository now contains direct local-deployment evidence for a real remote HTTP MCP serving path.

Current evidenced serving shape:

- FastAPI application wrapper in `src/ctxledger/http_app.py`
- `uvicorn`-based process startup
- Docker Compose startup through `docker/docker-compose.yml`
- healthcheck validation through `/debug/runtime`

Current evidenced Docker startup command shape:

```/dev/null/sh#L1-1
uvicorn ctxledger.http_app:app --host 0.0.0.0 --port 8080
```

Current evidenced local verification surfaces include:

- MCP endpoint:
  - `/mcp`
- debug endpoints:
  - `/debug/runtime`
  - `/debug/routes`
  - `/debug/tools`

Current evidenced smoke validation script:

- `scripts/mcp_http_smoke.py`

Future observability deployments that add Grafana should continue to preserve this core separation:

- MCP and debug routes remain application-facing operational surfaces
- Grafana remains an optional dashboard surface
- Grafana should consume PostgreSQL through read-only observability views rather than by shelling out to CLI commands

That smoke script now supports:

1. **basic MCP validation**
   - `initialize`
   - `tools/list`
   - `tools/call`
   - `resources/list`

2. **workflow-oriented MCP validation**
   - `workspace_register`
   - `workflow_start`
   - `workflow_checkpoint`
   - `workflow_resume`
   - `workflow_complete`

3. **resource read validation for real workflow data**
   - `resources/read` for:
     - `workspace://{workspace_id}/resume`
     - `workspace://{workspace_id}/workflow/{workflow_instance_id}`

Representative local validation command shapes:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://localhost:8443 --bearer-token replace-me-with-a-strong-secret --tool-name memory_get_context --insecure
```

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://localhost:8443 --bearer-token replace-me-with-a-strong-secret --scenario workflow --insecure
```

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://localhost:8443 --bearer-token replace-me-with-a-strong-secret --scenario workflow --workflow-resource-read --insecure
```

Operational meaning of this evidence:

- the MCP endpoint is not just unit-tested internally
- the Dockerized application is reachable as a real remote MCP server through the HTTPS proxy entrypoint
- a minimum client can perform MCP lifecycle setup, tool discovery, tool invocation, workflow mutation, workflow resume inspection, and workflow resource reads against the live server

## 6.3 Debug Endpoint Exposure Policy

`ctxledger` exposes operational debug endpoints under `/debug/*` for runtime introspection.

Current debug surfaces include:

- `/debug/runtime`
- `/debug/routes`
- `/debug/tools`

Representative HTTP route names exposed by these debug surfaces may include:

- `runtime_introspection`
- `runtime_routes`
- `runtime_tools`
- `workflow_resume`

Deployment policy:

1. debug endpoints are intended for operator visibility, not general client use
2. if bearer token authentication is enabled for HTTP access, `/debug/*` should be protected by the same authentication policy
3. production deployments should be able to disable `/debug/*` entirely with configuration
4. when debug endpoints are disabled, the preferred behavior is to avoid registering those routes at all so the HTTP surface does not advertise unnecessary debug endpoints

Operational recommendation:

- enable `/debug/*` by default only in local development or controlled internal environments
- require authentication whenever the HTTP surface is authenticated
- disable `/debug/*` in internet-exposed production deployments unless there is a clear operational need
- if exposure is required in production, place the service behind TLS and a reverse proxy, and restrict access to trusted operators

Current implementation behavior:

- `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS=false` removes `/debug/*` handlers from the HTTP runtime registration surface
- when HTTP bearer token authentication is enabled, `/debug/*` should follow the same authentication boundary as other protected HTTP endpoints
- operators should treat `/debug/*` responses as authenticated operational metadata rather than public diagnostics
- Docker-based local health validation can use `/debug/runtime` as an operational readiness probe for the FastAPI/`uvicorn` process

The payloads returned by `/debug/*` may reveal details such as:

- registered HTTP routes such as:
  - `runtime_introspection`
  - `runtime_routes`
  - `runtime_tools`

## 6.4 Local HTTPS paths

The repository now has two deployment patterns:

1. **`small` (default)**
2. **`large` (future plan; not implemented yet)**

Both patterns are intended to keep the backend private and terminate TLS at the proxy boundary.

Shared shape:

- Traefik remains the host-exposed MCP entrypoint
- Traefik terminates TLS
- the private `ctxledger` backend remains on internal plain HTTP inside the deployment network
- operators provide certificate material for the HTTPS listener rather than enabling TLS inside `ctxledger` itself
- proxy-layer authentication remains part of the intended deployment boundary

Expected local certificate files for the default Docker-based local stack:

- `docker/traefik/certs/localhost.crt`
- `docker/traefik/certs/localhost.key`

These files are mounted into the Traefik container and used for the HTTPS listener.

### 6.4.1 `small` deployment pattern (default)

This is the default deployment pattern for local operator use and development.

Current characteristics:

- HTTPS enabled
- proxy-layer authentication enabled
- Grafana enabled
- Apache AGE enabled
- repository-owned PostgreSQL 17 image with AGE + pgvector
- Docker Compose based

The intended shape is:

- Traefik exposes HTTPS on `8443`
- the forward-auth middleware protects the HTTPS entrypoint
- the backend remains private behind the proxy
- Grafana is part of the default stack
- the PostgreSQL path is AGE-enabled by default
- the default startup path applies the canonical schema automatically
- the default startup path ensures the `age` extension exists automatically
- the default startup path bootstraps the default constrained AGE graph automatically:
  - `ctxledger_memory`
- the default startup path prepares Grafana-facing observability access automatically
- no separate no-auth startup path is supported

Default startup command:

```/dev/null/sh#L1-1
CTXLEDGER_SMALL_AUTH_TOKEN=replace-me-with-a-strong-secret docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build --force-recreate
```

Default MCP endpoint:

- `https://localhost:8443/mcp`

Default Grafana endpoint:

- `http://localhost:3000`

Representative smoke validation command for local self-signed testing:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://localhost:8443 --bearer-token "$CTXLEDGER_SMALL_AUTH_TOKEN" --insecure --scenario workflow --workflow-resource-read
```

The validated default `small` pattern now performs the AGE and Grafana bootstrap work during startup so operators do not need separate AGE or observability overlays for normal local use.

### 6.4.2 `large` deployment pattern (future plan)

This pattern is planned but not implemented yet.

Intended characteristics:

- HTTPS enabled
- proxy-layer authentication enabled
- Grafana enabled
- Azure Database for PostgreSQL
- larger-scale deployment posture than the validated PostgreSQL 17-based default Docker local stack

Current status:

- planned only
- not yet implemented
- should be treated as a future deployment direction rather than a current operator workflow

### Certificate guidance

For local development, a practical option is to generate a certificate for `localhost` and loopback addresses with `mkcert`:

```/dev/null/sh#L1-2
mkdir -p docker/traefik/certs
mkcert -cert-file docker/traefik/certs/localhost.crt -key-file docker/traefik/certs/localhost.key localhost 127.0.0.1 ::1
```

An OpenSSL self-signed certificate can also work for local-only testing, but it may not be trusted automatically by your machine or client tooling.

Operational expectations:

- do not commit real certificate or key material to version control
- treat `localhost.key` as sensitive secret material
- use these paths for local or tightly controlled operator testing, not as a substitute for production certificate management
- if the local certificate is not trusted, use client-side trust configuration or an explicit insecure/testing mode only for local validation

### Relationship to production posture

These deployment patterns improve production-like operator validation, but they do not change the broader deployment model:

- TLS termination still belongs at the proxy boundary
- authentication still belongs at the proxy boundary
- the backend application remains private behind the proxy
- certificate issuance, trust, rotation, and secret handling remain deployment/operator concerns rather than application concerns

These details are useful for diagnostics but increase observability exposure, so they should be treated as operationally sensitive.

The deployment patterns do not add any additional operator-only mutation routes beyond the supported MCP and workflow inspection surfaces.

Operational guidance for these patterns:

- protect operator-facing HTTPS access with the same proxy-layer authentication boundary used for other protected endpoints
- expose the HTTPS surface only to trusted operators or trusted automation
- prefer exact path matching for supported entrypoints such as `/mcp` and `/debug/*`
- keep request logging enabled at the proxy or gateway boundary so operational access remains observable during incident review
- treat workflow-scoping identifiers that may appear in query strings, resource URIs, or logs as operational metadata

Representative reverse-proxy expectations:

- match only the intended HTTPS entrypoints
- apply the same auth, TLS, and trusted-network policy used for other protected operator endpoints
- preserve enough request logging to identify:
  - which route was called
  - whether auth succeeded or failed
  - which workflow-scoping identifiers were present
  - the response status returned to the caller
- query parameters may contain operational identifiers, so log retention and access policy should reflect that sensitivity
- proxy logs should make invalid-path `404 not_found` responses distinguishable from auth failures and validation-driven `400 invalid_request` responses

For the broader security posture around bearer authentication, secret handling, and `/debug/*` exposure, see `SECURITY.md`.

---

## 7. Schema Bootstrap and Migration Policy

Schema initialization and migration are explicit operational steps.

`ctxledger` should **not** implicitly apply schema changes during normal server startup.

This separation is intentional because:

- schema evolution is operationally sensitive
- automatic startup migration can cause race conditions
- startup failure modes should remain clear
- production safety improves when schema changes are explicit

## 7.1 Initial Bootstrap

For `v0.1.0`, schema bootstrap may be handled using the SQL file:

- `schemas/postgres.sql`

This schema includes the foundation for:

- workflow control
- verification
- projection failure tracking
- projection freshness tracking
- future episodic memory
- future semantic memory
- future relation graph

## 7.2 Bootstrap Order

Recommended operator order:

1. start PostgreSQL
2. ensure required extensions are available
3. apply bootstrap SQL / migration step
4. verify required tables exist
5. start `ctxledger`
6. verify readiness
7. begin MCP client usage

## 7.3 Migration Ownership

Migration or bootstrap execution should be treated as an operator/deployment concern, not as normal request-serving behavior.

## 7.4 Recovery for Stale Live Constraints After Schema Drift

In environments that persist PostgreSQL data across restarts, an older live constraint definition may remain in place even when the checked-in bootstrap schema has already been updated.

One concrete failure mode is a stale `memory_items_provenance_valid` constraint that does not yet allow:

- `workflow_complete_auto`

This can surface as:

- direct `memory_remember_episode` working normally
- `workflow_complete` creating the auto-memory episode but failing while inserting the corresponding memory item
- PostgreSQL `CheckViolation` errors referencing `memory_items_provenance_valid`
- auto-memory completion details indicating recording failure instead of successful embedding persistence

This is a schema-drift recovery problem, not an application-env forwarding problem.

Recommended recovery approach:

1. inspect the live constraint definition in the running database
2. confirm whether `workflow_complete_auto` is missing from the allowed provenance values
3. update or recreate the live constraint so it matches the current schema in `schemas/postgres.sql`
4. rerun a representative `workflow_complete` path and confirm:
   - the memory item is stored
   - auto-memory reports successful recording
   - embedding persistence succeeds when embedding is enabled

Operational reminder:

- rebuilding containers or restarting services does not by itself correct this class of drift when the PostgreSQL volume is retained
- treat the checked-in schema as the desired definition, but verify the live database separately before assuming migration state is current

---

## 8. Health and Readiness

`ctxledger` distinguishes:

- liveness
- readiness

## 8.1 Liveness

Liveness means the process is running and the runtime loop is functioning.

Liveness alone does **not** imply that workflow operations are safe to serve.

## 8.2 Readiness

Readiness means the service can safely process workflow requests.

At minimum, readiness should confirm:

- PostgreSQL connectivity
- required schema/table availability
- valid critical configuration

## 8.3 Degraded but Ready States

The service may still be considered ready when some non-canonical derived systems are degraded.

Examples:

- projection is stale
- projection write failed previously
- a derived artifact path is currently unavailable
- embedding generation is lagging
- memory indexing is incomplete

These affect quality or operator visibility, but do not necessarily invalidate workflow control availability.

## 8.4 Not-Ready Conditions

Typical not-ready conditions include:

- database unavailable
- missing required schema
- invalid critical configuration
- startup bootstrap incomplete

---

## 9. Docker Deployment

## 9.1 Recommended Local Workflow

For local deployment, the expected development path is:

1. start PostgreSQL and `ctxledger` via Docker Compose
2. apply the schema explicitly
3. verify readiness
4. connect an MCP-compatible client

## 9.2 Expected Endpoint

For the documented operator-facing deployment path, the expected MCP endpoint is:

- `https://localhost:8443/mcp`

## 9.3 Compose Expectations

A local `docker-compose` setup should provide:

- PostgreSQL service
- `ctxledger` service
- persistent PostgreSQL volume
- port exposure for HTTP MCP access
- environment variable injection

Recommended port exposure:

- PostgreSQL for local debugging if needed
- Traefik HTTPS entrypoint, typically `8443`

## 9.4 Persistence Expectations

PostgreSQL must use a persistent volume.

Without persistent DB storage, the system would lose canonical workflow state, which violates the core design of `ctxledger`.

---

## 10. Projection Behavior in Deployment

Projection files are derived artifacts, not canonical state.

Current workflow inspection should rely on supported PostgreSQL-backed interfaces and operator-facing observability surfaces.

## 10.1 Projection Path Policy

When derived artifacts are generated, output should remain restricted to the registered workspace root:

- under `workspace.canonical_path`
- never outside the workspace root

## 10.2 Projection Failure Semantics

Projection write failure must not roll back canonical DB state.

Instead, failure should be:

- logged
- recorded in canonical operational metadata
- available for later inspection or retry

## 10.3 Projection Freshness

Projection state should also be tracked for freshness, such as:

- `fresh`
- `stale`
- `missing`
- `failed`

This matters operationally, but canonical reads must still come from PostgreSQL.

---

## 11. Security Guidance

This section summarizes deployment-relevant security posture.  
For the fuller security model and operational guidance, see `SECURITY.md`.

## 11.1 Authentication

In `v0.1.0`, bearer token authentication is the primary formal access control boundary.

Authentication should be enforced at the transport boundary.

## 11.2 Authorization

Fine-grained authorization is deferred beyond `v0.1.0`.

This means:

- workspace-specific authorization may not yet be enforced
- role-based access policy may not yet exist
- multi-tenant isolation may not yet exist

Deployments should account for this limitation.

## 11.3 TLS and Reverse Proxy

For production-like deployment, use:

- reverse proxy
- TLS termination
- secure secret handling for bearer tokens

Do not expose the service publicly over plaintext HTTP in environments requiring security.

## 11.4 Secrets

Bearer tokens and database credentials should be injected via environment or secret-management mechanisms.

They should not be hardcoded into repository files.

---

## 12. Operational Logging and Diagnostics

Structured logging is the primary observability mechanism in `v0.1.0`.

For the current roadmap direction, structured logging should also be treated as the foundation for a broader `0.4.0` observability workstream centered on operator-facing visibility into:

- workflow volume and status
- attempt and verification activity
- episodic and semantic memory state
- canonical failure and persistence health

That `0.4.0` work is expected to expand beyond logs alone into:

- CLI inspection/reporting surfaces
- optional deployable Grafana-based dashboard support for lightweight dashboard-style visibility
- read-only observability SQL views and constrained dashboard database access when Grafana is enabled

Important logged events should include:

- startup
- shutdown
- readiness failures
- workspace registration
- workflow start
- checkpoint creation
- workflow termination
- verification persistence
- projection generation success/failure
- projection stale detection
- authentication failure
- DB conflict/invariant failure

Correlation identifiers should be used in logs where possible, but are not required as canonical workflow schema fields.

---

## 13. Recommended Local Startup Procedure

A practical local startup sequence is:

1. ensure Docker and Docker Compose are available
2. start PostgreSQL
3. apply `schemas/postgres.sql`
4. start `ctxledger`
5. verify the HTTP MCP endpoint is reachable
6. verify readiness conditions
7. register a workspace
8. start a workflow
9. create a checkpoint
10. verify resume behavior

This sequence confirms both deployment correctness and core workflow durability.

---

## 14. Failure Scenarios to Expect

Operators should expect and plan for these conditions:

## 14.1 Database Unavailable
Impact:
- service should be not-ready
- workflow operations should fail safely

## 14.2 Schema Missing or Incomplete
Impact:
- service should fail startup or remain not-ready
- operators must apply bootstrap/migrations explicitly

## 14.3 Projection Path Unavailable
Impact:
- canonical workflow state may still succeed
- projection failure should be recorded
- resume via MCP should still work from PostgreSQL

## 14.4 Auth Misconfiguration
Impact:
- service may fail startup or reject all requests
- should be visible in structured logs

## 14.5 Stale Projection
Impact:
- historical derived artifacts may lag behind canonical state
- MCP resources/tools should still reflect canonical data
- operators should inspect freshness/failure state

---

## 15. Production Readiness Notes

For a production-like environment, the minimum recommended posture is:

- persistent PostgreSQL storage
- explicit schema management
- reverse proxy with TLS
- bearer token authentication
- structured log collection
- readiness-aware service exposure

Recommended future improvements include:

- managed migrations
- metrics and tracing
- audit logging
- operator-facing observability CLI surfaces targeted for `0.4.0`
- optional deployable Grafana-based dashboard support targeted for `0.4.0`
- hierarchical memory retrieval and summary-layer expansion targeted for `0.5.0`
- background workers for embedding/index pipelines
- stronger authorization controls

---

## 16. `v0.1.0` Deployment Summary

A valid `v0.1.0` deployment should provide:

- a running `ctxledger` MCP server
- a reachable PostgreSQL instance
- explicitly initialized schema
- durable canonical workflow persistence
- readiness tied to DB and schema availability
- projection support as best-effort derived output
- HTTPS MCP access at `https://localhost:8443/mcp` for the documented local operator-facing deployment path

The most important deployment property is not simply that the service starts, but that:

- workflow state survives restart
- resume can be reconstructed from PostgreSQL
- canonical state is never confused with derived files
- operational problems remain diagnosable