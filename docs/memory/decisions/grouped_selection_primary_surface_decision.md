# Grouped Selection Primary Surface Decision

## Context

The recent `memory_get_context` work has already established a clearer internal structure for hierarchical retrieval.

Repository-backed retrieval inputs are now explicit for:

- workspace-root inherited context
- constrained relation-target item lookup
- bulk episode-child memory item lookup

Service-layer projection has also been cleaned up into narrower helpers for:

- summary selection details
- grouped memory context assembly
- retrieval-route explanation metadata

That means the next natural question is no longer primarily about another small repository primitive. It is about which output surface should be treated as the primary hierarchy-oriented behavior.

## Decision

The next hierarchy-oriented design direction should treat:

- `memory_context_groups`

as the **primary grouped hierarchy surface** for `memory_get_context`.

Other flat or compatibility-oriented fields should remain available, but they should be interpreted as:

- derived output
- compatibility output
- convenience output

rather than the canonical hierarchy surface.

## Why this decision is natural now

The current grouped structure already carries the hierarchy meaning more directly than the flat fields.

It encodes:

- scope
- parent relationships
- group selection route
- group selection kind
- summary grouping
- episode grouping
- workspace inherited grouping
- relation auxiliary grouping

That is the actual hierarchy-oriented shape of the response.

By contrast, several other existing fields are useful, but they are flatter and more compatibility-oriented, such as:

- `memory_items`
- `related_memory_items`
- `related_memory_items_by_episode`
- route explanation counts and flags

Those remain useful, but they do not represent the hierarchy as directly as `memory_context_groups`.

## Interpretation change

This decision does **not** require an immediate external breaking change.

Instead, it changes the intended interpretation:

- `memory_context_groups` is the primary hierarchy-aware response surface
- flat and compatibility fields remain supported as auxiliary or derived views
- future hierarchy-oriented behavior should be designed around grouped selection first

## Why not summary-first as the primary surface

Summary-first is important, but it is better understood as one selection route within the grouped hierarchy model rather than as the top-level primary abstraction.

In the current grouped shape:

- summary can be represented as a group
- episode groups can be represented as children or related grouped selections
- workspace and relation auxiliary context can be represented alongside that structure

That makes grouped selection the broader organizing concept, while summary-first remains one important behavior inside it.

## Why not relation-first

Relation-aware behavior is still intentionally constrained.

At the current stage:

- relation traversal is still narrow
- only constrained `supports` behavior is exposed
- broader graph semantics are still intentionally deferred

Because of that, relation-aware output should not define the primary hierarchy model yet. It remains an auxiliary grouped surface inside the broader hierarchy response.

## Practical meaning for future work

From this point onward, deeper hierarchy slices should prefer to answer questions in terms of:

- what groups exist
- how groups are related
- which selection route produced each group
- which scope each group belongs to
- which outputs are canonical vs compatibility-oriented

rather than primarily expanding flat convenience fields.

## Non-goals of this decision

This decision does **not** by itself do any of the following:

- remove flat compatibility fields
- change current response semantics
- redesign grouped output structure immediately
- broaden relation traversal
- introduce ranking changes
- force a breaking API change

It is a design-direction decision, not a behavior-breaking migration.

## Recommended next implementation slice

The next small implementation-oriented slice should likely be one of these:

1. make grouped selection semantics more explicit within `memory_context_groups`
   - keep behavior unchanged where possible
   - improve consistency of grouped fields and interpretation

2. tighten the distinction between:
   - primary grouped output
   - compatibility output
   - convenience output

3. avoid adding new relation behavior unless grouped hierarchy work actually requires it

## Decision summary

The next hierarchy-aware design step should treat `memory_context_groups` as the canonical grouped surface for `memory_get_context`.

The working rule is:

- grouped hierarchy output is primary
- flat fields are derived or compatibility-oriented
- future hierarchy slices should be designed around grouped selection semantics first