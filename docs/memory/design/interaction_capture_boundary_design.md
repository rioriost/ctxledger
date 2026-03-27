# Interaction Capture Boundary Design

## Purpose

This note defines the bounded `0.9.0` design for **automatic interaction-memory
capture at the MCP and HTTP boundaries**.

The goal is to make user requests and agent responses durable enough to support:

- resumability from minimal prompts
- bounded historical progress recall
- failure-pattern reuse and avoidance
- file-work intent recall

This design is intentionally narrow.

It does **not** define:

- a universal chat archiving system
- a replacement for canonical workflow or checkpoint truth
- broad indexing of Git-managed file contents
- unconstrained capture of every transport detail

It defines the current intended capture boundary for `ctxledger`.

---

## Why this design exists

`ctxledger` already has durable workflow and memory primitives.

That means the system can persist:

- workflows
- attempts
- checkpoints
- verify reports
- episodes
- memory items
- summaries
- failures

However, one important product gap remains:

- user requests and agent responses can still be transient transport state

That weakens the system for `0.9.0` goals such as:

- a plain `resume` prompt
- historical questions like:
  - what did I ask yesterday?
  - what did the agent say remained?
- repeated-failure avoidance based on prior discussion
- file-work intent recall from prior conversations

The repository already treats durable state as the operating substrate.
This design closes the gap between:

- canonical workflow state
- durable memory state
- actual user-agent interaction history

---

## Core design posture

Interaction capture at the MCP and HTTP boundaries should follow these rules:

- capture should happen automatically
- capture should happen near the transport boundary
- capture should preserve a clear canonical-versus-derived boundary
- capture should be bounded and explainable
- capture should produce retrieval-ready durable memory
- capture should avoid turning transport logs into a second workflow-truth system

This means:

- workflow/checkpoint truth remains canonical in relational workflow tables
- captured interactions become durable memory support layers
- interaction capture is important, but subordinate to canonical workflow truth

---

## Boundary definition

At the current intended boundary, interaction capture should occur in two places.

### 1. MCP tool boundary

Capture should occur around MCP tool calls that represent meaningful user-agent
work.

This includes:

- user-side request capture from incoming `tools/call` payloads
- agent-side response capture from outgoing tool results

This boundary is important because many practical task instructions arrive
through tool invocation shape rather than free-form HTTP resources.

### 2. HTTP boundary

Capture should also occur around HTTP request/response paths that represent
agent-visible operational work.

This includes:

- HTTP MCP request bodies when they carry tool calls
- HTTP resource responses when they expose bounded operational state relevant to
  resumability or recall
- selected non-MCP HTTP endpoints only when they materially represent user-agent
  interaction state rather than operator-only transport mechanics

The HTTP boundary should not be read as permission to persist every low-level
HTTP event.

The intended scope is:

- meaningful interaction content
- not generic access logging

---

## Preferred capture architecture

The preferred `0.9.0` architecture is a **two-stage boundary capture path**.

### Stage 1 — Normalize interaction event at the boundary

At the MCP or HTTP boundary, normalize the interaction into a stable internal
shape.

That normalized event should distinguish:

- interaction direction
  - inbound user request
  - outbound agent response
- transport class
  - MCP tool call
  - MCP resource read
  - HTTP response surface
- interaction kind
  - resume request
  - historical query
  - workflow action
  - memory lookup
  - failure-related explanation
  - file-work request
- bounded workflow/task context if available

The goal of this stage is to avoid leaking raw transport-specific structure too
deeply into the memory layer.

### Stage 2 — Persist derived interaction memory

After normalization, persist the interaction as durable memory records.

That persistence path should:

- create durable interaction-memory records
- preserve enough metadata for later retrieval
- optionally link the interaction to:
  - workspace
  - workflow
  - attempt
  - checkpoint
  - ticket
  - failure context
  - file-work metadata

This should be implemented as a derived memory-writing path, not as a canonical
workflow-writing path.

---

## Canonical boundary

Interaction capture must preserve the canonical-first reading.

### Canonical truth remains

Canonical truth still lives in:

- workspaces
- workflow instances
- attempts
- checkpoints
- verify reports
- structured failures
- canonical summaries and memberships where relevant

### Captured interaction memory becomes

Captured interaction memory should be read as:

- durable
- retrieval-ready
- recall-relevant
- resumability-relevant
- failure-reuse-relevant
- file-work-intent-relevant

but **not** as the source of truth for:

- which workflow is running
- which checkpoint was recorded
- which verify status was persisted
- whether work is complete

If a captured interaction and canonical workflow data disagree, canonical state
wins.

---

## What should be captured

At the current intended boundary, the system should capture the following classes
of interaction content.

### User-side captures

- direct task requests
- resume / continue prompts
- clarification requests
- historical progress questions
- user corrections
- user reprioritization
- explicit constraints
- file-touching requests and intent

