# MCP Module Split Proposal

## 1. Purpose

This document proposes a module split for the MCP transport rewrite in `ctxledger`.

It is intended to support the transition from the current monolithic MCP-related implementation inside:

- `src/ctxledger/server.py`

toward a cleaner structure that can support:

- MCP `2025-03-26`
- Streamable HTTP as the primary transport
- transport-agnostic business logic reuse
- clearer testing boundaries
- safer future maintenance

This proposal is downstream of:

- `docs/specification.md`
- `docs/plans/mcp_2025_03_26_compliance_remediation_plan.md`
- `docs/plans/mcp_2025_03_26_conformance_audit.md`
- `docs/plans/mcp_transport_rewrite_decision_memo.md`
- `docs/plans/mcp_transport_rewrite_execution_plan.md`
- `docs/plans/mcp_transport_cutover_checklist.md`

---

## 2. Core Design Goal

The module split should enforce one architectural rule:

> MCP protocol and transport concerns must be separated from workflow/domain logic.

In practical terms:

- MCP lifecycle and Streamable HTTP behavior should live in dedicated MCP modules
- workflow services and persistence should remain outside MCP transport modules
- tool/resource business handlers should be reusable from multiple transports
- auxiliary HTTP routes should remain outside MCP protocol modules
- tests should be able to target:
  - protocol behavior
  - transport behavior
  - feature binding
  - business logic
  independently

---

## 3. Current Problem

Right now, `src/ctxledger/server.py` mixes too many responsibilities:

- MCP lifecycle dispatch
- HTTP `/mcp` handling
- stdio MCP handling
- workflow HTTP routes
- operator action routes
- debug routes
- runtime composition
- startup/shutdown
- tool/resource handler binding
- tool schema definitions
- serialization helpers
- auth helpers
- status/introspection helpers

This causes several problems:

1. transport rewrite risk is too high
2. protocol compliance is hard to reason about
3. stdio and HTTP assumptions are entangled
4. tests are forced to work through a broad mixed surface
5. future MCP evolution would continue to bloat `server.py`

The split proposed here is designed to remove that pressure.

---

## 4. Proposed Module Layout

This proposal recommends introducing a dedicated MCP subpackage under:

- `src/ctxledger/mcp/`

Proposed modules:

- `src/ctxledger/mcp/__init__.py`
- `src/ctxledger/mcp/protocol_types.py`
- `src/ctxledger/mcp/protocol_errors.py`
- `src/ctxledger/mcp/lifecycle.py`
- `src/ctxledger/mcp/feature_registry.py`
- `src/ctxledger/mcp/tool_schemas.py`
- `src/ctxledger/mcp/tool_handlers.py`
- `src/ctxledger/mcp/resource_handlers.py`
- `src/ctxledger/mcp/result_mapping.py`
- `src/ctxledger/mcp/streamable_http.py`
- `src/ctxledger/mcp/stdio_transport.py`

Optionally, if the rewrite grows:

- `src/ctxledger/mcp/session.py`
- `src/ctxledger/mcp/sse.py`
- `src/ctxledger/mcp/security.py`

The existing `src/ctxledger/server.py` would then shrink and focus on:

- application bootstrap
- runtime composition
- health/readiness
- non-MCP HTTP routes
- shared server lifecycle

---

## 5. Proposed Responsibilities by Module

## 5.1 `mcp/protocol_types.py`

### Purpose
Define MCP-facing transport/protocol data structures that should not live in `server.py`.

### Candidate contents
- MCP result/response containers
- capability structures
- tool/resource registration record shapes
- session-related lightweight types
- SSE event internal shapes if needed

### Why split it
This keeps transport-neutral or protocol-neutral structures out of bootstrap code and avoids ad hoc dict-heavy design.

### Migration targets from current code
Potentially split or replace concepts currently represented by:
- `McpHttpResponse`
- `McpToolResponse`
- `McpResourceResponse`
- `McpToolSchema`
- `RuntimeDispatchResult` (if still useful in a narrower form)

### Notes
This module should contain types only, not behavior-heavy lifecycle logic.

---

## 5.2 `mcp/protocol_errors.py`

