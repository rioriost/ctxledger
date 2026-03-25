# Minimal Hierarchy Model Decision for `0.6.0` Phase B

## Purpose

This note defines the **minimal hierarchy model** for `0.6.0` Phase B.

It follows the Phase A canonical decision recorded in:

- `docs/memory/decisions/first_age_slice_boundary_decision.md`

This note is intended to answer the next constrained design question:

> What is the smallest useful hierarchy model that can support later
> hierarchy-aware retrieval work without prematurely redesigning the memory
> system?

The goal is to introduce the smallest durable model that:

- preserves PostgreSQL as the canonical system of record
- remains compatible with the current boundary-first AGE approach
- keeps repository contracts explicit and narrow
- creates a clear path toward one small hierarchical retrieval improvement
- avoids broad hierarchy or graph abstraction too early

---

## Status

**Decision status:** active  
**Phase:** `0.6.0` Phase B  
**Depends on:** `docs/memory/decisions/first_age_slice_boundary_decision.md`

This note should be treated as the canonical Phase B model decision until a
later phase intentionally broadens hierarchy structure or retrieval behavior.

---

## Decision

The minimal hierarchy model for `0.6.0` Phase B is:

- **canonical summary entities**
- **canonical summary-to-item membership links**
- **no required summary-to-summary hierarchy in the first slice**
- **no graph-native hierarchy truth**
- **graph mirroring only where later traversal is concretely justified**

More concretely:

1. introduce a canonical relational entity for a memory summary
2. introduce a canonical relational mapping between a summary and member memory
   items
3. treat the summary as the first hierarchy node
4. treat member memory items as the first hierarchy children
5. defer summary-to-summary links to a later slice
6. defer broad hierarchy taxonomies and graph-first hierarchy ownership
7. keep retrieval semantics unchanged until a later constrained service-layer
   improvement explicitly uses this model

This is the smallest useful hierarchy model because it introduces one true
compressed layer above memory items without forcing deeper recursive structure
too early.

---

## Why this is the right minimum

The repository already has:

- canonical episodes
- canonical memory items
- canonical memory relations
- a constrained graph boundary
- a behavior-preserving retrieval contract
- a Phase A rule that graph support must remain explicit, derived, and
  degradable

The next step should therefore add the smallest hierarchy primitive that is
genuinely hierarchical.

A summary layer above memory items is the smallest such primitive because it:

- introduces one explicit parent-like layer
- gives later retrieval work something compressive to select first
- remains understandable in relational storage
- can later be mirrored into AGE if traversal value is proven
- does not require immediate recursion, ranking redesign, or graph-owned truth

By contrast, jumping immediately to summary-to-summary trees, mixed graph-first
hierarchies, or generic hierarchy frameworks would overbuild the slice.

---

## Canonical model

## 1. Canonical summary entity

The first new canonical hierarchy entity should be a **memory summary**.

Its role is to represent a compressed or grouped memory unit that stands above a
set of canonical memory items.

The summary is canonical relational data, not a graph-only construct.

### Minimal conceptual fields

The first canonical summary entity should carry only the minimum identity and
ownership information needed for later retrieval work.

Recommended conceptual shape:

- `memory_summary_id`
- `workspace_id`
- optional `episode_id`
- `summary_text`
- `summary_kind`
- `metadata`
- timestamps

### Ownership reading

A summary is:

- canonical
- durable
- relationally owned
- suitable for later retrieval selection
- not merely a presentation artifact

### What a summary is not

In this first slice, a summary is not:

- a graph-native truth object
- a ranking policy object
- a generic hierarchy engine primitive
- a replacement for episodes
- a replacement for memory items

It is simply the first canonical compressed layer above memory items.

---

## 2. Canonical summary membership mapping

The second new canonical hierarchy entity should be an explicit mapping between a
summary and its member memory items.

This is the minimum relation needed to make the summary layer meaningful.

### Minimal conceptual fields

Recommended conceptual shape:

- `memory_summary_membership_id`
- `memory_summary_id`
- `memory_id`
- optional membership ordering field
- optional membership metadata
- timestamps

### Why this mapping is required

Without an explicit summary-to-item mapping, the summary entity would exist only
as isolated text.

