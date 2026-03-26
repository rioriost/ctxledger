# Task Recall 0.7.0 Plan

## 1. Purpose

The goal of `0.7.0` is to make `ctxledger` materially better at helping an agent **return to the main line of work after interruptions, side tasks, or temporary detours**.

This milestone exists because durable storage alone is not enough.

`ctxledger` already preserves canonical workflow and memory state in PostgreSQL, but that does not automatically mean an agent can reliably answer questions such as:

- what was I doing before this detour?
- what is the main objective for this workspace right now?
- which workflow should be re-foregrounded as the continuation target?
- which recent work was only a temporary side task, not the primary task thread?

`0.7.0` is therefore focused on **task-thread recovery**, not just generic memory retrieval.

The desired outcome is that canonical workflow and memory records can be surfaced through agent-facing retrieval paths in a way that supports:

- main-task recovery
- detour-aware continuation
- safer resumption after interruptions
- clearer separation between current primary work and recent-but-secondary work

This should be treated as a resumability and durable-memory product milestone, not merely as a search-tuning exercise.

---

## 2. Problem Statement

Current `ctxledger` behavior is strong in canonical persistence, but weaker in recall and re-foregrounding.

Observed failure mode:

- the database may contain enough canonical workflow/checkpoint state to reconstruct the real task thread
- but the agent-facing retrieval path may still fail to surface the correct main task naturally
- recent secondary work can eclipse the more important primary task thread
- concept queries may find nearby or recent memories, but not the operationally relevant continuation target

This means the system currently risks answering:

- "what is semantically nearby?"
instead of
- "what should I continue?"

That distinction is central.

`0.7.0` should improve retrieval so that `ctxledger` can answer both kinds of questions, while preserving the architectural rule that workflow state remains canonical and retrieval remains a derived layer.

---

## 3. Primary Objectives

`0.7.0` should implement the first explicit task-recall layer that can:

1. distinguish **primary work** from **detour work**
2. identify the most likely **return target**
3. surface the correct **continuation thread** for a workspace
4. connect workflows, checkpoints, episodes, and summaries into a more useful recall path
5. improve concept-to-task recovery for user prompts such as:
   - "what was I doing before coverage work?"
   - "what was the main task in this repo?"
   - "return me to the hierarchical memory work"
   - "which workflow should I resume now?"

This milestone should not require broad architectural replacement.

It should instead strengthen the retrieval and assembly layers on top of existing canonical state.

---

## 4. Non-Objectives

`0.7.0` is **not** intended to be:

- a full Mnemis-style redesign
- a graph-native replacement of PostgreSQL as canonical truth
- a broad rewrite of the memory model
- a release focused on embeddings alone
- a generic search relevance milestone detached from workflow continuity
- a catch-all documentation cleanup release
- a broad MCP protocol expansion unrelated to task recall

This milestone should remain tightly scoped to **return-to-main-task retrieval** and **detour-aware recall**.

## 4.1 Current implementation progress

The current `0.7.0` slice has started to move from generic workflow freshness toward more explicit task-recall signals.

Implemented in the current slice:

- workflow candidate signals now surface latest checkpoint fields needed for task-recall interpretation, including:
  - `latest_checkpoint_step_name`
  - `latest_checkpoint_summary`
  - `latest_checkpoint_current_objective`
  - `latest_checkpoint_next_intended_action`
  - normalized presence flags for objective and next-action signals
- task-recall ranking can now treat explicit checkpoint objective / next-action evidence as a stronger mainline signal than the older non-detour-only heuristic
- workspace-scoped workflow ordering now prefers explicit mainline checkpoint signals before falling back to pure recency when ranking continuation candidates
- `memory_get_context` now has a materially richer task-recall detail surface, including:
  - return-target details
  - primary-objective details
  - task-thread details
  - latest-versus-selected continuation comparison details
  - latest detour candidate details
  - prior-mainline candidate details
