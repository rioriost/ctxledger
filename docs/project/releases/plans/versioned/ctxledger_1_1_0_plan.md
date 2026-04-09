# `ctxledger` `1.1.0` Implementation Plan

## 1. Purpose

`1.1.0` is the next planned milestone after the bounded `1.0.1` stabilization
slice.

The purpose of `1.1.0` is to improve `ctxledger` as a durable workflow runtime
for AI agents by using evidence from actual PostgreSQL-backed usage, where agent
behavior was shaped by the repository `.rules` and executed through the
`ctxledger` tool surface.

This milestone should be read as a **rules-to-runtime alignment and
agent-quality improvement release**.

It is not primarily about adding a new storage backend or changing the canonical
truth boundary.

Instead, it focuses on making the current system better at:

- producing higher-quality structured workflow records
- turning repeated operational traces into reusable knowledge
- improving resumability and fallback visibility
- reducing memory-shape drift between intended policy and actual usage
- aligning `.rules` guidance with what the runtime can actually enforce and
  observe

---

## 2. Why `1.1.0` is needed

Completed Phase 0 gap analysis confirms that the current system is already
successful at producing a large durable trail, but that trail is still more
log-like than knowledge-like.

Representative PostgreSQL-backed findings now include:

- `episodes = 5410`
- `memory_items = 23520`
- `memory_summaries = 1`
- `memory_summary_memberships = 1`
- `interaction_request = 7663`
- `interaction_response = 7663`
- `workflow_checkpoint_note = 2730`
- `workflow_verification_outcome = 2708`
- `episode_note = 2629`
- `914` memory items currently have `workspace_id IS NULL`
- all observed interaction items currently have `episode_id IS NULL`
- structured checkpoint fields such as `current_objective`,
  `next_intended_action`, `root_cause`, `recovery_pattern`, and
  `what_remains` are structurally possible, but currently near-zero in observed
  checkpoint payloads
- summary build exists, but no observed checkpoint currently requests
  `build_episode_summary`

Phase 0 therefore confirms that the current system is good at **capturing work**,
but still weaker at:

- **structuring work**
- **distilling work**
- **measuring agent-quality outcomes**
- **closing the loop between `.rules`, runtime behavior, and durable memory**

The most important evidence-backed mismatches are now clear:

1. structured checkpoint intent is strong, but structured checkpoint population
   is near-zero in practice
2. summary build exists, but summary production is negligible because build
   requests are not being induced
3. interaction capture is strong, but interaction linkage to episodes and
   workflow context is weak
4. resumability behavior is strong, but resumability quality is not measured
   through aggregate metrics
5. observability is strong for volume and state, but weak for quality, hygiene,
   and linkage gaps

---

## 3. Milestone framing

Phase 0 findings show that `1.1.0` should be framed as:

- a release that improves the quality of AI-agent workflow records
- a release that improves the conversion of operational traces into reusable
  memory
- a release that strengthens resumability and orchestration observability
- a release that updates `.rules` so they better match the runtime and the
  evidence from real usage
- a release that improves linkage and hygiene quality without changing the
  canonical truth boundary

In short:

`1.1.0` should move `ctxledger` from a system that can reliably record agent
work into a system that can also more reliably **teach from that work**, while
making quality gaps visible enough to improve deliberately.

---

## 4. Non-goals

`1.1.0` should not try to solve every future memory or orchestration question.

This milestone should explicitly avoid:

- changing the canonical system of record away from PostgreSQL
- introducing a new truth model that competes with canonical relational state
- attempting full semantic interpretation of all interaction traffic
- overcommitting to a graph-first knowledge architecture
- mixing unrelated large architectural changes into the same milestone

The milestone should prefer bounded, additive, evidence-backed improvements.

---

## 5. Initial phase: `1.0.0` implementation gap analysis

Before finalizing the `1.1.0` implementation slices, the first work phase must
be a structured gap analysis against the `1.0.0` implementation and its intended
release posture.

The detailed Phase 0 checklist should live in a separate companion document:

- `docs/project/releases/plans/versioned/ctxledger_1_1_0_phase0_gap_analysis_checklist.md`

