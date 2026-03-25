# MCP Second Patch Plan

## 1. Purpose

This document defines the **second implementation patch** for the MCP transport rewrite in `ctxledger`.

Patch 1 is intended to extract stable MCP assets from `src/ctxledger/server.py`, especially:

- tool schemas
- tool handler builders
- resource handler builders and URI parsers

Patch 2 begins the first **real protocol-facing rewrite work**.

Its purpose is to introduce:

- MCP lifecycle scaffolding
- a new Streamable HTTP transport scaffold
- a clean seam between the old custom `/mcp` path and the new compliant transport path

This patch is still intentionally limited. It does **not** attempt to complete full MCP `2025-03-26` compliance in one step.

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

The broad rewrite strategy is:

1. extract transport-agnostic MCP assets
2. introduce new protocol/lifecycle modules
3. introduce a new Streamable HTTP transport boundary
4. rebind required tools/resources
5. replace the old custom `/mcp` path
6. validate with protocol-oriented tests

Patch 2 corresponds to step 2 and the beginning of step 3.

---

## 3. Patch Objective

Patch 2 should do exactly this:

1. create `mcp/lifecycle.py`
2. create `mcp/streamable_http.py`
3. define lifecycle-aware request handling primitives for MCP `2025-03-26`
4. define a new Streamable HTTP transport scaffold for `/mcp`
5. keep the new transport scaffold narrow and incomplete by design
6. avoid binding the entire required feature surface yet
7. avoid deleting the old custom `/mcp` path in this patch

In short:

> introduce the new compliant transport skeleton without yet cutting over the repository to it.

---

## 4. Why This Is the Right Second Patch

Patch 2 is the right next step because Patch 1 should have already separated the reusable MCP business layer from the monolithic server file.

That means Patch 2 can focus on:

- protocol version negotiation
- initialization rules
- correct notification naming
- transport entrypoint structure
- GET/POST scaffold
- future SSE/session/auth/origin hooks

without simultaneously moving large amounts of business code.

This is the first patch where the repository starts to embody the **correct transport model**.

---

## 5. Explicit Non-Goals

Patch 2 must **not** try to finish everything.

It should **not** do the following:

- fully implement all required tools through the new transport
- fully implement all required resources through the new transport
- complete SSE streaming behavior
- complete session management
- fully rewrite all `/mcp` tests
- delete the old custom transport path
- finish stdio decoupling
- change `docs/specification.md`
- weaken the MCP `2025-03-26` requirement

Those are later patches.

Patch 2 is a **transport foundation patch**, not a full cutover patch.

---

## 6. Files to Create

Patch 2 should create:

- `src/ctxledger/mcp/lifecycle.py`
- `src/ctxledger/mcp/streamable_http.py`

Optional, only if needed for clean structure:

- `src/ctxledger/mcp/protocol_errors.py`
- `src/ctxledger/mcp/protocol_types.py`

However, if those optional files would expand the patch too much, they should be deferred.

The core requirement is still just:

- lifecycle scaffold
- Streamable HTTP scaffold

---

## 7. Files to Modify

Patch 2 should modify only what is necessary:

- `src/ctxledger/server.py`
- possibly `src/ctxledger/mcp/__init__.py`
- possibly `tests/test_server.py`

No broad test rewrite should happen here unless it is directly required for the new scaffold to compile and coexist.

---

## 8. `mcp/lifecycle.py` Scope

## 8.1 Purpose

`mcp/lifecycle.py` should become the single place where MCP `2025-03-26` lifecycle semantics begin to live.

Its role in Patch 2 is to define:

- initialization request validation
- protocol version negotiation
- server capability response shaping
- initialized-notification recognition
- minimal initialization state model

It is acceptable for Patch 2 lifecycle logic to be incomplete, as long as it is clearly the new authority.

---

## 8.2 Patch 2 responsibilities

The lifecycle module should at minimum support:

### A. `initialize` request validation
Validate that:
- request method is `initialize`
- params are shaped correctly
- initialize is not treated as a generic local method dispatch

