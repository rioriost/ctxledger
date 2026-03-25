# MCP Transport Cutover Checklist

## 1. Purpose

This document is the code-level cutover checklist for replacing the current custom MCP HTTP transport in `ctxledger` with a spec-conforming MCP `2025-03-26` Streamable HTTP transport.

It maps the current server implementation to one of four actions:

- **Preserve**
- **Extract**
- **Replace**
- **Delete / Quarantine**

This checklist is derived from:

- `docs/specification.md`
- `docs/plans/mcp_2025_03_26_compliance_remediation_plan.md`
- `docs/plans/mcp_2025_03_26_conformance_audit.md`
- `docs/plans/mcp_transport_rewrite_decision_memo.md`
- `docs/plans/mcp_transport_rewrite_execution_plan.md`

The goal is to make the transport rewrite operationally actionable at the file/function level.

---

## 2. Cutover Rule

The primary cutover rule is:

> Preserve transport-agnostic workflow and persistence logic. Replace transport-coupled MCP HTTP machinery that currently implements a custom JSON-RPC-over-HTTP behavior at `/mcp`.

In practical terms:

- business logic stays if possible
- protocol dispatch stays only if it can be cleanly refactored into transport-neutral primitives
- current HTTP MCP request handling is not a valid end state
- stdio can remain temporarily, but must not define correctness for HTTP

---

## 3. Primary File Under Cutover

Primary implementation file currently involved:

- `src/ctxledger/server.py`

This file currently mixes:

- HTTP MCP transport behavior
- stdio MCP behavior
- workflow-specific HTTP routes
- operator action routes
- debug routes
- runtime bootstrap
- business-facing handler wiring
- serialization helpers

That means the cutover should not be treated as a single-function patch.
It is primarily a **separation and replacement exercise**.

---

## 4. Classification Legend

### Preserve
Keep as-is or with only minimal compatibility-safe adjustments.

### Extract
Move behind a transport-neutral boundary so it can be reused by the new transport.

### Replace
Re-implement because the current implementation is transport-model-dependent or non-compliant.

### Delete / Quarantine
Remove from the primary release path, or isolate as transitional code only.

---

## 5. Function / Component Cutover Checklist

## 5.1 MCP lifecycle and request dispatch

### `handle_mcp_rpc_request(...)`
**Current role**
- method switch for:
  - `initialize`
  - `initialized`
  - `ping`
  - `shutdown`
  - `exit`
  - `tools/list`
  - `tools/call`
  - `resources/list`
  - `resources/read`

**Problems**
- hardcodes protocol method names in a custom dispatcher
- returns `protocolVersion: 2024-11-05`
- uses `initialized` instead of `notifications/initialized`
- likely conflates stdio and HTTP lifecycle assumptions
- likely treats MCP as simple synchronous local method dispatch

**Action**
- **Replace**

**Cutover note**
- do not evolve this function into the final HTTP transport core
- if parts are reusable, split out only:
  - tool listing assembly
  - tool call routing
  - resource listing assembly
  - resource read routing
- lifecycle and protocol sequencing logic should be rebuilt around MCP `2025-03-26`

---

### `StdioRpcServer`
**Current role**
- newline-delimited stdio JSON-RPC server loop
- reads stdin
- writes stdout
- uses `handle_mcp_rpc_request(...)`

**Action**
- **Delete / Quarantine** for primary HTTP transport work
- **Preserve temporarily** if stdio must remain for development support

**Cutover note**
- do not let stdio transport assumptions shape the HTTP transport rewrite
- if stdio remains, it should consume extracted transport-neutral feature handlers, not define them

---

## 5.2 Runtime adapters

### `HttpRuntimeAdapter`
**Current role**
- placeholder HTTP runtime adapter
- handler registry
- route introspection
- startup/shutdown logging

**Problems**
- explicitly documented as placeholder
- models HTTP as route-name + path + optional body dispatch
- not a real Streamable HTTP transport abstraction

**Action**
- **Replace**

**Cutover note**
- a new HTTP MCP transport adapter should own:
  - lifecycle
  - POST handling
  - GET handling
  - SSE behavior
  - session semantics if used
  - content negotiation
  - origin validation

---

### `StdioRuntimeAdapter`
**Current role**
- stdio-side MCP tool/resource registry
- tool/resource dispatch
- introspection

**Action**
- **Extract** useful parts
- **Preserve temporarily** only as supporting/development surface

**Useful reusable aspects**
- tool registration inventory
- resource registration inventory
- tool schema registry concept

**Non-goal**
- must not remain the hidden canonical runtime that HTTP simply wraps

---

### `CompositeRuntimeAdapter`
**Current role**
- lifecycle aggregation for multiple runtimes

**Action**
- **Preserve**
- possibly **adjust lightly** if runtime composition changes

