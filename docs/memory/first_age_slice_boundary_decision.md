# First AGE-Backed Graph Slice Boundary Decision

## Context

Recent `0.6.0` work around `memory_get_context` has already established a much clearer current retrieval contract than earlier stages.

At the current stage, the implementation now has:

- a primary grouped hierarchy-aware response surface through `memory_context_groups`
- a stable enough current reading for:
  - summary-first primary grouped shaping
  - auxiliary-only no-match shaping
  - episode-less `include_episodes = false` shaping
- a deliberately constrained relation-aware slice:
  - one-hop only
  - `supports` only
  - auxiliary use only
- explicit contract/documentation coverage for:
  - grouped ordering
  - retrieval-route metadata
  - compatibility vs convenience relation-aware outputs
- a new bulk source relation lookup primitive:
  - `list_by_source_memory_ids(...)`

That means the current `0.6.0` retrieval contract area is now stable enough that the next natural unresolved question is not primarily about another narrow grouped-response clarification.

Instead, the next unresolved question is where the first Apache AGE-backed graph slice should begin.

The `0.6.0` plan already includes AGE as part of the milestone direction, but it also establishes strong constraints:

- relational first
- graph where justified
- incremental over sweeping
- operational clarity before opaque cleverness
- no premature abstraction
- behavior preservation outside the target area

Because of those constraints, the first AGE-backed slice needs a clear boundary.

## Decision question

What should the **first AGE-backed graph slice** for `0.6.0` actually do?

More specifically:

- should the first AGE-backed slice change retrieval behavior immediately
- or should it first define the graph boundary, bootstrap responsibility, and operational expectations without changing the current `memory_get_context` behavior yet

## Decision

For the current `0.6.0` stage, the first AGE-backed slice should be:

- **boundary-first**
- **bootstrap-first**
- **behavior-preserving**

In other words:

- the first AGE-backed slice should define the graph boundary and operational footing
- it should **not yet** change `memory_get_context` retrieval behavior
- it should **not yet** broaden traversal, relation semantics, or grouped output structure

## What this means

The first AGE-backed slice should focus on clarifying and preparing:

1. **ownership boundary**
   - what the graph layer is responsible for
   - what remains canonical in relational storage

2. **bootstrap responsibility**
   - where AGE setup/init happens
   - who is responsible for ensuring graph availability

3. **operational expectations**
   - what happens when the graph layer is unavailable
   - how local/dev/test environments should behave
   - whether the graph layer is optional or required in the first slice

4. **future insertion points**
   - where later constrained graph-backed reads may attach
   - how repository boundaries can stay compatible with later graph-backed work

It should **not** yet make the graph layer the driver of retrieval semantics.

## Why this decision is appropriate now

### 1. The current retrieval contract was only recently stabilized

The current `memory_get_context` grouped/auxiliary/episode-less reading is now covered well enough across:

- tests
- service-contract documentation
- MCP API documentation
- model-level notes
- handoff notes

Changing retrieval behavior immediately at the first AGE step would reopen an area that was only just made stable enough to reason about clearly.

### 2. AGE should not enter the system first as unexplained behavior drift

If the graph layer first appears as user-visible retrieval behavior before its boundary is clear, several risks increase immediately:

- boundary confusion between relational and graph layers
- difficulty explaining current retrieval semantics
- accidental broadening of relation traversal
- premature graph-shaped abstractions
- test fragility around partially-defined graph semantics

The plan explicitly warns against this kind of drift.

### 3. Operational clarity matters before retrieval expansion

AGE introduces operational questions that are distinct from retrieval semantics, including:

- initialization
- schema/graph lifecycle ownership
- failure handling
- optional vs required deployment expectations
- local development behavior
- testing assumptions

Those questions should be answered before AGE becomes a visible retrieval dependency.

### 4. A clean boundary helps later constrained prototypes

A later graph-backed prototype is more useful when it starts from a clear footing:

- canonical relational state remains explicit
- graph usage is intentionally scoped
- failure/degradation expectations are known
- repository/service insertion points are already understood

