# Historical Progress Query Contract

## Purpose

This note defines the bounded current contract direction for **historical progress
queries** in `ctxledger`.

A historical progress query is a user-facing request that asks, in effect:

- what happened before?
- what was completed?
- what remained?
- what did the user ask for?
- what did the agent answer?
- what file-related work was being done?
- what was the relevant task state at a bounded time or keyword anchor?
- which prior episode should be recalled from a keyword or topic anchor even when
  the exact wording does not match?
- which older episode should outrank newer ones because its development impact is
  higher?

This contract is intentionally narrow.

It does **not** define a general natural-language analytics system over all
repository artifacts.
It defines the minimum bounded query behavior needed for `0.9.0` product goals
around:

- resumability
- bounded historical recall
- failure-pattern avoidance
- interaction-memory reuse

---

## Why this contract exists

`ctxledger` already stores durable state for:

- workflows
- attempts
- checkpoints
- verify reports
- episodes
- memory items
- summaries
- bounded search and task-recall details

That means the system is already stronger at **recording** work than many ad hoc
agent workflows.

However, users often need a different capability:

- not only “resume the latest workflow”
- but also “tell me what happened around this topic / time / task”

Representative examples include:

- what was completed yesterday?
- what happened for this keyword?
- where did we stop?
- what remains?
- what did I ask the agent to do yesterday?
- what did the agent say was already finished?
- what file was being edited for this purpose?
- which prior episode is most relevant to this topic even if the stored wording
  used a different phrase?
- which older episode still matters more because it had higher development
  impact?

Without an explicit contract, these questions can drift into one of two bad
shapes:

1. too weak
   - the system can store history but cannot answer useful bounded questions

2. too broad
   - the system starts implying a full general-purpose natural-language history
     oracle that it does not actually implement reliably

This contract exists to keep the system in the useful middle:
**bounded, explainable historical progress recall**.

---

## Core contract posture

Historical progress queries should be read using these rules:

- canonical workflow/checkpoint state remains primary
- historical answers may also use derived memory and interaction-memory layers
- the query path should be bounded and explainable
- the query path should preserve canonical-versus-derived boundaries
- the system should answer practical development-history questions without
  implying unconstrained conversational analytics

This means historical progress queries should be treated as:

- operationally useful
- bounded
- retrieval-backed
- explanation-backed
- graph-assisted where keyword/topic-to-episode linkage materially improves
  episodic recall
- weighting-aware so recency is not the only ranking factor
- RAG-assisted where model-mediated normalization is needed to absorb paraphrase,
  spelling variation, or semantically close wording

but **not** as a promise to answer arbitrary questions about all prior repository
state.

---

## Supported question classes

At the current intended boundary, historical progress queries should support
bounded combinations of the following anchors, and should be able to assemble
answers from those anchors in a way that is closer to human episodic recall than
to thin full-text matching.

### 1. Time anchor

Examples:

- yesterday
- today
- earlier this session
- the last completed workflow
- the latest checkpoint before the most recent detour

### 2. Keyword or topic anchor

Examples:

- a phrase from the user request
- a phrase from the agent response
- a phrase from a checkpoint summary
- a phrase from remembered work
- a bounded topic label or failure pattern
- a normalized topic phrase derived from variant wording
- a semantically close paraphrase that still points to the same episode cluster

### 3. Workflow or task anchor

Examples:

- workflow id
- ticket id
- current mainline task
- prior detour
- return target
- primary objective

### 4. File-work anchor

Examples:

- file name
- file path
- purpose of creating a file
- purpose of modifying a file

### 5. Failure / recovery anchor

Examples:

- blocker pattern
- prior failure summary
- prior workaround
- prior correction from the user

The supported class is therefore not “any history question”.
It is:

- **bounded historical progress questions over durable workflow and memory state,
  optionally narrowed by time, keywords, task identity, file-work metadata, and
  failure/recovery signals, and enriched by graph-backed keyword/topic-to-
  episode linkage, weighting, and RAG-assisted normalization where those
  improve bounded episodic recall**

---

## Unsupported or explicitly out-of-scope question classes

The following should currently be treated as outside the bounded contract unless
a later milestone explicitly widens the scope.

- broad unconstrained “tell me everything about yesterday”
- arbitrary analytics over all repository artifacts
- indexing or answering over all Git-managed file contents
- broad conversational QA over every prior message with no bounded retrieval
  explanation
- graph-first historical truth that ignores canonical workflow state
- exact semantic reconstruction of every nuanced conversational meaning from all
  prior sessions

This is important for product honesty.
The system should answer useful bounded questions well, not imply universal
historical omniscience.

---

## Canonical first, derived second

Historical progress answers should be assembled in this order.

## Step 1 — Canonical workflow and checkpoint state

Use canonical state first to answer questions like:

- which workflow was active?
- which checkpoint was latest?
- what next action was recorded?
- what verify status was recorded?
- what workflow status was recorded?