This phase is required because the PostgreSQL corpus shows actual usage
outcomes, but those outcomes alone do not distinguish between:

- features that were never implemented
- features that were partially implemented
- features that were implemented but weakly surfaced
- features that were implemented correctly but weakly induced by `.rules`
- features that exist in the runtime but are not materially used in practice

### 5.1 Purpose of the gap analysis

The gap analysis should establish a three-way comparison between:

1. intended `1.0.0` behavior
2. current runtime and schema behavior
3. observed PostgreSQL-backed usage outcomes

This phase should prevent `1.1.0` from planning work that is actually:

- already implemented
- already planned elsewhere
- blocked by a different underlying mismatch
- better solved in `.rules` than in runtime code
- better solved in runtime code than in `.rules`

### 5.2 Questions the gap analysis must answer

The gap analysis should answer at least the following questions:

#### A. Structured workflow recording
- What structured checkpoint fields were intended by `1.0.0` design and release
  posture?
- Which of those fields are actually supported in tool payloads and storage?
- Which fields are only present in prose summaries?
- Which fields are present in storage but not surfaced well enough for reuse?

#### B. Summary and memory distillation
- What summary automation or summary build behavior was intended by `1.0.0`?
- What is implemented today for canonical summaries and summary memberships?
- Why is summary volume materially lower than raw memory volume?
- Is the main gap in runtime automation, `.rules` prompting, operator usage, or
  retrieval surfacing?

#### C. Interaction capture and reuse
- What interaction capture boundary was intended by `1.0.0`?
- How are interaction request/response items currently stored?
- What linkage exists today between interaction memory and episodes?
- Which missing links most directly reduce knowledge reuse?

#### D. Resumability and fallback quality
- What resumability guarantees were intended by `1.0.0`?
- Which resume and retry signals are currently stored?
- Which resume-quality outcomes are observable today?
- Which important resumability outcomes are happening but not measured?

#### E. Observability and operator signals
- Which operator-facing metrics were intended by `1.0.0` and `1.0.1`?
- Which metrics exist in CLI, SQL, and Grafana?
- Which agent-quality metrics are still missing?
- Which current metrics are too ambiguous to guide improvement?

#### F. `.rules` to runtime alignment
- Which `.rules` requirements are already enforceable by runtime structure?
- Which `.rules` requirements are only advisory today?
- Which runtime capabilities exist but are not strongly induced by `.rules`?
- Which `.rules` clauses should be tightened, clarified, or split?

### 5.3 Deliverables of the gap analysis phase

This first phase should produce:

1. a `1.0.0` intent vs current implementation matrix
2. a runtime vs `.rules` alignment matrix
3. a PostgreSQL evidence summary for the most important mismatches
4. a narrowed `1.1.0` scope recommendation
5. a list of items explicitly deferred out of `1.1.0`
6. a completed Phase 0 checklist in:
   - `docs/project/releases/plans/versioned/ctxledger_1_1_0_phase0_gap_analysis_checklist.md`

### 5.4 Exit criteria for the gap analysis phase

The gap analysis phase is complete when:

- the main `1.1.0` themes are justified by both implementation evidence and
  usage evidence
- each proposed `1.1.0` slice is classified as:
  - runtime change
  - `.rules` change
  - observability change
  - documentation/operator change
  - or a combination of those
- no major `1.1.0` slice remains ambiguous about whether it is already present
  in `1.0.x`

---

## 6. `1.1.0` themes after the gap analysis phase

Phase 0 findings narrow the milestone into five main themes.

### Theme 1. Better agent checkpoints

#### Goal
Improve the quality, structure, and reuse value of workflow checkpoints.

#### Why this matters
Phase 0 confirmed that successful work repeatedly uses:

- narrow next actions
- explicit verification language
- bounded slices
- resumability-aware progress notes

But these are still mostly embedded in prose rather than stored as structured
fields, and observed checkpoint payloads currently show near-zero population for
the most important structured fields.