That makes later constrained experiments safer and easier to evaluate.

## Relationship to the current canonical model

The current canonical system of record should remain:

- the relational database layer

The graph layer should initially be treated as:

- supplementary
- derived or support-oriented
- not yet the canonical determinant of retrieval behavior

At this stage, AGE should be introduced as an additional layer whose boundary is being defined, not as a replacement for the current relational contract.

## What the first AGE-backed slice should include

The first AGE-backed slice should include decisions or implementation support for items such as:

### 1. Graph ownership boundary
Clarify:

- what data the graph layer is expected to mirror or represent
- what data remains canonical in relational tables
- what kinds of queries the graph layer may later support

### 2. Bootstrap/init responsibility
Clarify:

- where AGE initialization happens
- whether bootstrap occurs at app startup, migration time, or a separate setup step
- who is responsible for ensuring the graph exists and is ready

### 3. Failure and degradation expectations
Clarify:

- whether the first slice treats AGE as optional or required
- what happens when AGE is unavailable
- whether retrieval paths should degrade cleanly to the relational path

### 4. Environment expectations
Clarify:

- local development expectations
- test environment expectations
- production assumptions for the first graph-enabled phase

### 5. Future extension boundary
Clarify:

- where later constrained graph-backed read experiments may plug in
- how to avoid locking the system into premature graph semantics

## What the first AGE-backed slice should not include

The first AGE-backed slice should **not** include any of the following:

- changing the current `memory_get_context` visible response contract
- broadening relation traversal beyond the current constrained shape
- introducing multi-hop graph retrieval
- adding relation types beyond the currently constrained reading
- making the graph layer the canonical source of retrieval truth
- redesigning grouped output structure
- changing auxiliary-group positioning
- introducing graph-first ranking or planning semantics
- using AGE as justification for broader hierarchy claims than the current retrieval semantics support

## Why not start with a graph-backed retrieval behavior change

A tempting alternative would be to start with a very small graph-backed retrieval behavior, such as:

- a constrained `supports` one-hop read experiment
- a graph-backed alternative relation lookup path

That may become a good **second** graph-oriented slice.

However, it is not the best **first** AGE-backed slice because it would force several unresolved questions too early:

- is graph availability required for that path
- how should failures degrade
- is graph state canonical or derived
- what boundary should repository contracts assume
- how should tests distinguish graph semantics from current relational semantics

Those are better answered first.

## Candidate second slice after this decision

Once the boundary-first AGE slice is done, a natural next candidate would be:

- a constrained internal prototype for one graph-backed relation read path

The most plausible later candidate would still remain narrow, such as:

- one-hop `supports` only
- behavior-preserving where possible
- no grouped-response redesign
- no graph-first semantics

That later slice should only happen after the boundary and operational footing are clear.

## Operational questions that should be settled in this first slice

This decision should connect directly to the AGE operational questions already identified in the `0.6.0` plan.

The first AGE-backed slice should settle questions such as:

- how AGE is initialized
- where graph namespace/schema lifecycle lives
- whether the graph layer is optional or required in the first stage
- how the app behaves when the graph layer is unavailable
- what local/dev/test environments are expected to provide
- whether graph bootstrap belongs to application startup, migration/setup tooling, or a separately managed operational step

## Non-goals of this decision

This note does **not**:

- implement AGE behavior
- change retrieval behavior
- add new response fields
- broaden relation traversal
- redesign grouped response structure
- decide any later graph-backed retrieval semantics in detail

It only sets the recommended boundary for the **first** AGE-backed slice.

## Working rule

Use this rule for the next graph-oriented work:

- **define the graph boundary first**
- **stabilize bootstrap and operational expectations second**
- **only then consider a constrained graph-backed retrieval experiment**

## Decision summary

For the current `0.6.0` stage, the first AGE-backed graph slice should be:

- **boundary-first**
- **bootstrap-first**
- **behavior-preserving**

The graph layer should enter the system first as a clearly bounded operational and architectural layer, not yet as a retrieval-semantics expansion.