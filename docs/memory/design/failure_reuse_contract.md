# Failure Reuse Contract

## Purpose

This note defines the bounded current contract direction for **failure reuse**
in `ctxledger`.

Failure reuse means making prior failures and their recoveries durable enough
that a later user or AI agent can:

- discover that a similar failure already happened
- understand why it mattered
- retrieve the recovery pattern or workaround that was used
- avoid repeating the same bad pattern

This contract is intentionally bounded.

It does **not** define a universal incident-management platform or a complete
autonomous policy engine.
It defines the minimum durable-failure-reuse behavior needed for the `0.9.0`
product direction around:

- resumability
- bounded historical progress recall
- automatic interaction memory
- failure-pattern avoidance

---

## Why failure reuse exists

`ctxledger` already has durable state for:

- workflows
- checkpoints
- verify reports
- failures
- episodes
- memory items
- summaries
- bounded retrieval and search

That is enough to persist evidence that something went wrong.

But simply **storing a failure** is not the same as **reusing failure knowledge**.

A system that wants agents to improve over time needs more than:

- a failure row existed

It needs enough structure to answer bounded practical questions like:

- have we hit this before?
- what was the root cause last time?
- what workaround did we use?
- did the user explicitly warn against this pattern?
- what recovery step succeeded?
- should the agent avoid retrying the same path?

Without that reuse layer, the system risks a weak pattern:

1. fail
2. persist failure
3. forget how to avoid it
4. fail again

Failure reuse exists to strengthen the path from:

- failure occurrence
- to durable capture
- to retrieval
- to later behavioral change

---

## Core contract posture

Failure reuse should be read using these rules:

- canonical workflow, checkpoint, and failure records remain the primary
  operational truth
- failure reuse is built on top of that canonical truth
- reusable failure knowledge may also live in memory items, summaries, and
  interaction memory
- failure reuse should be durable, searchable, and explainable
- failure reuse should help agents and users avoid repeating mistakes
- failure reuse should not silently replace canonical workflow truth

This means failure reuse is:

- canonical-record-informed
- memory-enriched
- retrieval-backed
- bounded
- operationally useful

It is **not** a separate truth system about workflow state.

---

## What counts as failure reuse

At the current intended boundary, failure reuse includes durable knowledge that
helps later work avoid or recover from a prior bad pattern.

Examples include:

- a structured failure record indicating what failed
- a memory item summarizing the failure or root cause
- a recovery note describing the successful workaround
- a user correction telling the agent not to repeat a known mistake
- an agent response explaining a recovery pattern
- interaction memory showing why a prior attempt was wrong
- a file-work metadata trail showing where a failure happened and why that file
  was touched

Failure reuse should therefore be read across multiple layers, not as a single
table or field.

---

## What does not count as failure reuse

Failure reuse should **not** be read as:

- simply having failures stored somewhere with no practical retrieval path
- broad indexing of all Git-managed file contents
- a complete future causal graph over every error in the repository
- an unconstrained “all prior mistakes” analytics engine
- a second workflow-status system
- a promise that every future failure will be automatically prevented

The contract is about bounded, reusable failure knowledge, not omniscient
prevention.

---

## Core product roles of failure reuse

Failure reuse exists to support four bounded product roles.

## 1. Repeated-failure avoidance

The system should make it easier to recognize:

- this looks like a known bad pattern
- we already tried this and it failed
- the user already corrected this approach
- a previous recovery path should be reused first

## 2. Resumability support

When resuming work, failure reuse should help answer:

- what blocked us last time?
- what was the latest recovery attempt?
- what should be avoided on resume?
- what known risk should be surfaced before continuing?

## 3. Historical explanation

Failure reuse should help answer bounded questions like:

- why did this task stall?
- what failed yesterday?
- what workaround did we use?
- what did the agent or user say about the failure?

## 4. File-work caution

Failure reuse should help preserve:

- which file or file group was involved in the failure
- why that file was touched
- what purpose was associated with the failed change
- what file-related pattern should not be repeated

This matters even when Git-managed file contents themselves are not indexed.

---

## Canonical boundary