### Agent-side captures

- task interpretation
- proposed next steps
- bounded status answers
- historical-progress answers
- blocker explanations
- recovery suggestions
- rationale about failure causes
- file-work explanations

---

## What should not be captured as durable interaction memory

The bounded implementation should avoid treating the following as first-class
interaction memory unless a later milestone expands scope.

- generic transport diagnostics
- low-level auth headers
- raw bearer tokens
- TLS details
- generic health probes
- unrelated debug traffic
- every introspection payload by default
- full Git-managed file contents

This is a durable interaction-memory design, not an access-log sink.

---

## Minimum normalized event shape

Before persistence, a captured interaction should be normalizable into a shape
equivalent to:

- `interaction_role`
  - `user`
  - `agent`
- `interaction_direction`
  - `inbound`
  - `outbound`
- `transport`
  - `mcp`
  - `http`
- `interaction_kind`
- `content`
- `created_at`
- optional `workspace_id`
- optional `workflow_instance_id`
- optional `attempt_id`
- optional `checkpoint_id`
- optional `ticket_id`
- optional `metadata`

The exact implementation type may differ, but the design should preserve that
reading.

---

## Required metadata themes

The current bounded design should support metadata themes such as:

- request kind
- response kind
- MCP method name
- tool name
- resource URI
- historical-query anchor class
- resume prompt class
- failure or recovery hints
- file-work intent
- touched file names
- touched file paths
- selected-versus-latest explanation hints
- mainline-versus-detour explanation hints

This metadata should improve retrieval and explanation later without turning the
record into a raw transport dump.

---

## Recommended memory-item mapping

For `0.9.0`, the simplest practical mapping is:

- persist interaction content as memory items
- mark provenance distinctly as interaction-oriented
- keep the record queryable by existing search and context surfaces
- attach structured metadata for future narrowing and explanation

A bounded initial reading could use memory-item values such as:

- `type`
  - `interaction_request`
  - `interaction_response`
- `provenance`
  - `interaction`

This keeps interaction memory distinguishable from:

- `episode`
- checkpoint-derived memory
- workflow-completion-derived memory
- other future memory classes

---

## MCP capture design

### Capture points

The MCP path should capture at these points:

1. immediately after request parsing and validation is sufficient to identify
   the invoked method
2. after tool dispatch or resource dispatch returns a bounded result
3. after transport-visible error mapping, when the error itself is meaningful
   user-agent interaction state

### Methods in scope first

The highest-priority MCP captures for `0.9.0` are:

- `tools/call`
- `resources/read`

`tools/list` and `resources/list` are usually lower value for durable recall and
may remain out of scope initially unless the repository later decides they are
material.

### Tool-call capture reading

For `tools/call`, the durable capture should distinguish:

- user request content
  - tool name
  - arguments
  - bounded normalized intent
- agent response content
  - success or error result
  - bounded explanation content
  - retrieval-relevant details only

This is especially important for:

- `resume`
- workflow progression
- memory lookup
- failure explanation
- file-work intent

---

## HTTP capture design

### Capture points

The HTTP path should capture at these points:

1. after route resolution identifies a meaningful interaction surface
2. after response shaping determines the bounded response payload
3. after error mapping when the error is meaningful to later recall

### HTTP surfaces in scope first

Priority HTTP surfaces for the bounded slice should include:

- MCP-over-HTTP requests carrying `tools/call`
- workspace resume resource responses
- workflow resume responses where they materially express resumability state

Low-level routes such as health checks should remain out of scope by default.

### HTTP body posture

The HTTP boundary should capture **meaningful normalized content**, not a raw
verbatim dump of every request and response field.

That means the implementation should prefer:

- selected user-visible content
- selected derived explanation content
- selected identifiers and anchors

over:

- entire opaque payload archival by default

---

## Resume-specific capture guidance

Because `0.9.0` prioritizes minimal-prompt resumability, the boundary design
should treat resume-related interactions as high value.

Important capture themes include:

- the raw minimal prompt if present
  - `resume`
  - `continue`
  - `作業を再開`
- the selected continuation target
- the latest candidate considered
- selected-versus-latest explanation details
- mainline-versus-detour hints
- next intended action surfaced to the user

These records should help later answer:

- what did the user mean by resume here?
- why was this workflow selected?
- what was the next action at that point?

---

## Historical-query capture guidance

Historical questions are also high value for `0.9.0`.

The boundary capture should preserve enough signal to reconstruct:

- the query text
- the anchor class
  - time
  - keyword
  - workflow/task
  - file-work
  - failure/recovery
- the bounded answer returned
- the explanation posture used to assemble the answer

This should help later support:

- repeated historical lookup
- answer explainability
- failure-reuse enrichment
- recall of prior user phrasing

---

## Failure-reuse capture guidance