- `memory_search` now has a bounded task-recall integration for workspace-scoped searches, including:
  - top-level search-context details for the latest considered workflow and the selected continuation workflow
  - candidate-level comparison details for latest-versus-selected continuation context when those diverge
  - a small selected-continuation-target bonus in divergent multi-candidate contexts
- focused detour-recovery tests now cover:
  - selection of a workflow with explicit checkpoint objective evidence
  - selection of a workflow with explicit next-intended-action evidence
  - preservation of detour penalties for side-work-like candidates
  - prior-mainline recovery before a latest detour-like workflow
  - separation of latest detour context from selected continuation context

What this slice does **not** yet claim:

- a complete task-thread model
- a first-class persisted return-target entity
- broad concept-to-task routing beyond the current bounded `memory_get_context` and `memory_search` task-recall path
- replacement of recency/resumability signals with objective-aware signals; this slice augments them

This should therefore be read as a substantial bounded `0.7.0` retrieval improvement, but still not full milestone closeout.

Rough progress reading at the current repository state:

- `0.7.0` now appears materially further along than early or mid-slice exploration
- a better shorthand is:
  - core bounded task-recall behavior is implemented
  - milestone closeout and broader completion questions still remain
- this reading is based on:
  - explicit task-recall ranking already being present
  - objective-aware continuation signals already being present
  - return-target, task-thread, and latest-versus-selected explanation surfaces already being present
  - latest detour versus selected continuation separation already being present
  - prior-mainline recovery already being present in the bounded `memory_get_context` path
  - focused validation already covering a meaningful continuation-selection surface
- this should **not** be read as release readiness
- it should be read as:
  - core retrieval/explanation scaffolding is real
  - several originally open continuation-recovery gaps now have bounded implementation
  - remaining work is now concentrated in closeout, broader concept-to-task scope decisions, and maintainability hardening

Main remaining gaps at this stage:

- clarify how far `0.7.0` should take concept-to-task recovery beyond the current bounded `memory_get_context` and `memory_search` task-recall path
- decide which adjacent retrieval surfaces, if any, should participate in task-recall semantics for `0.7.0`, and explicitly defer the rest
- a final `0.7.0` hardening slice that semantically splits oversized `src/` and `tests/` files so the task-recall implementation remains maintainable and easier to reason about
- a release-ready behavior summary and closeout-oriented acceptance reading for the bounded `0.7.0` slice
- an explicit milestone decision on whether the current derived return-target and task-thread surfaces are sufficient for `0.7.0`, or whether any further bounded hardening is still required

---

## 5. Why This Milestone Exists

There are several important differences between durable storage and practical recall.

### 5.1 Persistence is not equivalent to recoverability

A workflow, checkpoint, or episode can be stored correctly and still fail to be surfaced when an agent asks for the current main task.

### 5.2 Recent work is not always primary work

Coverage, diagnostics, cleanup, and small side fixes are often legitimate workflows, but they should not always become the dominant continuation target.

### 5.3 Semantic proximity is not enough

A query like `hierarchical` should ideally recover:

- relevant plans
- relevant workflows
- relevant checkpoints
- relevant episodes
- relevant memory summaries
- the most likely task thread to continue

Returning only recent semantically similar memories is not sufficient.

### 5.4 Main-line recovery is a product requirement

For an agent-oriented durable runtime, "return me to the main task" is not a convenience feature.
It is part of the core value proposition.

---

## 6. Conceptual Model Additions

`0.7.0` should introduce explicit retrieval concepts that do not currently have enough first-class treatment.

## 6.1 Primary Objective

A **primary objective** is the current main line of work for a workspace or task thread.

Properties:

- user-meaningful
- may span multiple checkpoints
- may survive temporary detours
- should usually be the first continuation target unless superseded explicitly

## 6.2 Detour Work

A **detour** is valid work that is not the main line of progress.

Examples:

- coverage improvements
- temporary diagnostics
- narrow cleanup
- release prep around a larger feature
- one-off operational investigation

Detours may still produce canonical workflows, checkpoints, and episodes.

The key issue is not whether they are real work.
The issue is whether they should dominate future recall.

## 6.3 Return Target

A **return target** is the workflow, checkpoint, or higher-level task-thread anchor that should be re-foregrounded after a detour finishes.

A return target may be:

- an active workflow
- the latest checkpoint of a previously active workflow
- a non-terminal but blocked workflow
- a primary-objective summary or thread anchor derived from canonical records

## 6.4 Task Thread

A **task thread** is the derived continuity structure linking:

- plan/task identity
- workflows
- attempts
- checkpoints
- episodes
- memory items
- summaries
- optional relation edges

A task thread is not a replacement for canonical records.
It is a derived recall structure used to answer continuity questions more effectively.

---

## 7. Retrieval Questions `0.7.0` Must Support Better

The following questions should become first-class design targets:

- what is the current main objective for this workspace?
- what workflow should be resumed as the primary continuation target?
- what work was active before the most recent detour?
- what is the most relevant non-terminal workflow for this repository?
- what plan or task thread does this recent side work belong to?
- what prior checkpoint best explains the next action to take?
- which memories are supporting context versus the primary thread anchor?
- what does the user likely mean when they refer to a known feature area by concept name?

These questions are more specific than current generic retrieval.

---

## 8. Proposed Retrieval Design Direction

## 8.1 Two-stage recall

The proposed `0.7.0` retrieval model should have at least two conceptual stages:

### Stage A — Candidate recovery

Recover candidate entities from canonical and derived records, including:

- workflows
- checkpoints
- episodes
- summaries
- memory items
- optional related plans/docs when available

### Stage B — Re-foregrounding / prioritization

Rank those candidates for continuation relevance, not only semantic similarity.

This ranking should consider signals such as:

- workflow terminality
- latest attempt status
- recency
- recency relative to detours
- checkpoint presence
- explicit objective wording
- task-thread continuity
- whether a workflow appears to be side work
- whether a workflow appears to be the prior main line

---

## 8.2 Continuation-first ranking

The ranking layer should distinguish at least:

- semantic relevance
- operational resumability
- task-thread centrality
- detour likelihood
- primary-objective likelihood

Semantic similarity alone must not dominate the result ordering.

---

## 8.3 Workspace-scoped primary recall

For a given workspace, the system should be able to answer:

- active primary workflow
- previous primary workflow before latest detour
- latest meaningful checkpoint for primary thread
- supporting episodic context for that thread

This should be available even when the latest workflow chronologically is not the desired continuation target.

## 8.4 Current implementation note

The current implementation now partially supports this direction by:

- exposing checkpoint objective and next-intended-action signals in candidate ordering details
- using those signals during task-recall ranking
- allowing explicit mainline checkpoint evidence to outrank a more recent but less task-central candidate in focused scenarios
- surfacing a structured latest-versus-selected comparison block that can show:
  - the latest considered candidate
  - the selected continuation candidate
  - checkpoint step/summary details for both
  - primary-objective and next-intended-action text for both where present
  - detour classification and continuation-basis details for both
  - resumability-oriented signals for both
- treating the candidate-level latest-versus-selected block as the primary comparison surface, with the older checkpoint-oriented naming preserved as a compatibility alias

However, the current behavior should still be read as a bounded heuristic layer:

- detour-like detection remains token- and wording-driven
- explicit objective presence is treated as strong evidence, not definitive canonical intent
- return-target selection is still expressed through ranked workflow selection rather than a separate first-class return-target object
- the latest-versus-selected comparison block improves explanation quality, but does not by itself guarantee full historical primary-thread recovery
- the current concept-to-task bridge is intentionally concentrated in `memory_get_context` and workspace-scoped `memory_search`, rather than spread across every retrieval surface

---

## 9. Canonical vs Derived Responsibilities

