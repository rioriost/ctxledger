# ctxledger last session

## Summary

Continued the `0.6.0` hierarchical memory retrieval work and completed a small
**contract-consolidation** slice for the current
**workspace auxiliary survives while relation auxiliary does not under query-filter no-match**
reading in `memory_get_context`.

This loop did **not** change implementation behavior, widen relation traversal,
change auxiliary-group positioning, introduce broader graph semantics, or add a
new response field.

Instead, it consolidated the documented reading for the already-covered
workspace-vs-relation negative interaction, especially where workspace-visible
items, relation-derived visibility, and no-match auxiliary routing can be
misread.

The current docs now more explicitly state that:

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
- workspace-visible items should **not** be re-read as surviving
  relation-derived output merely because a `supports` edge had existed before
  filtering

This means the current workspace-vs-relation no-match interpretation is now
better anchored in the docs rather than only in recent behavior tests.

---

## What was completed

### Small workspace-relation negative interaction contract consolidation slice implemented

A focused documentation pass was completed to align the current service-contract
and MCP API wording around the already-covered no-surviving-episode interaction
between workspace auxiliary visibility and constrained relation auxiliary
visibility.

The clarified current reading is:

- candidate episodes may first be collected for the resolved workflow
- lightweight query filtering may remove all returned episodes from the visible
  primary path
- because the current constrained relation auxiliary path is derived only from
  returned episode memory items, no visible `supports`-derived relation output
  remains in that case
- workspace-root inherited auxiliary context may still remain visible where
  currently supported
- the visible grouped route may therefore become workspace auxiliary only
- workspace-visible items should not currently be reclassified as surviving
  relation-derived output merely because a `supports` edge had existed before
  filtering

### Docs updated

The current interpretation was clarified in:

- `docs/memory/memory_get_context_service_contract.md`
- `docs/mcp-api.md`

The updates make explicit that the current docs should **not** be read as if:

- relation-derived `supports` context survives independently of returned
  episode-side memory context
- `supports` targets remain visible as relation-derived output merely because
  relation edges existed before query filtering
- workspace auxiliary visibility proves relation auxiliary coexistence in the
  no-match case
- a still-visible workspace item should be reclassified as surviving
  relation-derived output just because it had previously also been reachable
  through a filtered-out `supports` path

They also make explicit that:

- the current constrained relation auxiliary slice is still gated by returned
  episode memory items
- when query filtering removes all returned episodes, the current visible
  relation-derived route disappears
- workspace auxiliary grouped visibility may still remain visible independently
- workspace-visible items should still be interpreted through the actually
  emitted workspace auxiliary route rather than through a hidden surviving
  relation route

### Why this slice is useful

This slice improves continuity and interpretation quality without broadening
behavior.

It reduces ambiguity around the current meaning of:

- `related_context_is_auxiliary`
- `related_context_relation_types`
- `related_memory_items`
- `related_memory_items_by_episode`
- `relation_supports_auxiliary`
- workspace auxiliary visibility after query filtering removes all returned
  episodes
- the distinction between surviving workspace-visible items and surviving
  relation-derived output

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
- change workspace auxiliary positioning
- change constrained relation auxiliary positioning
- redesign grouped response structure
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

## Validation completed

Validated this docs-consolidation slice with:

- `pytest tests/memory/test_service_context_details.py`
- `pytest tests/memory/test_memory_context_related_items.py`

Result at completion time:

- `49 passed`

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
- workspace auxiliary no-match low-limit shaping may still leave
  `workspace_inherited_auxiliary` as the only visible grouped route
- low-limit truncation still applies to that surviving workspace auxiliary route
- still-visible workspace items should not currently be reclassified as
  surviving relation-derived output merely because they had previously also been
  reachable through filtered-out `supports` paths
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
  - workspace auxiliary grouped output may still remain visible where currently
    supported
  - low-limit shaping still applies to the actually emitted workspace auxiliary
    route
  - only the newest inherited workspace item remains visible under that current
    low-limit shaping

---

## Key conclusion

The current workspace-vs-relation no-match contract docs are now better aligned
with the existing behavior coverage.

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