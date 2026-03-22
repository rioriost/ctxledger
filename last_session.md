# ctxledger last session

## Summary

Continued the `0.6.0` hierarchical memory retrieval work and completed a small
focused **behavior-coverage** slice for the current
**workspace auxiliary survives while relation auxiliary does not under query-filter no-match**
reading in `memory_get_context`.

This loop did **not** change implementation behavior, widen relation traversal,
change auxiliary-group positioning, introduce broader graph semantics, or add a
new response field.

Instead, it fixed and validated the current behavior when:

- one workflow is resolved
- a query is provided
- all episodes are filtered out by the query
- a `supports` relation exists from episode-side memory to a workspace-root target
- workspace-root inherited auxiliary context is also available
- memory items are enabled
- summaries are disabled

The current behavior is now clearer that:

- when query filtering removes all returned episodes, constrained
  `supports`-derived relation auxiliary context does **not** survive
- this is because the current relation auxiliary path is still derived only from
  returned episode memory items
- `related_context_is_auxiliary = false` remains the current reading in this
  no-match case because no related context is actually returned
- `related_context_relation_types == []`
- `related_memory_items == []`
- `related_memory_items_by_episode == {}`
- `relation_supports_auxiliary` is absent from the visible grouped routes
- workspace inherited auxiliary context may still remain visible
- the visible grouped route in this shape is currently the workspace auxiliary
  route only
- the workspace auxiliary route may still include items that were also potential
  relation targets, but that does **not** mean the relation-derived route itself
  survived

This means the current workspace-vs-relation negative interaction is now better
fixed by behavior coverage rather than by inference alone.

---

## What was completed

### Small workspace-relation negative interaction coverage slice implemented

A focused test slice now covers the case where:

- one workflow is resolved
- one episode exists
- one episode-side memory item has a `supports` relation to a workspace-root item
- a separate workspace-root inherited item also exists
- the query filters out the episode
- `include_episodes = true`
- `include_memory_items = true`
- `include_summaries = false`

The current intended result in that case is:

- `episodes == ()`
- `query_filter_applied == true`
- `episodes_before_query_filter == 1`
- `matched_episode_count == 0`
- `episodes_returned == 0`
- `all_episodes_filtered_out_by_query == true`
- `inherited_context_is_auxiliary == true`
- `inherited_context_returned_without_episode_matches == true`
- `related_context_is_auxiliary == false`
- `related_context_relation_types == []`
- `related_context_returned_without_episode_matches == false`
- `related_memory_items == []`
- `related_memory_items_by_episode == {}`
- `retrieval_routes_present == ["workspace_inherited_auxiliary"]`
- `primary_retrieval_routes_present == []`
- `auxiliary_retrieval_routes_present == ["workspace_inherited_auxiliary"]`
- `retrieval_route_group_counts["relation_supports_auxiliary"] == 0`
- `retrieval_route_item_counts["relation_supports_auxiliary"] == 0`
- `retrieval_route_scopes_present["relation_supports_auxiliary"] == []`
- `memory_context_groups` contains only the workspace inherited auxiliary group
- `episode_explanations` retains the filtered episode with
  `explanation_basis = "query_filtered_out"`

### Test added

Added a new focused regression test covering the combined case:

- query present
- all episodes filtered out
- no returned primary episode path remains visible
- workspace inherited auxiliary context still remains visible
- relation-derived `supports` context does not remain visible
- one workspace item may still be visible through the auxiliary workspace route
  even though the relation-derived route is gone

The added test is:

- `test_memory_get_context_workspace_auxiliary_may_survive_query_filter_while_relation_auxiliary_does_not`

### Current intended reading of this behavior

Grouped and details consumers should currently understand this case like this:

1. candidate episodes are collected for the resolved workflow
2. query filtering removes all episodes from the returned primary path
3. because the current relation auxiliary path is derived from returned episode
   memory items only, no `supports`-derived relation auxiliary output remains
4. workspace-root inherited auxiliary context may still remain visible
5. the current visible grouped route is therefore workspace auxiliary only
6. workspace-visible items should not be reclassified as surviving relation
   output merely because a `supports` edge had existed before filtering

This should **not** be read as:

- relation auxiliary surviving independently of returned episode-side context
- `supports` targets remaining visible as relation-derived output just because
  relation edges existed before filtering
- `related_context_is_auxiliary = false` meaning relation-derived context became
  primary
- workspace auxiliary visibility proving relation auxiliary coexistence in the
  no-match case

It should be read as:

- the current constrained relation auxiliary path being gated by returned
  episode-side context