`0.7.0` must preserve the architectural separation already established in the repository.

## 9.1 Canonical

Canonical records remain in PostgreSQL:

- workspaces
- workflow instances
- workflow attempts
- workflow checkpoints
- verify reports
- episodes
- memory items
- memory relations
- other future canonical memory records

## 9.2 Derived

Derived structures may include:

- thread summaries
- primary-objective projections
- detour classification hints
- return-target candidates
- ranking features
- relation traversal results
- semantic retrieval indexes

## 9.3 Rule

Derived task-recall structures must improve recall without replacing canonical workflow truth.

---

## 10. Likely Product Surface Changes

## 10.1 `memory_get_context`

`memory_get_context` should evolve beyond episode-oriented retrieval toward a stronger task-recall role.

Potential additions:

- stronger primary-thread selection metadata
- explicit distinction between primary and auxiliary context
- return-target details
- detour-aware selection explanations
- clearer reporting of why a particular workflow/thread was foregrounded
- latest-versus-selected candidate comparison details that make it easier to inspect:
  - what the system considered latest
  - what it ultimately selected
  - which checkpoint/objective/next-action details differed
  - which detour and resumability signals differed

## 10.2 `memory_search`

`memory_search` should remain useful for semantic retrieval, but may need:

- task-thread-aware ranking signals
- workflow/checkpoint/thread-aware explanations
- stronger coupling to workspace continuation semantics
- better support for concept-word recovery that surfaces operationally relevant threads

Current implemented direction:

- `memory_search` now has a bounded workspace-scoped task-recall context surface layered into search results and top-level search details
- that bounded surface can now expose:
  - latest considered workflow identity
  - selected continuation workflow identity
  - selected-versus-latest equality
  - selected and latest checkpoint/objective/next-action context where available
  - candidate-level latest-versus-selected comparison details in divergent contexts
  - top-level comparison-summary explanations for divergent contexts
- `memory_search` also now applies a small selected-continuation-target bonus in bounded divergent contexts so concept search can begin to lean toward the currently preferred continuation thread without turning the search surface into a full workflow-selection replacement

This should still be read as a deliberately constrained integration:

- the search path remains primarily a memory-item search surface
- task-recall signals are additive and bounded
- the selected-continuation bonus is intentionally small and gated to divergent multi-candidate contexts
- this is concept-to-task recovery scaffolding, not a claim that `memory_search` is already a complete task-thread retrieval surface

## 10.3 `workflow_resume`

`workflow_resume` itself should remain an operational truth surface.

However, adjacent retrieval paths should better answer:

- which workflow should be resumed?
- is the latest workflow a detour rather than the main target?
- what earlier thread should be restored instead?

## 10.4 New dedicated retrieval surface

A dedicated surface may be justified if `memory_get_context` and `memory_search` become too overloaded.

Possible examples:

- `memory_return_target`
- `workflow_primary_context`
- `task_thread_get_context`

Whether this becomes a new tool or an extension of existing ones should be decided during implementation planning.

---

## 11. Data and Model Changes to Consider

`0.7.0` may require explicit new derived concepts and possibly new canonical link fields.

Current implemented direction in this area:

- no new canonical workflow or checkpoint ownership rules were introduced in this slice
- the added objective-aware task-recall behavior reads existing canonical checkpoint payload fields rather than creating a parallel source of truth
- the ranking layer remains derived and explainable through surfaced candidate signals, reason lists, and latest-versus-selected comparison details
- the newer candidate-level comparison block should be read as a derived explanation surface layered over canonical workflow/checkpoint records, not as a replacement source of truth
- the newer `memory_search` task-recall context and comparison details should also be read as derived explanation and ranking-support surfaces layered over canonical workflow/checkpoint records, not as a second workflow-truth mechanism

This preserves the intended architectural boundary while still improving continuation recall quality.


These should be introduced conservatively.

## 11.1 Possible canonical additions