**Cutover note**
- this is lifecycle plumbing, not protocol behavior
- only adjust if the new MCP HTTP runtime changes composition strategy

---

## 5.3 HTTP MCP response container and dispatch path

### `McpHttpResponse`
**Current role**
- plain response envelope for current custom HTTP handling

**Action**
- **Replace**

**Cutover note**
- current structure is tied to the custom route-dispatch model
- replacement transport may need a different internal response abstraction
- do not assume current shape is stable enough to preserve

---

### `dispatch_http_request(...)`
**Current role**
- route-name-based dispatcher for all HTTP handlers
- special-cases `mcp_rpc`

**Problems**
- treats `/mcp` as just another route handler
- does not represent Streamable HTTP semantics
- couples HTTP to route registry instead of protocol endpoint behavior

**Action**
- **Replace** for MCP transport
- **Preserve conceptually** for non-MCP route dispatch only if still useful

**Cutover note**
- split into:
  - MCP endpoint handling path
  - auxiliary non-MCP HTTP route handling path
- MCP endpoint should no longer be one ordinary route in a generic dispatcher

---

### `build_mcp_http_handler(...)`
**Current role**
- current custom `/mcp` implementation
- checks path
- requires JSON request body
- parses one JSON object
- invokes `handle_mcp_rpc_request(...)`
- returns plain JSON response
- returns 202 for no-response case

**Problems**
- central embodiment of current non-compliant transport model
- no demonstrated GET/SSE Streamable HTTP behavior
- likely incorrect lifecycle semantics
- likely incorrect request-category semantics
- likely incorrect error separation
- no origin validation visible here

**Action**
- **Replace**

**Cutover note**
- this is the single highest-priority cutover target in the code
- do not patch this into compliance incrementally
- rebuild `/mcp` on a new transport abstraction

---

## 5.4 MCP tool/resource dispatch internals

### `dispatch_mcp_tool(...)`
**Current role**
- resolve tool handler by name
- return `McpToolResponse`
- derive status

**Action**
- **Extract**

**Why**
- tool-name-to-handler dispatch is reusable
- status derivation may need adaptation
- current response semantics are not fully MCP-compliant for HTTP transport

**Cutover note**
- preserve core handler lookup
- move protocol result shaping elsewhere

---

### `dispatch_mcp_resource(...)`
**Current role**
- dispatch stdio resource URI requests

**Action**
- **Extract**

**Why**
- URI-to-resource handler matching is reusable
- transport result shaping is not

**Cutover note**
- preserve resource matching logic
- separate transport result formatting from resource resolution

---

## 5.5 Tool success/error helpers

### `build_mcp_success_response(...)`
**Current role**
- creates local payload:
  - `ok: true`
  - `result: ...`

**Action**
- **Extract**, but likely **deprecate** as transport-facing shape

**Problem**
- this is an internal/local shape, not MCP-native result shape
- current HTTP path serializes this into text content

**Cutover note**
- business handlers may still return structured domain results
- but transport adapter should map to proper MCP tool result semantics
- this helper should not remain the externally authoritative shape

---

### `build_mcp_error_response(...)`
**Current role**
- creates local payload:
  - `ok: false`
  - `error: { code, message, details }`

**Action**
- **Extract**, but likely **deprecate** as transport-facing shape

**Problem**
- conflates transport-visible error model with local app-level result model
- MCP distinguishes protocol errors from tool execution errors

**Cutover note**
- split future handling into:
  - protocol error builder
  - tool execution result builder with `isError`
- current helper is useful only as an intermediate application-level construct if explicitly isolated

---

## 5.6 Transport-neutral workflow/resource business logic

These should be preserved wherever possible.

### Preserve / Extract candidates

#### `build_workflow_resume_response(...)`
- **Extract**
- transport-neutral workflow resume assembly wrapper

#### `build_workspace_resume_resource_response(...)`
- **Extract**
- transport-neutral resource assembly logic

#### `build_workflow_detail_resource_response(...)`
- **Extract**
- transport-neutral resource assembly logic

#### `build_closed_projection_failures_response(...)`
- **Extract**
- transport-neutral HTTP read-side helper

#### `build_projection_failures_ignore_response(...)`
- **Extract**
- business logic result wrapper for operator action

#### `build_projection_failures_resolve_response(...)`
- **Extract**
- business logic result wrapper for operator action

---

### URI/path parsing helpers

These are likely reusable.

#### `parse_workspace_resume_resource_uri(...)`
- **Preserve**

#### `parse_workflow_detail_resource_uri(...)`
- **Preserve**

#### `parse_workflow_resume_request_path(...)`
- **Preserve** for auxiliary HTTP route only

