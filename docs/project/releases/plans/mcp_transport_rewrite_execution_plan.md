# MCP Transport Rewrite Execution Plan

## 1. Purpose

This document defines the concrete implementation sequence for rewriting the primary MCP transport of `ctxledger` so that `/mcp` becomes a real MCP `2025-03-26` Streamable HTTP server.

This plan is execution-oriented. It follows and operationalizes:

- `docs/specification.md`
- `docs/plans/mcp_2025_03_26_compliance_remediation_plan.md`
- `docs/plans/mcp_2025_03_26_conformance_audit.md`
- `docs/plans/mcp_transport_rewrite_decision_memo.md`

This plan does **not** weaken the requirement. The target remains:

- MCP `2025-03-26` compatibility
- Streamable HTTP as primary transport
- real client interoperability without `ctxledger`-specific behavior

---

## 2. Execution Goal

The goal of this work stream is to replace the current custom `/mcp` transport behavior with a spec-oriented MCP HTTP transport while preserving transport-agnostic business logic wherever possible.

At the end of this plan, the repository should be in a state where:

1. `/mcp` is implemented as the primary MCP endpoint
2. transport behavior is shaped around Streamable HTTP rather than ad hoc JSON-RPC-over-POST
3. lifecycle handling matches MCP `2025-03-26`
4. required workflow tools are discoverable and invokable through the compliant transport
5. required workflow resources are correctly surfaced if they remain in `v0.1.0` scope
6. protocol-oriented tests, not custom local assumptions, define acceptance

---

## 3. Non-Negotiable Constraints

1. `docs/specification.md` must not be edited
2. no new work should deepen the current custom `/mcp` behavior as if it were acceptable
3. transport-specific logic must be kept thin
4. workflow/persistence logic should be preserved unless a concrete protocol mismatch forces change
5. auxiliary HTTP routes must remain distinct from MCP transport behavior
6. release acceptance must not be based on "minimal MCP-like" behavior

---

## 4. Success Criteria

This execution plan is successful only when all of the following are true:

- `/mcp` uses a Streamable HTTP-compatible transport model
- protocol version negotiation is correct for `2025-03-26`
- lifecycle method names and sequencing are correct
- tools are listed and called through spec-compliant behavior
- required resource behavior is either compliant or explicitly out of scope
- transport tests validate spec-oriented behavior
- old custom transport assumptions are removed or isolated
- docs outside `specification.md` no longer understate the requirement

---

## 5. Workstream Overview

This rewrite should be executed through six tightly ordered workstreams:

1. **Freeze and isolate the current custom transport**
2. **Extract reusable transport-agnostic core**
3. **Implement compliant MCP HTTP transport foundation**
4. **Bind tools and resources into the new transport**
5. **Replace custom tests with protocol-oriented tests**
6. **Remove or quarantine obsolete transport code and doc drift**

These workstreams are intentionally ordered so that:

- the wrong abstraction stops growing
- reusable logic is preserved early
- transport semantics are corrected before feature-surface closeout
- test criteria follow the spec instead of local convenience

---

## 6. Workstream 1 — Freeze and Isolate Current Custom Transport

## Goal

Prevent further investment in the current non-compliant `/mcp` implementation while making migration safer.

## Tasks

### 6.1 Mark current transport boundary as transitional
- identify the current `/mcp` HTTP entrypoint
- identify transport-coupled helpers currently shared with stdio
- explicitly label the current custom transport path as transitional in code comments where appropriate

### 6.2 Separate MCP transport code from non-MCP HTTP routes
Create a clear boundary between:
- MCP endpoint behavior at `/mcp`
- workflow-specific HTTP routes
- projection operator routes
- debug routes

### 6.3 Stop broadening the old transport surface
Do not add:
- new custom `/mcp` behavior
- extra bespoke response conventions
- custom local lifecycle shortcuts
- transport-specific special cases for clients

## Deliverable

A repository state where the old `/mcp` path is clearly isolated as migration target, not future foundation.

## Exit Criteria

- engineers can identify the old transport code quickly
- no new feature work depends on the old transport abstraction becoming permanent

---

## 7. Workstream 2 — Extract Reusable Transport-Agnostic Core

## Goal

Preserve valuable existing logic before replacing transport machinery.

## Tasks

### 7.1 Extract reusable tool logic
Keep or refactor into transport-neutral functions:
- workspace registration logic
- workflow start logic
- workflow checkpoint logic
- workflow resume logic
- workflow complete logic
- projection failure action logic
- memory stub logic if still in scope

### 7.2 Extract reusable resource logic
Keep or refactor into transport-neutral functions:
- workspace resume resource assembly
- workflow detail resource assembly
- resource URI parsing helpers
- canonical serialization helpers

### 7.3 Extract reusable validation and mapping logic
Preserve or isolate:
- UUID parsing
- enum parsing
- argument object validation
- workflow error classification
- response content assembly helpers