The membership mapping makes the hierarchy real by defining:

- which canonical items the summary stands over
- which items may later be expanded from a selected summary
- which child set belongs to a summary in a durable, explainable way

### Canonical ownership rule

Summary membership must remain canonical relational data.

It should not be inferred only from graph state.

---

## 3. First-level hierarchy shape

The first minimal hierarchy shape should be:

- `summary -> memory_item`

This is enough to represent:

- one compressed parent-like node
- a set of concrete child memory items

This first shape is intentionally shallow.

### What is included

Included:

- summary nodes
- child memory items
- explicit membership links

### What is deferred

Deferred:

- summary-to-summary links
- arbitrary-depth recursive hierarchy
- hierarchy-wide ranking policies
- mixed graph-native hierarchy ownership
- generic “node type” platforms

This keeps the model small and semantically clear.

---

## What remains canonical outside the new model

The following remain canonical and unchanged in role:

- `episodes`
- `memory_items`
- `memory_relations`
- workflow-related entities
- workspace-related entities

The minimal hierarchy model is additive.

It does not replace the current canonical memory model.

Instead, it adds one new summary layer and one new membership mapping.

---

## Relationship to episodes

Episodes remain important context containers, but they should not be treated as
the hierarchy model itself.

That distinction matters.

### Episode role

Episodes remain:

- workflow-anchored memory containers
- chronological and operational grouping units
- retrieval inputs and response surfaces already present in the system

### Summary role

Summaries become:

- compressed semantic grouping units
- optional higher-level selection units
- future hierarchy-aware retrieval inputs

### Canonical relationship

For the first slice, a summary may optionally reference an `episode_id`, but the
summary should not be reduced to “just another name for an episode.”

This preserves the difference between:

- operational/chronological grouping
- semantic/compressed grouping

---

## Relationship to memory relations

Memory relations remain a separate concept from summary membership.

That distinction should stay explicit.

### Summary membership is not a generic memory relation

The summary-to-item link should not initially be modeled only as another row in
generic `memory_relations`.

Reasons:

- membership is structurally different from ad hoc semantic relations
- summary membership is part of the hierarchy model itself
- keeping it explicit avoids overloading relation semantics too early
- this keeps repository contracts clearer in early hierarchy work

### Current rule

Use:

- explicit canonical summary membership mapping for hierarchy membership
- canonical `memory_relations` for directional semantic relations such as
  `supports`

This separation keeps the first hierarchy model explainable.

---

## Relationship to AGE

This minimal hierarchy model is designed to be compatible with AGE without
making AGE canonical.

### Canonical rule

The canonical hierarchy model lives in relational PostgreSQL.

### AGE role

If later graph traversal is justified, AGE may mirror:

- summary nodes
- memory item nodes
- summary-to-item membership edges

But that mirroring is:

- supplementary
- derived
- rebuildable
- non-authoritative

### Why mirroring is deferred conceptually

The first need is to define what the hierarchy *is*, not to force immediate
graph traversal for it.

Graph mirroring should follow only when there is a concrete read path that gains
clear value from traversal.

---

## Recommended repository boundary

The repository layer should expose the minimum contracts needed to create and
read this hierarchy model.

The first repository surface should stay narrow and domain-local.

### Recommended canonical repositories or repository responsibilities

At minimum, later implementation should support responsibilities such as:

- create a memory summary
- list summaries by workspace
- list summaries by episode where relevant
- create summary membership
- list member items for a summary
- list summaries for a memory item where needed

### Design rule

Repository methods should express:

- summary persistence
- membership persistence
- simple lookup and expansion primitives

They should not immediately encode:

- full retrieval orchestration
- ranking policy
- grouped response shaping
- graph-first planning semantics

That logic should remain above the repository layer.

---

## Minimum useful read/write semantics

The first model should support these minimal semantics.

### Write semantics

Possible first writes:

1. create a canonical summary
2. attach one or more memory items to that summary through canonical membership
3. preserve ordering and metadata only if concretely needed

### Read semantics

Possible first reads:

1. retrieve summaries for a workspace or episode scope
2. retrieve member memory items for a selected summary
3. optionally retrieve summaries associated with a memory item

