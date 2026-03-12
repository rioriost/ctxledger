# MCP Transport Rewrite Decision Memo

## 1. Purpose

This memo decides how `ctxledger` should proceed with HTTP MCP transport remediation in order to satisfy the repository’s explicit requirement for:

- **MCP 2025-03-26 compatibility**
- **Streamable HTTP as the primary transport**
- interoperability with spec-conforming MCP clients

This memo is downstream of:

- `docs/specification.md`
- `docs/plans/mcp_2025_03_26_compliance_remediation_plan.md`
- `docs/plans/mcp_2025_03_26_conformance_audit.md`

It focuses on one practical decision:

> Should `ctxledger` adapt the current `/mcp` implementation, or replace it with a transport model explicitly designed for MCP 2025-03-26 Streamable HTTP compliance?

---

## 2. Executive Decision

## Decision

`ctxledger` should **replace the current custom HTTP MCP transport layer** rather than continue incrementally extending it.

## Rationale

The current `/mcp` direction appears to be based on:

- a custom JSON-RPC-over-HTTP request handler
- stdio-oriented request dispatch reused for HTTP
- minimal method support (`initialize`, `tools/list`, `tools/call`) without demonstrated Streamable HTTP semantics

That is too far from the required target.

The main gap is not “a few missing methods.”
The main gap is that the current implementation appears to embody the **wrong transport model**.

Therefore the correct strategy is:

- **preserve transport-agnostic application logic**
- **replace the transport-facing HTTP MCP machinery**
- **target MCP 2025-03-26 Streamable HTTP explicitly**
- **treat spec compliance as the design center, not as a later polish step**

---

## 3. Decision Statement

The project should adopt this rule:

> `ctxledger` will not treat a custom JSON-RPC-over-POST `/mcp` endpoint as an acceptable intermediate release target. The primary remote MCP surface must be implemented as a real MCP 2025-03-26 Streamable HTTP server.

This implies:

- no more docs or implementation effort should optimize for “minimal HTTP MCP path”
- no future release evidence should count custom endpoint behavior as MCP compliance
- transport work should be evaluated primarily by client interoperability and spec conformance

---

## 4. What We Are Deciding Between

Three realistic approaches exist.

## Option A — Patch the current HTTP handler incrementally

Meaning:

- keep the current `/mcp` request handler structure
- add missing protocol semantics one by one
- evolve the current custom handler toward compliance

### Advantages
- lower short-term disruption
- preserves current endpoint-local code structure
- may appear faster at first

### Disadvantages
- risks preserving the wrong transport architecture
- encourages “close enough” behavior
- increases complexity as compliance rules are layered onto a non-compliant foundation
- likely produces hidden incompatibilities in:
  - lifecycle
  - SSE behavior
  - session handling
  - error semantics
  - request category handling

### Conclusion
**Rejected**

This option is too likely to create a fragile custom implementation that still fails real-world MCP interoperability.

---

## Option B — Replace the transport layer while preserving application logic

Meaning:

- keep domain/application code that is transport-agnostic
- remove or isolate current custom HTTP MCP request handling
- implement a new HTTP MCP adapter explicitly shaped around:
  - MCP 2025-03-26 lifecycle
  - Streamable HTTP
  - compliant request/response behavior
- rebind existing tool/resource logic into the new adapter

### Advantages
- directly targets the actual requirement
- avoids carrying forward non-compliant transport assumptions
- preserves valuable existing workflow and persistence logic
- creates a cleaner architectural boundary
- reduces long-term maintenance risk

### Disadvantages
- higher short-term implementation cost than superficial patching
- may require temporary duplication while migrating
- demands more disciplined acceptance testing

### Conclusion
**Accepted**

This is the preferred path.

---

## Option C — Keep custom transport but weaken the requirement in surrounding docs

Meaning:

- keep current implementation mostly as-is
- redefine success as a project-local “minimal MCP-like” interface

### Advantages
- shortest apparent path to local closure

### Disadvantages
- directly conflicts with `docs/specification.md`
- violates the repository contract
- breaks the expectation of MCP client/server interoperability
- creates long-term trust and maintenance problems

### Conclusion
**Explicitly forbidden**

This option must not be used.

---

## 5. Final Chosen Approach

The chosen approach is:

## **Transport rewrite at the HTTP MCP boundary, with reuse of transport-agnostic core logic**

In practical terms:

1. preserve workflow service logic
2. preserve resource assembly logic
3. preserve validation helpers where transport-neutral
4. preserve tool/resource schemas where compatible
5. replace current custom `/mcp` transport semantics
6. rebuild `/mcp` as a spec-conforming Streamable HTTP MCP endpoint
7. validate behavior using protocol-oriented tests