Potential fields or records to consider:

- explicit parent/related workflow linkage for detour association
- optional objective or thread labels on checkpoints
- optional thread-scoped derived summary anchors
- explicit workflow classification hints where justified

Canonical additions should only be made where they materially improve recall and remain semantically meaningful.

## 11.2 Possible derived additions

Likely derived records or views:

- primary objective summaries
- task-thread summary records
- return-target candidate views
- detour/primary ranking features
- thread continuity projections

---

## 12. Classification Heuristics to Explore

`0.7.0` should explicitly evaluate detour vs primary classification.

Initial heuristics may include:

- workflow/ticket naming patterns
- workflow age and freshness
- checkpoint wording
- verify reports
- whether the workflow is an obvious support/cleanup task
- relation to earlier non-terminal or larger-scope work
- whether the checkpoint summaries repeatedly describe side work around another objective
- whether the thread has a stronger objective-bearing lineage in prior checkpoints/episodes

These heuristics should be transparent and explainable.
They should not become hidden magic.

---

## 13. Explanation Requirements

Task recall should not only produce an answer.
It should explain why that answer was chosen.

Useful explanation details may include:

- selected thread id / workflow id
- selected checkpoint id
- whether the selected target was active, blocked, or historical
- whether the latest workflow was deprioritized as a likely detour
- which signals contributed to the result
- what supporting memories were attached
- what was considered primary versus auxiliary

This explanation quality is essential for trust and debugging.

---

## 14. Relationship to Hierarchical Memory

`0.7.0` should build on `0.6.0` hierarchical memory work, but not be blocked by full graph sophistication.

The hierarchy work helps because:

- summaries can become thread anchors
- relations can support task-thread traversal
- grouped context can distinguish primary from supporting memory

But `0.7.0` should remain focused on practical recall behavior, not graph purity.

---

## 15. Relationship to Mnemis

Mnemis-style alignment should be evaluated later, not drive this milestone.

Reason:

- `0.7.0` should solve the user-facing recall problem first
- after that, the system can assess whether Mnemis-style dual-route or graph-heavy designs improve the implementation meaningfully
- premature Mnemis alignment risks turning a concrete recall milestone into a broad architecture comparison

Therefore:

- use Mnemis only as background inspiration during `0.7.0`
- reserve explicit alignment analysis for `0.8.0`

---

## 16. Suggested Implementation Phases

## 16.1 Phase A — Problem framing and retrieval contract

Goals:

- define the exact questions the system should answer
- define primary/detour/return-target semantics
- define explanation requirements
- decide whether to extend existing tools or add a new one

Deliverables:

- updated docs
- explicit retrieval contract
- minimal test matrix for target questions

---

## 16.2 Phase B — Workspace-scoped primary thread recovery

Goals:

- identify the most likely primary continuation target for a workspace
- distinguish latest workflow from best workflow to resume
- support return-to-main-task after recent detours

Deliverables:

- ranking logic
- workspace-scoped recovery implementation
- focused tests around detour recovery

---

## 16.3 Phase C — Checkpoint and summary re-foregrounding

Goals:

- strengthen use of latest meaningful checkpoint
- incorporate summary/thread anchors where available
- improve auxiliary-vs-primary context shaping

Deliverables:

- checkpoint/summarization-aware assembly improvements
- explanation fields
- retrieval behavior tests

---

## 16.4 Phase D — Concept-to-thread recovery

Goals:

- improve concept-word retrieval such as:
  - `hierarchical`
  - `projection`
  - `resume timeout`
  - `memory split`
- connect semantic retrieval to operational continuation targets
- make an explicit milestone-boundary decision about how far this concept-to-task behavior should extend in `0.7.0`

Deliverables:

- improved concept-query behavior within the current bounded task-recall path
- better workflow/checkpoint/thread surfacing for `memory_get_context` and workspace-scoped `memory_search`
- an explicit scope call that separates:
  - in-scope `0.7.0` concept-to-task behavior
  - deferred post-`0.7.0` broader retrieval-surface expansion
