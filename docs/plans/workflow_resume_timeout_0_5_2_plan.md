# Workflow Resume Timeout 0.5.2 Plan

## 1. Purpose

This document defines the implementation plan for the `0.5.2` milestone.

The goal of `0.5.2` is to eliminate the currently observed `workflow_resume` timeout failure mode and make resume-oriented workflow recovery more reliable for AI agents and other MCP/HTTP clients.

This milestone is a targeted reliability and operability follow-up to `0.5.1`.

It focuses on:

- preventing avoidable `workflow_resume` request timeouts
- making resume lookup behavior more diagnosable
- improving resilience when callers provide the wrong identifier type
- reducing ambiguity for AI agents that follow repository guidance files such as `.rules`
- clarifying the intended resume flow across tools, resources, docs, and operator guidance

`0.5.2` is not a broad feature milestone.

It is a hardening and correctness milestone.

---

## 2. Background

Recent investigation showed that `workflow_resume` can still time out from an MCP client even when the server is otherwise responsive.

A representative symptom pattern is:

1. `workspace_register` responds successfully or returns a normal validation/conflict response
2. `workflow_resume` is called immediately after
3. the request times out rather than returning a normal error payload

This matters because AI agents are expected to use `ctxledger` as the canonical system of record for resumability and workflow continuity.

If `workflow_resume` is unreliable or ambiguous, then:

- workflow continuity degrades
- agents may create duplicate workflows
- operators lose confidence in canonical state recovery
- timeout failures become difficult to distinguish from not-found, bootstrap, or caller-usage issues

Investigation also suggests that some calling patterns may incorrectly pass a `workspace_id` to `workflow_resume`, even though the tool requires a `workflow_instance_id`.

That misuse should not produce ambiguous behavior.

At minimum, it should fail quickly and clearly.

---

## 3. Problem statement

The current problem is likely a combination of two concerns rather than a single defect.

### 3.1 Runtime concern

`workflow_resume` currently assembles a composite response by performing multiple synchronous PostgreSQL lookups in sequence during request handling.

This makes the endpoint sensitive to:

- pool acquisition delay
- blocked or slow queries
- lock contention
- transport-level timeout budgets that are shorter than the total lookup path
- resume payload assembly work that is too tightly coupled to the request path

### 3.2 Caller-guidance concern

AI agents using `ctxledger` often consult repository guidance such as `.rules`.

If that guidance is incomplete or insufficiently explicit, an agent may:

- call `workflow_resume` with a `workspace_id`
- treat `workspace_register` output as the next input to `workflow_resume`
- skip a more appropriate resource or workflow discovery path
- keep retrying an invalid resume call until the transport times out

Even if the runtime bug is fixed, poor caller guidance can continue to produce avoidable failures, confusion, and noisy operational behavior.

`0.5.2` therefore must address both:

- runtime hardening
- guidance and contract hardening

---

## 4. Milestone intent

## 4.1 Primary objective

Make `workflow_resume` reliable, bounded, and clear for both valid and invalid caller inputs.

## 4.2 Secondary objectives

- improve observability of the resume path
- reduce ambiguity between `workspace_id` and `workflow_instance_id`
- ensure timeout-like failures degrade into fast, explicit error responses where possible
- improve AI-agent guidance so correct resume flows are more likely on the first attempt
- document the distinction between:
  - workflow-scoped resume
  - workspace-scoped current resume
  - starting new work

## 4.3 Non-objectives

`0.5.2` should not become:

- a broad transport rewrite
- an async database migration
- a major schema redesign
- a general performance program across all tools
- a replacement for `0.6.0` roadmap work
- a broad redesign of workflow semantics
- a large MCP protocol expansion unrelated to resume reliability

---

## 5. Scope

## 5.1 In scope

### Resume-path timeout remediation
Identify and remediate the practical causes of `workflow_resume` timing out in normal usage.

### Fast-fail invalid input handling
Ensure obviously invalid or mismatched identifiers fail quickly and clearly.

### AI-agent guidance improvements
Update `.rules` and related docs so agents are less likely to misuse `workflow_resume`.

### Resume contract clarification
Clarify which surface should be used for which job:

- `workflow_resume`
- workspace-scoped resume resource
- `workflow_start`

### Resume-path diagnostics
Improve logging, timing visibility, and operator-facing troubleshooting guidance.

### Documentation updates
Update roadmap, plan documents, changelog notes, architecture, and usage guidance where needed.

## 5.2 Out of scope

Unless required for correctness, the following should remain outside `0.5.2`:

- broad memory retrieval redesign
- large refactors outside the resume path
- unrelated observability dashboard work
- broad schema normalization efforts
- transport changes unrelated to timeout behavior
- feature additions to memory tools
- hierarchical memory implementation

