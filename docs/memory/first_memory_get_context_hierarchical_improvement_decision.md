# First `memory_get_context` Hierarchical Retrieval Improvement Decision

## Purpose

This note defines the **first constrained hierarchical retrieval improvement**
for `memory_get_context` in `0.6.0`.

It follows the current canonical design decisions already established for this
milestone:

- `docs/memory/first_age_slice_boundary_decision.md`
- `docs/memory/minimal_hierarchy_model_decision.md`
- `docs/memory/grouped_selection_primary_surface_decision.md`

This note answers the next narrow question:

> After fixing the Phase A boundary and the Phase B minimal hierarchy model,
> what is the first meaningful hierarchical retrieval behavior that
> `memory_get_context` should add?

The goal is to choose a behavior slice that is:

- hierarchy-aware
- small
- explainable
- behavior-preserving outside the active target area
- consistent with relational canonical ownership
- compatible with later graph-assisted traversal without requiring it now

---

## Status

**Decision status:** active  
**Phase:** `0.6.0` Phase D  
**Depends on:**
- `docs/memory/first_age_slice_boundary_decision.md`
- `docs/memory/minimal_hierarchy_model_decision.md`
- `docs/memory/grouped_selection_primary_surface_decision.md`

This note should be treated as the canonical decision record for the first
hierarchical retrieval improvement in `memory_get_context` until a later slice
explicitly broadens retrieval behavior further.

---

## Decision

The first hierarchical retrieval improvement for `memory_get_context` should be:

- **summary-first selection**
- followed by
- **summary-member memory-item expansion**
- while
- **preserving the current grouped-primary contract**
- and
- **avoiding broad response redesign**

More concretely:

1. introduce the ability for retrieval to select one or more canonical summaries
   as the first hierarchy-aware compressed layer
2. expand selected summaries to their member memory items
3. assemble both compressed and concrete context from that same selection
4. treat grouped output as the primary hierarchy-aware surface
5. preserve existing episode-oriented and compatibility-oriented output surfaces
   unless a later slice intentionally redesigns them
6. avoid making graph traversal, recursive hierarchy, or summary-to-summary
   traversal part of this first improvement

This is the first meaningful hierarchical improvement because it introduces a
real compressed-then-expand retrieval path without forcing deeper hierarchy or
graph semantics too early.

---

## Why this is the right first improvement

The repository has already clarified several important constraints:

- graph support must remain boundary-first and behavior-preserving
- relational storage remains canonical
- the minimal hierarchy model is:
  - canonical summary entities
  - canonical summary-to-item membership
  - a shallow `summary -> memory_item` structure
- grouped output should be treated as the primary hierarchy-aware response
  surface

Given those decisions, the next retrieval improvement should not be:

- a broad graph traversal experiment
- a recursive summary hierarchy experiment
- a grouped-output redesign
- an episode-less contract reshaping exercise
- another narrow metadata-only addition

Instead, it should be the smallest actual retrieval behavior that proves the
value of the new hierarchy model.

Summary-first selection with member expansion is that behavior.

It introduces:

- compressed selection
- explicit hierarchy-aware expansion
- a real retrieval route improvement
- a narrow and explainable service-layer behavior change

without requiring:

- recursive hierarchy
- graph-first semantics
- relation-first ranking
- major transport contract churn

---

## What this improvement means

The first hierarchical improvement should allow `memory_get_context` to do the
following, conceptually:

1. identify candidate summaries in the relevant scope
2. choose one or more summaries as the compressed retrieval layer
3. expand those summaries to their member memory items
4. assemble a response that can expose:
   - compressed grouped context
   - concrete child memory items
   - additive route/provenance metadata

This creates a real hierarchy-aware path of:

- `summary -> memory_item`

That path is enough to demonstrate hierarchical retrieval in a concrete way.

---

## Chosen behavior shape

## 1. Primary retrieval route

The first new hierarchy-aware route should be conceptually treated as:

- `summary_first_member_expansion`

The exact route name can remain implementation-local if needed, but the
behavioral meaning should be:

- a summary layer is selected first
- concrete memory items are then derived from summary membership

This is different from current episode-first retrieval because the compressed
selection unit becomes a summary rather than an episode.

---

## 2. Primary grouped surface