### B. version negotiation scaffold
Support:
- incoming client `protocolVersion`
- response `protocolVersion`
- negotiation hooks for unsupported versions

At minimum, the module should be shaped so that returning the wrong version is no longer hardcoded inside generic dispatch code.

### C. correct initialized notification naming
Recognize:
- `notifications/initialized`

and explicitly stop treating:
- `initialized`

as the final correct lifecycle method name.

### D. initialization state model
Introduce some explicit notion of:
- not initialized
- initialized
- maybe post-initialized / ready

This can be lightweight in Patch 2, but must exist.

---

## 8.3 What `lifecycle.py` should not do yet

Do **not** make Patch 2 lifecycle code responsible for:

- full request routing for all MCP methods
- all capability semantics
- all unsupported-feature handling
- all transport category handling
- all session behavior

Patch 2 should establish the lifecycle boundary, not finish the full protocol implementation.

---

## 9. `mcp/streamable_http.py` Scope

## 9.1 Purpose

`mcp/streamable_http.py` should become the new home for the primary `/mcp` transport.

Its purpose in Patch 2 is to define the **correct transport shape**, even if the behavior is still incomplete.

This module should begin to express that `/mcp` is:

- a single MCP endpoint
- centered on Streamable HTTP
- distinct from generic route-name dispatch
- distinct from the old custom RPC handler

---

## 9.2 Patch 2 responsibilities

Patch 2 should at minimum introduce scaffold-level support for:

### A. MCP endpoint abstraction
Represent `/mcp` as a transport endpoint, not just another route name in a generic dispatcher.

### B. POST handling scaffold
Create the boundary for:
- JSON-RPC messages over POST
- future request category handling
- future content negotiation

It is okay if Patch 2 only supports a minimal internal path for requests while keeping TODOs for complete compliance.

### C. GET handling scaffold
Introduce an explicit GET entrypoint or GET-aware transport branch, even if Patch 2 does not yet provide full SSE support.

This matters because the new transport must be shaped around Streamable HTTP from the start.

### D. lifecycle integration
The transport scaffold should call lifecycle-aware code rather than the old generic `handle_mcp_rpc_request(...)`.

### E. hook points for future compliance
The scaffold should make room for:
- SSE support
- session headers
- origin validation
- auth integration
- request category handling
- 202 handling
- protocol error shaping

---

## 9.3 What `streamable_http.py` should not do yet

Patch 2 should **not** try to fully implement:

- SSE streams
- session IDs
- resumability
- request replay
- full GET stream semantics
- all tool/resource routing
- complete error behavior
- complete header negotiation matrix

Those belong in later patches.

---

## 10. Relationship Between Old and New `/mcp` During Patch 2

Patch 2 should allow temporary coexistence.

That means the repository may temporarily contain:

- the old custom `/mcp` transport path
- the new `mcp/streamable_http.py` scaffold

But this coexistence must follow strict rules:

1. the new transport scaffold is the future direction
2. the old path remains transitional only
3. no new feature work should deepen the old handler
4. release acceptance must still reject the old custom transport
5. code comments should make the status unambiguous

This avoids a dangerous “half migration but old path still looks canonical” situation.

---

## 11. `server.py` Changes in Patch 2

Patch 2 should keep `server.py` mostly stable, but make one important structural move:

> stop treating MCP HTTP behavior as a normal route handler whose semantics are fully defined in `server.py`.

Practical changes may include:

- importing the new lifecycle helpers
- importing the new Streamable HTTP scaffold
- introducing a new runtime/handler wiring path for future `/mcp`
- keeping the old path temporarily behind compatibility wiring if needed

### Important constraint

Patch 2 should **not** try to fully clean `server.py` yet.
It only needs to begin moving the authority for MCP transport and lifecycle out of that file.

---

## 12. Suggested API Shape for the New Modules

Patch 2 should prefer small, explicit entrypoints.

Possible shapes:

### In `mcp/lifecycle.py`
- validate initialize request
- negotiate protocol version
- build initialize response
- recognize initialized notification
- maintain minimal lifecycle state

