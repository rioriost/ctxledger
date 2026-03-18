# `memory_get_context` Service Contract Note

## Purpose

`memory_get_context` returns **auxiliary memory context** for a workflow-, workspace-, ticket-, or query-oriented lookup.

It is intentionally distinct from `workflow_resume`.

- `workflow_resume` returns canonical operational state
- `memory_get_context` returns support context that may help reasoning, recall, or continuation

This note summarizes the **current service-layer contract direction** for the `0.6.0` hierarchical retrieval work.

---

## Current contract status

The current implementation is still transitional.

It is no longer just flat episode lookup, but it is also not yet the final hierarchical retrieval architecture.

The contract currently aims to be:

- episode-oriented
- hierarchy-aware
- relation-aware in a constrained way
- explainable through additive `details` metadata
- explicit about primary vs auxiliary outputs
- explicit about compatibility and convenience surfaces

---

## Current lookup inputs

The request currently supports these main lookup inputs:

- `query`
- `workspace_id`
- `workflow_instance_id`
- `ticket_id`

The request also supports response-shaping flags including:

- `limit`
- `include_episodes`
- `include_memory_items`
- `include_summaries`

At least one lookup input is required.

---

## High-level retrieval model

The current retrieval path is intentionally conservative.

At a high level, it works like this:

1. resolve candidate workflows from canonical workflow state
2. collect episodes from the resolved workflow set
3. optionally apply lightweight query filtering over episode summaries and metadata text
4. optionally collect direct episode memory items
5. optionally collect inherited workspace memory items as auxiliary context
6. optionally collect one-hop `supports`-related memory items from returned episode memory items
7. expose grouped and flat details that make the assembly path observable

This means the current contract is already multi-route, but still deliberately narrow and explainable.

---

## Current grouped scopes

The current grouped output model is organized around these scopes:

- `summary`
- `episode`
- `workspace`
- `relation`

These scopes describe the current response shape.
They should be treated as the current operational model, not as irreversible final architecture.

---

## Current retrieval routes

The current contract distinguishes between retrieval routes, including:

- `summary_first`
- `episode_direct`
- `workspace_inherited_auxiliary`
- `relation_supports_auxiliary`

These routes are exposed through additive metadata in `details`.

Representative route metadata includes:

- `retrieval_routes_present`
- `primary_retrieval_routes_present`
- `auxiliary_retrieval_routes_present`
- `retrieval_route_presence`
- `retrieval_route_group_counts`
- `retrieval_route_item_counts`
- `retrieval_route_scope_counts`
- `retrieval_route_scope_item_counts`
- `retrieval_route_scopes_present`

This metadata exists to help consumers and operators understand **what was returned** and **why**.

---

## Current grouped output interpretation

`memory_context_groups` should now be treated as the primary grouped hierarchy-aware surface of `memory_get_context`.

Other flat or compatibility-oriented fields remain supported, but they should be interpreted as:

- derived output
- compatibility output
- convenience output

rather than the canonical grouped hierarchy model.

This is an interpretation and contract-direction clarification, not an immediate breaking change.

### 1. Summary-scoped output

When summaries are enabled and returned, the response may include a grouped summary entry with:

- `scope = "summary"`
- `selection_kind = "episode_summary_first"`
- `selection_route = "summary_first"`

This is a grouped summary-oriented surface, not a replacement for raw memory items.

### 2. Episode-scoped output

When memory items are enabled, returned episodes may produce grouped episode entries with:

- `scope = "episode"`
- `selection_kind = "direct_episode"`
- `selection_route = "episode_direct"` or `summary_first`

These episode groups may contain:

- direct episode `memory_items`
- group-local `related_memory_items`
- related-item provenance and relation-edge details

### 3. Workspace-scoped output

When inherited workspace items are available, the response may include a workspace group with:

- `scope = "workspace"`
- `selection_kind = "inherited_workspace"`
- `selection_route = "workspace_inherited_auxiliary"`

This is currently auxiliary support context.

### 4. Relation-scoped output

When constrained relation-derived support context is available, the response may include a relation group with:

- `scope = "relation"`
- `scope_id = "supports"`
- `selection_kind = "supports_related_auxiliary"`
- `selection_route = "relation_supports_auxiliary"`

This is currently the primary grouped structured surface for relation-derived supporting context.

---

## Current related-context semantics

The current `0.6.0` slice distinguishes several related-context surfaces.

### Primary structured output

The current primary grouped structured relation-aware surface is:

- `memory_context_groups` relation-scoped entries

This is reflected by:

- `relation_memory_context_groups_are_primary_output`

### Compatibility outputs

The current compatibility-oriented related-context surfaces include:

- flat top-level `related_memory_items`
- per-episode `related_memory_items_by_episode`

These are reflected by metadata such as:

- `flat_related_memory_items_is_compatibility_field`
- `flat_related_memory_items_matches_grouped_episode_related_items`
- `related_memory_items_by_episode_are_compatibility_output`