Consistent with the grouped-surface decision, the primary hierarchy-aware
response surface should remain:

- `memory_context_groups`

The new improvement should therefore be designed primarily in grouped terms.

That means the ideal grouped reading is:

- a summary-scoped group
- with concrete member-derived context represented in a way consistent with the
  existing grouped-primary interpretation

This decision does **not** require a broad grouped-output redesign.

It only means that the first hierarchical improvement should be thought about
through grouped selection first, not flat compatibility fields first.

---

## 3. Concrete expansion target

The first expansion target should be:

- member `memory_item` records

It should **not** initially expand to:

- child summaries
- recursive summary descendants
- relation-derived supporting items as part of the core hierarchy behavior
- graph-only descendants

This keeps the improvement aligned with the minimal hierarchy model.

---

## 4. Compatibility behavior

Flat and compatibility-oriented fields may continue to exist.

However, they should be interpreted as:

- derived from the grouped hierarchy-aware result
- compatibility-oriented
- convenience-oriented

rather than as the canonical hierarchy model.

This follows the current contract direction and avoids forcing a breaking API
change in the first hierarchy-aware retrieval slice.

---

## Scope constraints

The first hierarchical retrieval improvement should remain deliberately narrow.

## Included

Included in scope:

- summary-first compressed selection
- summary-member memory-item expansion
- grouped-primary interpretation
- additive route/provenance metadata where needed
- behavior that can be implemented with relational canonical summary and
  membership data

## Excluded

Explicitly excluded from this first slice:

- summary-to-summary recursion
- arbitrary-depth hierarchy traversal
- graph-required traversal
- graph-first ranking or planning semantics
- broad redesign of `memory_context_groups`
- removal of compatibility fields
- relation-first retrieval redesign
- episode-less contract redesign
- automatic expansion into all related auxiliary contexts
- global ranking architecture changes

---

## Why not make the first improvement graph-first

Although Apache AGE is part of the `0.6.0` direction, the first hierarchical
retrieval improvement should not depend on graph-first traversal.

Reasons:

1. Phase A already established that graph support is supplementary and derived.
2. The minimal hierarchy model is canonical in relational storage.
3. A graph-first retrieval requirement would conflate:
   - hierarchy-model introduction
   - graph traversal semantics
   - deployment/readiness questions
4. The first retrieval improvement should prove hierarchy value even before
   richer graph traversal is necessary.

Graph mirroring or graph-backed traversal may become useful later, but they
should not define the first retrieval improvement.

---

## Why not make the first improvement relation-first

A relation-first improvement would push the next retrieval slice toward:

- broader `supports` semantics
- relation ranking questions
- traversal depth questions
- semantic relation policy questions

That would widen the slice too early.

The current constrained relation-aware path remains useful, but it is not the
best foundation for the **first** hierarchy-aware improvement.

The first hierarchy-aware improvement should be hierarchy-first, not
relation-first.

---

## Why not redesign the episode-less path first

The episode-less path has already been explicitly kept narrow.

That remains the right decision for now.

Revisiting episode-less shaping first would:

- reopen a recently stabilized contract boundary
- create a partial intermediate response shape
- blur the distinction between:
  - summary-first grouped shaping
  - episode-oriented shaping
  - episode-less shaping

That is not the best first hierarchical improvement.

The better move is to add a clear, positive hierarchical retrieval behavior
first, rather than revisiting the narrower suppression behavior.

---

## Why not choose another metadata-only slice

Another possible next step would be to add more `details` fields without changing
selection behavior.

That would have limited value now.

The milestone already has substantial explainability metadata.

The plan specifically benefits more from a real small behavior choice than from
another narrow metadata-only refinement.

Summary-first selection plus member expansion is the smallest behavior change
that materially advances hierarchical retrieval.

---

## Recommended retrieval reading

The first hierarchical improvement should be read as:

- **select compressed context first**
- **expand concrete context second**

In practical retrieval terms:

1. resolve the relevant scope
2. select summaries within that scope
3. choose one or more summaries
4. expand their member memory items
5. return both compressed grouped context and concrete member-derived context in
   one explainable response

This is the intended first proof of hierarchical retrieval value in
`memory_get_context`.

---

## Recommended selection boundary

The first selection boundary should stay conservative.

### Preferred first scope