Failure reuse should always be interpreted relative to canonical workflow truth.

### Canonical first

Canonical truth remains:

- workflow instances
- attempts
- checkpoints
- verify reports
- structured failures
- canonical summaries and memberships where relevant

### Derived and reusable failure reading

Failure reuse may additionally draw from:

- memory items
- episode summaries
- interaction memory
- file-work metadata
- bounded search and ranking signals

If a reusable failure explanation conflicts with canonical workflow truth, the
canonical workflow and failure records win.

The intended reading is:

- canonical failure and workflow records define what happened
- reusable memory and interaction layers help explain how to avoid repeating it

---

## Minimum durable record shape

A bounded failure-reuse implementation should preserve enough information to
recover:

- what failed
- where it failed
- when it failed
- why it mattered
- how it was recovered, if recovery happened
- what to avoid later

A minimum durable reusable failure shape should support fields equivalent to:

- `failure_id`
- `failure_scope`
- `failure_type`
- `summary`
- `status`
- `occurred_at`
- optional `resolved_at`
- optional `workflow_instance_id`
- optional `attempt_id`
- optional `checkpoint_id`
- optional recovery-oriented metadata
- optional file-work metadata
- optional interaction-memory links
- optional memory-item or summary links

The exact storage model may evolve, but the contract should preserve that
minimum reading.

---

## Required metadata themes

The current bounded contract should preserve metadata themes such as:

- failure pattern code or category
- root-cause hint
- recovery pattern
- retry recommendation
- avoid-again hint
- workflow or checkpoint anchor
- file path or file name involved
- file-edit purpose
- user correction hint
- agent recovery suggestion
- repeated-failure candidate hint
- relation candidates for later linking

These themes matter because they make later retrieval and behavioral shaping
possible.

---

## Failure reuse and interaction memory

Failure reuse should explicitly include interaction memory where useful.

This matters because many practically important failure signals are first
expressed in conversation, for example:

- the user says “don’t do that again”
- the user explains that a prior attempt already failed
- the agent explains why a pattern is unsafe
- the user narrows the correct recovery path
- the agent proposes a workaround and the user confirms it

These interaction records should be durably searchable later so the next agent
run does not have to rediscover them from scratch.

The intended reading is:

- structured failure records remain important
- interaction memory complements them by preserving discussion-layer failure and
  recovery knowledge

---

## Failure reuse and file-work metadata

Failure reuse should also preserve bounded file-work metadata.

At the intended boundary, this includes metadata such as:

- file names
- file paths
- create-vs-modify intent
- file-edit purpose
- reason the file was touched during the failed or recovered work

This supports bounded questions like:

- which file was involved in the last failure?
- what was the purpose of editing that file?
- which file-related change pattern failed before?

The intended boundary remains explicit:

- file-work metadata is in scope
- Git-managed file contents themselves do **not** need to be indexed for the
  failure-reuse contract

---

## Searchability contract

Failure reuse should be retrievable through at least two bounded support paths.

## 1. Vector-searchable path

Failure-related memory should be representable in embedding-searchable form so
that later users or agents can find:

- similar prior failures
- similar root causes
- similar recovery patterns
- similar warnings or cautions

This does **not** promise perfect semantic incident matching.
It means prior failure knowledge is eligible for bounded vector-backed search.

## 2. Graph-linkable path

Failure-related memory should also be eligible for bounded graph-linking or
relation writing where useful.

Examples of bounded relation candidates include:

- failure supports later caution
- recovery addresses prior failure
- interaction clarifies failure cause
- file-work metadata links to failure context
- agent response answers user concern about a failure

The contract does not require a broad future ontology.
It only requires that reusable failure knowledge is **not excluded** from
bounded relation and graph use.

---

## Repeated known failure reading

A bounded failure-reuse system should be able to distinguish, at least in
representative cases:

- fresh failure
- repeated known failure
- prior-known recovery path

This does not require full probabilistic incident clustering.
It requires enough durable structure and retrieval support that the system can
say, in effect:

- this appears similar to a previously observed failure
- here is the prior recovery or warning
- avoid blindly retrying the same path

