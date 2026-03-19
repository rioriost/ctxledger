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
- `summary_first_has_episode_groups`
- `summary_first_is_summary_only`
- `child_episode_count`
- `child_episode_ordering`
- `child_episode_groups_emitted`
- `child_episode_groups_emission_reason`

This metadata exists to help consumers and operators understand **what was returned** and **why**.

In particular, the current contract now makes the two current `summary_first`
sub-modes explicit:

- `summary_first_has_episode_groups = true` when the grouped response includes
  both the summary-scoped group and episode-scoped groups on the primary
  summary-first chain
- `summary_first_is_summary_only = true` when summary-first selection is active
  but the grouped response contains only the summary-scoped group and no
  episode-scoped groups

These flags are intentionally additive explanation metadata.
They do not introduce a new retrieval route.
They clarify whether the current primary summary-first grouped reading is:

- summary -> episode

or:

- summary only

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
- `child_episode_ids = [...]`
- `child_episode_count = N`
- `child_episode_ordering = "returned_episode_order"`
- `child_episode_groups_emitted = true | false`
- `child_episode_groups_emission_reason = "memory_items_enabled" | "memory_items_disabled"`

This is a grouped summary-oriented surface, not a replacement for raw memory items.

At the current `0.6.0` stage, the primary summary/episode-chain explainability
surface should be treated as explicit enough for the current contract slice.

That means consumers can now read the current summary-first primary chain
directly from the grouped summary entry and closely related top-level details
metadata without needing additional summary-group helper fields for the current
stage.

In particular, the current explicit primary-chain explainability surface now
covers:

- whether summary-first selection is active
- whether the current grouped reading is summary-only or summary-plus-episode
- which child episodes the summary group references
- how many child episodes the summary group represents
- what ordering semantics apply to those child episode references
- whether corresponding episode-scoped grouped entries were emitted
- the current reason for that emittedness or non-emittedness

This should currently be read as a good enough stopping point for the current
primary-chain explainability loop, not as an invitation to keep adding narrowly
incremental summary-group metadata without a stronger behavior need.

At the current stage, this summary-first grouped surface has two explicit
readings:

- **summary -> episode grouped selection**
  - `summary_first_has_episode_groups = true`
  - `summary_first_is_summary_only = false`

- **summary-only grouped selection**
  - `summary_first_has_episode_groups = false`
  - `summary_first_is_summary_only = true`

The summary-only case is expected when summary selection is active but no
episode-scoped grouped entries are emitted on the primary chain, such as when
memory items are disabled for the response shape.

The grouped summary entry now also makes summary-group child cardinality explicit
through:

- `child_episode_count`

This is additive grouped explainability metadata for the summary-scoped group.
It allows grouped consumers to read the current number of summary-linked child
episodes directly, rather than inferring that count only from the length of
`child_episode_ids`.

The grouped summary entry should also make the ordering semantics of those child
episode ids explicit through:

- `child_episode_ordering = "returned_episode_order"`

At the current stage, this means grouped consumers should read
`child_episode_ids` in the same order as the returned `episodes` list for the
current response. This is additive grouped explainability metadata for the
summary-scoped group. It does not introduce a new retrieval route or broaden
selection behavior; it only makes the current ordering commitment explicit.

The grouped summary entry should also make it explicit whether child
episode-scoped groups were emitted in the current response shape through:

- `child_episode_groups_emitted = true | false`

At the current stage, this field should be read as group-local output-shape
metadata for the summary-scoped group:

- `true` means the summary group's child episodes are also represented by
  emitted episode-scoped grouped entries in the current response
- `false` means the summary group still represents child episodes, but those
  episode-scoped grouped entries were not emitted for the current response shape

This is intentionally distinct from child cardinality and child ordering
metadata. It does not change selection behavior. It only makes explicit whether
the summary group's child episode references are accompanied by emitted
episode-scoped grouped entries.

The grouped summary entry should also make the current emittedness reason
explicit through:

- `child_episode_groups_emission_reason = "memory_items_enabled" | "memory_items_disabled"`

At the current stage, this field should be read as additive explainability
metadata for why the summary group's child episode-scoped grouped entries were
or were not emitted in the current response shape:

- `"memory_items_enabled"` means the current response shape permits emitted
  episode-scoped grouped entries for the summary group's child episodes
- `"memory_items_disabled"` means the current response shape does not emit those
  episode-scoped grouped entries because memory-item-shaped episode output is
  disabled

This emittedness-reason metadata is intentionally narrow and current-state
specific. It does not introduce a new retrieval route, a broader selection
policy, or a stronger parentage claim. It only makes the current emittedness
reason explicit for grouped consumers.

### Consolidation note for the current stage

Taken together, the current summary-scoped grouped metadata and the closely
related top-level summary-first details metadata should be treated as sufficient
primary-chain explainability for the current `0.6.0` slice.

In practical terms, the next work should not default to adding yet another small
summary-group explanation field unless a clearer behavior gap appears.

Instead, the current contract direction should be read as:

- primary summary/episode-chain explainability is explicit enough for now
- auxiliary workspace/relation grouped surfaces still remain top-level sibling
  auxiliaries
- broader relation expansion and deeper nesting semantics are still intentionally
  deferred
- the next meaningful step should preferably be either:
  - a genuinely new small grouped-selection behavior choice
  - or a contract-consolidation / interpretation step
  - rather than another narrowly incremental summary-group metadata addition

### 2. Episode-scoped output

When memory items are enabled, returned episodes may produce grouped episode entries with:

- `scope = "episode"`
- `selection_kind = "direct_episode"`
- `selection_route = "episode_direct"` or `summary_first`

These episode groups may contain:

- direct episode `memory_items`
- group-local `related_memory_items`
- related-item provenance and relation-edge details

When these episode-scoped groups are present under summary-first selection, the
contract should be read as the fuller primary grouped chain rather than the
summary-only variant.
That is the case where:

- `summary_first_has_episode_groups = true`
- `summary_first_is_summary_only = false`

In summary-first cases, episode-scoped groups should still be read with `selection_kind = "direct_episode"` as the scope-level kind of the group itself.

The fact that the episode group was surfaced through summary-first assembly is expressed separately through:

- `selection_route = "summary_first"`
- the summary parent-group linkage
- `selected_via_summary_first = true` when present

This means the current contract intentionally separates two ideas:

- `selection_kind` describes what kind of group the entry is at its own scope
- `selection_route` describes how that group was selected or surfaced in the current retrieval path

Under that interpretation, a summary-first episode group is still an episode-scoped direct memory group, but one surfaced through the summary-first retrieval route.

### 3. Workspace-scoped output

When inherited workspace items are available, the response may include a workspace group with:

- `scope = "workspace"`
- `selection_kind = "inherited_workspace"`
- `selection_route = "workspace_inherited_auxiliary"`

This is currently auxiliary support context.

At the current stage, grouped consumers should also read this workspace-scoped
auxiliary surface conservatively in no-episode-match cases.

In particular:

- inherited workspace auxiliary context may remain visible even when no episode
  survives query filtering
- this is an intentional auxiliary-context behavior of the current contract
- it should not be read as reviving filtered primary episode selection
- it should not be read as evidence that inherited workspace items themselves
  participated in episode matching

The current details-layer fields that make this reading explicit include:

- `all_episodes_filtered_out_by_query`
- `inherited_context_is_auxiliary`
- `inherited_context_returned_without_episode_matches`
- `inherited_context_returned_as_auxiliary_without_episode_matches`

Taken together, these fields mean the current contract distinguishes between:

- primary episode selection visibility
- auxiliary workspace-context visibility

That distinction is intentional for the current `0.6.0` slice.

### 4. Relation-scoped output

When constrained relation-derived support context is available, the response may include a relation group with:

- `scope = "relation"`
- `scope_id = "supports"`
- `selection_kind = "supports_related_auxiliary"`
- `selection_route = "relation_supports_auxiliary"`

This is currently the primary grouped structured surface for relation-derived supporting context.

At the current `0.6.0` stage, the constrained relation auxiliary grouped reading
should now also be treated as explicit enough for the current contract slice.

Grouped consumers should currently read this relation-scoped auxiliary surface
conservatively as:

- relation-derived support context is still auxiliary
- it is still limited to the current constrained `supports` slice
- it is still surfaced from returned episode memory items rather than from a
  broader graph traversal
- the relation group should therefore be read as support context linked back to
  returned episode-side context, not as an independent primary selection path

This linkage is now explicit enough through the current relation-group and
episode-group surfaces together.

At the relation-group level, the current grouped output now makes source-side
linkage easier to read through:

- `source_episode_ids`
- `source_memory_ids`

At the episode-group level, the current response still preserves linkage through
embedded provenance and relation-edge details such as:

- `related_memory_item_provenance[*].source_memory_id`
- `related_memory_item_provenance[*].target_memory_id`
- `related_memory_item_provenance[*].source_group_scope`
- `related_memory_item_provenance[*].target_group_selection_kind`
- `related_memory_relation_edges[*].source_memory_id`
- `related_memory_relation_edges[*].target_memory_id`

Taken together, these current fields mean grouped consumers can now recover the
linkage between:

- returned episode-side memory context
- constrained `supports` relation edges
- relation-scoped auxiliary grouped output

without needing another narrowly incremental relation-group helper field for the
current stage.

This should currently be read as a good enough stopping point for the present
relation-auxiliary explainability slice, not as an invitation to keep adding
tiny relation-group metadata without a stronger behavior need.

### Auxiliary visibility without episode matches

The current contract should also be read as allowing inherited workspace
auxiliary context to remain visible when the primary episode path becomes empty
after query filtering.

That means a response may currently have all of the following at once:

- no returned episodes after query filtering
- `all_episodes_filtered_out_by_query = true`
- inherited workspace auxiliary context still present
- workspace-scoped grouped output still present through
  `selection_route = "workspace_inherited_auxiliary"`

This should currently be interpreted as:

- preserved auxiliary support visibility

not as:

- recovered episode matching
- widened selection semantics
- inherited workspace items driving primary episode selection

This distinction matters for the current grouped reading because auxiliary
workspace visibility remains a sibling auxiliary surface, not part of the
primary episode-matching path.

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

The current convenience-oriented related-context surfaces include:

- episode-group embedded `related_memory_items`
- episode-group embedded relation provenance and relation-edge linkage details

These convenience-oriented episode-group fields are important to the current
grouped relation reading because they preserve the source-side linkage that
explains why relation-scoped auxiliary grouped output was surfaced.

### Consolidation note for the current stage

Taken together, the current relation-scoped grouped metadata and the existing
episode-group provenance/linkage fields should be treated as sufficient
relation-auxiliary explainability for the current `0.6.0` slice.

In practical terms, the next work should not default to adding yet another small
relation-group explanation field unless a clearer behavior gap appears.

Instead, the current contract direction should be read as:

- constrained relation auxiliary grouped reading is explicit enough for now
- workspace/relation auxiliary grouped surfaces still remain top-level sibling
  auxiliaries
- broader relation expansion and deeper graph semantics are still intentionally
  deferred
- the next meaningful step should preferably be either:
  - a genuinely new small grouped-selection behavior choice
  - or a contract-consolidation / interpretation step
  - rather than another narrowly incremental relation-group metadata addition

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