# Hierarchical Memory 0.6.0 Plan

## 1. Purpose

This document defines the implementation plan for the `0.6.0` milestone.

The goal of `0.6.0` is to add **hierarchical memory retrieval** to `ctxledger` in a way that:

- preserves PostgreSQL as the canonical system of record
- adds graph-assisted retrieval support through Apache AGE
- improves `memory_get_context` beyond flat episode lookup
- introduces summary layers and relation-aware traversal incrementally
- remains testable, resumable, and operationally understandable

This milestone intentionally focuses on **making hierarchical retrieval work in ctxledger itself**.

It does **not** attempt to align implementation with Mnemis during `0.6.0`.

That comparison and possible architectural alignment belong to `0.7.0`.

---

## 2. Milestone intent

## 2.1 Primary objective

Implement a first working hierarchical memory system that can:

- represent memory relations explicitly
- support summary layering
- assemble context using more than one retrieval route
- improve `memory_get_context` with hierarchy-aware behavior
- use Apache AGE and Cypher where that helps relation-aware traversal

## 2.2 Non-objectives

`0.6.0` should **not** become:

- a general memory architecture rewrite
- a broad database platform migration
- a premature Mnemis reimplementation
- a feature pileup unrelated to hierarchical retrieval
- a full graph-native replacement for the existing PostgreSQL model

---

## 3. Architectural constraints

## 3.1 Canonical system of record

PostgreSQL remains the canonical source of truth.

This means:

- workflow state remains canonical in relational PostgreSQL tables
- memory records remain canonically persisted in PostgreSQL-managed storage
- resume artifacts remain derived
- graph structures introduced through Apache AGE must support retrieval, not replace canonical durability rules

## 3.2 AGE role

Apache AGE should be introduced as a **supporting graph layer** for hierarchical memory.

AGE is intended to help with:

- explicit node/edge modeling for memory relations
- top-down and relation-aware traversal
- hierarchy-aware selection paths
- future extensibility for richer graph retrieval

AGE is **not** intended to become a separate source of truth.

## 3.3 Scope boundary relative to Mnemis

Mnemis should be treated as a future comparison target, not as a `0.6.0` implementation template.

For `0.6.0`:

- do not redesign ctxledger around Mnemis terminology or assumptions
- do not optimize for paper parity
- do build primitives that are compatible with future comparison

For `0.7.0`:

- evaluate whether Mnemis-style dual-route retrieval should influence future design

Reference:
- `https://github.com/microsoft/Mnemis`

---

## 4. Why this milestone exists

Current memory behavior in `ctxledger` is strong in:

- episodic recording
- lexical and embedding-backed search
- workflow-aware contextual lookup
- durable persistence and observability

But current retrieval is still limited relative to long-term structured memory needs.

Missing or partial capabilities include:

- hierarchical summary layers
- relation-aware selection across memory units
- top-down retrieval over compressed semantic structures
- project-level memory organization beyond flat search and episode ordering
- deliberate traversal over meaningful memory abstractions

`0.6.0` addresses those gaps.

---

## 5. Desired product outcomes

By the end of `0.6.0`, `ctxledger` should be able to support a first meaningful form of:

- multi-layer memory organization
- hierarchical summary retrieval
- relation-aware memory assembly
- better `memory_get_context` output for broader, structured recall

The expected user-visible outcome is not “a graph database product.”

The expected outcome is:

- better memory retrieval quality
- better organization of long-term memory
- better context composition for agents
- stronger future foundation for more advanced reasoning-oriented retrieval

---

## 6. Guiding principles

## 6.1 Incremental over sweeping

Introduce hierarchy in layers.

Do not attempt to build the final memory architecture in one pass.

## 6.2 Behavior preservation outside the target area

Changes should be tightly scoped to memory and retrieval paths.

Do not casually alter unrelated workflow/runtime behavior.

## 6.3 Relational first, graph where justified

Keep canonical persistence simple and durable.

Use AGE only where graph traversal materially helps.

## 6.4 Operational clarity matters

Graph-assisted retrieval should remain understandable to operators and future developers.

Avoid “magic” retrieval behavior that cannot be explained or tested.

