# Auxiliary Groups as Top-Level Sibling Groups Decision

## Context

Recent `0.6.0` work around `memory_get_context` has already clarified several important parts of the current hierarchy-aware retrieval shape.

On the retrieval-input side, the current implementation now has explicit repository-backed primitives for:

- workspace-root inherited context selection
- constrained relation-target item lookup
- bulk episode-child memory item lookup

On the service-layer side, projection and explainability have also been clarified through narrower helper boundaries for:

- summary selection details
- grouped memory context assembly
- retrieval-route explanation metadata

In parallel, the current contract direction has already been clarified so that:

- `memory_context_groups` is treated as the primary grouped hierarchy-aware surface
- flatter fields remain available, but are interpreted as derived, compatibility, or convenience outputs

That means the next natural design question is not whether grouped output exists, but how the grouped surfaces should be positioned relative to one another.

## Decision

At the current `0.6.0` stage, the following auxiliary grouped surfaces should remain:

- the workspace inherited auxiliary group
- the relation supports auxiliary group

as **top-level sibling auxiliary groups** inside `memory_context_groups`.

They should **not** yet be nested into the primary summary/episode hierarchy chain.

## What this means

The intended grouped interpretation is:

- the primary grouped path is centered on summary and episode grouping
- auxiliary grouped surfaces can still appear in the same grouped response
- workspace and relation auxiliary groups should remain adjacent grouped surfaces rather than children of summary or episode groups

In practical terms, the current grouped reading is:

- summary -> episode is the primary grouped hierarchy chain when summary-first selection is present
- workspace inherited context remains a top-level auxiliary grouped surface
- relation-derived supporting context remains a top-level auxiliary grouped surface

## Why this decision is appropriate now

### 1. It matches the current contract direction

The current response already distinguishes between:

- primary grouped selection behavior
- auxiliary grouped support behavior

Keeping auxiliary groups as top-level siblings preserves that distinction cleanly.

### 2. It avoids premature hierarchy claims

If workspace or relation groups were nested into the primary summary/episode chain too early, the contract would need to answer harder questions such as:

- is inherited workspace context conceptually a child of a summary group?
- is relation-derived support context conceptually a child of a summary group, an episode group, or both?
- how should multi-workflow workspace/ticket retrieval represent those parent links?
- does nesting imply stronger ownership, causality, or ranking than the current retrieval semantics actually support?

The current implementation is not yet ready to answer those questions without broadening behavior too early.

### 3. Relation behavior is still intentionally narrow

The current relation-aware slice is still constrained to:

- one outgoing hop
- `supports` only
- auxiliary use only

Because relation behavior is still deliberately narrow, it should not yet define or reshape the main hierarchy chain.

### 4. It keeps vertical and horizontal structure separate

The current grouped response is easier to reason about if it is read as:

- a vertical primary chain for summary/episode grouping
- horizontal top-level auxiliary grouped surfaces for workspace and relation support context

This is simpler and more honest than implying deeper ownership semantics the current retrieval behavior does not yet enforce.

## Current intended grouped reading

At the current stage, grouped consumers should read `memory_context_groups` approximately like this:

### Primary grouped path

- summary group when summary-first selection is active
- episode groups as the primary episode-scoped grouped surface
- episode groups may be linked to a summary group through parent-group linkage

### Auxiliary grouped surfaces

- workspace inherited auxiliary group remains top-level
- relation supports auxiliary group remains top-level

These auxiliary groups still belong to the grouped response model, but they are not yet part of the primary summary/episode hierarchy chain.

## Non-goals of this decision

This decision does **not** do any of the following:

- add new response fields
- change current retrieval semantics
- change current relation traversal limits
- make relation groups children of episode groups
- make workspace groups children of summary groups
- remove compatibility fields
- redesign grouped ordering
- introduce broader graph semantics

It is a positioning and interpretation decision, not a broader behavior expansion.

## Why not nest auxiliary groups yet

A future system might choose to make auxiliary groups more structurally attached to the primary chain.

For example, a later design might justify:

- relation groups attached to specific episode groups
- workspace groups attached to a broader workflow-level grouping
- richer graph-backed parent/child semantics

However, doing that now would likely overstate the maturity of the current retrieval model.

The current `0.6.0` slice is still intentionally incremental:

- relational first
- constrained behavior first
- explainability first
- no premature graph-shaped abstraction

Under those constraints, top-level sibling auxiliary groups are the safer and clearer choice.

## Recommended next implementation direction

With this decision in place, the next small behavior-oriented slice should likely focus on:

1. refining the primary grouped selection path
   - especially summary/episode grouped behavior

2. keeping auxiliary grouped behavior explicit but narrow
   - without expanding relation traversal

3. preserving current compatibility outputs
   - unless a later slice explicitly chooses to retire or reshape them

## Decision summary

At the current `0.6.0` stage:

- `memory_context_groups` remains the primary grouped hierarchy-aware response surface
- summary and episode groups define the current primary grouped chain
- workspace and relation auxiliary groups should remain top-level sibling auxiliary groups
- stronger nesting semantics for auxiliary groups are intentionally deferred

## Working rule

Use this rule for the next slices:

- primary grouped path first
- auxiliary grouped siblings alongside it
- no stronger auxiliary parentage until retrieval semantics genuinely justify it