---

## 6. Reuse vs Rewrite Boundary

## 6.1 Preserve

The following should be treated as reusable unless a concrete protocol mismatch forces change.

### Domain and application logic
- workflow service operations
- workspace registration logic
- workflow start/checkpoint/resume/complete logic
- projection failure lifecycle logic
- canonical persistence logic
- read-model assembly logic

### Persistence and repository layer
- PostgreSQL repositories
- unit-of-work / transaction orchestration
- serialization of canonical workflow data
- projection state and failure persistence

### Tool/resource business handlers
Where the logic is transport-neutral:
- input validation helpers
- structured response assembly helpers
- resource URI parsing
- domain error classification inputs

### Non-MCP HTTP routes
These are not MCP transport and can remain separately implemented:
- workflow-specific HTTP read routes
- projection failure operator routes
- debug/runtime inspection routes

They should remain clearly separated from MCP transport logic.

---

## 6.2 Rewrite or Isolate

The following should be treated as suspect and likely replaced.

### Custom HTTP `/mcp` request handler
Any implementation that:
- reads one JSON body
- dispatches directly through a local method switch
- returns ad hoc JSON-RPC responses
without Streamable HTTP semantics

### Shared stdio/HTTP request dispatcher assumptions
If HTTP currently reuses logic originally designed around:
- newline-delimited stdio messages
- stdio lifecycle assumptions
- stdio response timing rules

that coupling should be removed.

### Lifecycle method handling
Especially:
- `initialize`
- `initialized` / `notifications/initialized`
- capability advertisement
- request gating before initialization completion

### Error translation layer
Particularly where current behavior may:
- collapse tool execution failures into protocol errors
- collapse protocol validation failures into local custom errors
- return payloads that are JSON-RPC-like but not MCP-correct

### Transport-specific connection/session behavior
Especially:
- GET handling
- SSE support
- session ID handling
- resumability behavior if implemented
- request category behavior (`requests` vs `notifications` vs `responses`)

---

## 7. Architectural Direction After the Rewrite

The desired post-remediation structure is:

### Transport layer
A dedicated MCP HTTP adapter responsible for:
- MCP 2025-03-26 lifecycle
- Streamable HTTP request handling
- GET / POST behavior
- SSE behavior where required
- session handling if used
- protocol-visible error semantics
- capability negotiation

### Application binding layer
A thin adapter responsible for:
- mapping protocol operations onto internal tool/resource handlers
- preserving domain-neutral request validation
- shaping tool/resource results into spec-compliant MCP responses

### Domain / persistence core
Unchanged in principle:
- workflow orchestration
- resource assembly
- PostgreSQL-backed canonical state
- projection lifecycle logic

This keeps the transport rewrite contained.

---

## 8. Why Incremental Patching Is the Wrong Choice

The strongest reason to reject incremental patching is this:

The current problem is not that `/mcp` is missing a few fields.

The problem is that the implementation appears to have started from the assumption:

- “we need an endpoint that responds to MCP-like methods”

But the real requirement is:

- “we need a spec-conforming MCP server transport”

Those are not the same thing.

A custom endpoint can accidentally pass local tests for:
- `initialize`
- `tools/list`
- `tools/call`

while still failing:
- lifecycle correctness
- session behavior
- GET/SSE behavior
- content negotiation
- notifications naming
- protocol-version negotiation
- real client interoperability

Once that mismatch exists at the transport boundary, incremental patching tends to accumulate exceptions rather than produce compliance.

---

## 9. Target Properties of the Replacement Transport

The replacement `/mcp` transport should satisfy all of the following.

## 9.1 Lifecycle correctness
- `initialize` is first
- initialize is not batched
- protocol version negotiation is correct
- `notifications/initialized` is handled correctly
- behavior before/after initialization follows the spec

## 9.2 Streamable HTTP correctness
- a single MCP endpoint path
- correct POST behavior
- correct GET behavior
- correct content negotiation
- SSE support where required by the transport model
- correct status behavior for notifications / responses / requests

## 9.3 Capability correctness
- advertised capabilities match actual features
- unsupported features are omitted or represented honestly
- tools/resources capability structure matches MCP 2025-03-26

## 9.4 Tool correctness
- `tools/list` uses compliant response semantics
- pagination support exists if required by the spec
- `tools/call` distinguishes:
  - protocol errors
  - tool execution errors