That distinction is central to the product goal that agents should improve over
time rather than merely accumulate logs.

---

## Failure reuse and resumability

Failure reuse should directly support resume behavior.

When work is resumed, the system should ideally help surface:

- the latest blocker
- the prior failed approach
- the last known successful workaround
- the risk that a retry is repeating a known bad pattern
- the next safer action if one was previously identified

This is especially important for minimal prompts such as:

- `resume`
- `continue`
- `作業を再開`

The intended reading is:

- resumability is not only about finding the last checkpoint
- it is also about avoiding resuming into the same failure loop

---

## Failure reuse and historical progress queries

Failure reuse should also support bounded historical progress questions such as:

- what failed yesterday?
- why did this task stop?
- what workaround did we use last time?
- did we already hit this blocker?
- what did the user say about this failure?

The intended answer model is:

1. read canonical workflow/checkpoint/failure state first
2. enrich with reusable failure memory, interaction memory, and file-work
   metadata
3. preserve a bounded explanation of how the answer was assembled

This keeps the system useful without implying unconstrained retrospective QA.

---

## Primary versus compatibility surfaces

Failure reuse should prefer the repository’s current primary grouped reading
where applicable.

That means:

- canonical workflow and failure records are primary truth
- `memory_context_groups` remains the primary grouped memory surface
- top-level route and selection metadata remain the primary additive explanation
  surface

Flatter compatibility-oriented or convenience fields may still be useful, but
they should not be treated as the strongest contract reading.

For clients adopting grouped-primary reading:

1. canonical workflow / checkpoint / failure state first
2. grouped memory context surfaces
3. route and selection metadata
4. flatter compatibility fields only when operationally helpful

This same reading applies when a `primary_only` shaping mode is used for memory
context retrieval.

---

## Relationship to explicit memory tools

Failure reuse should not make explicit memory tools obsolete.

The intended division remains:

- structured failure records capture canonical failure metadata
- interaction memory captures discussion-layer failure and recovery knowledge
- explicit memory tools still capture deliberate, high-signal reusable lessons
- historical and resume retrieval reads across those layers in a bounded way

This prevents the contract from collapsing every failure-related concern into a
single storage surface.

---

## Bounded privacy and scope reading

The current contract is about repository-local durable memory for engineering
work.

It should be read narrowly:

- failure reuse should preserve what is materially useful for bounded
  resumability, recall, and avoidance
- it should not become an indiscriminate archive of every peripheral detail
- Git-managed file contents themselves do not need to be searchable here

This is a bounded engineering-memory contract, not a universal incident archive.

---

## Expected client reading

A client or agent reading this contract should understand:

- reusable failure knowledge is durable
- reusable failure knowledge is searchable
- reusable failure knowledge is eligible for vector-backed search
- reusable failure knowledge is eligible for bounded graph-linking
- reusable failure knowledge should help resume, historical recall, and
  repeated-failure avoidance
- canonical workflow and failure truth still win when operational truth is in
  question
- file-work metadata is in scope
- file-content indexing is not required

---

## Expected implementation boundaries for `0.9.0`

A bounded `0.9.0` implementation consistent with this contract should provide:

- durable retrieval-ready failure knowledge beyond raw failure storage alone
- bounded repeated-failure reuse behavior
- bounded recovery-pattern reuse behavior
- interaction-memory support for failure discussion
- file-work metadata support for failure context
- docs and tests for the contract
- no claim that every future failure will be prevented automatically

That is enough to satisfy the intended product direction without broadening the
milestone into a full incident-intelligence platform.

---

## Summary

Failure reuse in `ctxledger` should be treated as a bounded durable-memory layer
for:

- prior failures
- prior recoveries
- prior user corrections
- prior agent warnings or workaround explanations
- bounded file-work context tied to failures

It should support:

- vector-oriented search
- bounded graph-linking
- resumability
- historical progress recall
- repeated-failure avoidance

while preserving the core architectural rule:

- canonical workflow and failure state remain relational and authoritative
- reusable failure knowledge remains durable and important, but supportive rather
  than a competing workflow-truth layer

This is the intended bounded failure-reuse contract for `0.9.0`.