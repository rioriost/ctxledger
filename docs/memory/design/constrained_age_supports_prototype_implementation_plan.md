# Repository-Scoped Implementation Plan for the Constrained AGE `supports` Prototype

> Historical record note:
> This document should be read as a first-slice implementation plan and design
> record for the constrained AGE `supports` prototype.
> It remains useful for understanding the bounded prototype boundary and earlier
> implementation intent, but it is not the canonical source for the current
> `0.9.0` release posture.
> For the current release-facing reading, prefer the `0.9.0` acceptance,
> closeout, changelog, and product/runbook documents.

## Status

This implementation plan now describes a prototype path that is **partially
implemented**.

Implemented so far:

- a narrow repository-facing `supports` target lookup boundary exists
- relational baseline implementations exist for distinct one-hop `supports`
  target lookup
- AGE capability and graph-readiness checks exist
- a PostgreSQL AGE-backed one-hop `supports` lookup path exists
- explicit relational fallback exists
- the memory service can consume the narrow lookup boundary without changing the
  visible retrieval contract
- explicit config-gated prototype controls exist:
  - `CTXLEDGER_DB_AGE_ENABLED`
  - `CTXLEDGER_DB_AGE_GRAPH_NAME`
- an explicit prototype-grade bootstrap path now exists:
  - `ctxledger bootstrap-age-graph`

Not yet implemented:

- production-grade graph lifecycle automation
- incremental graph synchronization
- broader graph traversal semantics
- visible `memory_get_context` contract changes
- any shift away from relational canonical storage

## Purpose

This note defines the implementation plan for the first repository-scoped
Apache AGE-backed prototype described in:

- `docs/memory/design/constrained_age_supports_prototype.md`

Its purpose is to translate the already-chosen AGE direction into a concrete,
small, and testable engineering slice.

This plan is intentionally narrow.

It does **not** propose broad graph adoption.

It does **not** redesign `memory_get_context`.

It does **not** make the graph layer canonical.

It does **not** broaden current relation semantics.

---

## Implementation Goal

Implement one internal repository-scoped graph-backed read that can support the
current constrained relation direction without changing the visible retrieval
contract.

The first prototype should demonstrate all of the following:

1. Apache AGE can support one concrete memory relation lookup
2. the graph layer can remain supplementary and derived
3. graph capability can be handled explicitly
4. fallback behavior can preserve the current relational-first behavior
5. the resulting slice is small enough to validate and reason about clearly

The prototype should remain:

- one-hop only
- `supports` only
- repository-scoped first
- parity-oriented with the current relational path
- behavior-preserving at the service contract boundary

---

## Scope

This implementation plan covers:

- repository contract additions for the constrained prototype
- PostgreSQL/AGE repository implementation direction
- fallback behavior expectations
- graph availability/readiness handling
- graph mapping assumptions
- focused validation strategy
- acceptance criteria for the first graph-backed repository slice

This implementation plan does **not** cover:

- broad graph lifecycle automation
- generalized graph abstraction design
- graph-backed writes as the canonical write path
- grouped response redesign
- summary-first redesign
- multi-hop traversal
- additional relation types
- graph-first ranking or planning

---

## Current Starting Point

At the current stage, the repository already has several relevant ingredients:

- a minimal AGE capability check via `PostgresDatabaseHealthChecker.age_available()`
- graph-readiness checks for the constrained prototype
- a relational `MemoryRelationRepository`
- in-memory and PostgreSQL relation repository implementations
- a constrained relation-aware retrieval direction already centered on:
  - one-hop usage
  - `supports`
  - service-layer assembly
  - behavior preservation
- a config-gated AGE-backed repository path with explicit fallback
- an explicit prototype bootstrap CLI path:
  - `ctxledger bootstrap-age-graph`

That means the next slice does **not** need to invent the relation semantics or
invent the bootstrap entry point from scratch.

Instead, it needs to harden and validate the existing narrow graph-backed
repository path and explicit bootstrap path against the constrained relational
baseline.

---

## Prototype Target

The recommended first graph-backed operation is:

- a repository-scoped lookup that returns distinct target memory item IDs for
  one-hop `supports` edges from a set of source memory item IDs

Conceptually, the target operation should answer:

- given a set of source memory item IDs
- return distinct target memory item IDs
- for `supports` relations only
- using one-hop graph traversal only

The target output should be deterministic enough to support parity testing
against the current relational behavior for the constrained scenario.

---

## Design Constraints

The implementation must preserve the already-decided AGE boundaries.

### 1. Relational storage remains canonical

The canonical source of truth must remain relational:

- memory items remain canonical in relational tables
- memory relations remain canonical in relational tables

