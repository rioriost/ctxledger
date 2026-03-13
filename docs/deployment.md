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

---

## 2. Deployment Principles

The deployment model follows these principles:

1. **PostgreSQL is required**
2. **Database state must persist across container restarts**
3. **Schema bootstrap/migration is an explicit step**
4. **Readiness depends on DB connectivity and schema availability**
5. **Projection failures must not invalidate canonical workflow state**
6. **Production deployments should place the MCP server behind TLS and a reverse proxy**

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
- workflow control API
- resource assembly
- projection generation
- readiness/liveness handling

## 3.2 Recommended Production Topology

Recommended production topology:

- reverse proxy
- TLS termination
- bearer token authentication handling strategy
- `ctxledger` application container/process
- PostgreSQL with persistent storage
- optional future background workers for embeddings/summaries/indexing

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

---

## 5. Canonical Dependencies

## 5.1 PostgreSQL

PostgreSQL is mandatory.

The service is not meaningfully operational without:

- database connectivity
- required schema/tables
- writable canonical storage

## 5.2 pgvector

The schema enables `pgvector` so future semantic retrieval can be added without redesigning the database foundation.

In `v0.1.0`, vector-backed retrieval may still be incomplete, but enabling the extension early keeps the schema aligned with the architecture.

## 5.3 Filesystem Access

Filesystem access is needed for derived projections such as:

- `.agent/resume.json`
- `.agent/resume.md`

Projection writing is best-effort and must not be treated as canonical persistence.

---

## 6. Configuration

`ctxledger` should use a typed configuration boundary with startup validation.

Recommended environment variables include:

- `CTXLEDGER_DATABASE_URL`
- `CTXLEDGER_HOST`
- `CTXLEDGER_PORT`
- `CTXLEDGER_TRANSPORT`
- `CTXLEDGER_REQUIRE_AUTH`
- `CTXLEDGER_AUTH_BEARER_TOKEN`
- `CTXLEDGER_ENABLE_HTTP`
- `CTXLEDGER_ENABLE_STDIO`
- `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS`
- `CTXLEDGER_PROJECTION_ENABLED`
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
| `CTXLEDGER_TRANSPORT` | `http` | selects enabled transport mode | `http` for Docker/local deployment; avoid `both` unless explicitly validating non-primary transport behavior | `http` for the `v0.1.0` release posture |
| `CTXLEDGER_ENABLE_HTTP` | derived from transport | enables HTTP transport | keep aligned with `CTXLEDGER_TRANSPORT`; expected `true` for normal local deployment | keep aligned with `CTXLEDGER_TRANSPORT`; expected `true` |
| `CTXLEDGER_ENABLE_STDIO` | derived from transport | enables stdio transport | disable unless explicitly needed for internal development or comparison | usually `false`; not part of the primary `v0.1.0` deployment posture |
| `CTXLEDGER_HOST` | `0.0.0.0` | HTTP bind host | `0.0.0.0` is acceptable in containers/local networks | bind according to network policy, typically behind a reverse proxy |
| `CTXLEDGER_PORT` | `8080` | HTTP listen port | `8080` is a reasonable default | set explicitly to match deployment and proxy routing |
| `CTXLEDGER_HTTP_PATH` | `/mcp` | MCP HTTP endpoint path | keep default unless integration requires a different path | keep stable and document it for proxy configuration |
| `CTXLEDGER_REQUIRE_AUTH` | `false` | requires bearer auth for protected HTTP endpoints | `false` is acceptable for isolated local development; prefer `true` in shared environments | `true` |
| `CTXLEDGER_AUTH_BEARER_TOKEN` | none | expected bearer token when auth is required | set when `CTXLEDGER_REQUIRE_AUTH=true` | required when `CTXLEDGER_REQUIRE_AUTH=true`; inject as a secret |
| `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS` | `true` | controls whether `/debug/*` routes are registered at all | `true` is acceptable for local/operator use | usually `false`; enable only for a clear operational need |
| `CTXLEDGER_PROJECTION_ENABLED` | `true` | enables derived projection writing | `true` unless testing explicitly without projections | set according to operational need; does not replace canonical persistence |
| `CTXLEDGER_LOG_LEVEL` | `info` | log verbosity | `info` or `debug` during development | `info` or stricter, depending on operational policy |

Authentication and debug exposure expectations:

- if `CTXLEDGER_REQUIRE_AUTH=true`, `CTXLEDGER_AUTH_BEARER_TOKEN` must also be set or startup validation fails
- when HTTP bearer authentication is enabled, `/debug/*` follows the same authentication boundary as other protected HTTP endpoints
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
- malformed authentication configuration
- invalid host/port configuration
- invalid debug endpoint exposure configuration

## 6.2 Debug Endpoint Exposure Policy

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
- `workflow_closed_projection_failures`
- `projection_failures_ignore`
- `projection_failures_resolve`

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

The payloads returned by `/debug/*` may reveal details such as:

- enabled transports
- registered HTTP routes such as:
  - `runtime_introspection`
  - `runtime_routes`
  - `runtime_tools`
  - `workflow_resume`
  - `workflow_closed_projection_failures`
  - `projection_failures_ignore`
  - `projection_failures_resolve`
- registered stdio tools
- runtime wiring state

These details are useful for diagnostics but increase observability exposure, so they should be treated as operationally sensitive.

In addition to `/debug/*`, operators should also treat HTTP projection failure action routes as operational mutation surfaces:

- `projection_failures_ignore`
- `projection_failures_resolve`

Operational guidance for these routes:

- protect them with the same bearer-auth boundary as other protected HTTP endpoints
- expose them only to trusted operators or trusted automation
- prefer TLS termination and reverse-proxy access control when the HTTP surface is network-accessible
- require the strict implemented path shape for each action route:
  - `/projection_failures_ignore`
  - `/projection_failures_resolve`
- treat requests using the wrong path shape as invalid route targets that should resolve to `404 not_found` rather than as alternate entry points for the same action
- configure reverse proxies and gateways with exact path matching for these action routes so that unexpected alternate paths do not become accepted mutation entry points
- keep request logging for these routes enabled at the proxy or gateway boundary so operator-triggered lifecycle closures remain observable during incident review
- treat query parameters such as `workspace_id`, `workflow_instance_id`, and optional `projection_type` as operational identifiers that may reveal internal workflow metadata in logs or access traces
- avoid using these routes as general client-facing APIs; they are intended for explicit lifecycle handling of projection failures
- remember that `ignored` closes visibility of an open failure without claiming successful projection repair, while `resolved` should be used only when reconciliation or equivalent recovery evidence exists

Representative reverse-proxy expectations:

- match `projection_failures_ignore` only on `/projection_failures_ignore`
- match `projection_failures_resolve` only on `/projection_failures_resolve`
- apply the same auth, TLS, and trusted-network policy used for other protected operator endpoints
- preserve enough request logging to identify:
  - which action route was called
  - whether auth succeeded or failed
  - which workflow-scoping identifiers were present
  - the response status returned to the caller

Representative reverse-proxy example:

This is a representative Nginx-style example showing exact path matching for the HTTP action routes.  It is intentionally illustrative rather than production-complete.

```/dev/null/nginx.conf#L1-20
location = /projection_failures_ignore {
    proxy_pass http://ctxledger_upstream;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

    # Preserve normal operator-facing request logging.
    access_log /var/log/nginx/ctxledger-action-access.log;
}

location = /projection_failures_resolve {
    proxy_pass http://ctxledger_upstream;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

    # Preserve normal operator-facing request logging.
    access_log /var/log/nginx/ctxledger-action-access.log;
}
```

Representative proxy access-log example:

```/dev/null/log#L1-2
2026-03-12T10:15:30Z proxy=nginx request_id=req_123 remote_addr=10.0.0.12 method=GET path=/projection_failures_ignore query="workspace_id=11111111-1111-1111-1111-111111111111&workflow_instance_id=22222222-2222-2222-2222-222222222222&projection_type=resume_json" auth_result=success upstream_status=404 error_code=not_found
2026-03-12T10:15:30Z proxy=nginx request_id=req_123 error_message="projection failure ignore endpoint requires /projection_failures_ignore" forwarded_host=ctxledger.internal operator_subject=ops-user-7
```

Representative implications of this example:

- exact path matching avoids accidentally accepting alternate action paths such as prefixed or rewritten variants
- operator-facing auth and TLS policy should be applied consistently to both action routes
- access logging should preserve enough request/response visibility for later incident review
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
- `.agent/` path is currently unavailable
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

When HTTP transport is enabled, the expected MCP endpoint is:

- `http://localhost:8080/mcp`

## 9.3 Compose Expectations

A local `docker-compose` setup should provide:

- PostgreSQL service
- `ctxledger` service
- persistent PostgreSQL volume
- port exposure for HTTP MCP access
- environment variable injection

Recommended port exposure:

- PostgreSQL for local debugging if needed
- `ctxledger` HTTP port, typically `8080`

## 9.4 Persistence Expectations

PostgreSQL must use a persistent volume.

Without persistent DB storage, the system would lose canonical workflow state, which violates the core design of `ctxledger`.

---

## 10. Projection Behavior in Deployment

Projection files are derived artifacts, not canonical state.

Standard projection targets are:

- `.agent/resume.json`
- `.agent/resume.md`

## 10.1 Projection Path Policy

Projection output should be restricted to the registered workspace root:

- under `workspace.canonical_path`
- typically inside `.agent/`

If `.agent/` does not exist, it may be created automatically.

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
- `.agent/resume.*` may lag behind canonical state
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
- HTTP MCP access at `http://localhost:8080/mcp` in local development

The most important deployment property is not simply that the service starts, but that:

- workflow state survives restart
- resume can be reconstructed from PostgreSQL
- canonical state is never confused with derived files
- operational problems remain diagnosable