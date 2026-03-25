# Automatic Multilayer Memory Plan

## 1. Purpose

This document proposes a design and implementation plan for making `ctxledger`'s memory system naturally support **multilayer memory** when agents follow repository workflow rules, without depending too heavily on prompt discipline.

Target state:

- workflow activity remains the canonical operational truth
- episodic memory is created reliably as work progresses
- semantic memory is generated from episodic memory automatically where configured
- agents that follow `.rules` and use normal workflow tools gain both:
  - episodic memory
  - semantic memory

This plan is intended to reduce the gap between:

- "the system supports memory tools"
- and
- "the system actually accumulates reusable memory during routine agent operation"

---

## 2. Problem Statement

Current behavior is strong but still partially agent-discipline dependent.

Today:

- workflow tools record canonical progress
- `memory_remember_episode` creates episodic memory
- `memory_remember_episode` also triggers embedding persistence when enabled
- `memory_search` can generate semantic query embeddings for retrieval
- `memory_get_context` can return episodic context

However, semantic memory growth currently depends on the agent explicitly invoking memory persistence paths.

### Practical consequence

An agent can follow `.rules` reasonably well while still failing to accumulate semantic memory if it only uses:

- `workflow_start`
- `workflow_resume`
- `workflow_checkpoint`
- `workflow_complete`

and never uses:

- `memory_remember_episode`

That means the current system can preserve operational truth without reliably building reusable multilayer memory.

---

## 3. Desired Outcome

By the end of this work, the system should make the following experience true in normal practice:

1. an agent follows `.rules`
2. the agent uses canonical workflow tools as expected
3. meaningful episodic memory is automatically created
4. semantic embeddings are automatically persisted from that episodic memory when embedding is enabled
5. future sessions can benefit from:
   - workflow resume data
   - episodic recall
   - semantic retrieval

This means `.rules` compliance should be enough to make multilayer memory useful in ordinary operation.

---

## 4. Definitions

## 4.1 Canonical workflow state

Structured operational state stored by workflow services, including:

- workspaces
- workflow instances
- attempts
- checkpoints
- verify reports
- projection state

This remains the source of truth for execution status and resumability.

## 4.2 Episodic memory

Narrative memory entries that capture meaningful work events or learnings, typically represented by episode records and associated memory items.

## 4.3 Semantic memory

Embedding-backed retrieval capability derived from memory items and stored in `memory_embeddings`.

## 4.4 Multilayer memory

The combination of:

- canonical workflow state
- episodic memory
- semantic memory

working together during save, retrieval, and resumption flows.

---

## 5. Non-Goals

This plan does not aim to:

- replace workflow state with memory
- remove explicit `memory_remember_episode`
- eliminate `local_stub`
- redesign semantic ranking in `memory_search`
- implement graph memory
- solve all deduplication and summarization quality problems perfectly in the first pass
- make external embedding generation mandatory

---

## 6. Current System Observations

## 6.1 What already works well

- workflow state is structured and durable
- `memory_remember_episode` already creates memory items
- embedding persistence already exists on the remember path
- semantic retrieval has a real OpenAI-backed path
- embedding failure observability has improved

## 6.2 Current gap

Automatic multilayer accumulation is weak because:

- workflow tools do not automatically emit episodic memory
- semantic persistence depends on explicit memory tool usage
- `.rules` recommends memory tools, but recommendation is weaker than automatic integration

## 6.3 Key insight

The strongest place to bridge workflow and memory is not in retrieval first, but in **memory creation during workflow transitions**.

---

## 7. Design Principles

## 7.1 Workflow remains canonical

Automatic memory must be derived from workflow truth, not replace it.

## 7.2 Automatic memory should be additive

Automatic memory entries should enrich the system, not alter workflow semantics.

## 7.3 High-signal memory is better than noisy memory

Automatic generation should prefer fewer, more useful memories over checkpoint spam.

## 7.4 Explicit memory remains valuable

Agents should still be able to call `memory_remember_episode` manually for nuanced or high-value knowledge capture.

## 7.5 Semantic memory should emerge naturally

If episodic memory is created automatically, semantic memory should be produced from it automatically when embedding is enabled.

---

## 8. Recommended Architecture

## 8.1 Phase 1 recommendation

Implement **automatic closeout memory creation on `workflow_complete`** first.

This is the lowest-risk way to ensure that every completed workflow produces at least one reusable memory artifact.

### Why start here

Benefits:

- low noise
- high signal
- easy operator mental model
- easiest path to "workflow use implies memory growth"
- strong fit for `.rules`