#### Planned outcomes
- strengthen structured checkpoint payload support
- make high-value checkpoint fields easier to store and retrieve
- improve checkpoint quality observability
- reduce dependence on freeform summary parsing for core workflow state

#### Candidate fields
The runtime should support stronger structured capture for fields such as:

- `current_objective`
- `next_narrow_action`
- `what_changed`
- `what_was_learned`
- `what_remains`
- `verify_target`
- `blocker_or_risk`
- `resume_hint`
- `failure_guard`

---

### Theme 2. Better memory distillation

#### Goal
Turn repeated operational traces into reusable knowledge.

#### Why this matters
Phase 0 confirmed that the corpus contains a large amount of durable material,
but almost no canonical summary output relative to the amount of raw memory.

This is not mainly a schema absence problem.
It is an induction and usage problem.

#### Planned outcomes
- improve canonical summary generation from high-signal memory
- improve summary-build induction for high-signal closeout paths
- preserve traceability from summaries back to supporting memory items
- make summary backlog visible to operators
- make summary-first retrieval more useful in practice

#### Candidate summary kinds
Potential summary kinds include:

- `agent_planning_pattern`
- `agent_verification_pattern`
- `agent_resume_pattern`
- `agent_orchestration_pattern`
- `agent_failure_recovery_pattern`

---

### Theme 3. Better interaction linkage and promotion

#### Goal
Keep strong interaction capture, but make interaction memory more reusable.

#### Why this matters
Phase 0 confirmed that interaction capture is materially active, but linkage is
weak:

- interaction volume is the largest memory category
- all observed interaction items currently have `episode_id IS NULL`
- workflow context is often present only indirectly or weakly surfaced
- interaction memory therefore captures a lot, but teaches less than it should

#### Planned outcomes
- improve linkage between interaction memory and episode-level context
- improve workflow-context promotion for interaction memory
- make unlinked interaction volume visible
- support bounded promotion of high-signal interaction material into stronger
  reusable memory

---

### Theme 4. Better resumability and fallback quality

#### Goal
Make resumability quality measurable and easier to improve.

#### Why this matters
Phase 0 confirmed that resumability behavior is already strong in runtime design,
but weak in aggregate observability:

- composite resume views are implemented
- resumability-first posture is clear
- retry-capable architecture exists in bounded form
- but aggregate resume and fallback quality metrics are still missing
- structured resume-related checkpoint fields remain near-zero in observed data

#### Planned outcomes
- improve storage and surfacing of resume-related structured fields
- add clearer observability for resume attempts and outcomes
- make fallback-prevention behavior more visible
- improve operator understanding of resumability quality

#### Candidate metrics
Potential metrics include:

- `resume_attempt_count`
- `resume_success_count`
- `resume_failure_count`
- `retry_limit_hit_count`
- `silent_fallback_prevented_count`
- `structured_resume_hint_count`

---

### Theme 5. Better rules-to-runtime alignment

#### Goal
Update `.rules` and runtime behavior so they reinforce each other more directly.

#### Why this matters
Phase 0 confirmed that the PostgreSQL corpus is not just runtime output.
It is the result of AI-agent behavior shaped by `.rules`.

It also confirmed a split:

- workflow tracking, canonical posture, summary truth boundaries, and file-work
  recording align strongly
- structured checkpoint content, summary build induction, and agent-quality
  observability remain mostly advisory in practice

#### Planned outcomes
- tighten `.rules` where high-value behavior should be more explicit
- reduce cases where `.rules` ask for structure that the runtime does not store
  well
- reduce cases where runtime supports useful structure that `.rules` do not
  strongly induce
- improve observability so rule-following quality can be measured
- split broad rule areas where narrower guidance would improve induction quality

---

## 7. Proposed implementation phases

## Phase 0. `1.0.0` gap analysis and scope lock

This is the required first phase described above.

Use the dedicated checklist document to execute and close this phase:

- `docs/project/releases/plans/versioned/ctxledger_1_1_0_phase0_gap_analysis_checklist.md`

Phase 0 is now expected to drive the milestone using these confirmed findings:

- structured checkpoint support exists, but high-value structured fields are not
  being populated in practice