Canonical sources include:

- workflow instances
- attempts
- checkpoints
- verify reports

## Step 2 — Durable memory layers

Use durable memory layers to strengthen the answer with:

- episode summaries
- memory items
- summary-first retrieval
- interaction memory
- file-work metadata
- failure/recovery memory

## Step 2.5 — Graph-backed keyword/topic episodic recall and RAG-assisted normalization

When the question depends on a keyword or topic anchor, the bounded intended
reading should not stop at plain text matching.

Instead, the historical-progress path should be able to use:

- graph-backed keyword/topic-to-episode linkage or an equivalent bounded graph
  structure
- weighting over recency and development impact
- RAG-assisted normalization to absorb:
  - spelling variation
  - paraphrase
  - semantically close wording

This is important because human recall does not work as a simple full-text
filter.

A useful bounded historical-recall system should be able to surface:
- the newest relevant episode when recency dominates
- or an older episode when its development impact or structural relevance is
  stronger

## Step 3 — Derived explanation surfaces

Use derived explanation surfaces to explain:

- why this workflow or task was selected
- why this historical answer was assembled from these records
- whether the answer is mainline-oriented, detour-oriented, failure-oriented, or
  file-work-oriented
- whether the answer depends on primary grouped retrieval or compatibility views

This preserves the key boundary:

- canonical workflow truth remains canonical
- derived memory and explanation layers enrich historical recall without
  replacing canonical truth

---

## Interaction memory in historical progress queries

Historical progress queries should be able to use interaction memory.

Interaction memory means durable records of:

- user requests
- agent responses

This matters because some practical historical questions are better answered from
the conversation layer than from workflow rows alone.

Examples:

- what did I ask the agent to do yesterday?
- what did the agent say was complete?
- what did the agent say remained?
- what did we decide about a file change?

The intended reading is:

- canonical workflow state answers operational truth
- interaction memory improves recovery of intent, phrasing, and bounded history

Historical progress queries should therefore be able to include interaction
memory in the answer path where relevant.

---

## File-work metadata in historical progress queries

Historical progress queries should also be able to use file-work metadata.

This includes bounded metadata such as:

- file names
- file paths
- create purpose
- modify purpose

These file-work anchors may also participate in graph-linked episodic recall when
that is the clearest bounded way to connect:
- keyword/topic
- prior episode
- workflow/checkpoint context
- file-work purpose

Examples of supported questions:

- which file was being modified for this task?
- what was the purpose of editing this file?
- what work touched this file yesterday?

The intended boundary is explicit:

- file-work metadata is in scope
- Git-managed file contents themselves do **not** need to be indexed as part of
  this contract

That means a historical progress answer may say:

- we were modifying `foo.py` to add summary-build diagnostics

without requiring the system to index or search the full contents of `foo.py`.

---

## Failure and recovery knowledge in historical progress queries

Historical progress queries should also be able to use prior failure and recovery
signals.

Examples:

- what failed last time on this task?
- what workaround did we use?
- did we already hit this problem before?
- what did the agent or user say about this blocker?

This should draw from bounded durable sources such as:

- structured failures
- failure-oriented memory items
- interaction memory discussing failures or recoveries
- checkpoint or completion summaries mentioning blockers

This supports the broader product goal that the agent should be less likely to
repeat known bad patterns.

---

## Primary reading versus compatibility reading

Historical progress answers should prefer the current primary grouped memory
surface where applicable.

That means:

- `memory_context_groups` is the primary grouped hierarchy-aware surface
- route and selection metadata in `details` are the primary additive explanation
  surface
- keyword/topic-to-episode graph linkage, weighting, and RAG-assisted
  normalization should enrich that reading rather than replace it

Flatter compatibility-oriented or convenience-oriented fields may still be
useful, but they should not be treated as the strongest contract reading.

For clients that want the strongest current reading, the preferred order is:

1. canonical workflow/checkpoint state
2. `memory_context_groups`
3. top-level route / selection / retrieval metadata
4. compatibility-oriented flatter fields only when operationally helpful

This is especially important when `primary_only = true` is used.
In that mode, historical progress clients should expect the grouped primary
surface to remain available while flatter compatibility-oriented fields may be
omitted.

---

## The role of `primary_only`

`primary_only = true` should be read as a historical-progress-friendly shaping
mode for clients that want the grouped primary retrieval surface without flatter
compatibility projections.

At the current intended boundary:

- `primary_only = true` does **not** change the underlying retrieval algorithm
- it changes the response shape
- it preserves:
  - grouped primary retrieval output
  - route metadata
  - selection metadata
- it may omit flatter compatibility-oriented explainability fields

This is useful for historical progress clients that want:

- a smaller, clearer, grouped-first answer surface
- less dependency on convenience fields
- a stronger long-term client contract around primary grouped reading

---

## Required answer qualities

A historical progress answer should aim to satisfy these qualities.

## 1. Bounded