Tradeoff:

- intermediate learnings during long-running work are not captured automatically yet

This is acceptable for the first phase.

---

## 8.2 Phase 2 recommendation

Implement **conditional automatic memory creation on `workflow_checkpoint`**.

This enables memory accumulation during in-progress work loops and improves future resumption.

### Why make checkpoint memory conditional

Blindly creating memory for every checkpoint risks:

- repetition
- noise
- cost growth from embeddings
- lower retrieval quality

So checkpoint-driven auto memory should include signal filters.

---

## 8.3 Long-term model

Final intended model:

- `workflow_checkpoint`
  - may auto-create episodic memory when signal threshold is met
- `workflow_complete`
  - always creates a closeout episodic memory entry
- `memory_remember_episode`
  - remains available for explicit high-value memory capture

This creates layered behavior:

- minimum guarantee from workflow completion
- richer accumulation during checkpoints
- manual augmentation when agents want more precision

---

## 9. Proposed Functional Behavior

## 9.1 Automatic memory on workflow completion

When `complete_workflow()` succeeds:

1. the workflow and attempt become terminal
2. an automatic memory episode is created
3. a memory item is created from that episode summary
4. embedding persistence runs through the normal memory path when enabled

### Proposed content sources

The automatic completion memory should be built from:

- completion summary, if provided
- latest checkpoint summary, if present
- latest checkpoint next intended action, if present
- verify status
- workflow status
- failure reason, if any

### Proposed provenance

Use explicit provenance markers such as:

- episode metadata:
  - `memory_origin = "workflow_complete_auto"`
- memory item `provenance`:
  - `workflow_complete_auto`

This keeps automatic entries distinguishable from manual ones.

---

## 9.2 Automatic memory on workflow checkpoint

When `create_checkpoint()` succeeds:

1. the checkpoint is stored
2. a decision function evaluates whether checkpoint content is memory-worthy
3. if yes:
   - create episode
   - create memory item
   - generate embedding when enabled

### Proposed candidate signals for auto memory creation

A checkpoint is memory-worthy when one or more are true:

- checkpoint summary is non-empty and above a minimum length
- checkpoint includes a meaningful `next_intended_action`
- `verify_status` is present
- checkpoint summary differs substantially from the latest automatic memory content
- checkpoint step name suggests meaningful transition
  - e.g. implementation, validation, debugging, blocker, decision

### Recommended default heuristic

Start simple:

Create automatic checkpoint memory when:

- `summary` exists and is not blank
- and one of:
  - `verify_status` is not `None`
  - `checkpoint_json["next_intended_action"]` is a non-empty string
  - `step_name` is not trivially repetitive

This can be refined later.

---

## 10. Data Model Strategy

## 10.1 Reuse existing memory structures

Do not introduce a separate auto-memory table initially.

Use existing:

- `EpisodeRecord`
- `MemoryItemRecord`
- `MemoryEmbeddingRecord`

and distinguish automatic records through metadata and provenance.

## 10.2 Proposed metadata additions

For automatic memory episodes:

```/dev/null/json#L1-10
{
  "memory_origin": "workflow_complete_auto",
  "workflow_status": "completed",
  "verify_status": "passed",
  "step_name": "validate-openai",
  "auto_generated": true
}
```

Possible values for `memory_origin`:

- `workflow_complete_auto`
- `workflow_checkpoint_auto`
- `manual_episode`

## 10.3 Provenance field guidance

Suggested `MemoryItemRecord.provenance` values:

- `episode`
- `workflow_complete_auto`
- `workflow_checkpoint_auto`

This supports future filtering and retrieval tuning.

---

## 11. Summary Construction Strategy

## 11.1 Completion summary construction

Recommended precedence:

1. explicit completion `summary`
2. fallback to latest checkpoint summary
3. if both exist, combine them

### Example shape

```/dev/null/txt#L1-4
Completed workflow as passed.
Completion summary: Validated OpenAI embedding integration end to end.
Latest checkpoint: Broader targeted regression is green; next action was commit and close out.
Verify status: passed.
```

Goal:

- concise
- informative
- semantically meaningful for retrieval
- not too verbose

## 11.2 Checkpoint summary construction

For automatic checkpoint memory, use the checkpoint summary directly, optionally normalized with:

- step name prefix
- verify status suffix
- next intended action suffix

Example:

```/dev/null/txt#L1-3
Checkpoint `broader-regression-validation`: Broader targeted regression is green.
Verify status: passed.
Next intended action: review diff and commit.
```