### 7.4 Preserve persistence and service boundaries
Do not rewrite unless required:
- repositories
- unit-of-work boundaries
- workflow service orchestration
- projection failure lifecycle persistence

## Deliverable

A reusable internal core that can be bound into a new compliant transport.

## Exit Criteria

The majority of business logic can be called without depending on the old `/mcp` transport path.

---

## 8. Workstream 3 — Implement MCP 2025-03-26 HTTP Transport Foundation

## Goal

Create a new transport implementation centered on spec compliance.

## Tasks

### 8.1 Define transport architecture
Introduce a new MCP HTTP transport layer responsible for:
- lifecycle enforcement
- protocol version negotiation
- capability negotiation
- POST handling
- GET handling
- SSE behavior
- session semantics if used
- protocol error handling

### 8.2 Implement correct lifecycle flow
Support:
- `initialize` as first interaction
- proper protocol version response
- correct `notifications/initialized` handling
- correct pre/post-initialization gating

### 8.3 Implement Streamable HTTP endpoint behavior
At `/mcp`:
- support POST requests for client messages
- support GET behavior as required by Streamable HTTP
- support content negotiation
- support JSON and/or SSE response modes where required
- ensure request categories are handled correctly:
  - requests
  - notifications
  - responses

### 8.4 Add origin validation and transport security checks
Implement:
- `Origin` validation for incoming HTTP transport usage
- coherent auth boundary behavior
- clear local-vs-remote binding assumptions

### 8.5 Decide session model explicitly
Choose and implement one of:
- no stateful session ID support initially, while remaining otherwise compliant
- session support with `Mcp-Session-Id`

If sessions are used:
- generate secure IDs
- enforce them correctly
- support invalid/expired session behavior correctly

## Deliverable

A new MCP HTTP transport foundation shaped by the spec instead of by the old custom endpoint.

## Exit Criteria

There is a transport layer that can be evaluated independently from tool/resource business logic.

---

## 9. Workstream 4 — Bind Required Feature Surface

## Goal

Expose the required `v0.1.0` feature surface through the compliant transport.

## Required Workflow Tools

- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_resume`
- `workflow_complete`

## Resource Candidates

From `docs/specification.md`:
- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`
- `memory://episode/{episode_id}`
- `memory://summary/{scope}`

## Tasks

### 9.1 Bind tools/list
Ensure `tools/list`:
- advertises required tools
- uses correct JSON Schema shape
- supports pagination if required
- exposes honest capability surface

### 9.2 Bind tools/call
Ensure `tools/call`:
- routes to transport-neutral business handlers
- distinguishes protocol errors from execution errors
- returns content in spec-compatible result shape
- sets `isError` correctly for execution failures

### 9.3 Bind resource listing and reading
If resources remain in `v0.1.0` scope:
- implement `resources/list`
- implement `resources/read`
- add pagination where applicable
- ensure data shape is compliant

### 9.4 Decide treatment of currently partial memory surface
For memory tools/resources:
- either expose correctly as partial/stubbed but honest
- or explicitly keep out of required closeout surface

### 9.5 Keep non-MCP routes independent
Do not mix compliant MCP transport logic with:
- `/workflow-resume/...`
- `/projection_failures_ignore`
- `/projection_failures_resolve`
- `/debug/...`

## Deliverable

A compliant MCP feature surface over the new `/mcp`.

## Exit Criteria

A spec-oriented client can discover and use the required workflow features through the MCP endpoint itself.

---

## 10. Workstream 5 — Replace Local Tests with Protocol-Oriented Tests

## Goal

Make the spec, not the old custom endpoint behavior, the source of truth for acceptance.

## Tasks

### 10.1 Add lifecycle tests
Test:
- `initialize` first
- initialize not batched
- correct version negotiation
- required initialize payload handling
- `notifications/initialized`

### 10.2 Add transport tests
Test:
- POST request categories
- GET behavior
- content negotiation
- SSE behavior if implemented
- 202 behavior where required
- session behavior if implemented
- origin validation behavior
- auth boundary behavior

### 10.3 Add tools tests
Test:
- `tools/list`
- pagination if required
- required workflow tools visible
- required workflow tools callable
- protocol errors vs execution errors

### 10.4 Add resources tests
If resources are in scope, test:
- `resources/list`
- `resources/read`
- resource error behavior
- required workflow resource coverage

### 10.5 Add interoperability-oriented smoke tests
Where practical, add tests that approximate real client expectations rather than internal assumptions.

### 10.6 Demote or remove misleading tests
Review current tests that:
- encode custom local `/mcp` assumptions
- treat ad hoc JSON-RPC responses as sufficient proof
- imply compliance from method availability alone

Update or remove them as needed.

## Deliverable

A protocol-oriented transport test suite.

## Exit Criteria

The test suite would fail a custom MCP-like endpoint even if it answered the right method names.

---

