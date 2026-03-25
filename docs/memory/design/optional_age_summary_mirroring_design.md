# Optional Derived AGE Summary Mirroring Design for `0.6.0`

## Purpose

This note defines the **minimum design direction** for optional derived Apache
AGE mirroring of canonical summaries in `0.6.0`.

It follows the currently established hierarchy work, including:

- relational canonical summary ownership
- explicit summary-first retrieval
- explicit episode-scoped summary building
- replace-or-rebuild semantics for matching summary kinds
- behavior-preserving boundaries around current retrieval and workflow behavior

This note answers the next design question:

> If summary mirroring is added to AGE, what is the smallest safe and useful
> design that preserves relational canonical ownership and avoids premature graph
> expansion?

The goal is to define a mirroring path that is:

- optional
- derived
- rebuildable
- operationally understandable
- compatible with the current first summary loop
- small enough to avoid turning `0.6.0` into a graph-platform rewrite

---

## Status

**Decision status:** current design direction  
**Intended phase support:** later `0.6.0` follow-up after the first canonical
summary loop

This note is a design-direction note.
It does **not** claim that summary mirroring is already implemented.

---

## Context

The repository now already has a meaningful first summary hierarchy loop:

- canonical `memory_summaries`
- canonical `memory_summary_memberships`
- summary-first retrieval through `memory_get_context`
- explicit summary build through:
  - `build_episode_summary(...)`
  - `ctxledger build-episode-summary`
- replace-or-rebuild behavior for matching episode summaries
- in-memory and PostgreSQL-backed validation
- serializer, MCP, and HTTP transport coverage
- PostgreSQL-backed builder-to-retrieval integration coverage

That means the next graph-oriented question is no longer whether summaries can
exist canonically.

They can.

The question is:

- whether summaries should also be mirrored into AGE
- what that mirrored shape should look like
- when the mirrored state should be created or refreshed
- what operational guarantees should apply
- how to avoid confusing graph state with canonical truth

---

## Core direction

The current recommended direction is:

- **relational summaries remain canonical**
- **AGE summary state, if added, remains derived**
- **summary mirroring is optional**
- **summary mirroring should be rebuildable**
- **summary mirroring should be justified by a concrete traversal benefit**
- **summary mirroring should not be required for the current first retrieval loop**

In practical terms:

1. canonical summary rows and memberships remain in PostgreSQL tables
2. graph mirroring, if added, should reflect those canonical records
3. graph mirroring should not become the only readable source of summary truth
4. missing graph summary state must not break ordinary summary retrieval
5. summary-first retrieval in the current first slice should still work from
   relational state alone

This preserves the Phase A ownership boundary and avoids graph-first drift.

---

## Why this direction is appropriate now

### 1. The canonical summary model already exists relationally

The repository now has a real relational summary model:

- `memory_summaries`
- `memory_summary_memberships`

Those records are already sufficient for:

- explicit summary building
- summary-first retrieval
- replace-or-rebuild behavior
- deterministic testing

That means graph mirroring should be introduced only as a supporting read aid,
not as the thing that makes summaries possible.

### 2. The current first retrieval improvement does not require graph traversal

The first hierarchy-aware retrieval improvement is:

- summary-first selection
- direct summary-member memory-item expansion

That path is already meaningful without graph traversal.

So any graph mirroring added now must be justified by a later constrained
traversal benefit, not by retroactively pretending the first retrieval slice
needed graph support all along.

### 3. The system already has a strong canonical/derived boundary

Current `0.6.0` direction already says:

- PostgreSQL is canonical
- AGE is derived/supporting
- bootstrap is explicit
- failures degrade safely
- graph support is not allowed to silently redefine retrieval correctness

Summary mirroring should inherit that exact boundary.

### 4. Premature broad mirroring would overbuild the milestone

A tempting path would be to mirror:

- summaries
- memberships
- episodes
- workspaces
- workflows
- recursive summary links
- future ranking metadata

That would expand graph scope too quickly.

The current direction should remain:

- mirror only what a proven traversal path needs
- no more

---

## Recommended first mirrored shape

If summary mirroring is added, the first mirrored graph shape should be:

- summary nodes
- memory item nodes
- summary-membership edges

That means the first optional graph extension for summaries should mirror the
same first hierarchy shape that already exists canonically:

- `summary -> memory_item`