---

## 12. Implementation Approach

## 12.1 Preferred layering

Avoid making workflow service directly depend on the memory tool layer.

Instead, introduce a small internal memory bridge that can be used by workflow service.

### Recommended shape

Add an internal protocol, for example:

- `WorkflowMemoryRecorder`

with methods like:

- `record_workflow_completion_memory(...)`
- `record_workflow_checkpoint_memory(...)`

This keeps workflow service decoupled from transport-facing memory handlers.

---

## 12.2 Minimal first-pass implementation choice

If architectural simplicity is preferred for the first pass, an acceptable initial implementation is:

- add optional memory repositories / embedding generator support to `WorkflowService`
- create auto memory entries directly from workflow service methods

This is less pure architecturally, but may be practical.

### Recommendation

Prefer the protocol/bridge approach if implementation complexity stays reasonable.

---

## 13. Suggested File-Level Changes

## 13.1 `src/ctxledger/workflow/service.py`

Add support for automatic memory generation on:

- `complete_workflow()`
- later: `create_checkpoint()`

Possible additions:

- protocol or callback field on `WorkflowService.__init__`
- helper methods:
  - `_build_completion_memory_summary(...)`
  - `_build_checkpoint_memory_summary(...)`
  - `_should_record_checkpoint_memory(...)`

## 13.2 `src/ctxledger/memory/service.py`

Potentially add internal-facing helpers that can be reused by workflow service or a bridge layer, such as:

- record episode from workflow-derived inputs without transport concerns
- preserve current embedding behavior and observability

## 13.3 new internal bridge module

Possible new file:

- `src/ctxledger/workflow/memory_bridge.py`

or:

- `src/ctxledger/memory/workflow_recorder.py`

This module can:

- build episode summary text
- build metadata
- call memory persistence
- isolate workflow-to-memory translation logic

## 13.4 runtime/server wiring

Where workflow service is constructed, inject the bridge/recorder so workflow operations automatically emit memory.

Likely touchpoints:

- runtime factory
- server factory
- test helpers

## 13.5 tests

Need coverage for:

- completion auto-memory creation
- checkpoint auto-memory creation
- no-memory case when heuristics say skip
- embedding persistence on auto-generated memory
- behavior when embedding fails
- behavior when memory persistence fails
- provenance / metadata correctness

---

## 14. Failure Semantics

## 14.1 Completion should stay canonical-first

If workflow completion succeeds but automatic memory creation fails, the system must decide whether:

- workflow completion should still succeed
- or completion should fail

### Recommendation

Keep workflow completion canonical-first:

- completion succeeds
- automatic memory failure is surfaced and recorded, but does not roll back terminal state

Reason:

- workflow truth is more important than derived memory
- this matches current philosophy around projection failure handling

## 14.2 How to surface memory auto-failure

Recommended options:

- record a warning in workflow closeout result
- add structured warning/status in completion response payload
- optionally record a memory/projection-like operational warning later

For first pass, returning completion result with an additional warning field may be sufficient if response model changes are acceptable.

If not, fallback to logging and future checkpointing should be considered carefully.

## 14.3 Checkpoint failure semantics

Same recommendation:

- checkpoint persistence remains primary
- auto memory failure does not roll back checkpoint

---

## 15. Cost / Noise Control

## 15.1 Why this matters

If every checkpoint creates an embedding:

- API costs rise
- latency rises
- retrieval quality may degrade due to redundant memories

## 15.2 Initial controls

Recommended initial safeguards:

- only auto-record checkpoints with non-empty summaries
- require one additional signal beyond summary presence
- use provenance metadata to allow filtering later

## 15.3 Future improvements

Potential later enhancements:

- summary similarity deduplication
  - current closeout implementation now uses weighted field-aware similarity plus completion-summary token similarity
  - current extracted comparison fields include:
    - `completion_summary`
    - `latest_checkpoint_summary`
    - `next_intended_action`
    - `verify_status`
    - `workflow_status`
    - `attempt_status`
    - `failure_reason`
  - current near-duplicate closeout suppression still remains workflow-local and same-`step_name`
  - current metadata-aware matching requires:
    - `next_intended_action`
    - `verify_status`
    - `workflow_status`
    - `attempt_status`
    - `failure_reason`
  - current thresholds / controls:
    - completion-summary token similarity threshold: `0.75`
    - weighted field-aware similarity threshold: `0.7`
    - lookback window: `6 hours`
  - current token scoring discounts boilerplate workflow-closeout tokens such as:
    - `workflow`
    - `completed`
    - `summary`
    - `status`
    - `verify`
    - `latest`
    - `checkpoint`
    - `line`
    - `lines`