- with relation-derived context disappearing when query filtering removes all
  returned episodes
- and with workspace auxiliary visibility preserved where currently supported

### Why this slice is useful

This slice improves confidence in the current auxiliary-surface interaction
without broadening behavior.

It verifies that the current system behaves consistently when:

- a query removes all returned episodes
- relation-derived support context depends on returned episode memory items
- workspace auxiliary context may still remain visible independently
- workspace-visible items are not thereby reclassified as surviving
  relation-derived output

This makes the current workspace-vs-relation negative interaction explicit
rather than leaving it to be reconstructed from separate relation-auxiliary and
workspace-auxiliary cases.

### Tests added/updated

The relation-aware coverage now explicitly checks the no-surviving-episode,
query-filtered, workspace-vs-relation negative interaction case.

The expected current result is:

- no returned episodes
- no returned relation auxiliary context
- no visible relation-scoped grouped output
- workspace auxiliary grouped output still visible
- filtered episode diagnostics still preserved in `episode_explanations`
- combined focused memory test run passes

### Validation completed

Validated this slice with:

- `pytest tests/memory/test_memory_context_related_items.py`
- `pytest tests/memory/test_service_context_details.py tests/memory/test_memory_context_related_items.py`

Result at completion time:

- `8 passed` in `tests/memory/test_memory_context_related_items.py`
- `49 passed` in the focused combined memory test run

---

## What did not change

This slice intentionally did **not** do any of the following:

- broaden relation traversal beyond the current constrained shape
- include relation types beyond `supports`
- change workspace auxiliary positioning
- change constrained relation auxiliary positioning
- introduce broader graph-backed selection semantics
- add broader response-shape expansion
- make relation auxiliary survive independently of returned episode memory items
- reclassify workspace auxiliary visibility as surviving relation-derived output
- change grouped response structure to merge auxiliary surfaces

The current grouped interpretation remains:

- `memory_context_groups` is still the primary grouped hierarchy-aware surface
- summary-first remains one important grouped selection route within that
  surface
- workspace and relation outputs remain top-level sibling auxiliary grouped
  surfaces where currently emitted
- broader graph semantics remain intentionally deferred

---

## Files most relevant to the current state

### Core implementation
- `src/ctxledger/memory/service_core.py`

### Tests
- `tests/memory/test_service_context_details.py`
- `tests/memory/test_memory_context_related_items.py`

### Design and contract docs
- `docs/memory/memory_get_context_service_contract.md`
- `docs/mcp-api.md`
- `docs/memory-model.md`
- `docs/memory/grouped_selection_primary_surface_decision.md`
- `docs/memory/auxiliary_groups_top_level_sibling_decision.md`

---

## Validation status

Recent relevant validation includes:

- `pytest tests/memory/test_service_context_details.py`
- `pytest tests/memory/test_memory_context_related_items.py`

Recent validation result for this slice:

- `8 passed` in `tests/memory/test_memory_context_related_items.py`
- `49 passed` in `tests/memory/test_service_context_details.py tests/memory/test_memory_context_related_items.py`

---

## Current interpretation

The current `0.6.0` state should now be read as:

- still relational-first
- still constrained on relation-aware behavior
- still not broader graph traversal
- still not Apache AGE behavior expansion yet
- `memory_context_groups` remains the primary grouped hierarchy-aware surface
- primary summary/episode explainability remains explicit enough for the current
  stage when episode-oriented shaping is active
- summary-first query-filter surviving-child-set behavior is explicitly covered
  by behavior and aligned in the docs
- grouped summary child ids/count should currently be read from the surviving
  post-filter primary set rather than from the broader pre-filter candidate set
- top-level summary-first child ids/count should currently be read from that
  same surviving post-filter primary set
- grouped episode output should currently follow that same surviving post-filter
  primary set when memory items are enabled
- when memory items are disabled, the grouped response may remain summary-only
  while still using that same surviving post-filter child set
- `summary_first_has_episode_groups = false` and
  `summary_first_is_summary_only = true` should currently be read as shaping of
  the primary grouped route rather than as loss of summary-first selection
- `primary_episode_groups_present_after_query_filter = false` can currently mean
  either:
  - summary-only primary grouped output remains visible, or
  - no primary episode-scoped grouped output remains visible at all
- `auxiliary_only_after_query_filter = false` remains the correct reading for
  the current summary-only query-filter case
- this same summary-only reading still applies when low-limit shaping also
  applies
- low-limit shaping does not currently change the surviving child-set rule for
  summary-only query-filtered summary-first output