In practical terms, this also means retrieval contracts should expose enough metadata that a caller can understand:

- why context was returned
- which route produced it
- whether it is primary, auxiliary, compatibility, or convenience-oriented output
- how grouped structures and concrete items were assembled

## 6.5 Testability is mandatory

Every new retrieval layer should be testable in isolation and in integrated flows.

## 6.6 Avoid premature abstraction

Do not generalize every helper immediately.

Prefer stable domain-local helpers until repeated patterns are truly clear.

---

## 7. Key capability areas

## 7.1 Memory hierarchy representation

Introduce a minimal but useful hierarchy model.

Likely concepts:

- raw memory items
- summaries over groups of memory items
- summaries over summaries
- relation edges between memory objects
- links from workflow/episode context into hierarchy structures

## 7.2 Relation modeling

Support explicit memory relations such as:

- same episode
- derived from
- summarizes
- related topic
- same workflow
- same workspace
- possible temporal/causal adjacency

Not all relation types need to be implemented initially.

## 7.3 Retrieval routes

`0.6.0` should support at least two retrieval styles conceptually:

- direct lexical / semantic lookup
- hierarchy / relation-guided traversal

They do not need to be named after any external framework, but they should be separable in implementation and observable in results.

## 7.4 Context assembly

`memory_get_context` should evolve from simple episode selection into context assembly that can combine:

- selected episodes
- selected summaries
- selected memory items
- relation-derived supporting context

## 7.5 Retrieval contract explainability

As hierarchical retrieval is introduced incrementally, `memory_get_context` should become progressively more self-descriptive for downstream consumers and operators.

This means retrieval behavior should be observable not only through returned context objects, but also through additive metadata that explains:

- which retrieval routes participated
- whether a route contributed grouped structures and/or concrete items
- how many grouped structures a route contributed
- how many concrete items a route contributed
- which grouped scopes were involved
- how many grouped structures and concrete items appeared within each scope

This explainability layer is especially important while retrieval remains hybrid and transitional, because some outputs are primary structured surfaces while others remain compatibility or convenience surfaces.

## 7.6 Current grouped retrieval scopes

At the current `0.6.0` implementation stage, grouped retrieval output is expected to be understandable in terms of these scopes:

- `summary`
- `episode`
- `workspace`
- `relation`

These scopes do not imply final architecture lock-in, but they are a useful operational model for explaining current grouped output assembly.

## 7.7 Current retrieval route metadata direction

The current `0.6.0` retrieval-contract direction should favor additive metadata surfaces such as:

- retrieval routes present
- primary versus auxiliary retrieval routes
- per-route presence booleans
- per-route grouped-structure counts
- per-route item counts
- per-route scope counts
- per-route scope item counts
- per-route scopes present

This metadata should remain additive and descriptive. It should clarify behavior without forcing immediate redesign of storage-layer primitives.

## 7.8 Current related-context contract direction

At the current implementation stage, supports-derived related context should be treated as having:

- a dedicated relation-scoped auxiliary group in grouped output
- preserved compatibility outputs for older consumers
- preserved convenience outputs embedded in episode-local grouped structures where useful

The current contract direction is therefore:

- relation-scoped grouped output is the preferred primary structured surface for supports-derived related context
- per-episode related-context surfaces remain compatibility-oriented
- flat related-item output remains compatibility-oriented
- episode-local embedded related-item structures remain convenience-oriented

This distinction should help future work avoid ambiguity between:

- primary grouped retrieval structure
- compatibility response fields
- convenience projections for consumers that still expect older shapes

---

## 8. Apache AGE adoption plan

## 8.1 Why AGE is included

AGE is included in `0.6.0` to provide a path for:

- graph-backed relation storage
- Cypher queries for hierarchical traversal
- future expansion without forcing awkward relational-only traversals

## 8.2 Minimum AGE adoption target

The minimum successful use of AGE in `0.6.0` is not “full graph platform conversion.”

It is:

- AGE installed and usable in development/test environments
- at least one graph-backed memory relation model available
- at least one retrieval path using Cypher for hierarchical or relation-aware traversal
- clear boundaries between canonical relational data and graph-assisted retrieval structures

## 8.3 AGE design constraints

AGE usage should be:

- additive
- optional at the implementation-layer boundary if feasible
- shielded by repository/service abstractions
- observable enough that failures can be diagnosed

## 8.4 AGE operational questions to answer

Before implementation expands, answer:

- how AGE is provisioned locally
- how AGE is provisioned in Docker/dev environments
- how schema setup should initialize AGE objects
- how AGE-backed graph objects map to canonical relational IDs
- how to test AGE-dependent behavior
- what happens if AGE is unavailable

---

## 9. Data model direction

## 9.1 Canonical relational entities likely to remain

These likely remain relational and canonical:

- workspaces
- workflow instances
- attempts
- checkpoints
- verify reports
- episodes
- memory items
- memory embeddings
- projection states/failures

## 9.2 New likely concepts for `0.6.0`

Potential additions:

- memory summaries
- hierarchical summary nodes
- explicit summary membership mappings
- memory relation edges
- graph node/edge identifiers tied back to canonical relational records
- retrieval trace metadata

## 9.3 Relationship between relational and graph layers

Likely pattern:

- relational tables store canonical memory entities and summary entities
- AGE graph nodes/edges mirror or reference those entities for traversal
- graph structures are derived/supporting but still managed as part of the repository layer
- service logic decides when to use graph traversal vs direct lookup

---

## 10. Retrieval design direction

## 10.1 `memory_get_context` evolution

Current `memory_get_context` behavior is primarily workflow/episode-oriented.

`0.6.0` should evolve it toward:

- hierarchical selection
- summary-aware assembly
- relation-aware supporting context
- more explicit retrieval details

## 10.2 Expected request/response evolution

Likely additions in behavior, if not all at once:

- include summaries more meaningfully
- show relation-aware paths or provenance in details
- distinguish direct matches from hierarchy-derived selections
- report traversal or selection route metadata
- keep output explainable for debugging and future tuning

## 10.3 Minimum viable retrieval improvement

A minimally successful `0.6.0` does not need perfect global reasoning.

It does need to demonstrate at least one meaningful retrieval improvement such as:

- selecting a summary layer first, then drilling down
- traversing memory relations to gather relevant support
- returning both compressed and detailed context in one coherent response

---

## 11. Implementation phases

## 11.1 Phase A: schema and infrastructure preparation

### Goals
- prepare PostgreSQL + AGE foundation
- define minimum canonical and graph-assisted storage needs
- reduce uncertainty before service work

### Tasks
- identify required relational schema changes
- determine AGE extension setup requirements
- update local/dev provisioning paths
- define how graph nodes/edges reference canonical entities
- document fallback and failure expectations

### Deliverables
- schema plan
- AGE setup approach
- storage boundary decision note

---

## 11.2 Phase B: minimal hierarchy model

### Goals
- introduce the smallest useful hierarchy primitives
- avoid premature complexity

### Tasks
- define summary entities and relationships
- define summary-to-item and summary-to-summary links
- introduce minimal write/read repository interfaces
- keep naming explicit and domain-local

### Deliverables
- first canonical hierarchy model
- first graph-backed relation representation where useful

---

## 11.3 Phase C: relation-aware repository support

### Goals
- make hierarchy and relation data queryable
- isolate AGE-specific logic behind repository boundaries

### Tasks
- add repository methods for:
  - creating relations
  - reading related memory objects
  - traversing summary hierarchies
  - retrieving children/parents
- implement at least one AGE-backed traversal path
- add in-memory or test-friendly equivalents where practical

### Deliverables
- tested repository interfaces for hierarchical and relation-aware access

---

## 11.4 Phase D: service-layer retrieval assembly

### Goals
- make hierarchical retrieval available through memory services
- evolve `memory_get_context` meaningfully

### Tasks
- define retrieval strategy ordering
- combine direct search and hierarchy-guided retrieval
- add summary-aware context assembly
- add explicit detail/provenance metadata to responses
- ensure behavior remains debuggable and explainable

### Deliverables
- first integrated hierarchical `memory_get_context` behavior

---

## 11.5 Phase E: validation and refinement

### Goals
- prove the new retrieval is stable and useful
- avoid releasing a half-obscure system