- summary build exists, but summary production is negligible because build
  requests are not being induced
- interaction capture is strong, but interaction linkage is weak
- resumability behavior is strong, but aggregate quality metrics are missing
- observability is strong for volume and state, but weak for quality, hygiene,
  and linkage gaps

Outputs from this phase should determine the exact shape of later slices.

---

## Phase 1. Structured checkpoint and workflow record improvements

### Scope
- extend checkpoint payloads and storage for higher-value structured fields
- improve retrieval and surfacing of structured checkpoint content
- add observability for structured checkpoint coverage
- make `next_narrow_action` and `verify_target` first-class enough to become
  habitual rather than prose-only

### Expected result
The runtime should make it easier for agents to leave durable records that are:

- resumable
- verifiable
- narrow in scope
- easier to summarize later
- aligned with the strongest observed successful work patterns

---

## Phase 2. Summary distillation and reusable knowledge generation

### Scope
- improve canonical summary generation from high-signal checkpoint and episode
  material
- improve summary-build induction for high-signal closeout paths
- support summary kinds oriented toward agent improvement
- preserve summary membership traceability
- improve summary-first retrieval usefulness
- add summary backlog visibility

### Expected result
The system should produce more reusable knowledge from repeated successful and
recovery-oriented work, and operators should be able to see when summary support
exists but is under-produced.

---

## Phase 3. Interaction linkage and orchestration-aware memory

### Scope
- improve linkage between interaction memory and episode-level context
- improve workflow-context promotion for interaction memory
- identify promotion-worthy interaction patterns
- add visibility for unlinked interaction volume
- consider new memory types for orchestration boundaries, such as:
  - handoff notes
  - state transition notes
  - resume decision notes
  - fallback-prevention notes

### Expected result
The system should become better at learning from:

- planning pivots
- retry decisions
- resume decisions
- orchestration boundary failures and recoveries

without treating all interaction traffic as equally valuable or leaving most
interaction memory weakly linked.

---

## Phase 4. Resume-quality, hygiene, and agent-quality observability

### Scope
- add resume and fallback quality metrics
- improve CLI, SQL, and Grafana visibility for agent-quality signals
- surface summary backlog and memory hygiene signals
- surface null-`workspace_id` memory volume and weak-linkage signals
- reduce ambiguous operator readings

### Expected result
Operators should be able to see not only that memory exists, but whether the
agent operating model is improving and where linkage or hygiene gaps remain.

---

## Phase 5. `.rules` `v1.1` alignment update

### Scope
Update `.rules` so they better reflect the runtime and the evidence from actual
usage.

### Status
Applied and committed.

The canonical `.rules` file is already at `v1.1`, and the related policy
updates were committed as:

- `19403cd` — `Tighten v1.1 repository rules policy`

### Candidate rule changes
Applied changes include:

- stronger preference or requirement for structured checkpoint fields
- explicit emphasis on `next_narrow_action`
- explicit emphasis on named `verify_target`
- clearer guidance for when summary build should be requested
- clearer guidance for when interaction material should be promoted into durable
  knowledge
- stronger observability guidance for agent-quality and hygiene metrics
- stronger linkage expectations between file-touching work and corresponding
  checkpoint context
- narrower rule splits for checkpoint structure, observability, and promotion
  policy where broad rules are currently too advisory

### Expected result
The rules should more directly induce the kinds of durable records that the
runtime can best store, summarize, link, observe, and reuse.

### Outcome
This phase is now complete at the policy-document level.
Remaining `1.1.0` work is runtime, observability, and operator-documentation
follow-through.

---

## 8. Detailed `1.1.0` workstreams

## 8.0 Recommended initial execution slices

The first recommended execution sequence for `1.1.0` should follow the Phase 0
findings directly.

The initial three slices should be:

1. structured checkpoint improvements
2. summary build induction and summary backlog visibility
3. interaction linkage improvements

This order is recommended because:

- structured checkpoint improvements strengthen the quality of later summary and
  interaction work
- summary induction can reuse already implemented canonical summary paths once
  higher-signal checkpoint structure is easier to produce