## 9.5 Resource correctness
- required resources are discoverable
- resource listing/reading semantics are compliant
- optional resource features are either correctly implemented or honestly unsupported

## 9.6 Security correctness
- `Origin` validation
- proper authentication behavior
- clear local vs production binding posture

---

## 10. Implementation Recommendation on Runtime Strategy

The preferred implementation bias is:

> Use the thinnest possible custom code at the protocol layer.

That means:

- if a compliant MCP runtime/library can safely own the Streamable HTTP transport semantics, prefer that
- keep custom code focused on:
  - workflow logic
  - tool/resource binding
  - domain validation
  - persistence
- avoid re-implementing transport semantics manually unless unavoidable

This is not mandatory in a package-selection sense, but it is the right engineering posture.

---

## 11. Migration Plan Shape

The rewrite should proceed in this order.

### Step 1
Freeze any further investment in the current custom `/mcp` transport logic.

### Step 2
Extract or isolate reusable transport-agnostic logic:
- tool handlers
- resource handlers
- schemas
- domain validation
- serialization helpers

### Step 3
Introduce a new compliant MCP HTTP transport adapter.

### Step 4
Bind required workflow tools into the new adapter:
- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_resume`
- `workflow_complete`

### Step 5
Bind required resources if they remain in scope.

### Step 6
Add protocol-oriented tests against the new `/mcp`.

### Step 7
Retire or quarantine the old custom HTTP MCP handler.

---

## 12. Temporary Coexistence Policy

During migration, it may be acceptable to temporarily keep both:

- old custom handler code
- new compliant transport adapter

but only under these rules:

1. the old handler must not be treated as release-acceptable
2. release-facing docs must point only to the compliant target
3. migration should be short-lived
4. no new feature work should deepen the old handler

This avoids blocking progress while keeping the architecture honest.

---

## 13. Relationship to stdio

This memo does not require immediate stdio removal.

However, it does require this rule:

- stdio must not define correctness for the primary HTTP transport

So during rewrite:

- stdio may remain as development support
- stdio may remain as a local comparison surface
- but HTTP transport decisions must be driven by MCP 2025-03-26 Streamable HTTP requirements, not by stdio convenience

---

## 14. Risks of the Chosen Approach

### Risk 1 — Short-term implementation cost
The rewrite is more work than patching.

**Mitigation**
- preserve core business logic
- rewrite only transport-facing behavior
- define narrow milestones

### Risk 2 — Feature regression during transport migration
Some currently reachable behaviors may temporarily regress.

**Mitigation**
- build protocol-oriented test coverage first or in parallel
- keep non-MCP HTTP routes independent
- validate each required workflow tool end to end

### Risk 3 — Over-customizing the replacement too
Even the new transport could drift if built around local assumptions.

**Mitigation**
- use the spec as the first review checklist
- validate using transport-level test criteria
- avoid “good enough” JSON-RPC-only acceptance

### Risk 4 — Documentation drifting again
Docs may once again weaken the requirement under pressure.

**Mitigation**
- treat `docs/specification.md` as source contract
- align all other docs after implementation milestones
- reject “minimal path” language for release readiness

---

## 15. Explicit Decision Outcomes

This memo establishes the following project decisions.

### Accepted
- preserve transport-agnostic workflow logic
- replace the current custom HTTP MCP transport behavior
- target real Streamable HTTP compliance
- validate through protocol-oriented tests
- keep `docs/specification.md` unchanged as the contract

### Rejected
- further extending a bespoke `/mcp` RPC endpoint as if it were sufficient
- redefining release success around a custom minimal HTTP MCP flow
- using docs to relax the compliance requirement
- treating local method-level success as transport-level compliance

---

## 16. What This Means for the Next Work Loop

The next work loop should **not** begin by adding more custom endpoint behavior.

It should begin by producing and acting on a transport implementation plan with these concrete questions:

1. What exact current code can be reused untouched?
2. What exact current `/mcp` code must be deleted or isolated?
3. What transport runtime shape will own:
   - GET/POST
   - SSE
   - lifecycle
   - capabilities
   - session behavior
4. What test harness will prove conformance rather than local success?

---

## 17. Final Decision

The final decision of this memo is:

> `ctxledger` should perform a transport-layer rewrite at `/mcp`, preserving domain/application logic where possible, and should not continue evolving the current custom HTTP MCP endpoint as the primary release path.

That is the most direct path to satisfying the repository’s actual requirement:

- **MCP 2025-03-26 compatibility**
- **Streamable HTTP as primary**
- **real remote MCP client interoperability**