- workspace-only multi-workflow summary-first grouped summaries still keep
  `parent_scope_id = null`
- ticket-only multi-workflow summary-first grouped summaries also keep
  `parent_scope_id = null`
- the same conservative `parent_scope_id = null` reading still applies in
  summary-only low-limit query-filtered multi-workflow workspace/ticket cases
- narrowing to one surviving visible episode does not currently imply stronger
  grouped summary parentage
- inherited workspace-scoped memory remains auxiliary support context
- inherited workspace-scoped memory does not participate in the lightweight
  episode query filter
- inherited workspace-scoped memory does not drive primary episode selection
- inherited workspace context may remain visible even when no episode survives
  query filtering
- that no-match visibility should currently be read as preserved auxiliary
  workspace support context, not revived primary selection
- current workspace-only multi-workflow summary-first reading does not currently
  show sibling workspace auxiliary coexistence unless actually emitted
- constrained relation `supports` auxiliary grouped output remains explicit
  enough to correlate back to returned episode-side context
- constrained relation auxiliary aggregation across multiple returned source
  episodes is explicitly covered by behavior and aligned in the docs
- constrained relation auxiliary `memory_items` ordering is currently best read
  as first-seen distinct target order under the present source-side traversal
- shared constrained targets are currently aggregated once in the relation group
- multi-source constrained contribution should currently be read through
  `source_episode_ids` and `source_memory_ids`
- relation-scoped grouped output remains the primary structured grouped
  relation-aware surface
- flat `related_memory_items` remains a compatibility surface
- `related_memory_items_by_episode` remains a compatibility-oriented per-episode
  mirror
- episode-group embedded `related_memory_items` remains a convenience and local
  inspection surface
- constrained relation auxiliary low-limit truncation is currently best read as
  truncation over that first-seen distinct-target sequence
- constrained relation auxiliary output is currently disabled when
  `include_memory_items = false`
- constrained relation auxiliary does not currently survive when query filtering
  removes all returned episodes
- in that no-match relation case:
  - `related_context_is_auxiliary` remains `false`
  - `related_context_relation_types == []`
  - `related_memory_items == []`
  - `related_memory_items_by_episode == {}`
  - no relation-scoped grouped output remains visible
  - workspace auxiliary grouped output may still remain visible where currently
    supported
- constrained relation auxiliary remains fully disabled when memory items are
  disabled, even when:
  - query filtering leaves one surviving episode visible
  - low-limit shaping also applies
  - underlying `supports` relation data exists
- in that memory-items-disabled + low-limit + query-filter relation case:
  - `related_context_is_auxiliary == false`
  - `related_context_relation_types == []`
  - `related_memory_items == []`
  - `related_memory_items_by_episode == {}`
  - `relation_supports_source_episode_count == 0`
  - `relation_supports_auxiliary` remains absent from visible grouped routes
- `include_episodes = false` now has explicit shaping coverage for:
  - the baseline episode-less branch
  - the query-present / summaries-enabled episode-less branch
  - the low-limit, query-present, summaries-enabled episode-less branch
- in that query-present episode-less branch:
  - `query_filter_applied` is not currently surfaced as active
  - summary-first grouped output is not currently surfaced
  - direct episode-scoped grouped output is not currently surfaced
  - summary-selection metadata is not currently surfaced
  - visible grouped output should be read from the actually emitted response
    only
  - workspace auxiliary grouped output may still remain visible where currently
    supported
  - low-limit shaping still applies to the actually emitted workspace auxiliary
    route
  - only the newest inherited workspace item remains visible under that current
  low-limit shaping
- workspace auxiliary no-match low-limit shaping now also has explicit behavior
  coverage:
  - when query filtering removes all returned episodes, `workspace_inherited_auxiliary`
    may remain as the only visible grouped route
  - low-limit truncation still applies to that surviving auxiliary route
  - only the newest inherited workspace item remains visible
  - filtered episode diagnostics still remain preserved in `episode_explanations`

---

## Key conclusion

The current ticket-only summary-only low-limit query-filter behavior slice is now
covered well enough for the current stage.

The next step should still avoid:

- another hyper-narrow metadata addition without a clear missing behavior
- broad relation expansion
- graph-first behavior expansion
- auxiliary-group nesting without stronger retrieval semantics
- generic cleanup for its own sake

The next useful step should instead be one of:

1. a genuinely different grouped-selection behavior choice
2. a broader contract-consolidation / interpretation step in another part of the
   current response model
3. only later, broader relation/group behavior