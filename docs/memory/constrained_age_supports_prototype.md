# Constrained AGE `supports` Prototype for `0.6.0`

## Status

This note now describes a prototype direction that is **partially implemented**
in a still-constrained form.

Implemented so far:

- a narrow `supports` target lookup boundary exists
- a relational baseline implementation exists
- AGE capability and graph-readiness checks exist
- a PostgreSQL AGE-backed one-hop `supports` lookup path exists
- explicit relational fallback exists when AGE is disabled, unavailable, unready,
  or the graph-backed read fails
- the memory service can use the narrow lookup boundary without changing the
  visible `memory_get_context` contract
- configuration now includes explicit AGE prototype controls:
  - `CTXLEDGER_DB_AGE_ENABLED`
  - `CTXLEDGER_DB_AGE_GRAPH_NAME`

Not yet implemented:

- graph-backed writes or graph bootstrap population
- production-grade graph lifecycle automation
- broader graph traversal semantics
- visible `memory_get_context` contract changes
- any shift away from relational canonical storage

This note remains intentionally narrow.

It does **not** propose a broad graph platform rollout.

It does **not** treat the graph layer as canonical.

It does **not** redesign `memory_get_context`.

## Purpose

This note defines the recommended **first constrained Apache AGE-backed prototype**
for the `0.6.0` hierarchical memory milestone.

Its purpose is to turn the existing AGE boundary/setup decisions into one
concrete and testable next implementation slice without widening the current
retrieval contract too early.

---

## Relationship to Earlier AGE Decisions

This note follows and narrows the guidance already established in:

- `docs/memory/first_age_slice_boundary_decision.md`
- `docs/memory/age_setup_first_slice.md`

Those notes already establish that the first AGE-oriented work for the current
stage should be:

- boundary-first
- bootstrap-first
- behavior-preserving
- optional by default

This note answers the next question:

- once that boundary is accepted, what should the **first actual graph-backed
  prototype** be

The answer recommended here is:

- one constrained internal graph-backed read
- one-hop only
- `supports` only
- explicit fallback/degradation behavior
- no visible retrieval-contract redesign

That recommended shape is now partially implemented as:

- a narrow repository-facing `supports` target lookup boundary
- a relational baseline path for distinct target lookup
- an AGE-backed PostgreSQL lookup path for the same constrained query
- explicit graph-readiness gating and relational fallback
- service-layer adoption of the narrow lookup boundary without visible contract
  drift

---

## Prototype Goal

The goal of this prototype is to demonstrate that Apache AGE can support one
small, well-bounded graph-backed relation lookup that is compatible with the
current relational-first design.

The prototype should prove all of the following at once:

1. AGE can be used for one concrete memory-related read path
2. the graph layer can remain supplementary rather than canonical
3. graph availability can be handled explicitly rather than implicitly
4. the system can preserve current retrieval behavior while the prototype is
   introduced
5. the first graph slice can stay operationally clear and testable

This is a prototype of **graph-assisted relation lookup**, not a prototype of
full graph-driven retrieval semantics.

At the current repository state, this should be read as a **bounded internal
prototype substrate** rather than as a broad AGE rollout.

---

## Recommended Prototype Scope

The recommended first prototype is:

- a constrained internal repository-level read for `supports` relations

Conceptually, the prototype should answer a question of this form:

- given a set of source memory item IDs
- return distinct target memory item IDs
- using one-hop `supports` edges only

This should remain:

- internal
- narrow
- parity-oriented relative to the current constrained relational path

The first graph-backed prototype should **not** begin with:

- grouped-output changes
- graph-first ranking
- multi-hop traversal
- broad hierarchy traversal
- summary selection logic
- a user-visible contract expansion

---

## Why `supports` and One-Hop Are the Right First Target

This is the best first graph-backed target because it aligns with the current
`0.6.0` direction instead of reopening it.

At the current stage, relation-aware behavior is already intentionally
constrained.

The repository and service shape now already point toward:

- `supports` as the currently constrained relation type
- one-hop relation use
- behavior-preserving assembly in the service layer
- relational-first semantics

That makes a graph-backed `supports` one-hop read the most natural AGE
prototype because it:

- fits the current contract direction
- is small enough to validate clearly
- avoids inventing new graph semantics
- can be compared directly against the existing relational path
- justifies only minimal setup/bootstrapping work

In other words, it is a prototype with a clear comparison target rather than a
prototype that creates a new semantic surface area.

---

## Recommended Prototype Shape

The first constrained AGE-backed prototype should have the following shape.

### 1. Internal repository read only

The initial graph-backed operation should live at the repository layer.

It should be framed as a narrow internal capability such as:

- listing distinct `supports` targets by source memory item IDs
- or an equivalent narrowly-scoped graph relation lookup helper

The key point is that the first graph-backed prototype should begin as:

- an implementation substrate
- not yet a direct user-visible feature contract