The answer should remain tied to explicit anchors such as:

- time
- keyword/topic
- workflow/task
- file-work metadata
- failure/recovery pattern

## 2. Explainable

The system should be able to explain, in bounded form:

- which records were used
- why those records were selected
- whether the answer was canonical-first and memory-enriched
- which retrieval route mattered

## 3. Canonical-first

If the answer depends on workflow progression, checkpoint state, or verify state,
canonical workflow/checkpoint records should be read first.

## 4. Durable

The answer should rely on durable state, not on ephemeral local notes as the
primary truth source.

## 5. Honest about uncertainty

If the bounded retrieval does not support a confident answer, the system should
remain explicit rather than over-claiming.

## 6. Weighting-aware

The answer should not behave as if the newest episode always wins.
It should be possible for an older episode to outrank a newer one when bounded
weighting indicates that its development impact or structural relevance is
higher.

## 7. Normalization-aware

The answer should not depend entirely on exact wording matches.
It should be possible for bounded RAG-assisted normalization to map:
- spelling variation
- paraphrase
- semantically close wording

onto the same intended topic or episode candidate set.

---

## Minimum answer composition model

A bounded historical progress answer should ideally be able to surface some mix
of the following elements:

- selected workflow or task context
- latest relevant checkpoint
- latest relevant checkpoint summary
- next intended action
- verify or completion state
- bounded interaction-memory snippets
- bounded file-work metadata
- bounded failure/recovery references
- explanation of why this answer was assembled from these records

Not every answer must include every element.
The contract only requires that the system has a bounded path to assemble useful
answers from those components where applicable.

---

## Example question interpretations

The contract should support interpretations like these.

### Example 1

Question:

- what was completed yesterday?

Intended reading:

- use time anchor
- prefer completed workflows and relevant completion memory
- surface canonical completion state first
- enrich with memory summaries and interaction memory if helpful

### Example 2

Question:

- what happened around “summary build”?

Intended reading:

- use keyword/topic anchor
- search memory and interaction memory for that topic
- use graph-backed keyword/topic-to-episode linkage where available
- use weighting so a higher-impact older episode can still outrank a newer lower-
  impact one
- use RAG-assisted normalization if the stored wording used a different but
  semantically close phrase
- connect findings back to workflows/checkpoints where possible
- explain which workflow or task thread those results came from

### Example 3

Question:

- where did we stop on the auth change?

Intended reading:

- use task/topic anchor
- recover likely workflow and latest relevant checkpoint
- surface next intended action and bounded detour/mainline context
- use interaction memory if the auth change was clarified in conversation

### Example 4

Question:

- what file were we editing for this fix?

Intended reading:

- use file-work metadata
- surface file path/name and edit purpose
- connect back to workflow/checkpoint or interaction-memory context
- do not require indexing of the file contents themselves

### Example 5

Question:

- did we already hit this failure before?

Intended reading:

- use failure/recovery anchor
- search structured failure and memory layers
- enrich with prior interaction memory discussing the failure
- allow semantically close failure phrasing to map to prior episode or failure
  candidates through bounded normalization
- surface prior workaround or recovery guidance if present

---

## Relationship to resume behavior

Historical progress queries and resume behavior are adjacent, but not identical.

Resume asks:

- what should I continue now?

Historical progress asks:

- what happened before?
- what was done?
- what remains?
- what did we say or decide?

The same durable state supports both, but the answer framing differs.

The intended `0.9.0` posture is:

- strengthen both together
- avoid making them separate disconnected systems
- preserve canonical workflow truth across both

---

## Relationship to explicit memory tools

Historical progress queries should not make explicit memory tools obsolete.

The intended division is:

- explicit memory tools capture deliberate high-signal reusable knowledge
- interaction memory captures the user-agent conversation layer automatically
- workflow/checkpoint state captures canonical operational truth
- historical progress queries read across those layers in a bounded way

This layered model is important.
It avoids overloading any one surface with every responsibility.

---

## Relationship to future work

This contract is meant to be strong enough for bounded `0.9.0` implementation,
but not the last word forever.

Later milestones may choose to expand:

- time-oriented retrieval sophistication
- question classes
- relation modeling
- interaction-memory summarization policy
- file-work metadata normalization
- ranking strategies

But those future changes should preserve the current principles:

- bounded
- explainable
- canonical-first
- durable
- honest about scope

---

## Summary

Historical progress queries in `ctxledger` should be treated as a bounded,
durable, explainable query layer over:

- canonical workflow/checkpoint state
- durable memory layers
- interaction memory
- file-work metadata
- failure/recovery knowledge

They should support practical questions like:

- what was completed yesterday?
- what happened around this keyword?
- where did we stop?
- what remains?
- what did the user ask?
- what did the agent answer?
- what file was being changed and why?
- did we already hit this failure before?

They should **not** be treated as a promise of unconstrained natural-language
analytics over all repository state.

This bounded contract is the intended product shape for `0.9.0`.