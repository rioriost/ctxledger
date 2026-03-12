# MCP Third Patch Plan

## 1. Purpose

This document defines the **third implementation patch** for the MCP transport rewrite in `ctxledger`.

Patch 1 is intended to extract stable MCP assets from `src/ctxledger/server.py`.

Patch 2 is intended to introduce:

- `mcp/lifecycle.py`
- `mcp/streamable_http.py`

as the first new protocol-facing transport scaffold.

Patch 3 is the first patch that should make the new transport meaningfully useful for real MCP feature behavior.

Its purpose is to introduce:

- MCP-compliant result mapping
- required tool binding on the new transport
- initial resource binding on the new transport where appropriate
- protocol-oriented tests that validate the new transport behavior more strictly than the old custom `/mcp` path

This patch still does **not** need to complete every Streamable HTTP requirement. It is the patch where the new transport begins to carry actual MCP feature traffic in a spec-oriented way.

---

## 2. Position in the Overall Rewrite

This patch follows the direction established by:

- `docs/specification.md`
- `docs/plans/mcp_2025_03_26_compliance_remediation_plan.md`
- `docs/plans/mcp_2025_03_26_conformance_audit.md`
- `docs/plans/mcp_transport_rewrite_decision_memo.md`
- `docs/plans/mcp_transport_rewrite_execution_plan.md`
- `docs/plans/mcp_transport_cutover_checklist.md`
- `docs/plans/mcp_module_split_proposal.md`
- `docs/plans/mcp_first_patch_plan.md`
- `docs/plans/mcp_second_patch_plan.md`

The broad rewrite sequence is:

1. extract reusable MCP assets
2. introduce lifecycle and transport scaffold
3. bind actual MCP features through the new transport
4. harden transport semantics
5. retire the old custom `/mcp` path

Patch 3 corresponds to step 3.

---

## 3. Patch Objective

Patch 3 should do exactly this:

1. create `mcp/result_mapping.py`
2. introduce compliant result-shaping for:
   - `tools/list`
   - `tools/call`
   - `resources/list`
   - `resources/read`
3. bind required workflow tools into the new transport
4. bind the initial workflow resource surface into the new transport if in-scope
5. stop relying on the old local `ok/result/error` envelope as the transport-facing MCP result model
6. add protocol-oriented tests for the new feature surface on the new transport
7. keep full SSE/session/origin hardening for later patches

In short:

> Patch 3 should make the new MCP transport feature-capable, while still deferring the deepest transport hardening work.

---

## 4. Why This Is the Right Third Patch

Patch 2 should already have established:

- a new lifecycle authority
- a new Streamable HTTP transport scaffold
- a clear directional shift away from the old custom `/mcp` handler

At that point, the next most valuable step is **not** more skeleton work.

The next valuable step is to make the new transport actually carry:

- tool listing
- tool invocation
- resource listing
- resource reading

in a spec-oriented way.

This is also the patch where the repository begins to stop proving only transport intent and starts proving transport usefulness.

---

## 5. Explicit Non-Goals

Patch 3 must **not** try to finish the entire rewrite.

It should **not** do the following:

- complete full SSE behavior
- complete session management
- implement resumability/redelivery
- complete GET stream semantics
- remove stdio entirely
- delete the old custom `/mcp` path yet
- finish all docs cleanup
- modify `docs/specification.md`
- weaken the MCP `2025-03-26` requirement

Those belong to later patches.

Patch 3 is a **feature binding and result semantics patch**, not the final transport-hardening patch.

---

## 6. Files to Create

Patch 3 should create:

- `src/ctxledger/mcp/result_mapping.py`

Optional, only if Patch 2 did not already create them and they are needed now:

- `src/ctxledger/mcp/protocol_errors.py`
- `src/ctxledger/mcp/protocol_types.py`
- `src/ctxledger/mcp/feature_registry.py`

The only mandatory new file for Patch 3 is still:

- `result_mapping.py`

if feature binding can proceed cleanly with existing extracted modules.

---

## 7. Files to Modify

Patch 3 will likely need to modify:

- `src/ctxledger/mcp/streamable_http.py`
- `src/ctxledger/mcp/lifecycle.py`
- `src/ctxledger/mcp/tool_handlers.py`
- `src/ctxledger/mcp/resource_handlers.py`
- `src/ctxledger/server.py`
- `tests/test_server.py`

Possibly also:

- `src/ctxledger/mcp/tool_schemas.py`
- `src/ctxledger/mcp/__init__.py`

if import wiring or minor schema adjustments are required.

---

## 8. `mcp/result_mapping.py` Scope

## 8.1 Purpose

`mcp/result_mapping.py` should become the single place where internal business results are translated into MCP-facing protocol results.

This is necessary because the current codebase likely still carries local result conventions such as:

- `ok: true`
- `ok: false`
- `result`
- `error`

which are useful internally but are not themselves the final MCP result model.

---

## 8.2 Patch 3 responsibilities

The result mapping module should at minimum support:

### A. Tool success mapping

Map transport-neutral tool outputs into MCP tool results with:

- `content`
- `isError: false` when appropriate

### B. Tool execution error mapping

Map business/tool execution failures into MCP tool results with:

- `content`
- `isError: true`

rather than incorrectly treating them as protocol errors.

### C. Protocol error mapping

Ensure that true protocol failures are still represented as JSON-RPC errors, such as:

- invalid request shape
- unknown method
- invalid params
- unsupported state/lifecycle usage
- unsupported protocol version

### D. Resource result mapping

Map resource read/list results into MCP-compatible response shapes, including:

- `resources`
- `contents`

### E. Content item helpers

Provide helpers for:

- text content items
- resource content items
- future extensibility for image/audio/resource embedding if needed later

---

## 8.3 What `result_mapping.py` should not do

Patch 3 should **not** make `result_mapping.py` responsible for:

- lifecycle sequencing
- session state
- HTTP header negotiation
- SSE event writing
- auth policy
- domain validation rules

It is a mapping layer, not a transport or business-logic layer.

---

## 9. Required Tool Binding Scope

Patch 3 should bind the required workflow tools into the new transport.

## Required workflow tools

- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_resume`
- `workflow_complete`

## Patch 3 requirements

### 9.1 `tools/list`
The new transport should be able to return a compliant `tools/list` result including:

- required workflow tools
- correct `name`
- `description`
- `inputSchema`
- pagination hook support if implemented now or a clear path if deferred very briefly

### 9.2 `tools/call`
The new transport should be able to invoke at least the required workflow tools.

This means the new transport should no longer be “lifecycle-only scaffolding”; it should become a real feature path.

### 9.3 Tool execution error separation
The implementation must clearly separate:

- protocol errors
- tool execution failures

This is one of the main reasons Patch 3 exists.

### 9.4 Memory tools
Memory tools may remain supporting/stubbed, but Patch 3 should decide one of:

- bind them honestly through the new transport as partial/stubbed features
- defer them from the initial new transport feature set while keeping workflow tools primary

The preferred bias is:

- bind required workflow tools first
- bind optional memory tools only if the patch remains clean and low risk

---

## 10. Initial Resource Binding Scope

Patch 3 should make an explicit decision about workflow resource binding on the new transport.

## Candidate workflow resources

- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`

## Patch 3 recommendation

Patch 3 should **attempt** to bind these workflow resources into the new transport if doing so does not materially enlarge the patch.

If the patch would become too large, it is acceptable to do this in Patch 4 instead, but the decision must be explicit in code comments or patch notes.

## Non-goal for Patch 3
Do not try to finish future memory resources:

- `memory://episode/{episode_id}`
- `memory://summary/{scope}`

unless they come almost for free and do not blur the patch boundary.

---

## 11. `streamable_http.py` Changes in Patch 3

Patch 2 should have introduced the new transport scaffold.
Patch 3 is where that transport begins to carry actual feature traffic.

The new transport should now gain support for:

### A. MCP method routing on the new path
At minimum:
- `initialize`
- `notifications/initialized`
- `tools/list`
- `tools/call`

And optionally:
- `resources/list`
- `resources/read`

### B. Correct use of result mapping
The transport should stop serializing local app envelopes directly into ad hoc JSON text payloads.

Instead, it should call `result_mapping.py` to produce spec-oriented responses.

### C. Reduced reliance on the old generic dispatcher
Patch 3 should continue reducing the authority of any old generic MCP dispatcher still living in `server.py`.

It is acceptable if the old path still exists, but the new transport should now have enough logic that the old dispatcher is no longer the only meaningful MCP behavior path.

---

## 12. `server.py` Changes in Patch 3

Patch 3 should keep shrinking `server.py` as the protocol authority.

Practical expectations:

- new transport wiring should point more of `/mcp` behavior through `mcp/streamable_http.py`
- old local result helpers should be used less or become transitional only
- old handler paths may remain temporarily for fallback or coexistence, but should not grow

Patch 3 still does **not** require a full cleanup of `server.py`.
But after this patch, `server.py` should clearly no longer be the primary place where MCP result semantics are defined.

---

## 13. Testing Strategy for Patch 3

Patch 3 is the first patch where protocol-oriented tests need to become more serious.

### Add or update tests for:

#### A. `tools/list` on the new transport
Verify:
- required workflow tools are present
- schema exposure works
- response shape is compliant
- old custom assumptions are not required

#### B. `tools/call` on the new transport
Verify:
- required workflow tools can be called
- success results are mapped correctly
- execution failures use result-level error semantics where appropriate

#### C. Resource behavior if in scope
Verify:
- `resources/list`
- `resources/read`
- workflow resource shape
- not-found behavior

#### D. Lifecycle continuity
Verify:
- initialize first
- correct initialized notification name
- correct protocol version path
- request flow is tied to the new lifecycle authority

#### E. Regression isolation
Verify:
- workflow-specific HTTP routes still work
- debug routes still work
- projection operator routes still work
- startup/health/readiness remain stable

---

## 14. Review Checklist for Patch 3

Before merging Patch 3, verify:

- [ ] `mcp/result_mapping.py` exists
- [ ] local `ok/result/error` envelope is no longer the transport-facing MCP result authority
- [ ] new transport supports `tools/list`
- [ ] new transport supports `tools/call`
- [ ] required workflow tools are bound through the new transport
- [ ] protocol errors and execution errors are separated more cleanly
- [ ] workflow resources are either bound now or explicitly deferred
- [ ] tests validate the new feature surface
- [ ] old custom `/mcp` assumptions are reduced
- [ ] unrelated routes remain stable

---

## 15. Risks in Patch 3

### Risk 1 — Wrong error model survives
The patch may still accidentally flatten execution errors into protocol errors.

**Mitigation**
- make `result_mapping.py` explicit about the distinction
- test both success and execution-failure paths

### Risk 2 — Binding too many optional features
Trying to include all memory tools/resources may expand the patch too much.

**Mitigation**
- prioritize required workflow tools
- keep memory surface optional in this patch

### Risk 3 — Transport scaffold stays too abstract
A patch might introduce result mapping but still route real behavior through old code.

**Mitigation**
- ensure new transport actually owns `tools/list` and `tools/call`
- do not allow purely cosmetic indirection

### Risk 4 — Resource scope ambiguity
Trying to decide all resource questions now may delay progress.

**Mitigation**
- focus on workflow resources first
- explicitly defer broader resource surface if needed

### Risk 5 — Tests still encode old assumptions
Legacy tests may continue to pass while real compliance is not improving enough.

**Mitigation**
- add new tests that assert the new result semantics directly
- review old `/mcp` assertions critically

---

## 16. What Comes After Patch 3

If Patch 3 succeeds, the most natural next patch is:

### Patch 4
**Transport hardening and cutover patch**

Likely scope:
- fuller Streamable HTTP behavior
- GET semantics expansion
- SSE support
- 202 behavior for non-request POST categories
- `Origin` validation
- session model if adopted
- retirement or quarantine of the old `/mcp` custom handler
- stronger protocol-oriented end-to-end tests

Patch 3 should make Patch 4 possible without large business-layer refactors.

---

## 17. Recommended Minimal Patch 3 Boundary

To keep Patch 3 reviewable, the best boundary is:

### Must include
- `mcp/result_mapping.py`
- new transport ownership of `tools/list`
- new transport ownership of `tools/call`
- required workflow tool binding
- protocol-oriented tests for those paths

### May include
- workflow resource binding
- small protocol error helper extraction
- small protocol type extraction if needed

### Must not include
- full SSE implementation
- full session implementation
- old transport deletion
- broad docs rewrite
- stdio removal

This keeps Patch 3 meaningful but still scoped.

---

## 18. Final Recommendation

Patch 3 should be the patch where the new MCP transport stops being mostly a scaffold and starts becoming the real feature path.

It should:

- add result mapping
- bind required workflow tools
- optionally bind initial workflow resources
- add protocol-oriented tests
- continue reducing the authority of the old custom `/mcp` path

That makes it the correct third step in the rewrite sequence.