- content hash suppression across adjacent checkpoints
- per-workflow cap on auto-generated checkpoint memories
- configurable auto-memory mode:
  - `off`
  - `complete_only`
  - `checkpoint_and_complete`

---

## 16. Retrieval Implications

## 16.1 Immediate benefit

Once automatic memory is added:

- `memory_get_context` has more relevant episodes to return
- `memory_search` has richer semantic corpus
- resumed sessions benefit even when the prior agent never explicitly used memory tools

## 16.2 Provenance-aware future tuning

In future, retrieval can weight or filter by provenance:

- `workflow_complete_auto` may be high-value summaries
- `workflow_checkpoint_auto` may be useful but noisier
- manual episode memories may deserve stronger ranking weight

For workflow-complete auto-memory specifically, the current implementation already treats closeout quality as a matching problem rather than a pure text-equality problem:

- duplicate suppression rejects exact repeated closeout summaries
- near-duplicate suppression uses extracted closeout fields, metadata-aware matching, and weighted similarity
- this should make retrieval corpora less noisy without requiring provenance-aware retrieval changes yet

This is optional for the initial phase.

---

## 17. Testing Plan

## 17.1 Unit tests

Add focused tests for:

- completion auto-memory summary generation
- checkpoint auto-memory summary generation
- checkpoint eligibility logic
- provenance / metadata values
- closeout duplicate suppression
- closeout near-duplicate suppression
- extracted semantic field comparison for generated closeout summaries
- metadata-aware non-matches when:
  - `verify_status` differs
  - `attempt_status` differs
  - `failure_reason` differs
- weighted closeout similarity behavior
- low-similarity closeouts still recording

## 17.2 Integration tests

Add PostgreSQL-backed integration tests to prove:

- `workflow_complete` can create auto memory
- corresponding memory item is stored
- embedding row is stored when enabled
- `memory_search` can retrieve content created through workflow-only paths
- closeout duplicate suppression works against persisted PostgreSQL episodes
- closeout near-duplicate suppression works against persisted PostgreSQL episodes
- extracted semantic closeout fields participate in suppression decisions
- differing `attempt_status` and `failure_reason` do not get suppressed as near-duplicates

## 17.3 Regression expectations

Existing behavior must remain correct for:

- explicit `memory_remember_episode`
- workflow completion without summary
- disabled embedding mode
- external embedding enabled mode
- current memory observability contract

---

## 18. Suggested Delivery Phases

## Phase 1: plan + completion auto-memory
- write design doc
- implement auto memory on `workflow_complete`
- add focused tests
- validate PostgreSQL persistence and embedding generation

## Phase 2: checkpoint auto-memory
- implement eligibility heuristic
- add tests for signal filtering and noise control
- validate semantic retrieval quality remains acceptable

## Phase 3: retrieval/provenance tuning
- consider provenance-aware ranking or filtering
- consider dedupe / auto-memory caps
- document operational guidance

---

## 19. Acceptance Criteria

This work is successful when:

1. using normal workflow tools can produce episodic memory automatically
2. auto-generated episodic memory produces semantic embeddings when enabled
3. `workflow_complete` reliably leaves behind reusable memory
4. retrieval tools can benefit from workflow-derived memory without requiring explicit manual memory calls
5. workflow truth remains canonical even if automatic memory creation fails
6. tests prove:
   - episode creation
   - memory item creation
   - embedding persistence
   - retrieval usability

---

## 20. Recommended Immediate Next Step

Implement **Phase 1 only** first:

- add automatic memory generation on `workflow_complete`
- keep checkpoint auto-memory for a follow-up patch

Reason:

- this delivers the biggest practical improvement with the lowest design risk
- it moves the system toward ".rules compliance implies multilayer memory" immediately
- it avoids premature checkpoint-noise problems

---

## 21. Implementation Notes for the First Patch

For the first patch, prefer this behavior:

- if `CompleteWorkflowInput.summary` exists, use it
- else if latest checkpoint summary exists, use that
- else do not create auto memory
- mark created memory with:
  - `memory_origin = "workflow_complete_auto"`
  - `auto_generated = true`
- run embedding persistence through the normal existing memory path
- ensure automatic memory creation is tested in both:
  - embedding disabled
  - embedding enabled

This first patch should be enough to validate the architecture and make workflow-only usage materially more memory-capable.