These are sufficient to support the first future retrieval experiment:

- select a summary
- drill down to its member items

That is enough for a meaningful first hierarchical retrieval path later.

---

## Why not summary-to-summary yet

A tempting extension is to immediately support:

- summary-to-summary links
- nested summaries
- recursive compression layers

That is not part of the minimal model.

### Why it is deferred

Adding summary-to-summary links immediately would force early decisions about:

- recursive traversal semantics
- depth limits
- parent/child ambiguity
- summary inheritance rules
- ordering and expansion policies
- graph traversal expectations

Those are valid later questions, but they are not required to make the first
hierarchy layer useful.

### Current decision

For the first Phase B slice:

- summary-to-summary hierarchy is deferred
- deeper summary recursion is deferred
- one summary layer over memory items is sufficient

---

## Why not generic hierarchy nodes

Another tempting direction is to create a generic hierarchy-node abstraction
covering:

- episodes
- summaries
- memory items
- workspaces
- future graph nodes

That is also deferred.

### Why it is deferred

A generic hierarchy-node framework would:

- blur canonical domain meanings
- encourage premature abstraction
- make repository contracts less explicit
- hide the actual first use case behind a platform shape

The current project rules favor narrow, domain-local primitives over early
generalization.

### Current decision

Use explicit domain terms:

- memory summary
- summary membership
- memory item

Do not introduce a generic hierarchy engine in this slice.

---

## Recommended first graph-mirroring boundary

If later graph mirroring is added for this model, the first mirrored shape should
remain narrow.

### Recommended mirrored graph shape

- node label for summary
- node label for memory item
- edge label representing summary membership

### Mirroring rule

Only mirror what is needed for a proven traversal use case.

Do not mirror every possible hierarchy concept before a retrieval path needs it.

### Canonical ID traceability

Any mirrored nodes or edges should remain traceable to canonical relational IDs.

This preserves:

- rebuildability
- diagnostics
- explainability
- fallback safety

---

## Consequences for later retrieval work

Because of this model decision, the first meaningful hierarchical retrieval
improvement can remain small.

A later service-layer slice can do something like:

1. identify candidate summaries
2. select one or more summaries
3. expand to member memory items
4. assemble both compressed and detailed context

This is a true hierarchy-aware improvement without requiring:

- recursive traversal
- graph-first ranking
- replacement of current episode surfaces
- broad response redesign all at once

That is exactly the kind of constrained next step the plan calls for.

---

## Non-goals of this model decision

This note does **not**:

- define the final long-term hierarchy architecture
- require summary generation logic in this slice
- define ranking or selection heuristics
- define graph traversal semantics
- require summary-to-summary recursion
- replace episodes with summaries
- replace memory relations with summary membership
- make AGE the source of truth
- redesign `memory_get_context` by itself

It only fixes the smallest canonical hierarchy model worth carrying into later
implementation work.

---

## Canonical working rules

Use these rules for immediate follow-on work.

### Ownership rule
- summaries are canonical relational entities
- summary membership is canonical relational mapping
- graph state, if added later, is derived

### Scope rule
- start with one hierarchy layer:
  - `summary -> memory_item`
- defer recursive summary structure

### Abstraction rule
- use explicit domain-local terms
- do not introduce generic hierarchy platforms yet

### Retrieval rule
- repository contracts should enable summary creation and expansion
- retrieval semantics should only change in a later constrained service slice

### Graph rule
- mirror into AGE only when a concrete traversal benefit is established
- keep graph mirroring rebuildable and non-authoritative

---

## Decision summary

The minimal hierarchy model for `0.6.0` Phase B is:

- a canonical relational **memory summary** entity
- a canonical relational **summary-to-memory-item membership** mapping
- a first shallow hierarchy shape of:
  - `summary -> memory_item`
- no required summary-to-summary recursion in the first slice
- no graph-native hierarchy truth
- no generic hierarchy platform abstraction

This is the smallest useful model that creates a real hierarchical layer while
remaining consistent with the established Phase A boundary:

- relational canonical ownership
- explicit bootstrap/readiness boundaries
- graph as derived support, not truth
- behavior-preserving incremental evolution