### Purpose
Centralize MCP protocol-visible error definitions and mapping policy.

### Candidate contents
- protocol error constructors
- helpers for:
  - invalid request
  - method not found
  - invalid params
  - internal error
- mapping rules for:
  - tool execution failure vs protocol failure
  - resource-not-found semantics
  - unsupported feature semantics

### Why split it
Current local error shaping is mixed into tool helpers and HTTP response logic. This needs a single compliance-oriented authority.

### Migration targets from current code
Likely absorbs or replaces:
- `build_mcp_error_response(...)`
- ad hoc exception-to-JSON-RPC mapping in HTTP and stdio paths
- parts of `_map_workflow_error_to_mcp_response(...)`

### Notes
This module should be spec-oriented, not app-specific in naming or semantics.

---

## 5.3 `mcp/lifecycle.py`

### Purpose
Own MCP `2025-03-26` lifecycle behavior.

### Candidate contents
- initialize request validation
- protocol version negotiation
- capability negotiation rules
- initialized-notification handling
- initialization state transition logic
- pre/post-initialization request gating

### Why split it
Lifecycle is currently one of the clearest non-compliant areas and must not remain embedded in a generic dispatcher.

### Migration targets from current code
The lifecycle parts currently embedded inside:
- `handle_mcp_rpc_request(...)`

### Notes
This should be the single source of truth for:
- allowed request sequencing
- correct method names
- protocol version handling

---

## 5.4 `mcp/feature_registry.py`

### Purpose
Provide a transport-neutral registry of MCP-visible tools and resources.

### Candidate contents
- registration model for tools
- registration model for resources
- lookup by tool name
- lookup by resource URI / matching template
- capability derivation from registered features
- optional pagination helpers

### Why split it
The current stdio runtime adapter acts as an implicit registry. That pattern is useful, but it should not remain tied to stdio.

### Migration targets from current code
Likely absorbs concepts from:
- `StdioRuntimeAdapter`
  - tool/resource registration
  - registered_tools
  - registered_resources
  - tool_schema lookup
- parts of `dispatch_mcp_tool(...)`
- parts of `dispatch_mcp_resource(...)`

### Notes
This registry should be usable by:
- Streamable HTTP transport
- stdio transport
without either transport owning the canonical feature inventory

---

## 5.5 `mcp/tool_schemas.py`

### Purpose
Hold MCP tool schema definitions and serialization helpers.

### Candidate contents
- schema serialization
- all tool schema constants:
  - workspace register
  - workflow start
  - workflow checkpoint
  - workflow resume
  - workflow complete
  - projection failure tools
  - memory tools
- optional pagination-ready list helpers

### Why split it
Tool schemas are one of the more stable reusable assets and should be isolated from transport and bootstrap logic.

### Migration targets from current code
Direct extraction candidates:
- `DEFAULT_EMPTY_MCP_TOOL_SCHEMA`
- `serialize_mcp_tool_schema(...)`
- all `*_TOOL_SCHEMA` constants

### Notes
This module should have no transport logic.

---

## 5.6 `mcp/tool_handlers.py`

### Purpose
Provide transport-neutral MCP tool business handlers.

