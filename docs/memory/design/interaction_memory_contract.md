# Interaction Memory Contract

## Purpose

This note defines the bounded current contract direction for **interaction memory**
in `ctxledger`.

Interaction memory means durable records of:

- user requests to an AI agent
- agent responses back to the user

The goal is to make these interactions:

- durable across sessions
- queryable later
- reusable for resumability
- reusable for bounded historical progress recall
- reusable for failure-pattern avoidance

This contract is intentionally bounded.
It does **not** define a general conversational archive for every possible
message system.
It defines the minimum durable interaction-memory behavior needed for the
`0.9.0` product direction.

---

## Why interaction memory exists

`ctxledger` already stores meaningful canonical and derived state for:

- workflows
- attempts
- checkpoints
- verify reports
- episodes
- memory items
- summaries
- bounded search and retrieval

However, practical AI-agent work also depends on the **conversation layer**:

- what the user asked for
- how the agent interpreted the task
- what the agent answered
- what changed in the task understanding over time
- what file-touching intent was expressed
- what failure, blocker, or recovery guidance was discussed

If these interaction details remain only transient chat history, the system is
weaker at supporting:

- `resume`
- `continue`
- bounded questions like:
  - what did we decide yesterday?
  - what did I ask the agent to do about this topic?
  - what did the agent say was already complete?
- avoiding repeated failure patterns that were already discussed in prior
  interactions

Interaction memory is therefore intended to close the gap between:

- durable workflow state
- durable memory state
- real user-agent operating history

---

## Contract posture

Interaction memory should be read using these boundaries:

- workflow and checkpoint truth remain canonical in relational workflow tables
- interaction memory is durable and important, but it does **not** become a
  competing workflow-truth system
- interaction memory should support retrieval, recall, and explanation
- interaction memory may participate in vector-oriented search
- interaction memory may participate in bounded graph-linking or relation
  writing
- interaction memory should remain explicitly bounded and explainable

This means:

- interaction memory can support resumability
- interaction memory can support historical lookup
- interaction memory can support failure-pattern avoidance
- interaction memory should not silently redefine canonical workflow state

---

## What counts as interaction memory

At the current intended boundary, interaction memory includes:

### User-side interaction records

Examples:

- direct task requests
- clarification requests
- follow-up requests
- bounded historical questions
- resume / continue prompts
- user-provided acceptance criteria
- user-provided constraints
- user-provided correction or reprioritization

### Agent-side interaction records

Examples:

- task interpretation
- proposed next steps
- explicit status answers
- completion or blocker explanations
- historical-progress answers
- bounded recovery suggestions
- explicit rationale about failure causes or tradeoffs

---

## What does not count as interaction memory

Interaction memory should **not** be read as:

- raw indexing of all Git-managed file contents
- a second canonical workflow-status system
- a free-form unbounded chat archive with no durable contract
- a replacement for checkpoint summaries
- a replacement for verify reports
- a replacement for explicit memory items created for reusable knowledge

Interaction memory is one layer in the durable system, not the whole system.

---

## Core product roles of interaction memory

Interaction memory exists to support four bounded product roles.

## 1. Resumability support

Interaction memory should help recover:

- what the user most recently wanted
- what the agent believed it was doing
- what the latest bounded next step was
- whether a recent interaction was a detour or mainline continuation hint

## 2. Historical progress recall

Interaction memory should help answer bounded questions such as:

- what did the user ask about this topic yesterday?
- what did the agent say was already completed?
- what did the agent say remained?
- what did the user ask to continue?

## 3. Failure-pattern avoidance

Interaction memory should help surface:

- previously discussed blockers
- previously discussed bad patterns
- previously suggested recovery paths
- prior user corrections to agent behavior

## 4. File-work intent recall

Interaction memory should help preserve:

- what file the user wanted changed
- what the purpose of changing that file was
- what the agent said the change would do

This is especially important because the file content itself does not need to be
a memory-search target for the bounded current milestone.

---

## Canonical boundary

Interaction memory should always be interpreted relative to canonical workflow
state.

### Canonical first

Canonical truth remains:

- workspaces
- workflow instances
- attempts
- checkpoints
- verify reports
- canonical summary rows
- canonical summary-membership rows

### Derived or supportive interaction reading

Interaction memory should be read as:

- durable
- queryable
- retrieval-relevant
- explanation-relevant
- resumability-relevant

but still subordinate to canonical workflow truth for questions like:

- which workflow is actually running
- what checkpoint was actually recorded
- what verify status was actually persisted

If interaction memory and canonical workflow state disagree, the canonical
workflow system-of-record wins.

---

## Minimum durable record shape

Each interaction-memory record should be able to preserve, at minimum, enough
information to answer:

- who said what
- when it was said
- how it relates to workflow or task context
- whether it is useful for later search/retrieval

A bounded minimum record should support fields equivalent to:

- `interaction_memory_id`
- `interaction_role`
  - `user`
  - `agent`
- `content`
- `created_at`
- optional `workspace_id`
- optional `workflow_instance_id`
- optional `attempt_id`
- optional `checkpoint_id`
- optional `ticket_id`
- optional structured metadata

The exact storage model may evolve, but the durable contract should preserve
that minimum reading.

---

## Required metadata themes

The current bounded contract should preserve the ability to attach metadata such
as:

- request kind
- response kind
- topic or keyword hints
- file-work intent
- touched file names or paths
- status intent
  - for example:
    - ask_resume
    - ask_progress
    - answer_progress
    - answer_blocker
- bounded historical anchor hints
  - for example:
    - relative day reference
    - ticket-like reference
    - workflow-like reference