### Recommended labels

Suggested first labels:

- node label: `memory_summary`
- node label: `memory_item`
- edge label: `summarizes`

The exact label names can vary if implementation constraints suggest a better
repository-local naming convention, but the important thing is that they remain:

- explicit
- narrow
- stable enough for the first traversal slice
- traceable to canonical IDs

---

## Canonical-to-graph mapping

### Summary nodes

Each mirrored summary node should remain traceable to canonical summary identity.

Minimum recommended properties:

- `memory_summary_id`
- `workspace_id`
- `episode_id` when present
- `summary_kind`

Optional lightweight diagnostic properties:

- `created_at`
- small metadata subset if useful for graph diagnostics

The graph node does **not** need to carry the entire canonical summary payload if
that is not required for the traversal use case.

### Memory item nodes

The existing memory item mirroring model can remain the basis for child nodes.

Minimum identity property:

- `memory_id`

### Summary-membership edges

Each mirrored membership edge should remain traceable to canonical membership.

Minimum recommended properties:

- `memory_summary_id`
- `memory_id`
- `membership_order`
- optionally `memory_summary_membership_id`

The key rule is:

- edge identity must stay explainable against canonical relational rows

---

## What should remain out of the first mirrored shape

The first summary mirroring slice should **not** include:

- summary-to-summary recursive edges
- workspace summary nodes beyond proven need
- workflow nodes
- episode nodes purely for completeness
- ranking metadata graphs
- relation traversal composition between `supports` and `summarizes`
- graph-only parentage rules
- graph-native summary generation state

This keeps the graph mirroring small and faithful to the currently implemented
canonical model.

---

## Mirroring responsibility

The current recommended mirroring responsibility is:

- **explicit build/refresh path**
- not ordinary retrieval
- not ordinary startup
- not hidden side effects during canonical summary writes

### Preferred responsibility split

#### Canonical write path
Responsible for:

- writing `memory_summaries`
- writing `memory_summary_memberships`

#### Optional graph mirroring path
Responsible for:

- reading canonical summary rows
- reading canonical membership rows
- rebuilding or refreshing graph summary state

#### Retrieval path
Responsible for:

- checking graph readiness
- using graph-backed traversal only when explicitly enabled and ready
- degrading to relational traversal otherwise

This keeps graph summary state derived and operationally understandable.

---

## Recommended mirroring trigger model

The first summary mirroring slice should prefer:

- **explicit mirroring**
- **explicit refresh**
- **rebuild-first behavior**

Acceptable initial trigger shapes include:

- a dedicated bootstrap/refresh command
- an explicit operator/developer command
- a narrow follow-up command adjacent to current AGE bootstrap flows

What should **not** happen initially:

- automatic mirroring during `memory_get_context`
- automatic mirroring during every summary build
- hidden graph refresh on ordinary startup
- graph repair during unrelated runtime requests

The first summary mirroring slice should remain as explicit as the first graph
boundary slice was.

### Current recommended refresh trigger rule set

If summary mirroring is implemented, the current smallest acceptable trigger and
refresh rules should be:

1. **manual or operator-invoked refresh first**
   - the first supported trigger should be an explicit operator/developer action
   - not an implicit side effect of ordinary reads or writes

2. **refresh from canonical relational state**
   - refresh should read:
     - `memory_summaries`
     - `memory_summary_memberships`
     - canonical `memory_items` identity state needed for mirrored child nodes
   - refresh should not depend on graph state to discover canonical summary truth

3. **episode-scoped or explicitly selected refresh is acceptable first**
   - the first implementation may support:
     - one selected summary
     - one selected episode
     - or an explicit rebuild of all currently supported summary graph state
   - but the scope should be explicit in the invocation and result details

4. **replace-or-rebuild, not append-only accumulation**
   - if a mirrored summary scope is refreshed, stale mirrored summary state for
     that same canonical scope should be replaced rather than silently
     accumulated

5. **no implicit trigger from `build_episode_summary(...)` yet**
   - summary mirroring refresh should remain a separate operation in the first
     slice
   - canonical summary build success should not imply graph refresh success

6. **no implicit trigger from workflow completion automation**
   - even if workflow-oriented summary automation is later introduced, graph
     refresh should remain independently gated until there is a stronger reason
     to couple them

### Recommended first trigger priority

If more than one future trigger is considered, the recommended priority is:

1. explicit operator/developer refresh command
2. explicit rebuild command for a bounded summary scope
3. later, and only if clearly justified:
   - a gated post-build refresh path
   - or a gated post-workflow-completion refresh path

This preserves the repository's current explicit-state philosophy.

---

## Relationship to the existing AGE prototype

The repository already has a constrained AGE prototype for:

- one-hop `supports` lookup

Summary mirroring should not immediately collapse into that prototype as if both
graph shapes were the same concern.

### Current relationship

The existing prototype is still:

- narrow
- relation-specific
- behavior-preserving

Summary mirroring would be:

- a separate derived graph shape
- aligned with hierarchy rather than `supports`
- useful only if a later constrained summary traversal path needs it

### Why that distinction matters

Without this distinction, it would be easy to blur:

- relation support graph experiments
- hierarchy summary graph experiments
- canonical summary persistence
- graph-assisted traversal policy

Those should remain separable.

---

## Suggested operator model

If summary mirroring is added, the operator-facing model should remain simple:

1. canonical summary state exists in relational PostgreSQL
2. optional graph mirroring may be refreshed explicitly
3. runtime can report whether summary mirroring is ready
4. retrieval can choose graph-backed traversal only when that graph state is
   explicitly present and usable
5. fallback remains relational

This is the same operational philosophy already established for the first AGE
boundary.

### Recommended first refresh command reading

The first operator-facing mirroring flow should be readable as:

1. canonical summary state already exists
2. operator invokes explicit summary-mirroring refresh
3. refresh rebuilds the supported mirrored summary shape from canonical rows
4. readiness checks confirm whether that mirrored shape is usable
5. retrieval can optionally use the graph-backed path only when that readiness is
   satisfied

The important operational rule is:

- **build canonical summary state first**
- **refresh derived graph state second**
- **readiness gates graph-backed traversal third**

---

## Failure and degradation behavior

The recommended failure model is:

- summary mirroring failure must not invalidate canonical summary writes
- summary mirroring absence must not invalidate ordinary summary retrieval
- graph-backed summary traversal failure must degrade to relational traversal

### If graph summary state is missing

Then:

- canonical summary rows still exist
- canonical membership rows still exist
- `memory_get_context` can still use relational summary-first retrieval
- the graph path is simply unavailable

### If graph summary refresh fails

Then:

- canonical summary build should still be considered complete if the canonical
  relational writes succeeded
- the graph refresh failure should be surfaced explicitly
- the system should remain operational through relational summary retrieval

### If graph-backed summary traversal fails

Then:

- the request should fall back to relational summary expansion
- the failure should be diagnosable
- retrieval correctness should remain tied to canonical relational state

This is the same core degradation rule used elsewhere:

- graph problems degrade to relational behavior
- they do not redefine canonical correctness as broken

## Recommended readiness rules

The first summary mirroring slice should use explicit and narrow readiness rules.

### Readiness should mean

Graph summary state should be considered ready only when all of the following are
true:

1. AGE is available in the current environment
2. the named graph exists
3. the required mirrored summary shape for the supported use case exists
4. the mirrored summary nodes and membership edges are present in a form
   traceable to canonical IDs
5. the constrained graph-backed summary traversal path can run successfully for
   the supported scope

### Readiness should not mean

Graph summary readiness does **not** need to imply:

- recursive summary hierarchy support
- global summary synchronization across all future summary kinds
- graph-native summary truth
- broad graph administration maturity
- support for mixed `supports` + `summarizes` planning

### First acceptable readiness scope

For the first implementation, readiness may be defined only for the current
supported mirrored shape:

- `memory_summary -[summarizes]-> memory_item`

If that shape is not present or not usable, the graph-backed summary path should
be read as unavailable.

### Recommended readiness reporting fields

If runtime or operator reporting is later expanded for summary mirroring, the
first useful readiness details should include fields such as:

- whether summary mirroring is enabled
- whether the named graph exists
- whether mirrored summary nodes are present
- whether mirrored membership edges are present
- whether the constrained graph-backed summary traversal check succeeded
- whether the current retrieval path fell back to relational summary traversal

This keeps readiness operationally understandable.

---

## Replace-or-rebuild implications

The current canonical summary builder already uses replace-or-rebuild semantics
for matching summary kinds.

Graph mirroring should respect that.