---

## 6. Current-state analysis

## 6.1 Current runtime shape

The current `workflow_resume` path assembles a composite resume view from multiple lookups such as:

- workflow instance
- workspace
- running/latest attempt
- latest checkpoint
- latest verify report
- projection states
- open projection failures
- closed projection failures

This is useful behavior, but it also means a single resume call may depend on multiple storage operations before a response can be returned.

## 6.2 Current risk areas

The current failure surface likely includes some combination of:

- connection-pool checkout delay
- query latency in resume-related repositories
- projection failure lookup overhead
- insufficient timeout budgeting relative to synchronous request handling
- too little operator-visible information about which resume stage is slow
- invalid input that takes too long to fail
- AI-agent misuse caused by incomplete behavioral guidance

## 6.3 Current caller ambiguity

A key ambiguity is the distinction between:

- `workspace_id`
- `workflow_instance_id`

These IDs are both UUIDs, so type shape alone does not protect callers.

That means correctness must come from:

- naming
- docs
- error messages
- examples
- `.rules` guidance
- possibly helper/resource surfaces that reduce misuse pressure

---

## 7. Design principles

## 7.1 Fast failure is better than ambiguous timeout

If the caller provides the wrong identifier or the target workflow does not exist, the system should prefer a prompt explicit error over a slow path that times out.

## 7.2 Preserve canonical workflow semantics

PostgreSQL remains the canonical system of record.

The fix should not weaken workflow-state correctness.

## 7.3 Make the correct caller path obvious

When multiple resume-oriented surfaces exist, docs and rules must clearly explain when to use each one.

## 7.4 Improve diagnosability before over-optimizing

Before introducing large architectural change, ensure the system can reveal where time is being spent.

## 7.5 Harden both product and process

If AI agents are realistic first-class callers, then repository rules and operational guidance are part of the effective product surface.

---

## 8. Proposed remediation themes

## 8.1 Runtime hardening

The runtime should ensure that `workflow_resume` does not spend unbounded time in a synchronous request path without producing a useful result.

Possible implementation directions include:

- tightening query behavior and index usage
- bounding database waits more explicitly
- separating expensive optional resume subcomponents from the critical path
- adding targeted query-stage timing and warning logs
- making failure responses clearer when bootstrap, readiness, or persistence issues occur

## 8.2 Input misuse resilience

The system should be more resilient when a caller passes the wrong UUID category.

Possible implementation directions include:

- improve validation and error messaging for `workflow_resume`
- detect when a UUID exists as a workspace but not as a workflow instance
- return a specific guidance-oriented error when the ID appears to be a `workspace_id`
- point callers toward the workspace-scoped resume resource when that is what they actually need

This does not require changing the meaning of `workflow_resume`.

It requires making misuse obvious and recoverable.

## 8.3 Guidance hardening via `.rules`

The repository guidance should explicitly teach AI agents:

- `workspace_register` returns a `workspace_id`, not a `workflow_instance_id`
- `workflow_resume` requires a `workflow_instance_id`
- if only a `workspace_id` is known, use the workspace-scoped resume resource or another supported discovery path
- do not assume the output of one tool can be passed directly into a similarly named resume tool without verifying identifier semantics
- if resume fails repeatedly, avoid blind retries and surface the blocker clearly

This is an important part of the fix because the caller population includes rule-following agents.

## 8.4 Contract clarification

The intended tool/resource split should be documented more explicitly.

Suggested framing:

- use `workflow_resume` when you already know the `workflow_instance_id`
- use `workspace://{workspace_id}/resume` when you want the current resumable view for a workspace
- use `workflow_start` when no active workflow can be resumed and the work is genuinely new

---

## 9. Candidate implementation workstreams

## 9.1 Workstream A: reproduce and characterize the timeout

Goals:

- reproduce the timeout reliably
- distinguish database wait from transport timeout
- identify whether the issue occurs:
  - only on specific workflows
  - only under certain DB state
  - only through MCP
  - only through HTTP
  - only on cold start
  - only when invalid IDs are provided

Deliverables:

- documented reproduction matrix
- timing evidence for each resume stage
- narrowed list of actual slow or blocking operations

## 9.2 Workstream B: harden runtime behavior

Goals:

- make resume lookups bounded and predictable
- reduce the chance of timeout in common paths
- improve internal failure signaling

Candidate actions:

- audit resume-related queries and indexes
- verify pool settings and acquisition behavior
- ensure statement timeout / wait behavior is intentional
- consider reducing optional resume work on the main critical path if needed
- ensure not-found behavior is reached quickly
- ensure server readiness/bootstrap failures return explicit responses