Prefer a scope that is already understandable in current retrieval behavior, such
as:

- workflow-resolved episode context
- workspace-scoped summary context
- another already explainable canonical scope

The key rule is:

- do not introduce an entirely new scope model just to make the first
  hierarchical improvement work

### Preferred first selection semantics

The first selection semantics should remain simple:

- choose summaries from a clearly resolved scope
- keep deterministic ordering
- keep explainability visible
- avoid heavy ranking claims too early

---

## Recommended expansion boundary

The first expansion boundary should also stay conservative.

### Expand only direct members

For the first slice, expansion should mean:

- retrieve direct member `memory_item` records for the selected summaries

It should not yet mean:

- recursive descent
- relation traversal from members as part of the same hierarchy route
- expansion into sibling summaries
- expansion into arbitrary graph neighbors

### Keep explainability explicit

The response should make it understandable that:

- summaries were selected first
- member items were expanded from those summaries
- the result combines compressed and concrete layers

This can be done through grouped structure and additive details metadata.

---

## Contract direction for response shaping

The first hierarchical improvement should preserve the current broad contract
direction.

### Primary surface

Primary hierarchy-aware surface:

- `memory_context_groups`

### Secondary surfaces

Secondary surfaces may continue to exist for compatibility:

- flat memory-item lists
- related-item compatibility fields
- other derived convenience fields

### Explainability requirement

The response should remain explicit enough to show:

- that summary-first selection occurred
- whether concrete member expansion occurred
- how many summaries participated
- how many member items participated
- which route contributed the grouped and concrete outputs

This should remain additive and descriptive.

It should not force an immediate contract break.

---

## Minimal success criteria

A minimally successful first hierarchical retrieval improvement should be able to
do all of the following:

1. return at least one summary-derived grouped context surface
2. expand at least one selected summary into concrete member memory items
3. keep the result understandable through grouped output and details metadata
4. preserve canonical relational ownership
5. avoid requiring graph-backed traversal
6. avoid broad response redesign
7. remain compatible with later graph-assisted or deeper hierarchy work

If those criteria are met, the slice is a real hierarchical retrieval
improvement.

---

## Consequences for repository and service design

Because of this decision, later implementation work should naturally split into
two parts.

## Repository side

The repository layer should support minimal summary and membership primitives,
such as:

- create/read summary entities
- create/read summary membership mappings
- list member items for selected summaries
- list summaries in a resolved scope

## Service side

The service layer should remain responsible for:

- selecting the retrieval route
- choosing candidate summaries
- expanding member items
- shaping grouped output
- surfacing additive explainability metadata
- preserving compatibility outputs where needed

This keeps the repository narrow and the hierarchy behavior explainable.

---

## Non-goals of this decision

This note does **not**:

- define the full long-term retrieval architecture
- require graph-backed traversal in the first improvement
- define recursive summary traversal
- define all ranking heuristics
- remove compatibility fields
- redesign the grouped contract wholesale
- change the current episode-less suppression choice
- broaden constrained relation traversal
- define a generic hierarchy engine

It only chooses the first meaningful hierarchy-aware retrieval behavior.

---

## Canonical working rules

Use these rules for the immediate next implementation slice.

### Behavior rule
- the first real hierarchy-aware improvement should be a behavior change, not
  just another metadata refinement

### Selection rule
- summaries are selected first as compressed retrieval units

### Expansion rule
- selected summaries expand only to direct member memory items in the first slice

### Contract rule
- grouped hierarchy output remains primary
- flat outputs remain compatibility or convenience surfaces

### Ownership rule
- relational summary and membership data remain canonical
- graph support remains derived and optional at this behavior boundary

### Scope rule
- do not introduce recursion, graph-first traversal, or broad response redesign
  in this first improvement

---

## Decision summary

The first hierarchical retrieval improvement for `memory_get_context` in
`0.6.0` should be:

- **summary-first selection**
- plus
- **direct member memory-item expansion**

with these constraints:

- grouped hierarchy output remains the primary surface
- relational canonical data remains authoritative
- graph support is not required for this first improvement
- summary-to-summary recursion is deferred
- broad response redesign is deferred
- episode-less contract redesign is deferred

This is the smallest meaningful behavior slice that proves hierarchical
retrieval value while remaining consistent with the established Phase A and
Phase B decisions.