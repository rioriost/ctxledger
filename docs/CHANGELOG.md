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
  - MCP endpoint when HTTP transport is enabled
  - stdio transport indicator when stdio is enabled
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
- documentation updates for projection failure lifecycle behavior in:
  - `docs/architecture.md`
  - `docs/workflow-model.md`
- test coverage for:
  - repeated projection failures incrementing `retry_count`
  - ignored projection failures disappearing from open failure warnings
  - resume warning metadata exposing `retry_count` and failure `status`

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
- `/debug/*` routes now follow the same bearer-auth boundary as other protected HTTP endpoints when HTTP auth is enabled
- `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS=false` now removes `/debug/*` from HTTP route registration entirely rather than relying on handler-level fallback behavior
- documentation updated in:
  - `README.md`
  - `docs/deployment.md`
  - `docs/SECURITY.md`
  - `docs/mcp-api.md`
  - `docker/docker-compose.yml`
- projection failure warnings are now emitted only when a projection has open failures, rather than for every projection whose status is merely `failed`
- repeated projection failures for the same projection type now preserve failure-by-failure visibility instead of behaving like a single unresolved flag

### Notes

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
- a projection may remain in `failed` status even when `open_failure_count == 0`
- ignored projection failures remain in canonical history but are no longer surfaced as `open projection failure` warnings

---