Deliverables:

- code-level remediation
- targeted regression tests
- updated operator notes if behavior changes

## 9.3 Workstream C: harden invalid-ID behavior

Goals:

- detect obvious misuse quickly
- return guidance-rich error responses

Candidate actions:

- add explicit workflow-not-found diagnostics
- optionally detect known workspace UUID mismatch cases
- improve MCP/HTTP error payload wording
- add tests for:
  - valid workflow ID
  - unknown workflow ID
  - known workspace ID passed to `workflow_resume`

Deliverables:

- clearer response contract
- misuse-focused tests
- reduced ambiguity for AI agents and operators

## 9.4 Workstream D: update `.rules` and agent-facing guidance

Goals:

- reduce misuse probability at the source
- align agent instructions with the real tool contracts

Candidate `.rules` changes:

- explicitly define identifier classes used by each workflow tool
- add a rule stating that `workspace_register` output must not be reused as a `workflow_instance_id`
- add a preferred sequence for resume attempts
- add a fallback rule when resume fails or times out
- encourage use of workspace-scoped resume surfaces when only a `workspace_id` is available

Deliverables:

- updated `.rules`
- doc examples aligned to the rules
- less agent confusion in future sessions

## 9.5 Workstream E: documentation and roadmap alignment

Goals:

- document `0.5.2` as a real hardening milestone
- keep roadmap and operational docs aligned with the actual fix

Candidate docs to update:

- `docs/roadmap.md`
- `docs/CHANGELOG.md`
- `docs/architecture.md`
- `README.md`
- `last_session.md`
- `.rules`
- this plan document

---

## 10. Detailed design directions

## 10.1 Fast invalid-ID failure path

The system should preserve the current requirement that `workflow_resume` takes a `workflow_instance_id`.

However, the failure behavior should become more operator- and agent-friendly.

Preferred behavior:

1. attempt workflow-instance lookup promptly
2. if not found, fail with explicit `workflow_not_found` or equivalent
3. if practical, check whether the same UUID exists as a workspace
4. if it does, return a message that says the provided ID appears to be a `workspace_id`, and suggest the correct resume path

This behavior should be designed carefully to avoid:

- excessive extra database work in the common success path
- changing successful workflow-resume semantics
- masking genuine internal errors as caller mistakes

## 10.2 Resume payload critical-path review

The full composite resume view is useful, but not every component may deserve equal critical-path priority.

The implementation should review whether the following are required for the first successful response in all cases:

- projection states
- open projection failures
- closed projection failures

If one of these lookups is disproportionately expensive, `0.5.2` may choose one of these approaches:

- keep the data but optimize the query/index path
- degrade gracefully when optional subcomponents are unavailable
- split optional detail into a follow-up surface
- return partial resume results with warnings when that is architecturally acceptable

The guiding principle is that a usable resume response is better than a timeout.

## 10.3 Timeout budget alignment

The milestone should explicitly review timeout alignment across:

- database connection timeout
- pool acquisition timeout
- database statement timeout
- HTTP request handling expectations
- MCP/context-server timeout expectations

The goal is not necessarily to raise all timeout limits.

The goal is to make the system fail clearly and consistently within realistic budgets.

## 10.4 Logging and observability improvements

Resume-stage logs already exist in some form and should be strengthened where necessary.

Desired characteristics:

- clear stage names
- per-stage duration visibility
- correlation to workflow and workspace IDs where safe
- warnings when stage latency crosses useful thresholds
- enough context to distinguish:
  - bootstrap failure
  - pool wait
  - query slowness
  - invalid ID
  - partial resume degradation

## 10.5 `.rules` design guidance

`.rules` should be treated as part of operational correctness because AI agents actively consume it.

The revised guidance should include an explicit section such as:

- identifier semantics for workflow tools
- when to use workflow-scoped vs workspace-scoped resume
- what to do after `workspace_register`
- what to do if `workflow_resume` times out or returns not found
- a reminder not to start duplicate workflows merely because resume context is incomplete

---

## 11. Proposed deliverables

## 11.1 Code deliverables

Potential code deliverables for `0.5.2`:

- resume-path query/index hardening
- improved `workflow_resume` error responses
- explicit mismatch guidance for workspace-vs-workflow UUID misuse
- improved logging/timing around resume assembly
- tests covering timeout-adjacent and misuse scenarios

## 11.2 Documentation deliverables

Documentation deliverables should include:

- this plan document
- roadmap update for `0.5.2`
- changelog unreleased entry
- architecture note updates if runtime behavior changes
- README or usage guidance updates if caller guidance changes
- `.rules` updates for agent behavior
- `last_session.md` continuation note when work is complete