- interaction linkage is high value, but should begin with bounded linkage and
  observability improvements rather than broad semantic interpretation

### Slice 1. Structured checkpoint improvements

#### Goal

Make the highest-value checkpoint fields first-class enough that they become
habitual runtime structure rather than prose-only intent.

#### Bounded tasks

1. extend the checkpoint write contract so the most important high-signal fields
   are explicit and easy to populate:
   - `current_objective`
   - `next_narrow_action`
   - `what_changed`
   - `what_was_learned`
   - `what_remains`
   - `verify_target`
   - `blocker_or_risk`
   - `resume_hint`
   - `failure_guard`
2. preserve `checkpoint_json` as the compatibility and fallback carrier rather
   than replacing it
3. update retrieval and resume surfaces so these fields are surfaced directly
   where they materially improve continuation quality
4. add observability for structured checkpoint coverage so operators can see
   whether the new structure is actually being used
5. add focused validation for:
   - checkpoint persistence
   - retrieval surfacing
   - resume-view shaping
   - structured coverage metrics

#### Expected result

The system should stop depending primarily on prose parsing for the most
important continuation and verification signals.

### Slice 2. Summary build induction and summary backlog visibility

#### Goal

Turn the existing summary build path from a rarely used capability into a
bounded, visible, and intentionally induced operating path.

#### Bounded tasks

1. strengthen the conditions under which high-signal closeout paths request
   summary build
2. add operator-visible backlog metrics such as:
   - episodes without summaries
   - summary build requests
   - summary build successes
   - summary build skips
3. improve summary-first operator visibility so low summary volume is easier to
   notice and act on
4. keep summary build explicit, checkpoint-gated, and non-fatal rather than
   turning it into broad hidden automation
5. add focused validation for:
   - explicit build behavior
   - gated build behavior
   - backlog metrics
   - summary membership traceability

#### Expected result

The system should still use the current canonical summary model, but operators
and agents should be much more likely to produce summaries when the work is
high-signal enough to justify them.

### Slice 3. Interaction linkage improvements

#### Goal

Keep the current strong interaction capture posture while making interaction
memory materially more reusable.

#### Bounded tasks

1. improve linkage between interaction memory and episode-level context
2. promote workflow-context linkage into more stable and query-friendly metadata
   rather than leaving it buried inside captured payloads
3. add observability for:
   - unlinked interaction volume
   - weakly linked interaction volume
   - interaction linkage improvement over time
4. define a bounded promotion posture for high-signal interaction material
   without attempting broad semantic interpretation of all interaction traffic
5. add focused validation for:
   - interaction linkage persistence
   - retrieval behavior over linked interaction memory
   - observability for linkage gaps

#### Expected result

Interaction memory should remain bounded and subordinate to canonical workflow
truth, but it should become much more useful for resumability, historical recall,
and later knowledge promotion.


## 8.1 Runtime workstream

### Objectives
- improve structured workflow recording
- improve summary generation
- improve interaction linkage
- improve resumability observability
- improve memory hygiene

### Candidate slices
- checkpoint payload and schema extension
- retrieval prioritization for structured fields
- summary build automation improvements
- interaction-to-episode linkage improvements
- null-`workspace_id` prevention and auditing
- new observability counters and debug surfaces

---

## 8.2 `.rules` workstream

### Objectives
- align policy with runtime structure
- reduce prose-only expectations where structure is available
- improve induction of high-value agent behavior

### Status
Core policy patch applied and committed in `19403cd`.

### Candidate slices
- strengthen checkpoint structure guidance — done
- add explicit `next_narrow_action` guidance — done
- add explicit `verify_target` guidance — done
- add summary-promotion guidance — done
- add agent-quality observability guidance — done
- clarify interaction-promotion posture — done

---

## 8.3 Documentation and operator workstream

### Objectives
- make the new behavior understandable and operable
- reduce ambiguity in how to use the improved runtime and rules

### Candidate slices
- examples of good structured checkpoints
- examples of summary-worthy high-signal episodes
- operator guidance for reading resume-quality metrics
- guidance for interpreting summary backlog and interaction linkage signals
- release-facing explanation of `.rules` `v1.1` changes