The graph layer must remain:

- supplementary
- derived
- non-canonical
- scoped to the prototype

### 2. AGE remains optional by default

The first prototype must not make AGE a hidden requirement for ordinary
relational behavior.

If AGE is unavailable, the prototype must degrade explicitly.

### 3. Visible retrieval behavior remains unchanged

The first slice should not change:

- `memory_get_context` response structure
- grouped output semantics
- current retrieval-route metadata behavior
- current constrained relation semantics

### 4. The prototype remains repository-scoped first

The first slice should begin as repository infrastructure.

It should not immediately redesign higher-level service behavior.

---

## Proposed Repository Shape

The implementation should introduce a narrow internal repository capability for
the prototype.

A suitable shape would be a new graph-oriented lookup contract dedicated to the
prototype, for example:

- list distinct `supports` target IDs by source memory item IDs
- or an equivalently narrow helper method with the same practical effect

The important design properties are:

- input is a set of source memory item IDs
- output is a deterministic distinct sequence of target memory item IDs
- traversal is limited to one hop
- relation type is fixed to `supports`
- behavior is explicit when graph capability is unavailable

This should remain narrower than the general relational relation repository.

The goal is not to retrofit the whole relation contract into a graph system.

The goal is to add one small graph-backed read path.

---

## Recommended Interface Boundary

The prototype should use an explicit interface boundary rather than smuggling
graph behavior into existing generic repository methods.

Recommended approach:

- keep the existing `MemoryRelationRepository` focused on canonical relational
  relation storage and reads
- add a separate narrow read-only prototype-oriented contract for AGE-backed
  lookup
- keep the service layer free to ignore or adopt that graph-backed path later in
  a deliberate slice

This separation helps preserve architectural clarity:

- canonical relational repository remains stable
- graph-backed prototype remains clearly experimental and scoped
- fallback handling can be explicit at the prototype boundary

---

## Proposed Implementation Components

### 1. Graph capability/readiness boundary

Introduce a narrow repository-facing way to reason about graph availability.

The prototype needs to distinguish at least these states:

- AGE extension unavailable
- AGE extension available but prototype graph not ready
- AGE extension and prototype graph ready

The implementation should avoid silently conflating these states.

A simple approach is acceptable as long as it is explicit and testable.

### 2. Graph-backed lookup implementation

Add a PostgreSQL/AGE-backed implementation for the constrained lookup.

This implementation should:

- accept source memory item IDs
- traverse one-hop `supports` edges only
- return distinct target memory item IDs
- remain narrow and deterministic

### 3. Fallback behavior

If graph capability is not available or not ready, the prototype path should
fall back explicitly to the existing relational path.

That fallback should preserve constrained behavior rather than introduce a
different semantic interpretation.

### 4. Relational parity helper path

To make parity testing straightforward, the slice should preserve or expose a
clear relational baseline for the same constrained lookup.

This makes it easier to validate that the graph-backed result matches the
intended constrained behavior.

---

## Graph Mapping Assumptions

The prototype needs a minimum mapping between canonical relational records and
graph objects.

The recommended minimal mapping is:

- one graph node per relevant memory item
- one graph edge per relevant `supports` relation
- graph node and edge identity or properties must remain traceable to canonical
  relational IDs

At minimum, the mapping should make it possible to answer:

- which canonical memory item does this graph node represent
- which canonical `supports` relation does this graph edge correspond to

The first prototype should avoid richer graph modeling than necessary.

Do not add:

- summary graph models
- hierarchy graph models
- mixed entity graph schemas
- ranking metadata
- traversal scoring metadata

unless the narrow prototype strictly requires them, which it should not.

---

## Bootstrap and Setup Plan

The first implementation slice should add only the minimum setup behavior needed
to support the prototype.

### Recommended responsibility split

- AGE extension provisioning:
  - explicit database setup or migration concern
- graph namespace/graph object provisioning for the prototype:
  - explicit setup concern, not hidden retrieval behavior
- runtime capability detection:
  - application-side validation or repository-side readiness checks
- graph-backed lookup usage:
  - gated by explicit capability handling and fallback

### Recommended operational rule

Do not make application startup mutate graph state broadly as a hidden side
effect of ordinary retrieval.

If setup support is added in this slice, it should be:

- explicit
- prototype-scoped
- easy to diagnose
- easy to disable or bypass in non-graph environments

That reading now applies directly to the current prototype state because an
explicit bootstrap path already exists in CLI form:

- `ctxledger bootstrap-age-graph`

This should be read as:

- explicit bootstrap/population responsibility
- prototype-scoped operational setup
- still narrower than a full lifecycle or migration framework