### Candidate contents
- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_resume`
- `workflow_complete`
- projection failure mutation tools
- memory tools if still exposed

### Why split it
Current tool handlers are good business-layer bindings but are mixed with transport-facing result conventions.

### Migration targets from current code
Direct extraction candidates:
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

### Notes
This module should not decide final JSON-RPC protocol shapes.
It should return transport-neutral results or raise transport-neutral exceptions.

---

## 5.7 `mcp/resource_handlers.py`

### Purpose
Provide transport-neutral MCP resource resolution logic.

### Candidate contents
- workspace resume resource resolution
- workflow detail resource resolution
- URI parsing helpers
- resource read result builders
- optional future resource template support

### Why split it
Resources are currently stronger on stdio but should become a proper reusable feature layer.

### Migration targets from current code
Direct extraction candidates:
- `parse_workspace_resume_resource_uri(...)`
- `parse_workflow_detail_resource_uri(...)`
- `build_workspace_resume_resource_handler(...)`
- `build_workflow_detail_resource_handler(...)`
- `build_workspace_resume_resource_response(...)`
- `build_workflow_detail_resource_response(...)`

### Notes
This module should describe resource behavior independently of whether the caller is stdio or HTTP.

---

## 5.8 `mcp/result_mapping.py`

### Purpose
Map internal business results into MCP-compliant protocol results.

### Candidate contents
- tool success result mapping
- tool execution error mapping
- resource content mapping
- JSON Schema result shaping
- text/resource content item builders
- distinction between:
  - protocol error
  - tool execution error
  - resource-not-found semantics

### Why split it
Current implementation leaks local `ok/result/error` payload conventions into transport behavior. That must be corrected centrally.

### Migration targets from current code
Likely absorbs or replaces:
- `build_mcp_success_response(...)`
- `build_mcp_error_response(...)`
- parts of `_map_workflow_error_to_mcp_response(...)`
- parts of tool/resource read shaping inside `handle_mcp_rpc_request(...)`

### Notes
This module is crucial for eliminating ad hoc result semantics.

---

## 5.9 `mcp/streamable_http.py`

### Purpose
Implement the primary MCP `2025-03-26` Streamable HTTP transport.

### Candidate contents
- `/mcp` endpoint transport logic
- POST request handling
- GET handling
- content negotiation
- SSE stream creation
- request category handling
- optional session behavior
- optional resumability hooks
- origin validation integration
- transport-specific auth integration

### Why split it
This is the core replacement for the current custom HTTP MCP path.

### Migration targets from current code
Direct replacement target:
- `build_mcp_http_handler(...)`

Likely also replaces HTTP-specific MCP parts of:
- `dispatch_http_request(...)`
- `HttpRuntimeAdapter`

### Notes
This module should be the main center of compliance work.

---

## 5.10 `mcp/stdio_transport.py`

### Purpose
Retain stdio as a secondary/supporting MCP transport without letting it define HTTP correctness.

### Candidate contents
- stdio loop
- stdio message parsing
- stdio transport binding to the shared feature registry
- stdio-specific framing rules

### Why split it
stdio may remain useful, but it must stop sharing too much protocol machinery with the new HTTP transport.

### Migration targets from current code
Extraction target:
- `StdioRpcServer`
- stdio-specific runtime behavior from `StdioRuntimeAdapter`

### Notes
This module is optional for release scope, but useful during transition.

---

## 5.11 Optional `mcp/session.py`

### Purpose
Encapsulate Streamable HTTP session management if `Mcp-Session-Id` is implemented.

### Candidate contents
- secure session ID generation
- session store abstraction
- session expiration / termination
- request validation against session state

### Why split it
If sessions are added, they should not bloat the main transport module.

### Notes
Only create if the implementation actually adopts session support.

---

## 5.12 Optional `mcp/sse.py`

### Purpose
Encapsulate SSE event production and stream behavior.

### Candidate contents
- SSE event formatting
- event ID assignment
- resumability hooks
- stream-closing policy helpers

### Why split it
Streamable HTTP behavior can get noisy quickly. This keeps HTTP transport readable.

### Notes
Only create if SSE support is substantial enough to justify separation.

---

## 5.13 Optional `mcp/security.py`

### Purpose
Hold MCP-transport-specific security helpers.

### Candidate contents
- `Origin` validation
- transport auth boundary helpers
- localhost / binding posture checks if needed

### Why split it
Security requirements are explicit in the transport spec and should not be hidden in ad hoc handler code.

---

## 6. What Stays Outside the MCP Package

The following should stay outside `src/ctxledger/mcp/`.

## 6.1 `src/ctxledger/server.py`
Should remain responsible for:
- bootstrap
- runtime composition
- health/readiness
- startup/shutdown
- non-MCP HTTP route registration
- app-level wiring

## 6.2 `src/ctxledger/workflow/service.py`
Should remain the main workflow domain/application service.

## 6.3 `src/ctxledger/db/...`
Should remain persistence infrastructure.

## 6.4 `src/ctxledger/memory/service.py`
Should remain memory-domain/application logic.

## 6.5 Auxiliary HTTP routes
These should remain non-MCP:
- workflow read routes
- projection failure action routes
- debug routes

They may still be registered from `server.py` or another non-MCP HTTP routes module.

---

## 7. Proposed Near-Term Refactor Sequence

This is the recommended module split order.

### Step 1
Create `src/ctxledger/mcp/tool_schemas.py`
- move schema constants first
- low risk
- high reuse

### Step 2
Create `src/ctxledger/mcp/tool_handlers.py`
- extract business handlers
- keep result conventions temporarily if needed
- decouple from HTTP transport next

### Step 3
Create `src/ctxledger/mcp/resource_handlers.py`
- extract URI parsing and resource assembly

### Step 4
Create `src/ctxledger/mcp/feature_registry.py`
- move tool/resource registration inventory out of stdio runtime

### Step 5
Create `src/ctxledger/mcp/lifecycle.py`
- isolate initialization/version/capabilities logic

### Step 6
Create `src/ctxledger/mcp/result_mapping.py`
- eliminate transport-facing use of current local `ok/result/error` conventions

### Step 7
Create `src/ctxledger/mcp/streamable_http.py`
- implement new HTTP transport against extracted core

### Step 8
Create `src/ctxledger/mcp/stdio_transport.py`
- rebind stdio to extracted registry/handlers if still needed

### Step 9
Shrink `server.py`
- remove old MCP transport logic
- keep bootstrap and non-MCP routes only

---

## 8. Suggested Import Direction

To keep boundaries clean, dependency direction should look like this:

- `streamable_http.py`
  - depends on `lifecycle.py`
  - depends on `feature_registry.py`
  - depends on `result_mapping.py`
  - depends on auth/security helpers
- `stdio_transport.py`
  - depends on `feature_registry.py`
  - depends on `result_mapping.py`
- `feature_registry.py`
  - depends on `tool_schemas.py`
  - depends on extracted tool/resource handlers
- `tool_handlers.py`
  - depends on workflow/memory services
- `resource_handlers.py`
  - depends on workflow service / serializers
- `server.py`
  - depends on MCP modules for transport/runtime wiring
  - depends on non-MCP route handlers
  - must not re-embed protocol logic

This avoids circular ownership.

---

## 9. Anti-Patterns to Avoid During the Split

1. creating `mcp_http.py` but leaving all lifecycle logic in `server.py`
2. moving code without reducing responsibility coupling
3. letting `stdio_transport.py` remain the implicit canonical feature registry
4. keeping `build_mcp_success_response(...)` style local envelopes as final protocol result model
5. using a new module split to cosmetically reorganize old non-compliant transport behavior
6. mixing workflow-specific HTTP routes into MCP transport modules

---

## 10. Minimal First Split Recommendation

If the team wants the smallest useful first refactor, start with exactly these files:

- `src/ctxledger/mcp/tool_schemas.py`
- `src/ctxledger/mcp/tool_handlers.py`
- `src/ctxledger/mcp/resource_handlers.py`
- `src/ctxledger/mcp/streamable_http.py`

This gives the highest leverage because it:

- preserves reusable business logic first
- creates a real place to build the compliant HTTP transport
- starts shrinking `server.py` immediately

After that, add:

- `feature_registry.py`
- `lifecycle.py`
- `result_mapping.py`

---

## 11. Recommended End State for `server.py`

After the split, `src/ctxledger/server.py` should no longer be the place where MCP protocol behavior is defined.

It should ideally contain only:

- app bootstrap objects
- health/readiness
- workflow HTTP route builders
- debug route builders
- operator route builders
- runtime composition
- server startup/shutdown

And should no longer contain:

- MCP lifecycle dispatch
- MCP protocol version negotiation
- current custom `/mcp` request parsing
- stdio protocol loop
- MCP feature registry authority
- transport-facing tool/resource protocol shaping

---

## 12. Final Recommendation

The recommended module split is:

- **create a dedicated `ctxledger.mcp` package**
- **move schemas, handlers, lifecycle, result mapping, and transport into it**
- **leave `server.py` as bootstrap + non-MCP HTTP orchestration**
- **treat `streamable_http.py` as the primary compliance work surface**

This is the cleanest path to making the MCP transport rewrite manageable without rewriting the workflow system itself.