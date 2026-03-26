# Remember Path 0.8.0 Plan

## 1. Purpose

The goal of `0.8.0` is to make `ctxledger` reliably **remember** meaningful work in a multi-layer form instead of stopping at sparse episodic notes.

This milestone exists because retrieval quality is downstream of recording quality.

`ctxledger` already has:

- canonical workflow state in PostgreSQL
- append-only episodic memory
- initial memory-item persistence
- optional embedding generation
- constrained summary and AGE-backed read paths

But that does **not** yet mean the system is accumulating the kind of layered memory needed for durable agent recall.

In particular, a deployment can remain in a state where:

- episodes exist
- memory items exist
- embeddings may exist
- `memory_relations` remains empty
- AGE graph bootstrap succeeds mechanically but mirrors little useful structure

That is not sufficient for the intended product direction.

`0.8.0` is therefore focused on the **remember path**:

- how work becomes memory
- how canonical memory structure is accumulated
- how AI agents are expected to record completion-centered knowledge
- how multi-layer memory becomes operationally meaningful

This should be treated as a durable-memory production milestone, not merely as an observability or cleanup pass.

---

## 2. Problem Statement

The current repository state is stronger at **storing workflow progress** than at **building rich memory structure** from that progress.

Observed failure mode:

- a workflow can be completed correctly
- a checkpoint can contain useful `current_objective` and `next_intended_action` fields
- an episode may be recorded
- a memory item may be created
- but canonical memory relations may still remain empty
- and the graph layer may therefore have little or nothing useful to mirror

This creates a gap between the intended model and operational reality.

The intended model is multi-layer:

1. workflow state
2. episodic memory
3. semantic / procedural memory
4. hierarchical / graph-backed retrieval support

The current practical remember path often behaves more like:

1. workflow state
2. maybe an episode
3. maybe one memory item
4. stop

That is too weak for the product promise.

A system that aims to help an agent remember from:

- an entity
- a concept
- a time slice
- a prior task thread
- a recovery pattern

must first record enough linked memory structure to make that possible.

---

## 3. Primary Objectives

`0.8.0` should implement the first explicit remember-path milestone that can:

1. define the minimum canonical memory artifacts a normal work loop should leave behind
2. strengthen completion-centered memory capture for AI-agent-driven usage
3. transform checkpoint and closeout information into reusable memory structures more consistently
4. introduce the first useful canonical relation-writing behavior
5. make the AGE-backed graph layer meaningful by ensuring it has canonical relational inputs to mirror
6. improve operator visibility into where memory recording succeeds, skips, or breaks

This milestone should not attempt a broad architecture rewrite.

It should strengthen the current relational-first memory pipeline so later retrieval and graph work are built on a more meaningful substrate.

---

## 4. Non-Objectives

`0.8.0` is **not** intended to be:

- a full Mnemis-style architectural redesign
- a graph-native replacement for PostgreSQL canonical truth
- a broad rewrite of every memory data structure
- an embeddings-only milestone
- a retrieval-ranking milestone detached from memory creation
- a catch-all docs-only effort

This milestone should remain tightly scoped to **remember-path quality**, **canonical memory accumulation**, and **agent-operable recording behavior**.

---

## 5. Current Issues

## 5.1 Memory relations can remain empty in normal usage

The repository already has:

- canonical `memory_relations`
- relation repositories
- constrained `supports` lookup
- AGE bootstrap logic that mirrors `supports` edges

But normal operation can still produce:

- `memory_relation_count = 0`

That means the graph layer is not wrong so much as underfed.

## 5.2 AGE is currently downstream of memory recording

The current AGE implementation is largely:

- readiness checking
- graph bootstrap
- derived graph refresh
- constrained read traversal

This means graph usefulness depends on canonical relational inputs already existing.

If relation writing is weak, AGE remains mostly decorative.

## 5.3 Remember behavior is too episodic-note-centric

The current practical remember path is centered on:

- `memory_remember_episode`
- workflow completion auto-memory
- memory item creation
- optional embedding creation

This is valuable, but insufficient for the intended layered memory model.

## 5.4 Completion does not reliably become linked memory

Useful completion information exists in fields such as:

- workflow status
- verify status
- failure reason
- latest checkpoint summary
- `current_objective`
- `next_intended_action`

But these do not yet reliably turn into:

- relation-rich memory structures
- explicit anchors for later recall
- reusable semantic / procedural memory links

## 5.5 Agent compliance depends too much on discretionary tool use

The repository has strong operational guidance in `.rules`, but the remember path still depends too much on:

- whether an agent voluntarily records an episode
- whether the right structured fields are included
- whether memory capture is treated as optional rather than integral

For an MCP-driven system, this is too fragile.

## 5.6 Observability is not pipeline-shaped enough

Current observability can show counts such as:

- episodes
- memory items
- embeddings
- memory relations

But it is harder to tell:

- what was attempted
- what was skipped
- why it was skipped
- which stage of the remember pipeline is underperforming

---

## 6. Desired End State

At the end of `0.8.0`, a normal AI-agent work loop should more reliably leave behind a useful multi-layer memory trail.

That should mean, at minimum:

- workflow and checkpoint truth remains canonical in PostgreSQL
- meaningful completion or checkpoint knowledge becomes episodes more consistently
- episodes are transformed into memory items more consistently
- embeddings are created where configured and applicable
- the first constrained relation-writing path is active
- graph mirroring can operate on non-trivial relational memory inputs
- operators can tell whether remember-path failure is due to:
  - policy gating
  - missing inputs
  - duplicate suppression
  - configuration
  - disabled features
  - relation-generation gaps
  - graph refresh gaps

---

## 7. Milestone Scope

## 7.1 In scope

- completion-centered remember-path design
- structured checkpoint-to-memory promotion rules
- first constrained relation-writing behavior
- stronger agent-facing memory-recording expectations
- observability for remember-path stages and skips
- documentation of canonical vs derived remember responsibilities
- operator guidance for validating whether the system is actually accumulating layered memory

## 7.2 Out of scope

- broad graph-model redesign
- generalized ontology/entity extraction across all text
- replacing current relational memory ownership with graph ownership
- broad Mnemis alignment work
- solving all retrieval/ranking questions in the same slice

---

## 8. Conceptual Model for 0.8.0

## 8.1 Remember pipeline

The intended `0.8.0` remember pipeline should be read as:

1. canonical workflow and checkpoint state exists
2. a meaningful event is selected for memory capture
3. an episode is recorded
4. one or more memory items are created
5. optional embeddings are created
6. one or more canonical relations may be created
7. summary / graph mirrors may be refreshed from canonical relational state

This sequence preserves the architectural rule:

- PostgreSQL canonical first
- retrieval and graph support derived later

## 8.2 Completion-centered memory capture

A completion or closeout event should not be treated as only a terminal log line.

It is often the best source for durable memory because it can contain:

- what was done
- what was learned
- why it mattered
- what remains
- what should be continued next

## 8.3 Relation-first minimum viable graph substrate

The first relation-writing slice does not need to be broad.

It should be enough to create useful canonical links for a constrained first relation type such as:

- `supports`

The important thing is to move from:

- relation-capable but relation-empty

to:

- relation-capable and relation-producing

## 8.4 Agent-operable memory discipline

For an MCP-capable agent, remember-path behavior should become more operationally explicit.

The system should not rely on:

- best effort
- discretionary note taking
- local auxiliary files

Instead, memory creation should be integrated into canonical workflow operation and explicit memory tools.

---

## 9. Proposed Implementation Direction

## 9.1 Define minimum remember artifacts per work loop

Specify what a healthy work loop should leave behind under common cases.

Candidate policy:

### For a meaningful workflow completion
At minimum:

- one episode
- one memory item
- optional embedding if configured
- relation candidates if enough structure exists

### For a meaningful checkpoint
At minimum, if the checkpoint contains sufficient signal:

- episode-worthy promotion should be possible or automatic
- checkpoint objective / next-action fields should be reusable in later memory creation
- relation generation should be able to anchor these fields to the resulting memory items

## 9.2 Introduce constrained canonical relation-writing

The first relation-writing behavior should be deliberately narrow.

Recommended first slice:

- create `supports` relations for clearly justified memory-item pairs produced during completion-centered memory capture or summary-building flows

Examples of candidate relation shapes:

- a next-action memory item supports a current-objective memory item
- a completion note supports a primary objective memory item
- a recovery note supports a failure/root-cause note
- a summary member relation induces a constrained support-style retrieval link where justified

This should begin narrowly and explicitly.

## 9.3 Strengthen completion auto-memory

The existing workflow completion auto-memory path should be evaluated and likely extended so it can move beyond:

- one episode
- one memory item
- optional embedding

toward:

- richer structured memory item creation
- relation candidate generation
- better surfaced skip reasons
- more explicit policy / trigger reporting

## 9.4 Clarify explicit memory tool expectations for agents

The repository should define more clearly when an agent should:

- call `memory_remember_episode`
- rely on workflow-completion auto-memory
- treat memory capture as mandatory rather than optional
- include structured fields such as:
  - current objective
  - next intended action
  - root cause
  - recovery pattern
  - failure / resolution summary

## 9.5 Improve remember-path observability

Operator-facing and debug-facing surfaces should make it possible to inspect:

- episode creation attempts
- memory item creation attempts
- embedding creation attempts
- relation creation attempts
- summary build attempts
- skip reasons by stage

This should help answer:

- is the system not remembering?
- is it remembering only episodes?
- is embedding disabled?
- are relation writes never attempted?
- is graph state stale relative to canonical memory state?

---

## 10. Workstreams

## 10.1 Workstream A — remember-path audit and contract definition

Deliverables:

- explicit remember pipeline description
- minimum expected artifacts by workflow event type
- clear distinction between:
  - canonical records
  - derived retrieval helpers
  - optional graph mirrors

## 10.2 Workstream B — completion and checkpoint memory promotion

Deliverables:

- stronger completion auto-memory shaping
- explicit promotion rules for meaningful checkpoint content
- better handling of:
  - `current_objective`
  - `next_intended_action`
  - failure / recovery
  - verification outcomes

## 10.3 Workstream C — constrained relation generation

Deliverables:

- first canonical relation-writing implementation
- tests showing relation creation under expected flows
- clear bounded semantics for the first relation type(s)

## 10.4 Workstream D — agent-facing operational guidance

Deliverables:

- `.rules`-aligned memory-recording guidance
- MCP usage guidance for agents
- clearer expectations for when memory capture is required

## 10.5 Workstream E — remember-path observability

Deliverables:

- improved stats / diagnostics / debug reporting
- visibility into stage-level success, skips, and failures
- operator guidance for validating a healthy layered-memory deployment

---

## 11. Proposed Acceptance Criteria

`0.8.0` should not be considered complete unless all of the following are true.

---

## Appendix A. Current remember-path behavior at planning time

The current repository behavior should be read as a **bounded completion auto-memory path**, not yet as a full remember-path implementation.

Current practical flow during `workflow_complete` is:

1. workflow and attempt terminal state are written canonically
2. latest checkpoint is inspected for gating
3. one closeout episode may be created
4. one closeout memory item may be created
5. one embedding may be created when configured
6. optional episode-summary automation may run if explicitly requested
7. stop

This means the current repository already has a useful completion memory bridge, but it still commonly stops before multi-item promotion and canonical relation creation.

### A.1 What currently works

At planning time, the repository already supports:

- completion-centered auto-memory gating
- duplicate suppression for near-duplicate closeout memory
- one canonical closeout episode on successful recording
- one canonical closeout memory item derived from that episode
- optional embedding persistence for that closeout memory item
- optional explicit summary-building metadata/reporting for the completion-created episode

### A.2 Where the current path usually stops

The current path still usually stops after:

- episode creation
- one closeout memory item
- optional embedding
- optional summary-build reporting

In particular, the current behavior is still weak or absent for:

- separate promoted memory items for `current_objective`
- separate promoted memory items for `next_intended_action`
- separate promoted memory items for failure / recovery knowledge
- separate promoted memory items for verification outcomes
- canonical `memory_relations` writing during normal completion flows
- stage-shaped observability across the full remember pipeline

### A.3 Current canonical / derived boundary

The current boundary should be read as:

- PostgreSQL workflow / checkpoint / memory tables are canonical
- episode summaries are canonical relational artifacts when explicitly built
- AGE graph state is derived from canonical relational records
- graph usefulness is downstream of relation creation and therefore cannot compensate for sparse canonical memory structure