---

## 9. Prioritization

## 9.1 Must-have for `1.1.0`

Phase 0 findings support the following core milestone scope:

1. `1.0.0` gap analysis and scope lock
2. structured checkpoint improvements
3. summary build induction and summary backlog visibility
4. interaction linkage improvements
5. aggregate resume and fallback observability improvements
6. `.rules` alignment updates for structured checkpoint quality and summary
   promotion

## 9.2 Strongly desirable for `1.1.0`

These items are highly valuable if they fit the bounded milestone:

1. null-`workspace_id` hygiene metrics and prevention
2. stronger workflow-context metadata promotion for interaction memory
3. first-class audit surfaces for weak linkage and missing expected file-work
   coverage
4. orchestration-aware memory promotion patterns
5. stronger operator-facing agent-quality dashboards

## 9.3 Likely deferrable if needed

If scope pressure appears, the following should be considered for deferral:

- broader semantic interpretation of all interaction traffic
- heavy graph-derived knowledge expansion
- large architectural changes unrelated to the observed evidence
- any change that weakens the canonical relational-first truth boundary

---

## 10. Validation strategy

`1.1.0` should be validated through a combination of:

- targeted automated tests
- schema and repository validation
- CLI and observability validation
- live PostgreSQL-backed usage checks where relevant

Validation should explicitly cover:

- structured checkpoint persistence and retrieval
- structured checkpoint coverage metrics
- summary generation and membership traceability
- summary backlog visibility
- resume-quality metrics and fallback-prevention visibility
- interaction linkage behavior
- null-`workspace_id` hygiene visibility
- `.rules`-aligned usage examples
- operator interpretation of new metrics and states

Where possible, validation should include evidence that the new behavior is not
only implemented in tests, but also visible in the intended running stack.

---

## 11. Canonical boundary after `1.1.0`

`1.1.0` should preserve the current canonical truth posture.

After `1.1.0`:

- PostgreSQL should remain canonical
- workflow, checkpoint, episode, memory item, and canonical summary truth should
  remain relational-first
- graph-backed or derived layers should remain subordinate and degradable
- observability fields should remain operator signals, not replacement truth
- `.rules` should remain policy guidance, not a second canonical state store

The milestone should improve the quality of canonical records and their reuse,
not replace the canonical model.

---

## 12. Release interpretation

The intended reading of `1.1.0` should be:

- `1.0.0` established the major deployment milestone
- `1.0.1` hardened restart, file-work, and observability behavior
- `1.1.0` improves the quality of AI-agent workflow records, memory distillation,
  resumability observability, and `.rules` alignment

In short:

`1.1.0` should be the release where `ctxledger` becomes materially better at
learning from the work it already knows how to record.

---

## 13. Exit criteria for the milestone

`1.1.0` should be considered complete when:

- the `1.0.0` gap analysis has been completed and incorporated into scope
- structured checkpoint quality is materially improved
- canonical summary generation is materially more useful than in `1.0.x`
- summary backlog is visible enough to guide operator action
- interaction linkage quality is materially improved
- resume and fallback quality are more observable
- key hygiene gaps such as null-`workspace_id` memory and weak linkage are more
  visible or reduced
- `.rules` and runtime behavior are more directly aligned
- operator-facing documentation explains the new behavior clearly
- the canonical truth boundary remains intact

---

## 14. Follow-on boundary

`1.1.0` should not be treated as the final word on AI-agent memory quality.

Likely follow-on themes after this milestone may include:

- stronger long-term summary lifecycle policy
- richer historical pattern mining
- more advanced interaction promotion heuristics
- broader operator quality scoring
- future derived-layer enhancements that remain subordinate to canonical truth

Those belong after the bounded `1.1.0` scope is closed.

---

## 15. One-line milestone summary

`ctxledger` `1.1.0` should improve how AI-agent work is structured, distilled,
linked, observed, and guided, starting with an explicit gap analysis against
`1.0.0` before implementing bounded runtime and `.rules` improvements.