#### `parse_closed_projection_failures_request_path(...)`
- **Preserve** for auxiliary HTTP route only

**Cutover note**
- these are not MCP transport logic
- they belong to resource or auxiliary-route handling

---

## 5.7 Auxiliary HTTP routes (non-MCP)

These are not the MCP transport and should not be rewritten as part of MCP protocol machinery.

### `build_workflow_resume_http_handler(...)`
- **Preserve**
- auxiliary workflow HTTP route

### `build_closed_projection_failures_http_handler(...)`
- **Preserve**
- auxiliary workflow HTTP route

### `build_projection_failures_ignore_http_handler(...)`
- **Preserve**
- operator/action route

### `build_projection_failures_resolve_http_handler(...)`
- **Preserve**
- operator/action route

### `build_runtime_introspection_http_handler(...)`
- **Preserve**
- debug route

### `build_runtime_routes_http_handler(...)`
- **Preserve**
- debug route

### `build_runtime_tools_http_handler(...)`
- **Preserve**
- debug route

**Cutover note**
- these should remain clearly non-MCP
- docs and tests must not confuse them with MCP transport evidence

---

## 5.8 Tool handler implementations

These are mostly transport-neutral business bindings and should be retained.

### Extract / Preserve
- `build_resume_workflow_tool_handler(...)`
- `build_workspace_register_tool_handler(...)`
- `build_workflow_start_tool_handler(...)`
- `build_workflow_checkpoint_tool_handler(...)`
- `build_workflow_complete_tool_handler(...)`
- `build_projection_failures_ignore_tool_handler(...)`
- `build_projection_failures_resolve_tool_handler(...)`
- `build_memory_remember_episode_tool_handler(...)`
- `build_memory_search_tool_handler(...)`
- `build_memory_get_context_tool_handler(...)`

**Action**
- **Extract**

**Cutover note**
- keep business behavior
- stop coupling them to the current local `ok/result/error` envelope as the final MCP semantics

---

## 5.9 Schema definitions

These are strong reuse candidates.

### Preserve
- `DEFAULT_EMPTY_MCP_TOOL_SCHEMA`
- `serialize_mcp_tool_schema(...)`
- `WORKSPACE_REGISTER_TOOL_SCHEMA`
- `WORKFLOW_RESUME_TOOL_SCHEMA`
- `WORKFLOW_START_TOOL_SCHEMA`
- `WORKFLOW_CHECKPOINT_TOOL_SCHEMA`
- `WORKFLOW_COMPLETE_TOOL_SCHEMA`
- `PROJECTION_FAILURES_IGNORE_TOOL_SCHEMA`
- `PROJECTION_FAILURES_RESOLVE_TOOL_SCHEMA`
- `MEMORY_REMEMBER_EPISODE_TOOL_SCHEMA`
- `MEMORY_SEARCH_TOOL_SCHEMA`
- `MEMORY_GET_CONTEXT_TOOL_SCHEMA`

**Action**
- **Preserve**

**Cutover note**
- these are among the strongest current assets
- only adjust if exact MCP tool schema or feature-scope decisions require it

---

## 5.10 Auth helpers

### `_extract_bearer_token(...)`
- **Preserve**, but review transport integration assumptions

### `_http_auth_error_response(...)`
- **Preserve** for auxiliary HTTP routes
- **Do not assume reusable as-is for MCP protocol transport**

### `_require_http_bearer_auth(...)`
- **Extract**
- may be reusable, but must be integrated with Streamable HTTP and spec-compliant request handling carefully

**Cutover note**
- MCP transport may need auth checks before lifecycle handling
- current query-param-based token extraction may be acceptable for internal routes but needs explicit review for compliant MCP usage

---

## 5.11 Runtime wiring

### `build_http_runtime_adapter(...)`
**Current role**
- registers:
  - `mcp_rpc`
  - debug handlers
  - workflow routes
  - operator routes

**Action**
- **Replace partially**

**Cutover note**
- split into:
  - MCP transport construction
  - auxiliary HTTP route registration
- `mcp_rpc` registration should no longer point at the old custom transport handler

---

### `build_stdio_runtime_adapter(...)`
**Current role**
- registers stdio resources and tools

**Action**
- **Preserve temporarily**
- possibly **refactor**
- not the primary release path

**Cutover note**
- keep only if development support still needed
- do not let stdio remain the source of truth for MCP feature binding

---

### `create_runtime(...)`
**Action**
- **Adjust**
- new HTTP transport runtime will need to be wired here

**Cutover note**
- the control point is reusable
- the concrete HTTP runtime instance should change

---

### `create_server(...)`
**Action**
- **Preserve**
- maybe light adjustments only

---

### `run_server(...)`
**Action**
- **Preserve**, but **adjust**
- startup path should continue to work
- runtime launch behavior may need updates depending on new HTTP transport runtime shape