### Acceptable first-step bootstrap options

The prototype may choose one of these approaches:

1. explicit setup/migration-managed graph provisioning
2. explicit operator/developer setup step for graph creation
3. minimal test fixture provisioning for graph-specific tests

The current repository has now effectively chosen option 2 first:

- explicit operator/developer setup through `ctxledger bootstrap-age-graph`

The least risky next step is therefore to harden and validate that explicit
bootstrap path rather than replace it with broader hidden automation.

---

## Fallback Strategy

The required fallback strategy for the first prototype is:

- relational fallback

This means:

- if AGE is unavailable, use the existing constrained relational path
- if AGE is available but the prototype graph is not ready, use the relational
  path
- if the graph-backed query fails in a way that clearly indicates graph
  unavailability/readiness issues, the prototype path should degrade explicitly
  rather than destabilize ordinary relational behavior

The implementation should make this fallback understandable in logs, diagnostics,
or internal naming.

The first prototype should avoid a “best effort but opaque” graph path.

---

## Implementation Steps

## Step 1: Define the prototype repository contract

Add a narrow internal contract for the graph-backed lookup.

This contract should be:

- read-only
- prototype-specific
- `supports`-focused
- one-hop only

It should not be framed as a generalized graph repository.

### Deliverable

- a new internal protocol or repository contract for constrained graph-backed
  `supports` lookup

---

## Step 2: Add a relational parity implementation

Add or identify a relational implementation for the same constrained lookup so
the graph-backed path has a clear baseline.

This step may reuse existing relational repository behavior if the parity path is
already expressible cleanly.

### Deliverable

- a deterministic relational baseline for distinct one-hop `supports` target
  lookup by source memory item IDs

---

## Step 3: Add AGE capability/readiness checks for the prototype boundary

Extend the existing AGE capability approach enough to support the prototype
boundary.

This should answer questions such as:

- is AGE installed
- is the prototype graph expected to exist
- is the prototype graph ready enough for the constrained lookup

This does not need to become a broad graph lifecycle framework.

### Deliverable

- explicit graph capability/readiness detection for the prototype path

---

## Step 4: Implement the PostgreSQL/AGE-backed lookup

Add the narrow AGE-backed repository implementation.

This implementation should:

- use one-hop traversal only
- read `supports` edges only
- return distinct target memory item IDs
- remain deterministic enough for parity tests

### Deliverable

- repository-scoped PostgreSQL/AGE lookup for constrained `supports` traversal

---

## Step 5: Add explicit relational fallback wiring

At the prototype boundary, ensure unavailability or unready graph state degrades
to the relational path.

This fallback should be explicit in code structure.

Do not rely on accidental exception swallowing.

### Deliverable

- graph-aware lookup path with explicit relational fallback

Status:

- implemented in constrained form through the AGE-backed repository path plus
  explicit relational fallback behavior

---

## Step 6: Validate parity and degradation behavior

Add focused tests that prove:

- graph unavailable path preserves relational behavior
- graph ready path can perform the constrained lookup
- graph and relational paths agree for the constrained scenario
- current visible retrieval behavior remains unchanged

### Deliverable

- focused prototype tests covering capability, fallback, parity, and behavior
  preservation

Status:

- partially implemented with focused coverage for capability, fallback, config
  gating, and service-layer parity

---

## Step 7: Add explicit bootstrap/population path

Add one explicit bootstrap/population path for the constrained prototype graph.

This step should:

- create the named graph if needed
- clear the currently managed prototype graph contents
- repopulate:
  - `memory_item` nodes from canonical `memory_items`
  - `supports` edges from canonical `memory_relations`
- remain explicit rather than a hidden retrieval-time side effect
- stay prototype-scoped rather than becoming a broad graph administration layer

### Deliverable

- explicit constrained bootstrap/population entry point

Status:

- implemented in initial CLI form through:
  - `ctxledger bootstrap-age-graph`

The next work for this step is to harden rerun behavior, validation depth, and
operator-facing clarity.

---

## Validation Plan

The first prototype should be validated in a way that makes both success and
limits obvious.

### A. Capability-absent validation

Confirm that when AGE is unavailable:

- the prototype path does not become a hidden requirement
- relational fallback remains available
- no visible retrieval contract change occurs

### B. Capability-present validation

Confirm that when AGE is available and the prototype graph is ready:

- one-hop `supports` graph lookup works
- the returned target IDs match the intended constrained semantics

### C. Readiness-degraded validation

Confirm that when AGE is available but the graph is not ready:

- the graph-specific boundary handles this explicitly
- the relational fallback still preserves constrained behavior

