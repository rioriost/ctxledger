# ctxledger last session

## Summary

Continued the `0.6.0` hierarchical memory retrieval work and completed a small
**contract-consolidation** slice for the current
**workspace/ticket multi-workflow no-match shaping** reading in
`memory_get_context`.

This loop did **not** change implementation behavior, widen relation traversal,
change auxiliary-group positioning, introduce broader graph semantics, or add a
new response field.

Instead, it consolidated the documented reading for the already-covered
workspace-only and ticket-only multi-workflow no-match behavior, especially
where no-match auxiliary survival, grouped-route disappearance, and stored-memory
presence can be misread.

The current docs now more explicitly state that:

- when query filtering removes all returned episodes, workspace auxiliary
  visibility may still survive in **some** current shapes
- but this should **not** be generalized into a stronger invariant that every
  workspace- or ticket-resolved no-match shape preserves some visible auxiliary
  grouped route
- some workspace-only or ticket-only multi-workflow no-match shapes may instead
  collapse to **no visible grouped routes at all**
- this can remain true even when workflow-linked memory still exists in storage
- in those shapes, the response should be read from the grouped routes and
  grouped outputs that are actually emitted rather than from a hidden auxiliary
  route inferred only from stored-memory presence

This means the current workspace/ticket multi-workflow no-match interpretation
is now better anchored in the docs rather than only in recent behavior tests.

---

## What was completed

### Small workspace/ticket no-match contract consolidation slice implemented

A focused documentation pass was completed to align the current service-contract
and MCP API wording around the already-covered multi-workflow no-surviving-episode
behavior.

The clarified current reading is:

- candidate episodes may first be collected from one or more resolved workflows
- lightweight query filtering may remove all returned episodes from the visible
  primary path
- in some current shapes, inherited workspace auxiliary context may still remain
  visible
- but in some workspace-only or ticket-only multi-workflow no-match shapes, the
  visible grouped routes may collapse to **none**
- in those cases, `all_episodes_filtered_out_by_query` and
  `episode_explanations` may still preserve the filtered-episode diagnostics
  even though neither primary nor auxiliary grouped output remains visible

### Docs updated

The current interpretation was clarified in:

- `docs/memory/memory_get_context_service_contract.md`
- `docs/mcp-api.md`

The updates make explicit that the current docs should **not** be read as if:

- workspace-scoped lookup always preserves inherited auxiliary grouped
  visibility after all episodes are filtered out
- ticket-scoped lookup always preserves some grouped auxiliary visibility after
  all episodes are filtered out
- stored inherited workspace items are equivalent to emitted auxiliary grouped
  output in every no-match workflow-expansion shape
- hidden auxiliary grouped output should be inferred from storage presence even
  when no grouped route is actually emitted

They also make explicit that:

- no-match auxiliary survival is current-shape-dependent behavior
- some no-match workflow-expansion shapes may still preserve visible workspace
  auxiliary grouped output
- some workspace-only or ticket-only multi-workflow no-match shapes may instead
  emit **no visible grouped routes**
- consumers should therefore read the current no-match response from the grouped
  routes and grouped outputs that are actually emitted

### Why this slice is useful

This slice improves continuity and interpretation quality without broadening
behavior.

It reduces ambiguity around the current meaning of:

- `all_episodes_filtered_out_by_query`
- `retrieval_routes_present`
- `primary_retrieval_routes_present`
- `auxiliary_retrieval_routes_present`
- `workspace_inherited_auxiliary`
- workflow-expansion no-match shaping
- the difference between stored memory presence and actually emitted grouped
  output

That is useful because these response shapes are now covered by behavior, and
the docs should say the same thing the tests already establish.

---

## What did not change

This slice intentionally did **not** do any of the following:

- change `memory_get_context` service behavior
- add new grouped metadata fields
- add new retrieval routes
- broaden relation traversal beyond the current constrained shape
- include relation types beyond `supports`
- change workspace auxiliary positioning globally
- change constrained relation auxiliary positioning
- redesign grouped response structure
- force workspace auxiliary visibility to survive in every no-match workflow
  expansion shape
- revive summary-first grouped output after all episodes are filtered out
- revive relation-derived grouped output after all episodes are filtered out

The current grouped interpretation remains:

- `memory_context_groups` is still the primary grouped hierarchy-aware surface
- summary-first remains one important grouped selection route within that
  surface when episode-oriented shaping is active
- workspace and relation outputs remain top-level sibling auxiliary grouped
  surfaces where currently emitted
- broader graph semantics remain intentionally deferred

---

## Validation completed

Validated this docs-consolidation slice with:

- `pytest tests/memory/test_service_context_details.py`
- `pytest tests/memory/test_memory_context_related_items.py`

Result at completion time:

- `51 passed`

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
- `auxiliary_only_after_query_filter = false` does not currently guarantee that
  some grouped route is still visible
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
  query filtering in some current shapes
- but workspace-only multi-workflow no-match shaping is not currently guaranteed
  to preserve that auxiliary visibility
- ticket-only multi-workflow no-match shaping is also not currently guaranteed
  to preserve any visible grouped route
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
  - workspace-visible items should not thereby be re-read as surviving
    relation-derived output
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
  - low-limit shaping still applies to the actually emitted workspace auxiliary
    route
- workspace auxiliary no-match low-limit shaping may still leave
  `workspace_inherited_auxiliary` as the only visible grouped route
- low-limit truncation still applies to that surviving workspace auxiliary route
- still-visible workspace items should not currently be reclassified as
  surviving relation-derived output merely because they had previously also been
  reachable through filtered-out `supports` paths

---

## Key conclusion

The current ticket-only no-match shaping behavior slice is now covered well
enough for the current stage.

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