- failure or recovery hints
- relation candidates for later linking

These metadata themes should be treated as contract-important because they
support later retrieval and interpretation.

---

## File-work metadata boundary

Interaction memory often includes file-touching intent.

At the current bounded contract, it is valid and desirable to preserve metadata
such as:

- file names
- file paths
- file purpose
- create-vs-modify intent
- grouped file-touching objective

This should **not** be interpreted as requiring indexing of the Git-managed file
contents themselves.

The intended current reading is:

- file contents may remain outside interaction-memory search scope
- file-work metadata should still be durable and searchable

Examples of valid interaction-memory metadata:

- `target_file_paths`
- `target_file_names`
- `file_edit_purpose`
- `file_create_purpose`
- `file_modify_purpose`

These may later be normalized into separate memory-item or relation structures,
but the interaction-memory contract should preserve them from the start.

---

## Searchability contract

Interaction memory should be retrievable through at least two bounded support
paths.

## 1. Vector-searchable path

Interaction memory should be representable in embedding-searchable form so that:

- user requests can be found by semantic similarity
- prior agent responses can be found by semantic similarity
- closely related prior discussions can help bounded recall

This does **not** require promising perfect conversational semantic search.
It means interaction memory should be eligible for the same bounded vector-backed
retrieval foundations used elsewhere in the system.

## 2. Graph-linkable path

Interaction memory should be eligible for bounded graph-linking or relation
writing where useful.

Examples of bounded relation candidates:

- interaction supports workflow objective
- interaction clarifies checkpoint intent
- interaction references prior failure
- interaction explains file-work purpose
- agent response answers user request

The contract does not require a broad graph ontology.
It only requires that interaction memory is **not excluded** from bounded graph
or relation use.

---

## Interaction memory and resumability

Interaction memory should contribute to resumability, but carefully.

It can help answer:

- what did the user most recently ask for?
- what did the agent think the task was?
- what was the last discussed next step?
- was the most recent interaction likely a detour?

It should not alone decide:

- the canonical running workflow
- the canonical latest checkpoint
- the canonical verify state

The intended bounded behavior is:

- canonical workflow/checkpoint state provides the durable operational frame
- interaction memory sharpens interpretation and recovery of user intent inside
  that frame

---

## Interaction memory and historical progress questions

Interaction memory should help answer bounded historical progress questions such
as:

- what did the user ask yesterday?
- what did the agent say was complete?
- what did the agent say remained?
- what explanation was given for a blocker?

The intended current answer model is:

- combine canonical workflow and checkpoint state first
- use interaction memory to improve:
  - user-intent recovery
  - answer phrasing recovery
  - bounded historical narrative reconstruction

This means interaction memory is a historical-recall support layer, not a
replacement for canonical progress records.

---

## Interaction memory and failure reuse

Interaction memory is especially useful when failure information is discussed but
not fully represented by workflow tables alone.

Examples:

- the user warns the agent not to repeat a previous mistake
- the agent explains a prior failure pattern
- the user explains why a prior approach was wrong
- the agent suggests a workaround
- the user accepts or rejects that workaround

These records should be durably searchable later so failure-pattern avoidance is
not limited only to explicit structured failure rows.

The intended bounded contract is:

- structured failures remain important
- interaction memory complements them by preserving discussion-layer failure and
  recovery knowledge

---

## Relationship to explicit memory tools

Interaction memory should not make explicit durable memory tools obsolete.

The intended relationship is:

- interaction memory captures the user-agent conversation layer automatically
- explicit memory tools still capture:
  - high-signal durable lessons
  - reusable knowledge
  - deliberate episode creation
  - deliberate structured memory promotion

This distinction matters because not every interaction should automatically be
treated as a reusable durable lesson at the same strength as an explicit memory
record.

---

## Bounded privacy and scope reading

The current contract is about repository-local durable operating memory for
agent-assisted development work.

It should be read narrowly:

- interaction memory should be limited to what is materially useful for bounded
  resumability, recall, and failure avoidance
- the repository should avoid turning this into an indiscriminate archive of all
  surrounding context
- Git-managed file contents do not need to be interaction-memory targets

This is a bounded engineering-memory contract, not a universal conversation
retention policy.

---

## Expected client reading

A client or agent reading this contract should understand:

- interaction memory is durable
- interaction memory is searchable
- interaction memory is eligible for vector-backed retrieval
- interaction memory is eligible for bounded graph-linking
- interaction memory helps with resume, history questions, and failure avoidance
- canonical workflow and checkpoint truth still win when operational truth is in
  question
- file-work metadata is in scope
- file content indexing is not required

---

## Expected implementation boundaries for `0.9.0`

A bounded `0.9.0` implementation consistent with this contract should provide:

- automatic capture of user requests
- automatic capture of agent responses
- durable storage of interaction records
- retrieval eligibility for interaction records
- file-work metadata capture in interaction memory
- explicit docs and tests for the contract
- no claim that every conversation feature or file-content surface is now
  indexed

That is enough to satisfy the intended product direction without broadening the
milestone into a full archive or graph-redesign project.

---

## Summary

Interaction memory should be treated as a bounded durable-memory layer for:

- user requests
- agent responses
- file-work intent
- bounded failure/recovery discussion

It should support:

- vector-oriented search
- bounded graph-linking
- resumability
- historical progress recall
- failure-pattern avoidance

while preserving the core architectural rule:

- canonical workflow and checkpoint state remain relational and authoritative
- interaction memory remains durable and important, but supportive rather than a
  competing workflow-truth layer