### Recommended first rule

If a summary is rebuilt canonically, the graph mirroring refresh should also be
understood as:

- replacing the graph mirror for that canonical summary scope
- not accumulating stale parallel graph state

This strongly favors a rebuild-first graph mirroring model in the first slice.

### Why rebuild-first still fits

A rebuild-first mirroring model is appropriate because:

- graph summary state is derived
- graph summary scope is narrow
- operational clarity is more valuable than early incremental sync logic
- replace-or-rebuild semantics already exist canonically

---

## When summary mirroring becomes justified

The current recommendation is to add summary mirroring only when one of these is
true:

1. a concrete traversal path clearly benefits from graph navigation over
   relational joins
2. a constrained summary traversal query becomes awkward or noisy enough in
   relational-only form that graph traversal materially improves clarity
3. a later `0.6.0` or `0.7.0` experiment specifically needs summary graph
   traversal to evaluate retrieval quality

Until then, relational summary retrieval remains the preferred baseline.

---

## Recommended first graph-backed summary use case

If summary mirroring is added later, the first graph-backed summary use case
should still remain narrow.

A plausible first candidate is:

- traversing from one summary node to its direct member memory items through
  graph edges
- only for a constrained internal read path
- with explicit fallback to relational expansion

That would preserve:

- single-layer traversal
- behavior-preserving retrieval
- no recursive graph semantics
- no graph-only correctness

This is a better first graph-backed summary use case than:

- summary-of-summary recursion
- mixed `supports` + `summarizes` multi-hop planning
- graph-first ranking

---

## Validation strategy

If summary mirroring is added, validation should stay incremental.

### 1. Graph shape validation
Test:

- summary nodes are created
- membership edges are created
- canonical IDs are mirrored correctly
- rebuild removes stale graph state

### 2. Refresh-trigger validation
Test:

- explicit refresh creates the mirrored summary shape from canonical state
- repeated refresh replaces stale mirrored summary state rather than appending it
- bounded refresh scopes behave as documented
- refresh failure leaves canonical summary state intact

### 3. Readiness validation
Test:

- graph summary state absent -> relational fallback
- graph summary state present -> graph path eligible
- graph summary state invalid -> relational fallback
- readiness reporting reflects the actual supported mirrored shape rather than a
  broader implied graph capability

### 4. Retrieval validation
Test:

- graph-backed summary traversal returns the same canonical child set as the
  relational fallback for the constrained use case
- explainability remains intact
- failure handling remains non-catastrophic

### 5. Broader validation
After the slice is stable:

- rerun focused suites
- rerun full pytest suite

---

## What should remain out of scope for now

This optional summary mirroring design should **not** yet include:

- recursive summary graphs
- graph-required summary build
- graph-required summary retrieval
- graph-native summary truth
- automatic graph mirroring on every canonical write
- broad multi-route ranking logic
- graph-driven summary generation
- summary mirroring as a release prerequisite

Those would over-expand the current milestone and weaken the clarity of the
relational-first model.

---

## Working rules

Use these rules if summary mirroring is implemented later.

### Ownership rule
- canonical summary rows and memberships remain relational truth

### Shape rule
- first mirrored shape is only:
  - `memory_summary`
  - `memory_item`
  - `summarizes`

### Trigger rule
- mirroring is explicit and rebuildable
- not a hidden side effect of ordinary reads or writes

### Failure rule
- graph problems degrade to relational summary retrieval

### Scope rule
- no recursive summary graph semantics in the first mirroring slice

### Justification rule
- mirror only when a concrete traversal benefit is clear

---

## Decision summary

The current recommended design for optional derived AGE mirroring of summaries is:

- keep summary ownership canonical in relational PostgreSQL
- mirror summary nodes and summary-membership edges only as derived graph state
- keep mirroring explicit, optional, and rebuild-first
- use explicit refresh triggers before any later automatic trigger is considered
- gate graph-backed traversal behind narrow readiness rules for the mirrored
  summary shape
- keep graph-backed summary traversal non-required and fallback-safe
- start with the narrow mirrored shape:
  - `memory_summary -[summarizes]-> memory_item`
- defer recursive summary graphs and graph-first semantics

This is the smallest graph-oriented summary extension that stays consistent with
the current `0.6.0` boundaries, the existing AGE posture, and the now-implemented
canonical summary build/retrieval loop.