That reading still applies to the current implementation state:

- the service layer can now consume the narrow lookup boundary
- but the visible retrieval contract is still intended to remain unchanged

### 2. One-hop traversal only

The prototype should use only:

- source memory item
- direct `supports` edge
- target memory item

It should not include:

- multi-hop graph walks
- path scoring
- neighborhood expansion
- transitive reasoning
- mixed traversal modes

### 3. `supports` only

The prototype should support only the currently constrained relation reading:

- `supports`

It should not broaden relation semantics by introducing:

- multiple relation types
- reverse traversal semantics
- implicit relation grouping
- relation ranking
- relation-weight semantics

### 4. Distinct target output

The prototype should return a distinct target set in a deterministic order that
matches the intended constrained reading as closely as practical.

If parity with the current relational path is a goal, the graph prototype should
be judged against that parity rather than against future graph ambitions.

### 5. No grouped-response redesign

Even if this graph-backed read is later used by service logic, the first
prototype should not redesign:

- `memory_context_groups`
- retrieval-route metadata
- auxiliary-group positioning
- grouped ordering rules
- summary-first behavior

Those concerns should remain outside the prototype boundary.

---

## Canonical Storage Boundary

The canonical system of record should remain:

- relational storage

For this prototype, the graph layer should be treated as:

- supplementary
- derived
- support-oriented
- explicitly non-canonical

That means:

- relational tables remain the authoritative source for memory items and memory
  relations
- AGE-backed graph objects mirror or reference canonical relational records
- graph-backed reads are evaluated as an implementation path, not as a canonical
  truth source

This boundary matters because it keeps the first graph prototype from quietly
rewriting the architecture.

---

## Recommended Graph Ownership Model

The recommended ownership model for the first prototype is:

- graph state mirrors a narrow subset of canonical relational memory state

In the first prototype, that should likely mean:

- graph nodes represent memory items needed for the prototype
- graph edges represent `supports` relationships between those items
- graph node/edge identity should remain traceable back to canonical relational
  IDs

The graph layer should not yet be treated as:

- the authoritative place to discover memory existence
- the only place to discover relations
- a replacement for canonical relational integrity
- a broad general-purpose hierarchy engine

The graph layer is a derived traversal aid in this prototype.

---

## Bootstrap and Setup Recommendation

The first graph-backed prototype should use only the minimum setup needed to
support its own narrow scope.

### Recommended setup rule

Do **not** introduce broad bootstrap automation without a concrete prototype
consumer.

The current repository state now has that concrete prototype consumer in a
narrow form:

- one-hop `supports` target lookup
- explicit config gating
- explicit graph-readiness checks
- explicit relational fallback

Even so, broad bootstrap automation is still intentionally deferred.

Because this note defines a concrete prototype consumer, setup can now be
introduced — but only in the minimum form needed to support this prototype.

### Recommended setup responsibility

The preferred first-step responsibility split is:

- extension and graph availability:
  - explicit database setup or migration responsibility
- runtime capability detection:
  - explicit application-side validation or availability checks
- graph-backed prototype use:
  - gated behind explicit capability handling and fallback behavior

Current implementation progress is aligned with that split:

- runtime capability detection exists
- graph-readiness detection exists
- graph-backed prototype use is gated and fallback-aware
- explicit graph population/bootstrap responsibility still remains outside this
  note's implemented scope

### What setup should not become yet

The first prototype should not use setup as a reason to introduce:

- implicit app-start graph creation with broad side effects
- hidden runtime mutation of graph state for unrelated paths
- mandatory AGE dependence for all environments
- future-proof generalized graph lifecycle machinery

---

## Optionality and Fallback

For the first prototype, AGE should remain:

- optional by default

That optionality is now reflected in implementation shape as well as design
intent:

- explicit enablement is controlled by `CTXLEDGER_DB_AGE_ENABLED`
- graph selection is controlled by `CTXLEDGER_DB_AGE_GRAPH_NAME`
- the relational path remains the default-preserving route when AGE is disabled
  or not ready

That optionality should be expressed in behavior, not only in documentation.

### Required fallback rule

If AGE is unavailable, the system should not reinterpret that as a general memory
retrieval failure.

The prototype should instead do one of the following explicitly:

- fall back to the existing relational lookup path
- or remain disabled at the graph-specific boundary with a clear internal reason

For this prototype, the recommended behavior is:

- **fallback to the existing relational path**

### Why fallback is preferred here

Relational fallback is preferred in the prototype because the current AGE
direction is explicitly behavior-preserving.

Fallback preserves that property by ensuring:

- stable current behavior remains available
- graph availability does not become a hidden prerequisite
- graph-related experimentation can proceed without destabilizing existing
  retrieval work
- parity between graph and relational paths can be tested intentionally

---

## Runtime Behavior Recommendation

The first graph-backed prototype should behave like this:

### When AGE is available and the prototype is enabled