## 11.3 Validation deliverables

Validation should include:

- unit tests for invalid-ID and mismatch handling
- integration tests for normal resume behavior
- targeted tests for slow/optional resume subcomponents if behavior changes
- HTTP and MCP-facing regression checks where practical

---

## 12. Testing and validation strategy

## 12.1 Functional validation

Confirm that:

- valid `workflow_instance_id` resumes succeed
- unknown workflow IDs fail fast with explicit error
- known `workspace_id` used as `workflow_instance_id` yields a clear, actionable error
- workspace-scoped resume behavior remains correct
- `workflow_start` semantics remain unchanged

## 12.2 Operational validation

Confirm that:

- resume-stage timing logs identify slow stages
- the system no longer degrades into ambiguous timeout under the known reproduction pattern
- pool and timeout settings behave predictably
- HTTP and MCP surfaces return consistent error semantics

## 12.3 Regression validation

Confirm that:

- existing workflow lifecycle behavior still passes
- projection-failure tracking behavior is preserved
- connection-pool lifecycle remains correct
- documentation examples match actual behavior

---

## 13. Risks and tradeoffs

## 13.1 Risk: overfitting to one timeout case

There is a risk of fixing only the observed reproduction while leaving more general resume latency issues unresolved.

Mitigation:

- characterize the failure carefully before finalizing remediation
- test both valid and invalid identifier paths

## 13.2 Risk: adding too much work to the common path

Workspace-ID mismatch detection could introduce extra database lookups.

Mitigation:

- keep extra checks out of the success path when possible
- make misuse detection cheap and narrowly targeted

## 13.3 Risk: weakening resume completeness

If the system degrades optional subcomponents to avoid timeout, resume responses may become less rich.

Mitigation:

- preserve core correctness first
- use warnings and explicit partial-result signaling if needed
- avoid silently dropping important canonical state

## 13.4 Risk: docs drift from implementation

If `.rules`, roadmap, README, and runtime behavior are updated inconsistently, the confusion may persist.

Mitigation:

- treat docs and `.rules` as required deliverables, not optional follow-up

---

## 14. Execution checklist

The following checklist is intended to turn the `0.5.2` plan into a practical implementation sequence.

### 14.1 Investigation

- reproduce the current timeout case
- confirm whether the reproduced caller input uses a `workspace_id` instead of a `workflow_instance_id`
- measure where time is spent in the resume path
- confirm whether the issue is transport-specific or runtime-general

### 14.2 Runtime remediation

- audit resume-path queries and indexes
- harden not-found and invalid-input behavior
- review critical-path optional lookups
- align timeout behavior across the stack
- add or refine timing and warning logs

### 14.3 Guidance remediation

- update `.rules` with explicit identifier semantics
- document the correct post-`workspace_register` workflow
- add examples distinguishing workspace resume from workflow resume
- add retry guidance that avoids blind timeout loops

### 14.4 Validation

- add unit tests for wrong-ID handling
- add integration tests for valid/invalid resume cases
- validate HTTP and MCP-facing behavior
- verify no regression in the broader workflow lifecycle

### 14.5 Documentation closeout

- update `docs/roadmap.md`
- update `docs/CHANGELOG.md`
- update any affected architecture/README guidance
- update `last_session.md` when implementation work is done

---

## 15. Success criteria

`0.5.2` should be considered successful when:

- the known `workflow_resume` timeout failure mode is no longer reproduced in the targeted scenarios
- valid workflow resume requests complete reliably
- invalid resume requests fail fast and clearly
- passing a `workspace_id` to `workflow_resume` no longer results in an ambiguous timeout experience
- AI-agent guidance in `.rules` explicitly reduces identifier misuse risk
- docs consistently explain the intended resume flow
- targeted validation demonstrates both runtime and guidance improvements

---

## 16. Deferred follow-up items

The following are reasonable future follow-ups, but should not block `0.5.2` unless required for correctness:

- deeper async/offloaded request execution work
- richer resume subresource decomposition
- broader operator dashboards for latency hot spots
- more general query-performance initiatives beyond the resume path
- broader contract refinements for workflow-discovery tooling

---

## 17. Version framing

`0.5.2` should be treated as a **workflow resume reliability and caller-guidance hardening release**.

It follows `0.5.1` by focusing not just on connection-pool ownership and bootstrap correctness, but on the practical end-to-end reliability of the resume experience for real callers.

In particular, `0.5.2` recognizes that:

- runtime implementation
- error semantics
- operational observability
- AI-agent guidance in `.rules`

all jointly influence whether `workflow_resume` works reliably in practice.

That combined surface is the real target of this milestone.