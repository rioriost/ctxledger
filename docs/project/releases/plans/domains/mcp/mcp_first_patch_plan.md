# MCP First Patch Plan

## 1. Purpose

This document defines the **first implementation patch** for the MCP transport rewrite in `ctxledger`.

It is intentionally narrow.

The goal of this first patch is **not** to complete MCP `2025-03-26` compliance.
The goal is to create the first safe refactor step that:

- reduces coupling inside `src/ctxledger/server.py`
- preserves existing business behavior
- prepares the repository for a real Streamable HTTP transport rewrite
- avoids deepening the current custom `/mcp` transport path

This patch should be small enough to review safely, while still moving the codebase in the correct architectural direction.

---

## 2. Position in the Overall Rewrite

This patch is the first concrete implementation step implied by:

- `docs/specification.md`
- `docs/plans/mcp_2025_03_26_compliance_remediation_plan.md`
- `docs/plans/mcp_2025_03_26_conformance_audit.md`
- `docs/plans/mcp_transport_rewrite_decision_memo.md`
- `docs/plans/mcp_transport_rewrite_execution_plan.md`
- `docs/plans/mcp_transport_cutover_checklist.md`
- `docs/plans/mcp_module_split_proposal.md`

The broader rewrite says:

- replace the current custom HTTP MCP transport
- preserve transport-agnostic workflow logic
- move MCP concerns out of `server.py`

This first patch begins that process by extracting **stable, low-risk MCP assets** first.

---

## 3. Patch Objective

The first patch should do exactly this:

1. create the new MCP package scaffold
2. extract MCP tool schema definitions from `server.py`
3. extract transport-neutral MCP tool handler builders from `server.py`
4. extract transport-neutral MCP resource handler builders and URI parsers from `server.py`
5. update `server.py` imports so behavior remains the same
6. avoid changing the current `/mcp` transport semantics in this patch

In short:

> move reusable MCP definitions and business bindings out of `server.py` without yet rewriting the transport layer.

---

## 4. Why This Is the Right First Patch

This is the right first patch because it targets code that is:

- already relatively stable
- highly reusable
- low-risk to extract
- currently mixed into the wrong file
- needed by both current and future transports

It also avoids the biggest risk of an overly ambitious first patch:

- trying to rewrite lifecycle and Streamable HTTP behavior before transport-neutral core is separated

This patch creates a cleaner substrate for later work on:

- lifecycle compliance
- result mapping cleanup
- feature registry
- Streamable HTTP implementation
- stdio decoupling

---

## 5. Explicit Non-Goals

This patch must **not** try to do any of the following:

- rewrite `/mcp` transport behavior
- change `protocolVersion`
- implement `notifications/initialized`
- add GET/SSE handling
- implement session handling
- add `Origin` validation
- rework protocol error semantics
- change docs outside ordinary code comments if avoidable
- remove stdio
- change acceptance claims

Those are later patches.

This patch is a **bootstrap refactor**, not a compliance patch.

---

## 6. Files to Create

The first patch should create these files:

- `src/ctxledger/mcp/__init__.py`
- `src/ctxledger/mcp/tool_schemas.py`
- `src/ctxledger/mcp/tool_handlers.py`
- `src/ctxledger/mcp/resource_handlers.py`

Optional:
- keep `__init__.py` minimal or empty

These are the smallest high-value files from the module split proposal.

---

## 7. Files to Modify

The first patch should modify:

- `src/ctxledger/server.py`

Possibly:
- `tests/test_server.py`

Only if necessary to fix imports or references after extraction.

No broader file changes should be attempted in patch 1.

---

## 8. Detailed Extraction Scope

## 8.1 Extract to `mcp/tool_schemas.py`

Move these definitions out of `server.py`:

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

Also move the schema type if it is practical and low-risk:

- `McpToolSchema`

### Goal
Make schemas independently reusable by future:
- feature registry
- Streamable HTTP transport
- stdio transport
- tests

### Constraints
Do not change the schema content in this patch.
This is a move, not a redesign.

---

## 8.2 Extract to `mcp/tool_handlers.py`

Move these handler-builder functions out of `server.py`:

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

Also move the transport-neutral helper functions they depend on if practical:

- `_parse_required_uuid_argument(...)`
- `_parse_optional_projection_type_argument(...)`
- `_parse_required_string_argument(...)`
- `_parse_optional_string_argument(...)`
- `_parse_optional_dict_argument(...)`
- `_parse_optional_verify_status_argument(...)`
- `_parse_required_workflow_status_argument(...)`
- `_map_workflow_error_to_mcp_response(...)`

### Goal
Make tool business behavior independent from transport implementation details.