### In `mcp/streamable_http.py`
- build MCP endpoint handler
- handle POST
- handle GET scaffold
- integrate lifecycle
- delegate business operations later

The exact names can vary, but the shape should communicate ownership clearly.

---

## 13. Testing Strategy for Patch 2

Patch 2 testing should prove the new scaffold exists and is structurally correct, without pretending that full compliance is done.

### Add or update tests for:

#### A. lifecycle basics
- correct expected protocol version path
- correct initialized notification naming
- initialize validation entrypoint exists
- non-initialize-first behavior can be reasoned about

#### B. transport scaffold basics
- `/mcp` is represented through the new transport module
- POST path is handled by the new scaffold
- GET path is at least explicitly recognized
- old route-name-only assumptions are reduced

#### C. non-regression
- unrelated workflow routes still work
- startup/health/readiness are unaffected
- existing extracted handlers still import and function

### Do not yet require:
- full SSE tests
- full session tests
- full protocol-oriented integration suite

Those should wait for the next transport-compliance patch.

---

## 14. Review Checklist for Patch 2

Before merging Patch 2, verify:

- [ ] `mcp/lifecycle.py` exists
- [ ] `mcp/streamable_http.py` exists
- [ ] protocol version handling is no longer hardcoded in the old generic dispatcher as the only authority
- [ ] `notifications/initialized` is introduced as the correct lifecycle name
- [ ] `/mcp` has a new transport scaffold separate from generic route-style logic
- [ ] GET handling is at least explicitly scaffolded
- [ ] no accidental full cutover has happened prematurely
- [ ] old custom `/mcp` code is still clearly transitional
- [ ] unrelated HTTP routes remain stable
- [ ] tests still pass or are updated only as needed for scaffold correctness

---

## 15. Risks in Patch 2

### Risk 1 — Doing too much transport behavior too early
Trying to finish SSE/session/origin/auth in one patch will make the patch too large.

**Mitigation**
- keep this patch scaffold-focused
- reserve deep transport completion for the next patch

### Risk 2 — Fake scaffold with no real ownership transfer
A new file may be created, but `server.py` may still own all real lifecycle logic.

**Mitigation**
- move real authority for initialize/version/initialized naming into `mcp/lifecycle.py`

### Risk 3 — Old custom dispatcher remains the hidden truth
The repository may look cleaner while the old custom dispatcher still defines behavior.

**Mitigation**
- ensure new code path is actually introduced
- avoid purely cosmetic extraction

### Risk 4 — Review confusion due to coexistence
Temporary coexistence may confuse future work.

**Mitigation**
- use explicit comments and narrow transitional wiring
- keep old/new roles clear in code and tests

---

## 16. What Comes After Patch 2

If Patch 2 succeeds, the most natural Patch 3 is:

### Patch 3
**Protocol result and transport compliance expansion**

Likely scope:
- `mcp/result_mapping.py`
- proper protocol vs execution error separation
- `tools/list` and `tools/call` on the new transport
- initial resource surface on the new transport
- stronger protocol tests

After that:

### Patch 4
**Full Streamable HTTP semantics**
- SSE behavior
- request category handling
- 202 behavior
- origin validation
- session model if implemented
- old `/mcp` handler retirement

---

## 17. Recommended Minimal Patch 2 Boundary

To keep Patch 2 reviewable, the best boundary is:

### Must include
- `mcp/lifecycle.py`
- `mcp/streamable_http.py`
- `server.py` import/wiring changes needed to introduce them

### May include
- small protocol error helpers if needed
- tiny protocol types if needed

### Must not include
- full feature registry
- full transport cutover
- full result-mapping rewrite
- full SSE/session behavior
- broad doc rewrites

This keeps the patch both meaningful and safe.

---

## 18. Final Recommendation

Patch 2 should be the first patch that gives the repository a **new transport authority**.

It should:

- establish lifecycle correctness scaffolding
- establish a new Streamable HTTP transport scaffold
- begin shifting `/mcp` ownership away from the old custom handler
- remain intentionally incomplete but directionally correct

That makes it the right second step after the extraction-focused first patch.