### Convenience output

The current convenience-oriented related-context surface is:

- episode-group embedded `related_memory_items`

This is reflected by:

- `group_related_memory_items_are_convenience_output`

In other words:

- `memory_context_groups` is the primary grouped hierarchy-aware surface
- relation groups inside `memory_context_groups` are the primary structured grouped relation-aware surface
- flat related-item output is retained for compatibility
- embedded group-local related items are retained for convenience

---

## Current relation-aware constraints

Relation-aware retrieval is currently narrow by design.

Current constraints include:

- only one outgoing relation hop is traversed
- only `relation_type = "supports"` is currently included
- relation-derived context is treated as auxiliary support context
- relation-derived context does not currently drive episode selection

This keeps the retrieval path understandable while the broader hierarchy work is still in progress.

---

## Current auxiliary-context semantics

The contract currently treats some returned context as auxiliary rather than primary selection output.

Representative metadata includes:

- `inherited_context_is_auxiliary`
- `inherited_context_returned_without_episode_matches`
- `inherited_context_returned_as_auxiliary_without_episode_matches`
- `related_context_is_auxiliary`
- `related_context_relation_types`
- `related_context_selection_route`

This means the response may contain useful support context even when episode matching is narrow or absent.

For example:

- workspace-inherited context may still appear when no episodes survive query filtering
- relation-derived support context is currently additive auxiliary context, not a primary ranking route

---

## Current query-filter semantics

Lightweight query filtering currently applies to:

- episode `summary`
- lightweight metadata-derived text

It does not currently apply as a primary filter over:

- inherited workspace items
- relation-derived support items

This means the response may still include auxiliary context even when:

- `matched_episode_count = 0`
- `episodes_returned = 0`
- `all_episodes_filtered_out_by_query = true`

When interpreting the response in those cases, consumers should still prefer the grouped hierarchy-aware reading first:

- use `memory_context_groups` as the primary grouped surface
- treat flat compatibility fields as derived or compatibility-oriented views of that grouped result

That behavior is currently intentional.

---

## Representative `details` fields

The current service contract is meant to be explainable through additive `details` metadata.

Representative fields include:

- request echo and normalization
  - `query`
  - `normalized_query`
  - `query_tokens`
  - `lookup_scope`
  - `workspace_id`
  - `workflow_instance_id`
  - `ticket_id`
  - `limit`
  - `include_episodes`
  - `include_memory_items`
  - `include_summaries`

- workflow resolution and filtering
  - `workflow_candidate_ordering`
  - `resolved_workflow_count`
  - `resolved_workflow_ids`
  - `query_filter_applied`
  - `episodes_before_query_filter`
  - `matched_episode_count`
  - `episodes_returned`
  - `episode_explanations`
  - `all_episodes_filtered_out_by_query`

- grouped assembly and hierarchy
  - `summary_selection_applied`
  - `summary_selection_kind`
  - `hierarchy_applied`
  - `memory_context_groups`

- direct, inherited, and related outputs
  - `memory_items`
  - `memory_item_counts_by_episode`
  - `summaries`
  - `inherited_memory_items`
  - `related_memory_items`
  - `related_memory_items_by_episode`

- route and output semantics
  - `retrieval_routes_present`
  - `primary_retrieval_routes_present`
  - `auxiliary_retrieval_routes_present`
  - `retrieval_route_presence`
  - `retrieval_route_group_counts`
  - `retrieval_route_item_counts`
  - `retrieval_route_scope_counts`
  - `retrieval_route_scope_item_counts`
  - `retrieval_route_scopes_present`
  - `flat_related_memory_items_is_compatibility_field`
  - `flat_related_memory_items_matches_grouped_episode_related_items`
  - `related_memory_items_by_episode_is_primary_structured_output`
  - `related_memory_items_by_episode_are_compatibility_output`
  - `relation_memory_context_groups_are_primary_output`
  - `group_related_memory_items_are_convenience_output`

Not every field is present for every interpretation need, but together they describe the current contract direction.

---

## Intended consumer interpretation

Consumers should currently interpret `memory_get_context` as:

- a support-context assembly operation
- not a canonical workflow-state operation
- not yet a fully mature semantic retrieval contract
- already rich enough to expose route- and scope-level explainability
- explicitly transitional in its coexistence of primary, auxiliary, compatibility, and convenience surfaces

When in doubt:

- treat `memory_context_groups` as the most structured current surface
- treat top-level flat related-item outputs as compatibility-oriented
- treat group-embedded related-item outputs as convenience-oriented
- use the additive `details` metadata to understand how the response was assembled

---

## Near-term direction

The current near-term direction is to keep refining the service-layer retrieval contract so it remains:

- small-slice implementable
- operationally understandable
- testable
- compatible with deeper repository/schema hierarchy work later in `0.6.0`

This note is therefore a snapshot of the **current contract direction**, not a promise that every field name or route will remain unchanged forever.