---

## 5.12 Introspection and status

These are not MCP transport correctness, but useful operationally.

### Preserve
- `RuntimeIntrospection`
- `collect_runtime_introspection(...)`
- `serialize_runtime_introspection(...)`
- `serialize_runtime_introspection_collection(...)`
- `_print_runtime_summary(...)`

**Cutover note**
- update only as needed to reflect new runtime shape
- these are supporting diagnostics, not acceptance criteria

---

## 5.13 Core server / workflow read-side orchestration

### Preserve
- `CtxLedgerServer`
- `serialize_workflow_resume(...)`
- `serialize_closed_projection_failures_history(...)`
- `serialize_stub_response(...)`
- DB health checker classes/functions
- workflow service factory wiring
- startup/shutdown/health/readiness logic

**Action**
- **Preserve**

**Cutover note**
- these are not the protocol problem
- only change where new transport runtime integration requires it

---

## 6. Test File Cutover Priority

Primary test file likely requiring the most rewrite:

- `tests/test_server.py`

### Sections likely to rewrite first
1. custom `/mcp` lifecycle tests
2. custom `/mcp` tool tests
3. any tests asserting current ad hoc JSON-RPC response shape
4. tests assuming:
   - `initialized`
   - `2024-11-05`
   - POST-only behavior
   - no SSE / GET semantics
   - local error shaping as compliance evidence

### Tests likely reusable with small adaptation
- tool handler business logic tests
- workflow route tests
- operator route tests
- debug route tests
- readiness/health tests
- resource handler business tests
- config tests
- CLI tests

---

## 7. Immediate Code-Level Cutover Sequence

### Step 1
Identify and isolate all code paths that call or depend on:
- `build_mcp_http_handler(...)`
- `handle_mcp_rpc_request(...)`
- `dispatch_http_request(...)` for `mcp_rpc`

### Step 2
Extract transport-neutral tool/resource handler logic into a clear internal layer.

### Step 3
Introduce a new MCP HTTP transport adapter and keep it separate from generic route dispatch.

### Step 4
Bind preserved tool/resource handlers into the new transport.

### Step 5
Rewrite `/mcp` tests around:
- MCP 2025-03-26 lifecycle
- Streamable HTTP behavior
- protocol semantics

### Step 6
Delete or quarantine the old custom `/mcp` handler path.

---

## 8. Delete / Quarantine List

These should not survive as the primary `/mcp` path once cutover is complete:

- current `build_mcp_http_handler(...)`
- current HTTP use of `handle_mcp_rpc_request(...)`
- any current tests treating the custom `/mcp` JSON response model as acceptable MCP compliance
- any docs claiming “minimal path” acceptance

If temporarily retained during migration, they must be clearly marked transitional and excluded from release acceptance reasoning.

---

## 9. Preserve List Summary

These are the strongest preservation candidates:

- workflow service logic
- PostgreSQL repositories and UoW
- workflow/resource assembly helpers
- tool schemas
- tool business handlers
- resource URI parsers
- non-MCP HTTP routes
- startup / health / readiness
- status/introspection utilities

---

## 10. Replacement List Summary

These are the strongest replacement candidates:

- current custom `/mcp` HTTP transport handler
- shared local MCP request dispatcher as final protocol authority
- lifecycle method handling model
- transport-level error model
- HTTP route-style MCP endpoint registration model
- any assumptions that stdio and HTTP can share the same protocol machinery unchanged

---

## 11. Final Cutover Checklist

Before declaring the transport rewrite complete, verify all of the following:

- [ ] current custom `/mcp` path is no longer the primary transport implementation
- [ ] `protocolVersion` is correct for `2025-03-26`
- [ ] `notifications/initialized` is handled correctly
- [ ] lifecycle sequencing is enforced
- [ ] `/mcp` transport behavior matches Streamable HTTP expectations
- [ ] GET behavior is implemented correctly
- [ ] SSE behavior is implemented correctly if required by the chosen design
- [ ] `Origin` validation exists
- [ ] required workflow tools are listed through compliant `tools/list`
- [ ] required workflow tools are invokable through compliant `tools/call`
- [ ] protocol errors and tool execution errors are separated correctly
- [ ] required resources are compliant or explicitly out of scope
- [ ] old custom `/mcp` tests are removed or rewritten
- [ ] old custom `/mcp` code is deleted or quarantined
- [ ] docs outside `specification.md` no longer understate the requirement

---

## 12. Final Note

This checklist intentionally pushes the project away from “small endpoint patching” and toward “clean transport replacement with business-logic reuse.”

That is the only safe path if the repository is to remain honest about:

- MCP `2025-03-26`
- Streamable HTTP as primary
- real MCP client interoperability