### Important caveat
If some helper is still used by non-MCP HTTP routes in `server.py`, leave it in place or re-export carefully.
Do not force a bad split just to maximize movement.

### Constraint
Do not change the returned behavior in this patch unless required to keep imports consistent.

---

## 8.3 Extract to `mcp/resource_handlers.py`

Move these resource-related functions out of `server.py`:

- `parse_workspace_resume_resource_uri(...)`
- `parse_workflow_detail_resource_uri(...)`
- `build_workspace_resume_resource_handler(...)`
- `build_workflow_detail_resource_handler(...)`
- `build_workspace_resume_resource_response(...)`
- `build_workflow_detail_resource_response(...)`

If the direct response builders are only thin wrappers over `CtxLedgerServer`, they may remain in `server.py` and only the parsers/handlers may be moved in patch 1.
Choose the smaller safe move.

### Goal
Separate resource URI logic and resource business binding from transport code.

### Constraint
Do not redesign resource semantics in this patch.

---

## 9. `server.py` After Patch 1

After this patch, `src/ctxledger/server.py` should still contain:

- bootstrap/runtime classes
- `HttpRuntimeAdapter`
- `StdioRuntimeAdapter`
- `CompositeRuntimeAdapter`
- `CtxLedgerServer`
- health/readiness/startup/shutdown
- non-MCP HTTP route handlers
- current custom MCP transport code
- any helpers still shared with non-MCP routes

But it should no longer own:
- tool schema constants
- most tool handler builders
- most resource URI/handler helpers

### Desired effect
`server.py` becomes smaller without yet changing transport behavior.

---

## 10. Import Policy for Patch 1

The first patch should prefer:

- explicit imports from `ctxledger.mcp.tool_schemas`
- explicit imports from `ctxledger.mcp.tool_handlers`
- explicit imports from `ctxledger.mcp.resource_handlers`

Avoid:
- wildcard imports
- circular imports
- making `mcp/__init__.py` a giant re-export layer in patch 1

Keep import surfaces simple.

---

## 11. Testing Strategy for Patch 1

Patch 1 is a refactor-preserving patch.

So the testing goal is:

> behavior should remain unchanged.

Minimum test expectation:

- existing tests should continue to pass without semantic updates

Likely especially relevant:
- `tests/test_server.py`
- `tests/test_cli.py`
- `tests/test_config.py`

If tests refer to moved symbols directly, update imports only.
Do not rewrite expectations unless absolutely necessary.

---

## 12. Review Checklist for Patch 1

Before merging the first patch, verify:

- [ ] new `src/ctxledger/mcp/` package exists
- [ ] schemas are moved out of `server.py`
- [ ] tool handler builders are moved out of `server.py`
- [ ] resource URI/handler logic is moved out of `server.py` where safe
- [ ] no transport behavior changes were introduced accidentally
- [ ] no acceptance claims were changed implicitly
- [ ] imports remain readable and non-circular
- [ ] tests pass without semantic expectation changes

---

## 13. Risks in Patch 1

### Risk 1 — Circular imports
Because handler builders depend on workflow service/domain types.

**Mitigation**
- keep imports explicit
- move only what is cleanly separable
- avoid premature creation of a shared registry module in patch 1

### Risk 2 — Hidden transport coupling in handlers
Some helpers may be more transport-shaped than they look.

**Mitigation**
- if a helper is still too transport-aware, leave it in `server.py` for now
- patch 1 should bias toward safety over purity

### Risk 3 — Over-expanding the patch
It may be tempting to also introduce lifecycle or result-mapping cleanup.

**Mitigation**
- do not do that in patch 1
- stop after extraction and import rewiring

### Risk 4 — Breaking tests by moving public symbols
Some tests may import directly from `ctxledger.server`.

**Mitigation**
- either update tests carefully
- or temporarily re-export moved helpers from `server.py` if needed for stability

---

## 14. If Patch 1 Succeeds, What Comes Next

The next patch after this one should likely be one of:

### Patch 2A
Introduce:
- `mcp/feature_registry.py`
- `mcp/lifecycle.py`

### Patch 2B
Introduce:
- `mcp/result_mapping.py`

### Patch 2C
Start the first real transport rewrite file:
- `mcp/streamable_http.py`

The recommended next step is:

> create `mcp/lifecycle.py` and `mcp/streamable_http.py` scaffolding after stable handler/schema extraction is complete.

---

## 15. Final Recommendation

The first implementation patch should be a **safe extraction patch**.

It should:
- create the MCP package
- move schemas
- move business handler builders
- reduce `server.py` responsibility
- preserve behavior

It should **not**:
- attempt transport compliance yet
- modify `docs/specification.md`
- broaden the patch into a transport rewrite

That makes it the correct bootstrap refactor for the larger MCP transport rewrite.