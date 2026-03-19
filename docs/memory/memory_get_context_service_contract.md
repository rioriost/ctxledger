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
4. form the current primary summary-first or direct-episode visible set from the surviving post-filter episode set
5. optionally collect direct episode memory items
6. optionally collect inherited workspace memory items as auxiliary context
7. optionally collect one-hop `supports`-related memory items from returned episode memory items
8. expose grouped and flat details that make the assembly path observable

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
- `summary_first_child_episode_count`
- `summary_first_child_episode_ids`
- `child_episode_count`
- `child_episode_ordering`
- `child_episode_groups_emitted`
- `child_episode_groups_emission_reason`
- `relation_supports_source_episode_count`
- `primary_episode_groups_present_after_query_filter`
- `auxiliary_only_after_query_filter`

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

The current top-level details surface should also expose:

- `summary_first_child_episode_count`
- `summary_first_child_episode_ids`

These fields should be read as additive summary-first selection metadata.
They make the current child-episode cardinality and child-episode identity
represented by the summary-first selection directly readable from top-level
details without requiring grouped consumers to derive those values only from
summary-group-local fields.

The current top-level details surface should also expose:

- `primary_episode_groups_present_after_query_filter`

This field should be read as additive post-filter primary-path presence metadata.
It makes it explicit whether episode-scoped grouped output remains present on the
primary path after query filtering, without requiring consumers to infer that
only from grouped routes, summary-first sub-mode fields, or auxiliary-context
survival fields.

At the current stage, this field is intentionally narrower than a general
"primary grouped visibility" indicator.

In particular, it should currently be read as tracking episode-scoped grouped
presence after query filtering, not whether some other primary grouped surface
such as a surviving summary-only summary-first route remains visible.

The current top-level details surface should also expose:

- `auxiliary_only_after_query_filter`

This field should be read as additive post-filter auxiliary-only survival
metadata.
It makes it explicit when the primary episode path no longer remains visible
after query filtering but auxiliary context still remains visible, without
requiring consumers to reconstruct that outcome only from primary-path absence
plus auxiliary-route presence.

At the current stage, this field should not be read as becoming `true` merely
because episode-scoped grouped output is absent after query filtering if the
remaining visible grouped route is still the primary summary-first route in its
summary-only shape.

When `include_episodes = false`, the current episode-less shaping path is
narrower still:
the response does not currently surface summary-first grouped output, direct
episode-scoped grouped output, or summary-selection metadata even when a query is
present and summaries are enabled.
In that shape, this field should be read from the currently surfaced grouped
response only, not from a hypothetical summary-first route that would have been
visible under episode-oriented shaping.

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
- whether episode-scoped grouped output remains present on the primary path after
  query filtering
- whether the current post-filter reading is now auxiliary-only rather than
  primary-path-visible
- how many child episodes the current summary-first selection represents at the
  top-level details layer

This current primary-chain explainability surface should also be read as
episode-oriented shaping.
When `include_episodes = false`, the response currently takes a narrower
episode-less shaping path instead of surfacing a partially visible summary-first
primary chain.
- which child episodes the current summary-first selection represents at the
  top-level details layer
- which child episodes the summary group references
- how many child episodes the summary group represents
- what ordering semantics apply to those child episode references
- whether corresponding episode-scoped grouped entries were emitted
- the current reason for that emittedness or non-emittedness
- that in query-filtered summary-first cases, the visible child set should
  currently be read from the surviving post-filter primary episode set rather
  than from the broader pre-filter candidate set
- that this surviving-child-set reading applies both to the top-level
  `summary_first_child_episode_*` details metadata and to the grouped summary
  entry's `child_episode_*` fields
- that in multi-workflow ticket- or workspace-resolved summary-first cases, the
  grouped summary entry may still conservatively keep `parent_scope_id = null`
  even when the surviving visible child set narrows to a single returned episode

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

  This should not currently be confused with the separate
  `include_episodes = false` episode-less shaping path.
  In that narrower shaping path, the response does not currently surface the
  summary-first route in summary-only form; instead, it suppresses visible
  episode-oriented primary output altogether.

  In the current query-filtered summary-first reading, this summary-only shaping
  does not change the meaning of the visible child set:
  the grouped summary entry should still be read from the surviving post-filter
  primary episode set even though no episode-scoped grouped entries were emitted.

The grouped summary entry now also makes summary-group child cardinality explicit
through:

- `child_episode_count`

This is additive grouped explainability metadata for the summary-scoped group.
It allows grouped consumers to read the current number of summary-linked child
episodes directly, rather than inferring that count only from the length of
`child_episode_ids`.

In the current query-filtered summary-first reading, both `child_episode_ids`
and `child_episode_count` should be interpreted from the surviving post-filter
visible primary episode set.

That means the current grouped summary entry should not be read as preserving a
separate pre-filter child snapshot when query filtering has already narrowed the
visible primary episode set.

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

In the current query-filtered summary-only case, `"memory_items_disabled"`
therefore explains response shaping, not a different surviving-child-set rule
and not an auxiliary-only interpretation.

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