When an interaction includes failure or recovery content, the boundary path
should preserve metadata that helps later reuse.

Useful themes include:

- failure pattern label
- blocker summary
- root-cause hint
- workaround hint
- retry caution
- explicit user correction
- whether the response indicates fresh failure or repeated known failure

This should make interaction memory useful for:

- avoiding repeated mistakes
- surfacing prior recovery guidance
- explaining why a task previously stalled

---

## File-work metadata capture guidance

Interaction capture should preserve file-work intent without indexing file
contents.

Useful fields include:

- `file_name`
- `file_path`
- `file_operation`
  - `create`
  - `modify`
- `purpose`
- optional related workflow/checkpoint identifiers

This should be stored as metadata attached to interaction memory and be eligible
for later retrieval and linking.

The bounded design explicitly keeps the following out of scope:

- durable indexing of Git-managed file contents
- semantic retrieval over full file bodies by default

---

## Error capture posture

Not every error should become durable interaction memory.

Errors should be captured when they are meaningful to future work, such as:

- invalid resume target selection
- bounded workflow-not-found outcomes
- historical query narrowing failures
- failure or recovery explanations
- user-visible tool errors that shape later decisions

Errors that are mainly transport noise should generally stay out of durable
interaction memory.

Examples of likely out-of-scope error noise:

- malformed unrelated probes
- auth failures with sensitive details
- low-level internal debug traces not useful for later recall

---

## Privacy and safety posture

The boundary implementation should avoid durable capture of secrets and
sensitive transport material.

The design should therefore prefer:

- selected normalized content
- redaction of credentials or tokens
- omission of irrelevant headers
- omission of auth internals
- omission of raw file contents unless a later milestone explicitly changes scope

If content is not needed for resumability, bounded recall, failure reuse, or
file-work intent, it should usually not be persisted.

---

## Deduplication posture

The capture path should avoid obvious duplicate writes where one interaction
would otherwise be persisted multiple times in near-identical form.

Recommended bounded behavior:

- one durable request-side record per meaningful inbound interaction
- one durable response-side record per meaningful outbound interaction
- optional relation linking between request and response records
- avoid duplicating the same response at both transport and downstream layers
  unless each layer adds distinct bounded value

This matters especially when MCP is transported over HTTP.

The system should avoid creating:

- one HTTP request interaction record
- plus one identical MCP request interaction record

for the same semantic event unless the design intentionally distinguishes them.

---

## Relation-writing posture

Where useful, interaction records may participate in bounded relation writing.

Examples include links between:

- user request and agent response
- interaction memory and workflow/checkpoint context
- interaction memory and failure/recovery memory
- interaction memory and file-work metadata
- interaction memory and keyword/topic anchors

This should remain bounded and operational.
It is not a requirement for broad graph-native redesign.

---

## Implementation guidance for `0.9.0`

A practical bounded implementation order is:

1. define internal normalized interaction event helpers
2. add MCP `tools/call` request/response capture
3. add HTTP MCP transport-aware capture without duplicating the same semantic
   event twice
4. add resume-focused metadata shaping
5. add historical-query and failure/file-work metadata shaping
6. expose interaction provenance clearly in retrieval and observability surfaces
7. add focused validation for request capture, response capture, filtering, and
   retrieval posture

This keeps the first slice narrow and testable.

---

## Validation expectations

Focused validation for this design should cover at least:

- request-side MCP interaction capture
- response-side MCP interaction capture
- bounded HTTP interaction capture
- no accidental capture of irrelevant transport noise
- provenance distinction for interaction memory
- resume-related metadata capture
- historical-query metadata capture
- failure-related metadata capture
- file-work metadata capture
- retrieval visibility for captured interaction memory

Validation should also confirm the canonical boundary remains intact.

---

## Non-goals

This design is not intended to provide:

- a full transcript store for every possible conversation
- broad analytics across all raw HTTP traffic
- automatic canonical workflow mutation from interaction text alone
- broad Git file-content indexing
- unconstrained archival of debug and auth material
- a separate executable policy engine for `.rules`

---

## Intended end state

When this design is implemented strongly enough for the bounded milestone, the
repository should support this reading:

- meaningful user requests and agent responses are captured automatically at the
  MCP/HTTP boundary
- captured interactions become durable, retrieval-ready memory
- interaction memory supports resume, bounded historical recall, failure reuse,
  and file-work intent recall
- interaction capture remains canonical-second rather than becoming a competing
  workflow-truth system
- the repository keeps scope bounded and explainable

---

## Summary

The `0.9.0` interaction capture boundary should:

- capture meaningful user and agent interaction content automatically
- do so at MCP and HTTP boundaries
- normalize before persistence
- persist as derived durable interaction memory
- preserve workflow canonical truth boundaries
- support resume, bounded history, failure reuse, and file-work intent
- avoid broad raw transport archival and file-content indexing