## 11. Workstream 6 — Remove or Quarantine Obsolete Code and Drift

## Goal

Prevent the old transport model from continuing to distort implementation or documentation.

## Tasks

### 11.1 Remove or quarantine old `/mcp` custom transport code
After migration:
- delete obsolete custom transport code
or
- isolate it clearly outside the release path if temporarily retained

### 11.2 Re-evaluate stdio
Decide whether stdio should:
- remain as development-only support
- remain in tests only
- be partially retained
- be removed from the release path

### 11.3 Correct docs outside `specification.md`
Align:
- `README.md`
- `docs/mcp-api.md`
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/CHANGELOG.md`
- `docs/imple_plan_review_0.1.0.md`
- `docs/v0.1.0_acceptance_evidence.md`

### 11.4 Remove forbidden framing
Eliminate release-facing language such as:
- "minimal MCP path is enough"
- "custom HTTP MCP surface is acceptable"
- "MCP-like HTTP transport"

## Deliverable

A repository whose implementation and docs point at one target only: real MCP compliance.

## Exit Criteria

There is no remaining ambiguity about what `/mcp` is supposed to be.

---

## 12. Concrete Milestone Plan

## Milestone 0 — Freeze
- isolate current transport code
- stop adding custom `/mcp` behavior

## Milestone 1 — Core extraction
- transport-neutral handlers isolated
- reusable schemas/serializers isolated

## Milestone 2 — HTTP transport skeleton
- new transport boundary exists
- lifecycle scaffolding exists
- GET/POST model exists

## Milestone 3 — Lifecycle compliance
- correct version negotiation
- correct initialized notification handling
- capability advertisement aligned

## Milestone 4 — Tool compliance
- `tools/list` compliant
- `tools/call` compliant
- required workflow tools callable

## Milestone 5 — Resource compliance
- required resources handled if in scope

## Milestone 6 — Transport/security hardening
- SSE/session/origin/auth semantics aligned

## Milestone 7 — Test-based acceptance
- protocol-oriented tests pass
- misleading custom tests removed or rewritten

## Milestone 8 — Cleanup and closeout docs
- old transport code retired
- docs aligned
- acceptance re-evaluated

---

## 13. Priority Order Inside the Codebase

If implementation begins immediately, work should happen in this priority order:

1. identify and isolate current `/mcp` transport entrypoint
2. isolate reusable business handlers
3. design new MCP HTTP transport boundary
4. implement lifecycle/version/capability correctness
5. implement Streamable HTTP behavior
6. wire required tools
7. wire required resources if in scope
8. harden error semantics
9. add protocol tests
10. retire old transport code
11. align remaining docs

This order prevents the project from polishing the wrong abstraction.

---

## 14. Risks During Execution

### Risk 1 — Rewriting too much
A transport rewrite may accidentally expand into application rewrites.

**Mitigation**
- preserve business logic first
- keep rewrite scoped to transport semantics

### Risk 2 — Hidden coupling to old dispatcher
Business handlers may rely on old transport assumptions.

**Mitigation**
- extract and test handlers independently early

### Risk 3 — False confidence from old tests
Legacy tests may still pass while compliance remains broken.

**Mitigation**
- add protocol-oriented tests before declaring success

### Risk 4 — Partial transport rewrite accepted too early
The team may be tempted to stop once `initialize/tools/list/tools/call` pass again.

**Mitigation**
- use this plan’s success criteria
- do not treat method-level success as transport compliance

### Risk 5 — stdio distorting HTTP design
The codebase may continue to shape HTTP around stdio convenience.

**Mitigation**
- keep stdio explicitly secondary during rewrite
- review transport decisions from HTTP spec requirements first

---

## 15. What Must Not Happen

The following failure modes must be explicitly avoided:

1. keeping the old `/mcp` handler and merely renaming methods
2. claiming compliance because a local test client can call three methods
3. weakening docs instead of fixing transport behavior
4. mixing debug/operator HTTP routes into MCP acceptance evidence
5. preserving non-compliant lifecycle names or version behavior for convenience
6. treating JSON-RPC shape alone as sufficient evidence of MCP compliance

---

## 16. Immediate Next Implementation Step

The immediate next implementation step should be:

> Produce a code-level transport cutover checklist that names the existing transport-coupled functions/modules to preserve, replace, or delete.

That checklist should directly enumerate:
- old `/mcp` entrypoints
- shared dispatch code
- lifecycle code
- transport-neutral handlers
- response builders
- test files to rewrite first

This is the most useful bridge from planning into code changes.

---

## 17. Final Execution Decision

This execution plan commits the project to the following implementation posture:

- rewrite the HTTP MCP transport layer
- preserve transport-agnostic workflow logic
- validate against MCP `2025-03-26` behavior
- use Streamable HTTP as the primary design target
- do not accept a custom MCP-like HTTP endpoint as the release result

That is the correct implementation path for meeting the repository’s stated contract.