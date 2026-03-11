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
- documentation updated in:
  - `README.md`
  - `docs/mcp-api.md`

### Notes

- runtime/status inspection is now consistently available from:
  - startup summary output
  - `health()`
  - `readiness()`
  - `/debug/runtime`
  - `/debug/routes`
  - `/debug/tools`
- these surfaces are intended for operational visibility and runtime verification
- they do not replace canonical workflow state access through workflow tools and resources

---