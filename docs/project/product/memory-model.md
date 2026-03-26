# Memory Model

## 1. Purpose

`ctxledger` uses a layered memory model so that durable workflow state and reusable knowledge are related, but not conflated.

The memory system exists to help agents:

- continue interrupted work safely
- record meaningful lessons from execution
- retrieve prior context across sessions
- distinguish operational truth from retrieval-oriented support data

A core design rule is:

- **workflow state is canonical operational truth**
- **memory is durable support context derived from or linked to work**
- **derived retrieval structures are not the same thing as canonical records**

This separation matters because agents need both:

1. exact resumable state for the current workflow
2. broader, reusable context from prior work

Those are related, but they are not the same problem.

---

## 2. Layer Overview

The current memory model is organized into four conceptual layers:

1. **Layer 1 — Workflow state**
2. **Layer 2 — Episodic memory**
3. **Layer 3 — Semantic / procedural memory**
4. **Layer 4 — Hierarchical memory**

These layers are not four unrelated subsystems. They build on one another.

- Layer 1 answers: **what is the exact current operational state?**
- Layer 2 answers: **what happened that is worth remembering?**
- Layer 3 answers: **what reusable knowledge can be retrieved by meaning?**
- Layer 4 answers: **what compressed or higher-level understanding should be surfaced first?**

In the current repository state:

- Layer 1 is the most mature and is the primary `v0.1.0` implementation focus
- Layer 2 has begun to become real
- Layer 3 is only partially real:
  - canonical `memory_items`, `memory_embeddings`, and `memory_relations` exist
  - but the practical remember path still tends to accumulate episodes and some memory items more reliably than relation-rich semantic/procedural memory
- Layer 4 is still largely planned, but `memory_get_context` now exposes a small hierarchy-aware response shape as an early bridge toward later hierarchical retrieval
- within that early bridge, `memory_context_groups` should be treated as the primary grouped hierarchy-aware surface, while flatter compatibility-oriented fields remain derived or compatibility views

This means the current bottleneck is no longer only “can the system store work?”, but also “does the system turn meaningful work into enough linked memory structure to matter later?”

---

## 3. Governing Principles

## 3.1 Canonical truth lives in PostgreSQL

Canonical workflow and memory records belong in PostgreSQL.

Repository files, summaries, embeddings, and other retrieval helpers are derived structures.

## 3.2 Workflow control and memory retrieval are separate

`workflow_resume` and `memory_get_context` should not collapse into one concept.

- `workflow_resume` returns operational truth
- `memory_get_context` returns support context

## 3.3 Not every event becomes reusable memory

A workflow may contain many checkpoints, but only some events deserve durable recall as reusable memory.

That is why:

- checkpoint != episode
- workflow != single episode
- one workflow may produce many episodes

## 3.4 Retrieval layers are downstream of canonical records

Embeddings, summaries, relations, and other accelerators are useful, but they must not become the primary truth source.

If derived structures are stale or missing, the system should still retain correct canonical history.

This also applies to the current minimal hierarchy-aware retrieval slice:
grouped or inherited context presentation in `memory_get_context` is a derived read model layered over canonical workflow, episode, and memory-item records.

It also applies to the current AGE-backed graph layer:
the graph is only as meaningful as the canonical relational memory it mirrors.
If canonical memory relations are sparse or absent, graph bootstrap and refresh can still succeed mechanically while remaining semantically weak.

## 3.5 Resumability is different from recall

A resume view must be exact enough for safe continuation.

A memory context view may be approximate, filtered, ranked, summarized, or relevance-based.

---

## 4. Layer 1 — Workflow State

## 4.1 Purpose

Layer 1 is the durable workflow control layer.

It exists to answer questions such as:

- what workspace is being operated on?
- what workflow instance is active or terminal?
- what attempt is current?
- what was the latest checkpoint?
- what verification evidence exists?
- what projection failures are open or closed?

This layer is about safe execution and safe continuation.

## 4.2 Typical records

Representative canonical records include:

- `workspaces`
- `workflow_instances`
- `workflow_attempts`
- `workflow_checkpoints`
- `verify_reports`
- `projection_states`
- `projection_failures`

## 4.3 Characteristics

Layer 1 is:

- canonical
- operational
- exact
- transactionally important
- required for restart-safe behavior

This is the layer that powers:

- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_resume`
- `workflow_complete`

## 4.4 Why Layer 1 is not enough

Layer 1 is necessary, but not sufficient for long-term agent usefulness.

A workflow checkpoint may tell an agent how to continue execution, but not necessarily:

- what non-obvious bug pattern was found
- why a design decision mattered
- which recovery method worked before
- what lesson should be reused in a different future task

That is where Layer 2 begins.

---

## 5. Layer 2 — Episodic Memory

## 5.1 Purpose

Layer 2 stores memorable, reusable units of experience.

An episode is not just "something that happened." It is a retained unit of knowledge that may help future work.

Typical episode-worthy content includes:

- a root cause that was difficult to identify
- a meaningful design decision
- a debugging lesson
- a recovery pattern
- a verification lesson
- a failure mode and how it was resolved
- an implementation insight likely to help later work

## 5.2 Conceptual role

If Layer 1 is the operational ledger, Layer 2 is the "what was learned" layer.

Layer 2 should preserve memory that is:

- more reusable than a raw checkpoint
- more concrete than a semantic embedding
- closer to source reality than a hierarchical summary

The current `memory_get_context` implementation still lives mostly in this Layer 2 space:
it assembles support context from workflow-linked episodes first, then adds a small hierarchy-aware presentation layer over direct and inherited memory-item context.

## 5.3 Typical records

Representative records in the schema/model include:

- `episodes`
- `episode_events`
- `episode_summaries`
- `episode_failures`
- `episode_artifacts`

Not all of these are fully exploited yet, but they define the intended episodic shape.

## 5.4 Current implementation status

In the current repository state:

- `memory_remember_episode` is implemented
- episodes are persisted append-only
- multiple episodes per workflow are supported
- `attempt_id` is now canonically persisted on the base `episodes` record when provided
- `memory_get_context` has an initial episode-oriented retrieval path
- `memory_get_context` now also has a first minimal hierarchy-aware details layer
- `memory_get_context` now begins to expose a minimal summary-first selection contract when summaries are returned
- `memory_context_groups` should now be interpreted as the primary grouped hierarchy-aware surface of the current `memory_get_context` response
- PostgreSQL-backed episode persistence exists
- PostgreSQL-backed retrieval for the initial context path exists
- workflow-completion auto-memory can create:
  - an episode
  - a memory item
  - an embedding when enabled

This means Layer 2 is no longer only conceptual.

However, the current remember path is still uneven:
useful workflow and checkpoint knowledge can stop at the episode or single-memory-item stage instead of consistently flowing into richer linked memory structures.

## 5.5 Current behavior

At present, episodic behavior includes:

- validating `workflow_instance_id`
- optionally validating `attempt_id`
- verifying workflow existence before recording
- persisting a new episode
- canonically storing `attempt_id` with the episode when it is provided
- retrieving episodes by `workflow_instance_id`
- applying `limit`
- honoring `include_episodes`
- honoring `include_memory_items`
- honoring `include_summaries`
- applying an initial query-aware filter against episode summary and metadata text
  - the current lightweight behavior is field-based first:
    - episode `summary`
    - metadata keys
    - metadata values
  - this should be understood as a simple case-insensitive text match layer rather than semantic retrieval
- returning direct episode-scoped memory items for returned episodes
- returning a first minimal hierarchy-aware details shape that distinguishes:
  - direct episode-scoped memory
  - inherited workspace-scoped memory whose `episode_id` is `null`
- exposing explicit retrieval details for this minimal hierarchy slice, including:
  - `hierarchy_applied`
  - `inherited_context_is_auxiliary`
  - `inherited_context_returned_without_episode_matches`
  - `related_context_is_auxiliary`
  - `related_context_relation_types`
  - `related_context_returned_without_episode_matches`
  - `memory_context_groups`
  - `inherited_memory_items`
  - `related_memory_items`
  - `related_memory_items_by_episode`
- exposing an increasingly explicit task-recall detail layer in `memory_get_context`, including:
  - selected continuation target details
  - latest considered candidate details
  - selected and latest checkpoint step/summary details
  - selected primary-objective and next-action details where present
  - candidate-level latest-versus-selected comparison details as a derived explanation surface
- keeping related context semantics explicit across primary, compatibility, and convenience surfaces:
  - `memory_context_groups` is the primary grouped hierarchy-aware surface in the current slice
  - relation-scoped entries inside `memory_context_groups` are the current primary structured grouped relation-aware surface
  - `related_memory_items` remains the top-level compatibility field in the current slice
  - `related_memory_items_by_episode` remains a compatibility-oriented per-episode surface in the current slice
  - episode-group-local `related_memory_items` should be understood as a convenience projection inside `memory_context_groups`
  - later slices may choose to retire some compatibility surfaces, but that is not part of the current contract
- exposing explicit selection metadata inside `memory_context_groups`, including:
  - `selection_kind = direct_episode` for episode-scoped direct context
  - `selection_kind = inherited_workspace` for workspace-scoped inherited context
- keeping inherited workspace-scoped memory as auxiliary context rather than part of episode query matching:
  - lightweight query filtering applies only to episode summary and metadata text
  - inherited workspace-scoped memory does not participate in episode selection
  - inherited workspace-scoped memory does not participate in the lightweight episode query filter
  - inherited workspace-scoped memory may still remain visible when memory items are enabled
  - this can remain true even when no episode survives query filtering
  - when all episodes are filtered out, `episode_explanations` may still preserve pre-filter episode diagnostics with `explanation_basis = "query_filtered_out"`
  - `all_episodes_filtered_out_by_query` now makes that all-filtered diagnostic case explicit in the response details
  - `inherited_context_returned_as_auxiliary_without_episode_matches` now makes the auxiliary inherited-without-matches case explicit in the response details
  - `inherited_context_is_auxiliary` and `inherited_context_returned_without_episode_matches` make that contract explicit in the response details
  - this should currently be read as preserved auxiliary workspace visibility after the primary episode path was emptied by query filtering, not as inherited workspace items driving primary episode selection
- beginning a minimal summary-first selection contract when summaries are returned:
  - `summary_selection_applied = true` indicates that summaries are not only present, but are being surfaced as the first selection layer for the current response shape
  - `summary_selection_kind = "episode_summary_first"` identifies the current summary-first assembly mode
  - when summaries are disabled or none are returned, `summary_selection_applied = false` and `summary_selection_kind = null`
  - this should be understood as an early hierarchical retrieval signal rather than as a full summary-layer planner or ranking system
- exposing a first minimal relation-aware detail surface through:
  - `related_memory_items`
  - current behavior limited to one outgoing `supports` hop from returned episode memory items
- exposing a task-recall comparison surface that can now distinguish between:
  - the latest considered workflow/candidate
  - the selected continuation target
  - whether their checkpoint details match or differ
  - whether their detour classification differs
  - whether their continuation basis differs
  - whether their resumability-oriented signals differ

This is still an early version of episodic memory, but it is a real working path and now includes a first minimal hierarchy-aware retrieval slice, a constrained relation-aware extension, and a more explicit continuation-selection explanation surface.

## 5.6 Workflow / checkpoint / episode relationship

These three concepts are related but distinct:

### Workflow
An operational container for work.

### Checkpoint
A resumable operational progress snapshot.

### Episode
A reusable memory unit worth retaining beyond immediate execution.

A useful mental model is:

- one workflow has many checkpoints
- one workflow may also have many episodes
- some checkpoints may inspire episodes
- not every checkpoint should become an episode

## 5.7 Why append-only matters

Episodes should generally be append-only because they form part of the durable recall trail.

Append-only storage helps preserve:

- operational auditability
- future interpretability
- multi-step learning history
- repeated meaningful discoveries inside one workflow

## 5.8 Current limitations

Layer 2 is still incomplete.

Current gaps include:

- richer retrieval beyond the current workflow-linked episodic lookup path
- stronger ranking and relevance behavior beyond the initial query-aware text filter
- more mature workspace-scoped and ticket-scoped retrieval behavior
- more explicit provenance/filtering behavior built on top of the now-canonical `attempt_id`
- more explicit use of episode detail tables beyond the base episode record
- more consistent promotion of meaningful checkpoint/completion content into reusable memory artifacts
- fuller latest-versus-selected primary-thread recovery that can robustly preserve:
  - the latest considered detour candidate
  - the selected continuation target
  - the previous primary workflow before the latest detour
  as distinct concepts rather than only as explanation-friendly surfaced details
- stronger concept-to-task recovery beyond the current bounded task-recall path in:
  - `memory_get_context`
  - `memory_search`

One practical consequence is that an installation can look healthy from a workflow perspective while still remembering too little in a reusable form.

---

## 6. Layer 3 — Semantic / Procedural Memory

## 6.1 Purpose

Layer 3 is intended to support retrieval by meaning rather than only by direct workflow linkage.

This layer should answer questions such as:

- what similar problem has been solved before?
- what past design tradeoff resembles this case?
- what fix pattern is relevant to this error?
- what procedural guidance applies here?

## 6.2 Typical records

Representative planned tables include:

- `memory_items`
- `memory_embeddings`
- `memory_relations`

## 6.3 Expected role

Layer 3 should make it possible to retrieve knowledge that is:

- not limited to one exact workflow
- not dependent on remembering a workflow ID
- reusable across repositories, tasks, or tickets when appropriate
- meaningfully ranked or filtered

It is also the layer where the system starts to need explicit anchors and links, such as:

- enough task-recall context to connect a concept match back to the current continuation thread
- a bounded distinction between:
  - the latest considered workflow
  - the selected continuation target
- structured comparison context that can explain why a search result may matter to the currently preferred task thread

- meaningful memory items rather than only free-form episode summaries
- embeddings that support semantic lookup
- canonical relations that connect reusable units of memory
- enough structure for later graph or hierarchy layers to mirror usefully

## 6.4 Procedural versus semantic memory

This layer may contain both:

### Semantic memory
Facts, concepts, and repository-specific knowledge.

### Procedural memory
Patterns for how to do something, such as:

- how to stabilize a flaky integration fixture
- how to recover from a projection failure mode
- how to validate a deployment path safely

## 6.5 Current implementation status

This layer is still future work.

In current terms:
In the current repository state:

- `memory_search` is implemented as a bounded memory-item search surface
- lexical and embedding-backed ranking signals are present where configured
- relation-aware retrieval is not implemented in a mature general form
- `memory_search` now has a bounded task-recall integration for workspace-scoped searches, including:
  - latest considered workflow identity
  - selected continuation workflow identity
  - selected-versus-latest equality
  - selected and latest checkpoint/objective/next-action context where available
  - selected-versus-latest candidate comparison details in divergent multi-candidate contexts
  - a small selected-continuation-target bonus in bounded divergent contexts
  - top-level comparison-summary explanations for divergent contexts

This should still be read as a constrained integration:

- `memory_search` remains primarily a memory-item search surface
- task-recall signals are additive and gated
- the search path is not yet a complete task-thread retrieval surface

---

## 6.6 Current remember-path gap

At the moment, the system is better at **recording workflow progress** than at **accumulating rich linked memory** from that progress.

A practical unhealthy-but-plausible state today is:

- workflow state is correct
- episodes are present
- some memory items are present
- embeddings may be present
- `memory_relations` is still empty
- AGE graph bootstrap and refresh can still run, but have little useful relation structure to mirror

That means the graph layer is not necessarily malfunctioning.
It may simply be downstream of a weak remember path.

The current remember-path weakness can be summarized as:

- completion-centered memory capture is still too sparse
- agent memory recording depends too much on discretionary tool use
- checkpoint and completion structure does not yet flow reliably into canonical relations
- semantic/procedural memory remains under-populated compared to workflow truth

This is the main reason `0.8.0` is now planned as a remember-path milestone.

## 6.7 Planned 0.8.0 focus

The current intended `0.8.0` direction is to strengthen the remember path so the system more reliably accumulates:

- episodes
- memory items
- embeddings
- memory relations
- graph/hierarchy inputs derived from those canonical records

The central goals of that milestone are:

- make completion-centered memory capture more reliable
- define the minimum useful memory artifacts a normal work loop should leave behind
- introduce the first constrained canonical relation-writing behavior
- improve observability so operators can tell where memory creation is succeeding, skipping, or failing
- strengthen agent-facing operational guidance so MCP-capable agents following repository rules are more likely to record memory correctly and automatically

This work is intentionally earlier than any broader Mnemis-style architectural evaluation.
The repository should first become better at **remembering**, then later decide whether it also needs a broader graph-memory redesign.

## 7. Layer 4 — Hierarchical Memory

## 7.1 Purpose

Layer 4 is intended to support compressed, multi-level understanding.

This layer should help answer:

- what is the high-level state of knowledge in this project?
- what should an agent see first before reading many raw episodes?
- what summary best represents a set of related memories?
- how can long-context memory be surfaced efficiently?

## 7.2 Expected features

Representative planned behavior includes:

- hierarchical summaries
- scope-level summaries
- project-level recall
- relation-aware rollups
- compressed context assembly for long-running work

## 7.3 Why a separate layer is useful

Without hierarchical memory, retrieval may become too literal or too noisy.

Layer 4 is meant to support:

- prioritization
- compression
- navigation
- scalable long-horizon recall

## 7.4 Current implementation status

This layer is still conceptual/planned.

There is no mature hierarchical retrieval path yet.

---

## 8. Retrieval Paths

## 8.1 Operational retrieval

Operational retrieval is exact-state retrieval.

Representative example:

- `workflow_resume`

This path should return canonical current-or-latest workflow state and related operational diagnostics.

## 8.2 Memory retrieval

Memory retrieval is support-context retrieval.

Representative examples:

- `memory_remember_episode` for capture
- `memory_get_context` for retrieval
- future `memory_search` for semantic retrieval

## 8.3 Why `memory_get_context` exists separately

`memory_get_context` should remain distinct from `workflow_resume` because its role is different.

It is intended to return:

- relevant episodes
- future semantic hits
- future summaries
- future relation-aware memory context

rather than the exact operational state machine view.

## 8.4 Current `memory_get_context` stage

Right now, `memory_get_context` is best understood as:

- **episode-oriented**
- **partially implemented**
- **workflow-linked first**
- **lightly query-aware**
- **not yet a full multi-layer context assembler**

In its current form, it:

- resolves context from canonical workflow linkage first
- can expand retrieval from `workflow_instance_id` to `workspace_id` and `ticket_id`
- can apply a lightweight query-aware filter against episode summary and metadata text
  - the current lightweight behavior is field-based first over:
    - episode `summary`
    - metadata keys
    - metadata values
  - this is intentionally more explicit than relying on whole-metadata stringification, but is still not semantic retrieval
- returns richer assembly details such as:
  - `query`
  - `normalized_query`
  - `lookup_scope`
  - `workspace_id`
  - `workflow_instance_id`
  - `ticket_id`
  - `limit`
  - `include_episodes`
  - `include_memory_items`
  - `include_summaries`
  - `resolved_workflow_count`
  - `resolved_workflow_ids`
  - `query_filter_applied`
  - `episodes_before_query_filter`
  - `matched_episode_count`
  - `episodes_returned`
  - `hierarchy_applied`
  - `memory_context_groups`
  - `inherited_memory_items`
  - `related_memory_items`
  - `summary_selection_applied`
  - `summary_selection_kind`

More specifically, the current details payload is intended to explain:

- what lookup anchor was used
- how many workflows were resolved before episode collection
- which workflow IDs were resolved for collection
- whether the lightweight query filter ran
- how many episodes were available before the query filter
- how many episodes matched the current lightweight filter
- how many episodes were ultimately returned
- whether `episode_explanations` preserves matched-only output or filtered-out diagnostics in the current query-filtering case
- whether the current response is in the explicit all-filtered diagnostic case via `all_episodes_filtered_out_by_query`
- whether the current response is explicitly surfacing inherited auxiliary context without episode matches via `inherited_context_returned_as_auxiliary_without_episode_matches`
- whether summary-first selection metadata is being surfaced through `summary_selection_applied` and `summary_selection_kind`
- whether inherited workspace-scoped memory is being surfaced as auxiliary context outside episode-match filtering
- whether inherited workspace-scoped memory is explicitly marked as auxiliary via `inherited_context_is_auxiliary`
- whether inherited workspace-scoped memory was returned even though no episodes survived filtering via `inherited_context_returned_without_episode_matches`
- whether relation-aware context is explicitly marked as auxiliary via `related_context_is_auxiliary`
- which relation types are currently exposed through the constrained relation-aware slice via `related_context_relation_types`
- whether relation-aware context can be returned without episode matches via `related_context_returned_without_episode_matches`

That means it has started to become useful, but it is not the final design target.

Within that current details payload, `memory_context_groups` should now be understood as
an explicit grouping surface rather than only an incidental formatting choice.

At the current implementation stage, when summaries are enabled and returned, that
grouping surface may also expose a minimal summary-oriented group marker before the
more detailed episode-scoped and workspace-scoped groups. This keeps the current
summary-first assembly signal visible in grouped output without redesigning the
existing group structure.

At the current implementation stage, that grouping surface also reflects a deliberate
boundary between episode-oriented query matching and inherited auxiliary context:
episode selection is query-aware, while inherited workspace-scoped memory does not
participate in that selection and can still be returned as supporting context when
memory items are enabled.

This means a query may filter all episodes out of the returned `episodes` list while
still returning workspace-scoped inherited memory in `inherited_memory_items` and the
workspace entry of `memory_context_groups`. In that all-filtered case,
`episode_explanations` may still preserve the pre-filter episode diagnostics, with
non-matching entries marked by `explanation_basis = "query_filtered_out"`,
`all_episodes_filtered_out_by_query = true` makes the all-filtered case explicit, and
`inherited_context_returned_as_auxiliary_without_episode_matches = true` makes the
auxiliary inherited-without-matches case explicit. That behavior should currently be
interpreted as intentional auxiliary-context behavior: preserved auxiliary workspace
visibility after the primary episode path was emptied by query filtering, rather than
evidence that inherited workspace items are part of the lightweight query filter or
that they drive primary episode selection.

That current all-filtered auxiliary reading should also be kept distinct from two
other nearby response shapes.

First, it is not the same as the current summary-only primary grouped reading.
When summary-first selection remains visible but no episode-scoped grouped output is
emitted, the response may still preserve a primary grouped route in summary-only
form. In that shape, the absence of primary episode-scoped grouped output should not
be re-read as auxiliary-only survival.

Second, it is not the same as the narrower `include_episodes = false` episode-less
shaping path. In that episode-less shape, the response should currently be read from
the grouped routes and top-level details fields that are actually emitted, rather
than from a hidden episode-oriented primary path inferred from other query-filter
cases.

At the current implementation stage, when summaries are enabled and returned,
`summary_selection_applied = true` and
`summary_selection_kind = "episode_summary_first"` should be read as a minimal
hierarchical assembly signal: summary material is being surfaced as the first
selection layer for the response before consumers drill down into the more detailed
episode-scoped context. This is still intentionally narrow and does not yet imply a
full summary-ranking, cross-scope planning, or multi-layer traversal system.

In grouped output, that same summary-first signal may now also appear through a
minimal summary-oriented `memory_context_groups` entry with fields such as:

- `scope = "summary"`
- `scope_id = null`
- `parent_scope = "workflow_instance"`
- `parent_scope_id = {workflow_instance_id}` when exactly one workflow instance is resolved for the current response
- `parent_scope_id = null` when the response is not anchored to exactly one resolved workflow instance, including the multi-workflow workspace/ticket case
- `selection_kind = "episode_summary_first"`
- `summaries = [...]`

This grouped summary marker should be understood as a compact projection of the same
summary-first retrieval state already exposed through `summaries`,
`summary_selection_applied`, and `summary_selection_kind`, rather than as a broader
hierarchical redesign.

When the current response is clearly driven by exactly one resolved workflow
instance, the summary group may also carry that workflow identity through
`parent_scope_id`. This keeps the grouped summary marker aligned with the
single-workflow case without implying stronger cross-workflow summary-planning
behavior for broader workspace- or ticket-scoped retrieval.

In particular, when workspace- or ticket-scoped resolution returns multiple
workflows, the summary-oriented group should keep `parent_scope_id = null`.
That makes the grouped summary marker intentionally conservative in the
multi-workflow case rather than overstating summary ownership by any one
workflow instance.

At the current implementation stage, grouped output ordering should also be
understood as intentional rather than incidental when the corresponding groups
are present:

- the summary-oriented group appears first
- episode-scoped groups follow in the same order as returned `episodes`
- the workspace-scoped inherited-context group appears last

When some group classes are absent, this ordering degrades naturally rather than
introducing placeholder groups:

- summary-only grouped output contains only the summary-oriented group
- workspace-only grouped output contains only the workspace-scoped inherited group
- summary + episode grouped output omits the workspace group without inserting a placeholder
- episode + workspace grouped output omits the summary group without inserting a placeholder

This ordering should be read as a current-stage compatibility commitment for
grouped consumers in this slice, not as a broader hierarchical planner or a
claim that future retrieval stages cannot refine grouping behavior.

At the current implementation stage, groups may carry explicit selection metadata such as:

- `selection_kind = episode_summary_first`
- `selection_kind = direct_episode`
- `selection_kind = inherited_workspace`

The current details payload also includes a first constrained relation-aware surface:

- `related_memory_items`
- `related_context_is_auxiliary`
- `related_context_relation_types`
- `related_context_returned_without_episode_matches`
- `relation_memory_context_groups_are_primary_output`
- `related_memory_items_by_episode_are_compatibility_output`
- `group_related_memory_items_are_convenience_output`

At the current implementation stage, these relation-aware surfaces should be read with distinct roles:

- relation-scoped `memory_context_groups` entries are the primary structured grouped relation-aware surface
- flat `related_memory_items` remains a compatibility surface
- `related_memory_items_by_episode` remains a compatibility-oriented per-episode mirror
- episode-group embedded `related_memory_items` remains a convenience and local inspection surface

At the current implementation stage, `related_memory_items` should be understood narrowly:

- start from returned episode memory items only
- follow one outgoing relation hop only
- include only `relation_type = "supports"`
- exclude other relation types from this slice

The current details payload now also makes that constrained relation contract more explicit:

- `related_context_is_auxiliary = true` when related context is returned
- `related_context_relation_types = ["supports"]` for the current constrained relation-aware slice
- `related_context_returned_without_episode_matches = false` in the current implementation, because related context is derived only from returned episode memory items

The current grouping boundary should also be understood explicitly:

- `memory_context_groups` now organize direct episode-scoped context, inherited workspace-scoped context, and relation-scoped supporting context
- relation-scoped `memory_context_groups` entries are the current primary structured grouped relation-aware surface
- the flat top-level `related_memory_items` field is still retained as a compatibility surface
- `related_memory_items_by_episode` remains a compatibility-oriented per-episode related-context surface
- episode-scoped groups may also include group-local `related_memory_items` as a convenience projection of that same related context
- flat and per-episode related-item outputs should currently be read as compatibility-oriented mirrors of the same constrained relation-aware slice, not as stronger or more canonical relation-selection surfaces than the relation-scoped grouped output
- group-local embedded related items should currently be read as local grouped explainability and inspection surfaces, not as replacements for the top-level relation-scoped grouped aggregation
- workspace-scoped groups are not widened by this slice
- if compatibility surfaces are retired later, that should be treated as a separate incremental contract change rather than assumed from the current grouping shape

This keeps the current minimal hierarchy-aware contract explainable while adding
one explicit relation-aware behavior without yet introducing broader traversal logic.

---

## 9. Canonical Records vs Derived Structures

A critical distinction in this system is:

## 9.1 Canonical records

These are durable source-of-truth records such as:

- workflows
- attempts
- checkpoints
- episodes
- projection failure lifecycle records

## 9.2 Derived structures

These are secondary outputs such as:

- embeddings
- summaries
- projections
- ranked retrieval views
- compressed context bundles

## 9.3 Operational rule

If a derived structure is stale, missing, or not yet implemented:

- canonical truth should still exist
- the system should still remain understandable
- recovery should still be possible

This rule is especially important for future memory layers.

---

## 10. Example Mental Model

A practical way to think about the layers is:

### Layer 1
"What exact work state am I in right now?"

### Layer 2
"What happened before that is worth remembering?"

### Layer 3
"What prior knowledge is relevant to this problem by meaning?"

### Layer 4
"What is the best compressed understanding to surface first?"

An agent often needs all four, but in different proportions depending on the task.

For example:

- resuming an interrupted edit mostly needs Layer 1
- recalling a prior debugging lesson benefits from Layer 2
- finding similar fixes benefits from Layer 3
- quickly understanding project-level history benefits from Layer 4

---

## 11. Current Repository Reality

The current repository state can be summarized as follows:

### Mature
- workflow control
- resumable state assembly
- PostgreSQL-backed canonical execution state

### Emerging
- append-only episodic recording
- initial episode-oriented context retrieval
- multiple episodes per workflow
- minimal hierarchy-aware context grouping
- minimal supports-only relation-aware related context retrieval

### Not yet implemented
- semantic memory search
- embedding-backed retrieval
- broader relation-aware memory retrieval
- hierarchical summaries
- fully realized multi-layer context assembly

This is why it is accurate to say:

- `ctxledger` already has a real memory subsystem path
- but it is still at the beginning of the broader planned memory architecture

---

## 12. Near-Term Design Questions

Important near-term questions include:

- how should the now-canonical `attempt_id` be used for provenance, filtering, and retrieval quality?
- how should workspace-scoped episode retrieval be ranked or limited?
- how should ticket-scoped retrieval behave when multiple workflows match?
- how should the current lightweight field-based query-aware filter evolve into stronger retrieval behavior?
- how long should the flat compatibility field `related_memory_items` remain alongside the primary structured mapping `related_memory_items_by_episode` and the convenience group-local related output?
- how should episode records evolve into semantic memory items?
- what summary boundaries should exist for hierarchical memory?

These are natural next steps as the model moves from episodic foundations toward richer retrieval.

---

## 13. Practical Guidance for Contributors

When extending the memory model:

- preserve the distinction between operational truth and support context
- avoid collapsing checkpoints and episodes into one object
- prefer append-only memory capture for meaningful events
- keep derived retrieval structures clearly downstream of canonical records
- document whether a feature is canonical, derived, partial, or stubbed
- be explicit about current maturity instead of overstating completeness

A good memory feature should make future continuation easier without weakening correctness.

---

## 14. Summary

The `ctxledger` memory model is intentionally layered.

- **Layer 1** provides exact operational truth
- **Layer 2** captures reusable experience as episodes
- **Layer 3** is intended for semantic and procedural retrieval
- **Layer 4** is intended for hierarchical compression and project-scale recall

Today, the system is strongest in Layer 1 and has begun real work in Layer 2.

That is already enough to establish the direction:

- durable workflows are the execution backbone
- episodic memory is the first reusable knowledge layer
- semantic and hierarchical retrieval should build on canonical records rather than replace them
- `memory_get_context` is evolving toward a multi-layer retrieval surface, but is currently still in an early episode-oriented form with only small hierarchy-aware and supports-only relation-aware extensions