- focused tests using realistic repository history patterns

### 16.4.1 Bounded `0.7.0` concept-to-task reading

The current best `0.7.0` default is:

- keep concept-to-task recovery centered on:
  - `memory_get_context`
  - workspace-scoped `memory_search`
- treat those two surfaces as the first bounded agent-facing recovery bridge from concept words toward continuation targets
- avoid broadening `0.7.0` into a general all-surfaces routing rewrite

Under this reading, `0.7.0` should be considered complete enough on concept-to-task behavior when:

- realistic concept queries can better surface the current continuation thread through the existing bounded path
- the task-recall explanation details make the selected continuation context inspectable
- release-facing docs clearly say that broader retrieval-surface rollout is deferred

### 16.4.2 Adjacent retrieval surface scope for `0.7.0`

For `0.7.0`, adjacent surface integration should be read narrowly.

In scope for bounded task-recall semantics:

- `memory_get_context`
- workspace-scoped `memory_search`
- `workflow_resume`-adjacent reasoning only to the extent that resume-facing responses explain why a continuation target was selected

Not required for `0.7.0` closeout unless a later slice proves they are both necessary and still explainable:

- broad task-recall propagation to every retrieval or transport surface
- new dedicated retrieval tools solely to widen concept routing
- broader architectural routing changes that would make multiple surfaces compete as workflow-selection authorities

The intended `0.7.0` default should therefore be:

- strengthen the bounded current surfaces
- name the non-bounded expansion ideas explicitly
- defer the broader rollout rather than leaving it ambiguous

---

## 16.5 Phase E — Hardening and operator clarity

Goals:

- ensure explanation details are debuggable
- verify behavior with multiple recent side-task workflows
- confirm that auxiliary local notes are no longer required for normal main-task recovery

Deliverables:

- full validation pass
- docs alignment
- release-ready behavior summary
- semantic splitting of oversized `src/` and `tests/` files as a final maintainability hardening step for the `0.7.0` task-recall slice

---

## 17. Validation Criteria

`0.7.0` should be considered successful when:

- an agent can recover the current primary task thread for a workspace more reliably
- recent detour workflows no longer automatically eclipse the main continuation target
- concept-word retrieval can surface the relevant task thread more often through the bounded `memory_get_context` / workspace-scoped `memory_search` path
- explanation details make result selection understandable
- canonical PostgreSQL state remains the source of truth
- workflow resume semantics remain correct and separate from support-context retrieval
- release-facing docs make it explicit which broader retrieval-surface expansions were deferred beyond `0.7.0`
- tests cover both:
  - semantic relevance
  - operational continuation relevance

---

## 18. Risks

Key risks include:

- overfitting heuristics to recent local history
- conflating support context with operational truth
- creating hidden ranking logic that users cannot understand
- making retrieval richer but harder to debug
- overcomplicating the milestone with premature graph redesign
- introducing large canonical schema changes where derived structures would suffice

---

## 19. Deliverables

By the end of `0.7.0`, the repository should ideally have:

- an explicit task-recall design
- better workspace-scoped main-thread recovery
- detour-aware recall behavior
- improved bounded concept-to-thread retrieval through `memory_get_context` and workspace-scoped `memory_search`
- explanation-rich result metadata
- tests proving return-to-main-task behavior
- docs that clearly describe:
  - primary objective
  - detour
  - return target
  - which broader retrieval-surface expansions were intentionally deferred beyond `0.7.0`

---

## 20. Summary

`0.7.0` should make `ctxledger` better at answering the question:

- **what should I continue now?**

not only:

- **what is semantically nearby?**

This milestone is about turning durable workflow and memory records into a stronger practical recall experience for real agent work, especially after interruptions and side-task detours.

It should preserve the current architectural principles while materially improving the retrieval path that helps agents recover the main line of progress.