In query-filtered summary-first cases, the emitted episode-scoped groups should
currently be read as the surviving post-filter primary episode groups only.

This means filtered-out candidate episodes should not currently be assumed to
remain visible in grouped episode output merely because they participated in the
broader pre-filter candidate set for the same ticket- or workspace-resolved
lookup.

When memory items are disabled, this episode-scoped grouped layer is not
emitted, but that should not be read as a different child-set rule.
In that summary-only shape, the grouped summary entry and the top-level
`summary_first_child_episode_*` metadata should still be read from the same
surviving post-filter primary episode set.

When `include_episodes = false`, this episode-scoped grouped layer is also not
emitted, but the current meaning is different again:
the response does not currently preserve a visible summary-first grouped route in
parallel.
Instead, the current episode-less shaping path suppresses visible
episode-oriented primary grouped output and may leave only auxiliary grouped
visibility where otherwise supported.

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
- it should not be read as inherited workspace items contributing to the
  lightweight episode query filter at all

The current details-layer fields that make this reading explicit include:

- `all_episodes_filtered_out_by_query`
- `primary_episode_groups_present_after_query_filter`
- `auxiliary_only_after_query_filter`
- `inherited_context_is_auxiliary`
- `inherited_context_returned_without_episode_matches`
- `inherited_context_returned_as_auxiliary_without_episode_matches`

Taken together, these fields mean the current contract distinguishes between:

- primary episode candidate collection before filtering
- primary episode selection visibility after filtering
- primary episode-group visibility after query filtering
- auxiliary-only survival after query filtering
- auxiliary workspace-context visibility that may remain even when the primary
  episode path is empty

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
- when multiple source-side contexts surface multiple constrained `supports`
  targets, the current relation-group `memory_items` ordering should be read as
  first-seen target ordering under the current source-side traversal path rather
  than as graph ranking, semantic importance, or a broader canonical order
- shared constrained targets are currently aggregated once in the relation-scoped
  grouped surface even when multiple returned source episodes or source memory
  items contribute to that same visible target
- multi-source contribution should therefore currently be read through
  `source_episode_ids` and `source_memory_ids`, not by expecting duplicated
  target entries in relation-group `memory_items`

This linkage is now explicit enough through the current relation-group and
episode-group surfaces together.

At the relation-group level, the current grouped output now makes source-side
linkage easier to read through:

- `source_episode_ids`
- `source_memory_ids`

The current top-level details surface should also expose:

- `relation_supports_source_episode_count`

This field should be read as additive constrained relation-source cardinality
metadata.
It makes the current number of source episodes contributing to the constrained
`supports` auxiliary reading directly readable from top-level details without
requiring consumers to derive that count only from relation-group-local source
linkage fields.

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
- current first-seen target ordering within the constrained relation auxiliary
  aggregation
- aggregated shared targets and the multiple contributing sources behind them

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
- auxiliary context that remained visible after the primary episode path was
  emptied by query filtering

not as:

- recovered episode matching
- widened selection semantics
- inherited workspace items driving primary episode selection
- inherited workspace items participating in the lightweight episode query filter

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

These compatibility surfaces should currently be read as flatter mirrors of the
same constrained relation-aware slice, not as stronger or more canonical
relation-selection surfaces than the relation-scoped grouped output.

### Convenience output

The current convenience-oriented related-context surfaces include:

- episode-group embedded `related_memory_items`
- episode-group embedded relation provenance and relation-edge linkage details

These convenience-oriented episode-group fields are important to the current
grouped relation reading because they preserve the source-side linkage that
explains why relation-scoped auxiliary grouped output was surfaced.

They should currently be read as local grouped explainability and inspection
surfaces, not as replacements for the top-level relation-scoped grouped
aggregation.

### Consolidation note for the current stage

Taken together, the current relation-scoped grouped metadata and the existing
episode-group provenance/linkage fields should be treated as sufficient
relation-auxiliary explainability for the current `0.6.0` slice.

That current explainability surface should also be read as sufficient to explain
the present constrained aggregation behavior:

- relation-group target `memory_items` currently follow first-seen target
  ordering under the source-side traversal path
- shared targets are aggregated once
- multiple contributing sources can still remain visible through
  `source_episode_ids` and `source_memory_ids`
- grouped relation output remains the primary structured relation-aware surface,
  while flat and per-episode related outputs remain compatibility or convenience
  surfaces over that same constrained slice

In practical terms, the next work should not default to adding yet another small
relation-group explanation field unless a clearer behavior gap appears.

Instead, the current contract direction should be read as:

- constrained relation auxiliary grouped reading is explicit enough for now
- top-level details may still mirror a small amount of constrained relation
  source-cardinality metadata when that improves direct readability without
  broadening behavior
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

At the current stage, some of these grouped and summary-selection details are
specific to response shapes where episode-oriented primary output is actually
surfaced.
When `include_episodes = false`, the current episode-less shaping path does not
currently surface summary-first grouped output or summary-selection metadata even
when a query is present and summaries are enabled.

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