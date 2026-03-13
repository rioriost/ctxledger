# Changelog

All notable changes to `ctxledger` are documented in this file.

The project currently follows a lightweight, human-maintained changelog style.

---

## [Unreleased]

### Added

- runtime introspection summary for active transports, including:
  - transport name
  - registered HTTP routes
  - registered MCP tools
- HTTP debug endpoint `/debug/runtime` for transport-level runtime inspection
- HTTP debug endpoint `/debug/routes` for route-only runtime inspection
- HTTP debug endpoint `/debug/tools` for tool-only runtime inspection
- `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS` configuration for controlling whether `/debug/*` routes are registered
- `.env.example` for local HTTP deployment defaults
- `.env.production.example` for production-like HTTP deployment defaults with bearer auth enabled and debug endpoints disabled
- `docs/SECURITY.md` covering:
  - bearer authentication posture
  - `/debug/*` exposure guidance
  - TLS / reverse proxy recommendations
  - secret-handling expectations
  - current security limitations
- startup stderr runtime summary output including:
  - overall health status
  - readiness status
  - runtime wiring summary
  - MCP endpoint for the HTTP runtime
- test coverage for:
  - runtime introspection serialization
  - runtime debug endpoint handlers
  - route and tool dispatch for debug surfaces
  - health/readiness runtime summaries
  - startup runtime summary output
  - debug endpoint auth and registration behavior
- projection failure lifecycle support, including:
  - `retry_count` on projection failure records
  - failure `status` visibility in resume warning metadata
  - `ignore_resume_projection_failures(...)` for explicitly closing open projection failures without treating them as successful projection recovery
- closed projection failure read-side exposure, including:
  - `get_closed_failures_by_workflow_id(...)` on projection failure repositories
  - `WorkflowResume.closed_projection_failures`
  - `workflow_resume` / CLI JSON output exposing closed failure history
  - CLI text output section for closed projection failures
  - warning differentiation between `ignored_projection_failure` and `resolved_projection_failure`
  - closed failure warning details including:
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
- documentation updates for projection failure lifecycle behavior in:
  - `docs/architecture.md`
  - `docs/workflow-model.md`
  - `README.md`
  - `docs/mcp-api.md`
  - `docs/specification.md`
  - `docs/SECURITY.md`
  - `docs/deployment.md`
  - including clearer operator-handling semantics for `ignored` versus `resolved` closure
  - including representative operator action surface design for explicit `ignored` / `resolved` lifecycle mutation
  - including HTTP action request examples for auth-enabled and auth-disabled operation
  - including representative `404 not_found` response examples for invalid HTTP action route path shapes
  - including representative edge/proxy logging examples for HTTP projection failure action routes
  - including operational cautions and deployment guidance for HTTP projection failure action routes
- test coverage for:
  - repeated projection failures incrementing `retry_count`
  - ignored projection failures disappearing from open failure warnings
  - resume warning metadata exposing `retry_count` and failure `status`
  - HTTP projection failure action routes, including:
    - bearer-auth enforcement
    - validation errors
    - server-not-ready behavior
    - success payloads for `projection_failures_ignore` and `projection_failures_resolve`
    - handler-level service error mapping coverage
    - handler-level invalid path coverage for strict action route path shapes

### Changed

- `health()` now includes `details["runtime"]` so liveness responses expose current runtime wiring
- `readiness()` now includes `details["runtime"]` across all branches, including:
  - `not_started`
  - `ready`
  - database failure states
  - schema failure states
- HTTP runtime adapter registration now includes:
  - `runtime_introspection`
  - `runtime_routes`
  - `runtime_tools`
  - `workflow_resume`
  - `workflow_closed_projection_failures`
  - `projection_failures_ignore`
  - `projection_failures_resolve`
- `/debug/*` routes now follow the same bearer-auth boundary as other protected HTTP endpoints when HTTP auth is enabled
- `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS=false` now removes `/debug/*` from HTTP route registration entirely rather than relying on handler-level fallback behavior
- documentation updated in:
  - `README.md`
  - `docs/deployment.md`
  - `docs/SECURITY.md`
  - `docs/mcp-api.md`
  - `docs/specification.md`
  - `docs/workflow-model.md`
  - `docker/docker-compose.yml`
- projection failure warnings are now emitted only when a projection has open failures, rather than for every projection whose status is merely `failed`
- closed projection failure history is now exposed separately from open failure reads
- HTTP projection failure action handlers now require strict path shapes:
  - `/projection_failures_ignore`
  - `/projection_failures_resolve`
  - unexpected action paths return `404 not_found`
- resume surfaces now distinguish:
  - `open_projection_failure`
  - `ignored_projection_failure`
  - `resolved_projection_failure`
- repeated projection failures for the same projection type now preserve failure-by-failure visibility instead of behaving like a single unresolved flag

### Notes

- the repository now also evidences a minimal HTTP MCP path at `/mcp`, including:
  - `initialize`
  - `tools/list`
  - `tools/call`
- current closeout framing should treat that minimal HTTP MCP path as proven, while still distinguishing it from broader protocol-scope claims that may need additional verification
- runtime/status inspection is now consistently available from:
  - startup summary output
  - `health()`
  - `readiness()`
  - `/debug/runtime`
  - `/debug/routes`
  - `/debug/tools`
- `/debug/*` is intended for operational visibility and runtime verification, not general client use
- production-oriented guidance now recommends:
  - `CTXLEDGER_REQUIRE_AUTH=true`
  - `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS=false`
  - TLS termination and reverse-proxy deployment
- local-oriented guidance now keeps auth disabled and debug endpoints enabled by default in sample configuration
- these surfaces do not replace canonical workflow state access through workflow tools and resources
- projection failure lifecycle now distinguishes:
  - projection status such as `failed`
  - failure lifecycle state such as `open`, `resolved`, or `ignored`
- closed projection failure history is now readable through dedicated read-side accessors, resume surfaces, and the dedicated HTTP endpoint `/workflow-resume/{workflow_instance_id}/closed-projection-failures`
- a projection may remain in `failed` status even when `open_failure_count == 0`
- ignored projection failures remain in canonical history but are no longer surfaced as `open projection failure` warnings
- resolved and ignored closed failures are both retained in history, but are distinguished by lifecycle status and warning code
- operator-driven closure semantics are now documented more explicitly:
  - `resolved` indicates successful reconciliation or equivalent recovery evidence
  - `ignored` indicates visibility/handling closure without claiming successful projection repair
- operator action surfaces are now documented as implemented across both MCP and HTTP route surfaces:
  - `projection_failures_ignore`
  - `projection_failures_resolve`
  - HTTP docs now describe query-parameter request shape using `workspace_id`, `workflow_instance_id`, and optional `projection_type`
  - HTTP docs now include representative request examples for both auth-enabled and auth-disabled operation
  - HTTP docs now include representative success response, validation error, and invalid-path `404 not_found` response examples
  - security and deployment docs now describe operator-only handling expectations for these mutation routes
  - security docs now include a representative edge logging example for invalid-path and other operator-route outcomes
  - deployment docs now include a representative proxy access-log example for invalid-path and related operator-route outcomes
  - action responses preserve history and report `updated_failure_count`
  - the aligned HTTP action route contract is now documented across implementation, tests, API docs, security guidance, deployment guidance, and changelog notes
- HTTP projection failure action route coverage now verifies:
  - bearer-auth enforcement
  - invalid request mapping
  - `server_not_ready` responses
  - successful ignore / resolve dispatch behavior

---