### D. Parity validation

Confirm that for the constrained scenario:

- graph-backed output matches relational output

This is the most important validation in the slice because it demonstrates that
the graph-backed path is a faithful implementation experiment rather than a new
semantic branch.

### E. Behavior-preservation validation

Confirm that the slice does not change:

- visible `memory_get_context` response structure
- current grouped route behavior
- current relation-aware output semantics

unless a later slice explicitly opts into such changes.

---

## Suggested Test Cases

Recommended focused test coverage includes:

1. graph capability absent returns relational-equivalent result
2. graph ready returns expected distinct one-hop `supports` targets
3. graph ready result matches relational baseline for the same inputs
4. graph unready path falls back explicitly
5. unsupported broadening is not introduced:
   - no multi-hop behavior
   - no non-`supports` relation semantics
6. current service-level retrieval behavior remains unchanged by the prototype
   infrastructure

Where possible, the tests should stay semantically small and isolate one concern
per case.

---

## Risks

### 1. Premature generalization

Risk:
- the prototype may turn into a generalized graph repository abstraction too
  early

Mitigation:
- keep the contract prototype-specific and read-only
- limit the method shape to the one constrained lookup

### 2. Hidden canonical drift

Risk:
- graph state may start being treated as authoritative without being designed as
  canonical

Mitigation:
- preserve relational writes and relational baseline reads as canonical
- document graph as derived/supporting only

### 3. Opaque fallback

Risk:
- graph failure may silently alter semantics or debugging clarity

Mitigation:
- make fallback explicit at the graph-specific boundary
- distinguish unavailable vs unready where practical

### 4. Behavioral spillover

Risk:
- the prototype may accidentally alter `memory_get_context` behavior

Mitigation:
- keep the first slice repository-scoped
- add explicit behavior-preservation tests

### 5. Test fragility

Risk:
- graph tests may become brittle across environments

Mitigation:
- keep broad suites relational-first by default
- isolate graph-specific tests
- avoid making graph capability a default assumption

---

## Non-Goals

This implementation plan does **not** include:

- rewriting memory retrieval around AGE
- making the graph layer canonical
- changing grouped response structures
- adding summary graph traversal
- introducing multi-hop traversal
- adding more relation types
- implementing graph-first ranking or planning
- creating a full graph administration framework
- making AGE mandatory for general development or test workflows

---

## Acceptance Criteria

This first repository-scoped AGE prototype is successful when all of the
following are true:

- a narrow prototype-specific repository contract exists
- a PostgreSQL/AGE-backed implementation exists for one-hop `supports` target
  lookup
- relational storage remains canonical
- AGE remains optional by default
- explicit relational fallback exists for unavailable or unready graph states
- focused tests validate:
  - capability absent behavior
  - capability present behavior
  - graph/readiness degradation behavior
  - parity with the relational baseline
  - preservation of the current visible retrieval contract

If these are not all true, the slice should be considered incomplete or too
broad.

---

## Recommended Next Follow-Up After This Slice

Because this prototype is now partially implemented, the next reasonable
follow-up should still remain constrained and should focus on hardening rather
than broadening.

The most natural next step would be one of:

- refinement of the explicit bootstrap/population path:
  - rerun expectations
  - graph-ready validation depth
  - operator/developer guidance
- refinement of graph readiness/setup documentation based on the implemented
  prototype
- deeper graph-enabled validation of the current constrained path
- a second constrained graph-backed relation read only if the current prototype
  is clearly successful, operationally understandable, and still behavior-
  preserving

The next step should **not** immediately escalate into broad graph semantics.

---

## Working Rule

Use this rule while implementing the first repository-scoped AGE prototype:

- **one concrete graph-backed read only**
- **one-hop `supports` only**
- **relational remains canonical**
- **fallback must be explicit**
- **service behavior must remain unchanged**

This keeps the prototype honest, testable, and aligned with the current `0.6.0`
direction.

---

## Decision Summary

The recommended implementation plan for the current AGE-oriented slice is now
partially implemented and should be read as:

- a repository-scoped constrained AGE-backed lookup for distinct one-hop
  `supports` targets by source memory item IDs exists
- relational storage remains canonical
- AGE remains optional by default
- explicit graph capability/readiness handling exists
- explicit relational fallback exists
- an explicit constrained bootstrap/population path now exists in CLI form:
  - `ctxledger bootstrap-age-graph`
- focused validation exists for parity and behavior preservation in the covered
  prototype areas

This is no longer only a planned implementation slice.

It is now a bounded, partially implemented engineering proof point.

The next useful work is to harden and validate that proof point further without
reopening the current retrieval contract prematurely.