### Tasks
- add focused tests for:
  - schema behavior
  - repository traversal
  - relation handling
  - summary selection
  - service-level context assembly
- rerun broader suites
- validate failure handling when graph support is absent or degraded
- review observability and operational messages

### Deliverables
- green focused tests
- green broader/full validation before closeout
- clear documentation of supported `0.6.0` behavior

---

## 12. Candidate implementation areas

## 12.1 Memory service layer
Likely files:
- `src/ctxledger/memory/service.py`
- `src/ctxledger/workflow/memory_bridge.py`

Potential work:
- hierarchy-aware retrieval assembly
- summary-aware response shaping
- relation-aware support gathering

## 12.2 Workflow service layer
Likely file:
- `src/ctxledger/workflow/service.py`

Potential work:
- integrating hierarchical memory into workflow-oriented context lookup semantics
- consistent validation and result shaping

## 12.3 Persistence layer
Likely files:
- `src/ctxledger/db/postgres.py`
- `src/ctxledger/db/__init__.py`

Potential work:
- AGE-backed graph support
- repository interfaces for hierarchy traversal
- in-memory parity where useful

## 12.4 MCP / HTTP response layers
Likely files:
- `src/ctxledger/runtime/server_responses.py`
- `src/ctxledger/runtime/http_handlers.py`
- `src/ctxledger/mcp/tool_handlers.py`
- `src/ctxledger/runtime/serializers.py`

Potential work:
- surfacing richer hierarchical retrieval details
- keeping response contracts understandable and testable

---

## 13. Risk management

## 13.1 Main risks

### AGE setup complexity
Adding AGE could create local/dev/test friction.

### Boundary confusion
Graph support may blur canonical vs derived responsibilities.

### Retrieval opacity
Hierarchy-aware retrieval may become difficult to explain or debug.

### Overbuilding
The milestone could drift into a research project rather than an implementation milestone.

### Test fragility
New retrieval routes may introduce weakly specified behavior.

## 13.2 Mitigations

- keep PostgreSQL canonical by rule
- adopt AGE incrementally
- hide graph specifics behind repositories/services
- make retrieval details explicit in responses
- add focused tests before broad expansion
- avoid pulling Mnemis-specific design goals into `0.6.0`

---

## 14. Validation strategy

## 14.1 Focused validation after each slice
Examples:

- repository tests after schema/repository changes
- memory tests after hierarchy selection changes
- MCP/HTTP tests after response contract changes

## 14.2 Broader validation after grouped changes
Examples:

- `tests/test_coverage_targets.py`
- memory and workflow-focused suites
- full pytest suite when the wave is substantial

## 14.3 Minimum closeout expectation for 0.6.0
Before declaring `0.6.0` complete:

- targeted tests for hierarchy and retrieval behavior should pass
- full suite should pass
- PostgreSQL canonical behavior should remain intact
- AGE-backed behavior should be documented clearly
- docs should distinguish:
  - what `0.6.0` implemented
  - what `0.7.0` will evaluate around Mnemis

---

## 15. Deliverables

A successful `0.6.0` should leave behind:

- a first working hierarchical memory implementation
- PostgreSQL canonical persistence preserved
- Apache AGE integrated as a supporting graph layer
- Cypher used where it materially improves hierarchical or relation-aware retrieval
- improved `memory_get_context`
- summary layering support
- relation-aware retrieval support
- clear tests and docs
- a clean handoff point for `0.7.0` Mnemis evaluation

---

## 16. Non-goals and anti-patterns

Avoid:

- replacing canonical relational persistence with graph-only storage
- pulling in Mnemis design constraints too early
- over-generalizing graph abstractions before they are proven useful
- building large generic utility layers just because multiple modules look similar
- adding graph complexity without a measurable retrieval benefit
- obscuring retrieval behavior behind clever but untestable heuristics

---

## 17. Suggested immediate next steps

1. update roadmap and continuation notes to mark `0.6.0` active
2. define the minimal hierarchical memory entity/relationship model
3. decide the first AGE-backed graph slice
4. identify the first `memory_get_context` hierarchical retrieval improvement
5. add focused tests before expanding scope
6. defer Mnemis comparison and alignment decisions to `0.7.0`