- the constrained graph-backed relation read may execute
- its result should stay within the prototype’s narrow contract
- service behavior should remain unchanged unless a later slice explicitly opts
  in to using the graph result

### When AGE is unavailable

- the system should not fail generic memory retrieval because of graph absence
- the graph-backed prototype path should degrade explicitly
- the relational path should remain available

### When AGE is available but graph state is not ready

The system should still avoid silent semantic drift.

Recommended handling:

- treat the graph path as unavailable or not ready
- surface that state at the graph-specific boundary if needed
- continue preserving the relational path

This avoids confusing “graph not initialized yet” with “retrieval logic is
broken.”

---

## Suggested Implementation Boundary

The first prototype should remain constrained to items such as:

- a narrow graph-backed repository method
- capability checks for AGE and graph readiness
- minimal graph mapping assumptions for memory items and `supports` edges
- explicit fallback handling
- tests proving constrained parity and degradation

That is also the current implementation boundary reached so far.

The first prototype should **not** include:

- service-layer redesign
- grouped-response redesign
- broader graph abstractions
- generalized query planning
- multi-hop graph APIs
- canonical write-path migration to graph storage
- broad summary or hierarchy traversal in AGE

The implementation boundary should remain on the side of:

- one concrete graph read
- one concrete fallback rule
- one clear architectural boundary

---

## Suggested Validation Strategy

The prototype should be accepted only if it is validated in a way that is clear
about both capability and limits.

### 1. AGE unavailable path

Add focused validation that confirms:

- the graph-backed prototype does not become a hidden requirement
- the relational path remains usable
- the graph-specific path degrades or falls back explicitly

### 2. AGE available path

Add focused validation that confirms:

- one-hop `supports` graph lookup works
- the returned targets match the intended constrained semantics
- graph usage is limited to the prototype boundary

### 3. Parity validation

Add focused validation that confirms:

- for the constrained scenario, the graph-backed prototype and existing
  relational path produce equivalent results

This parity check is one of the most important validations in the prototype
because it shows whether the graph layer is actually behaving as intended rather
than merely existing.

### 4. Behavior-preservation validation

Add focused validation that confirms:

- current `memory_get_context` behavior remains unchanged unless and until a
  later slice intentionally opts into the graph-backed path

---

## Acceptance Criteria

The first constrained AGE-backed prototype is successful when all of the
following are true:

- one narrow internal graph-backed repository read exists
- that read is limited to one-hop `supports`
- relational storage remains canonical
- AGE is treated as optional by default
- graph unavailability does not break current relational retrieval behavior
- explicit fallback or degradation behavior exists
- focused tests cover:
  - AGE unavailable handling
  - AGE available handling
  - constrained parity with the relational path
  - preservation of the current visible retrieval contract

Current state against those criteria:

- partially met
- the repository-scoped read exists
- the read is constrained to one-hop `supports`
- optionality and fallback are implemented
- service-layer parity coverage exists for the narrow lookup boundary
- graph bootstrap/population and broader operationalization remain unfinished

If those conditions are not met, the prototype is either too broad or not yet
operationally clear enough.

---

## Non-Goals

This prototype should not attempt to do any of the following:

- change the visible `memory_get_context` contract
- introduce grouped-output redesign
- broaden traversal beyond one hop
- add new relation semantics beyond constrained `supports`
- introduce graph-first ranking or planning
- replace relational canonical storage
- build a generalized graph framework before the first concrete use is proven
- turn AGE into a hidden global runtime dependency
- use graph presence as justification for broader product claims than the system
  currently supports

---

## Working Rule

Use this rule for the first constrained AGE-backed prototype:

- **one graph-backed read only**
- **one-hop `supports` only**
- **relational remains canonical**
- **fallback must be explicit**
- **visible retrieval behavior should remain unchanged**

This keeps the first prototype small enough to evaluate honestly and useful
enough to justify the minimal AGE setup that supports it.

---

## Decision Summary

The recommended next AGE implementation slice for `0.6.0` is:

- continue the constrained internal graph-backed prototype for one-hop
  `supports` relation lookup

That prototype should:

- remain repository-scoped and narrowly service-consumable
- preserve relational canonical storage
- treat AGE as optional by default
- use explicit fallback or degradation behavior
- avoid any visible retrieval-contract redesign

The current repository has already crossed the threshold from pure planning into
partial prototype implementation.

The purpose of the next slice is therefore no longer to invent the prototype
boundary.

It is to finish and harden that boundary by clarifying:

- graph population/bootstrap responsibility
- runtime wiring expectations in real PostgreSQL-backed flows
- operational documentation
- validation depth for graph-ready and graph-unavailable environments

The purpose of this slice is still not to make the graph layer broadly
important.

Its purpose remains to create one concrete, testable, behavior-preserving proof
point that AGE can support a narrowly-scoped future retrieval path without
forcing premature graph semantics onto the rest of the system.