### A.4 Current operator reading

If a deployment currently shows:

- workflows and checkpoints present
- episodes present
- memory items present
- embeddings present
- `memory_relations = 0`

that should be read as a remember-path weakness rather than as a graph-layer defect.

### A.5 Immediate contract implication for `0.8.0`

The `0.8.0` implementation contract should therefore strengthen the current path from:

- workflow completion -> maybe episode -> maybe one memory item -> stop

toward:

- workflow completion / meaningful checkpoint
- episode capture
- structured memory-item promotion
- constrained canonical relation writing
- optional embedding / summary / graph refresh
- explicit stage-level reporting of success, skip, and failure reasons

## 11.1 Canonical remember pipeline is clearer and stronger

- the repository documents how meaningful work becomes layered memory
- the remember path is explicitly defined, not merely implied by scattered features

## 11.2 Completion-centered recording is materially improved

- normal workflow completion leaves behind durable canonical memory more reliably
- the system can explain when it skipped recording and why

## 11.3 Canonical relation writing exists in a useful first form

- at least one constrained relation-writing path is implemented
- relation counts no longer remain structurally zero in healthy representative usage

## 11.4 Graph mirroring has meaningful inputs

- AGE bootstrap / refresh can operate on a non-trivial canonical memory substrate
- graph usefulness is no longer blocked primarily by absent relation data

## 11.5 Agent-operable expectations are documented

- MCP-capable agents have clearer memory-recording expectations
- the repository guidance supports automatic and correct memory capture more strongly

## 11.6 Validation demonstrates end-to-end remember-path improvement

Validation should include representative coverage for:

- workflow completion memory creation
- checkpoint-derived memory promotion
- relation creation
- observability / diagnostics
- graph bootstrap / refresh behavior against non-empty relation data

---

## 12. Risks

## 12.1 Over-recording noisy memory

If promotion rules are too broad, the system may accumulate low-value memory clutter.

Mitigation:

- start with high-signal, clearly scoped triggers
- prefer bounded relation semantics
- preserve duplicate suppression and explain skip reasons

## 12.2 Relation semantics becoming hand-wavy

If relations are introduced without strict meaning, the graph layer becomes unreliable.

Mitigation:

- begin with a single constrained relation type
- document exact write conditions
- keep canonical relation meaning narrow and testable

## 12.3 Agent burden increasing too much

If the memory contract becomes too manual, agents may comply inconsistently.

Mitigation:

- favor automatic capture where possible
- use explicit policy and structured defaults
- keep manual memory tools for high-signal cases, not everything

## 12.4 Confusing canonical and derived layers

If graph or summary layers begin to look authoritative, operators may misread the system.

Mitigation:

- keep relational canonical ownership explicit everywhere
- document graph and summary layers as derived and degradable

---

## 13. Validation Strategy

Representative validation for `0.8.0` should include:

---

## Appendix B. `0.8.0` implementation contract

The repository should treat the following as the concrete implementation contract for this milestone.

### B.1 Event types that must participate in the remember path

The first `0.8.0` slice should cover:

- meaningful workflow completion
- meaningful checkpoints with high-signal structured fields

A checkpoint should be treated as high-signal when it contains one or more of:

- `current_objective`
- `next_intended_action`
- failure / recovery signal
- verification outcome signal
- other explicitly documented closeout-worthy fields

### B.2 Minimum artifacts for meaningful workflow completion

For a meaningful workflow completion, the intended minimum artifact set is:

- one canonical episode
- one canonical closeout memory item
- promoted canonical memory items when structured fields are present
- optional embedding persistence where configured
- constrained canonical relation creation where enough structure exists
- additive reporting for each remember stage

The promoted memory-item set should be intentionally narrow at first.

Recommended first promoted item categories are:

- current objective
- next intended action
- verification outcome
- failure reason / recovery note

### B.3 Minimum artifacts for meaningful checkpoint promotion

For a meaningful checkpoint, `0.8.0` should make it possible for checkpoint structure to be reused in later memory creation rather than disappearing into checkpoint-only storage.

At minimum, the contract should allow:

- objective-bearing checkpoints to produce or feed objective memory
- next-action-bearing checkpoints to produce or feed next-action memory
- failure / recovery-bearing checkpoints to produce or feed recovery-oriented memory
- verify-bearing checkpoints to produce or feed verification-outcome memory

### B.4 First constrained relation-writing rule

The first canonical relation-writing slice should remain narrow.

The default first rule should be:

- write `supports` relations only

The first allowed relation shapes should be constrained to explicitly justified pairs such as:

- next-action memory item -> supports -> current-objective memory item
- verification-outcome memory item -> supports -> completion note
- failure / recovery memory item -> supports -> completion note
- other equally narrow completion-derived pairs that are documented and tested

If no justified pair exists, relation writing should skip explicitly rather than invent weak edges.

### B.5 Observability contract

Remember-path observability should become stage-shaped.

The implementation should surface stage-level outcomes for at least:

- gating
- summary-source selection
- duplicate suppression
- episode creation
- primary memory-item creation
- promoted memory-item creation
- embedding persistence
- relation creation
- summary build, when applicable

Each stage should ideally report:

- whether it was attempted
- whether it succeeded, skipped, failed, or was not configured
- skip or failure reason when applicable
- counts or created identifiers where useful

### B.6 Agent-facing contract

Repository guidance for MCP-capable agents should become more explicit.

The intended reading is:

- workflow completion auto-memory should handle normal closeout capture
- explicit episode recording should still be used for high-signal knowledge that is not safely captured by completion automation alone
- agents should include structured checkpoint fields when they know them, especially:
  - `current_objective`
  - `next_intended_action`
  - root cause
  - recovery pattern
  - verification outcome
  - what remains

### B.7 Non-goals of this contract

This contract still does **not** require:

- broad ontology extraction
- broad graph-native redesign
- unconstrained relation semantics
- broad retrieval/ranking redesign
- treating derived graph state as canonical truth

- unit tests for remember-path decision logic
- integration tests for workflow-completion auto-memory
- tests for relation creation and counting
- tests for relation-aware graph bootstrap inputs
- tests for operator/debug surfaces that report memory creation outcomes
- focused end-to-end checks that demonstrate:
  - episode creation
  - memory item creation
  - embedding creation when enabled
  - relation creation
  - graph bootstrap against non-empty canonical relation data

---

## 14. Documentation Deliverables

`0.8.0` should update at least:

- roadmap wording for `0.8` and `0.9`
- memory model documentation for the strengthened remember path
- operator guidance for validating layered memory accumulation
- release changelog entries for the new remember-path behavior
- agent-facing rules/guidance where memory recording expectations become stricter or clearer

---

## 15. Relationship to Later Work

This milestone is intentionally positioned before broader architectural evaluation work.

`0.9.0` can evaluate whether `ctxledger` should move closer to a Mnemis-style graph/hierarchy design **after** the remember path is no longer the main bottleneck.

That ordering matters.

It is too early to judge graph-memory architecture quality if the system is not yet reliably creating the canonical relational memory structure the graph layer would depend on.

So the intended sequence is:

- `0.7.0`: improve task recall
- `0.8.0`: strengthen remember-path accumulation
- `0.9.0`: evaluate broader graph-memory architectural alignment questions

---

## 16. Immediate Next Steps

1. audit the current completion-to-memory pipeline and write down where memory creation stops today
2. define the minimum expected memory artifacts for a meaningful completed workflow
3. identify the narrowest useful first canonical relation-writing rule
4. add observability for relation-generation attempts and skips
5. update agent-facing guidance so memory recording is more operationally explicit
6. validate remember-path improvement before broadening graph-memory design ambitions

---

## 17. Summary

`0.8.0` should be the milestone where `ctxledger` becomes materially better at **remembering**, not only at **storing workflow state** or **reading from derived retrieval layers**.

The central problem is not that graph support exists and is broken.

The central problem is that the system does not yet consistently accumulate enough canonical linked memory for the graph, semantic, and hierarchical layers to matter.

So the milestone focus should be:

- improve the remember path
- create canonical memory links
- make completion-centered memory capture operationally strong
- make agent-driven recording behavior more reliable
- ensure the graph layer has something meaningful to mirror

That is the right foundation for later retrieval and architectural work.