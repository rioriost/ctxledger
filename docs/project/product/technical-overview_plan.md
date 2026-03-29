# Technical Overview Document Plan

## Purpose

This plan defines the scope, source policy, structure, and drafting approach for a new technical overview document for `ctxledger`.

The intended outcome is a repository-level technical reference that explains:

- the overall architecture of `ctxledger`
- the separation between workflow control and memory retrieval
- the multi-layer memory model
- the PostgreSQL technologies used by each layer
- the current data model shape, including relational and graph-oriented structures
- the current bounded retrieval model exposed through the MCP-facing runtime

The document should help a reader understand the current implemented system, not only the historical design direction.

---

## Proposed target document

Recommended target file:

- `docs/project/product/technical-overview.md`

Recommended title:

- `ctxledger Technical Overview`

---

## Intended audience

Primary readers:

- engineers new to the repository
- contributors working on workflow, memory, retrieval, or runtime code
- operators or maintainers who need to understand the current architectural posture
- readers comparing canonical relational state, vector retrieval support, and AGE-backed graph support

Secondary readers:

- AI-agent platform integrators
- reviewers who need a concise explanation of what is implemented now
- release or architecture reviewers validating current repository behavior

---

## Documentation policy and source-of-truth rule

The overview should be informed by the documentation under `docs/`, but it must remain consistent with the codebase and schema.

The source policy for the final document is:

1. use current docs to discover intended architecture, terminology, and design boundaries
2. validate implementation-facing claims against code and schema
3. prefer the code and schema when docs and implementation diverge
4. describe implemented behavior rather than stale design intent
5. label optional, derived, bounded, or historical elements explicitly

This means:

- `docs/` is the primary narrative source
- the codebase and `schemas/postgres.sql` are the correctness boundary
- historical design notes should not be treated as current behavior without implementation confirmation
- the technical overview must distinguish:
  - implemented behavior
  - derived or optional support layers
  - bounded current contracts
  - historical or superseded design records

Recommended wording to preserve in the final overview:

- canonical workflow and memory state lives in PostgreSQL
- workflow control and memory retrieval are separate
- repository projections are derived artifacts
- graph-backed support is derived, optional, and not canonical truth
- response shaping is not the same thing as a different retrieval algorithm

---

## Scope

The planned technical overview should cover the currently implemented repository posture through the completed `0.9.0` milestone line.

It should explain the current design and implementation of:

- overall runtime architecture
- workflow architecture
- multi-layer memory architecture
- relational persistence structure
- vector-backed retrieval support
- constrained graph-backed support
- MCP-facing tool and resource posture
- retrieval routes and grouped response shaping
- operator-facing technical characteristics that materially affect architecture understanding

It should not try to become:

- a full API reference
- a full operator runbook
- a release changelog
- a speculative future roadmap
- a full reproduction of every design record

Where deeper detail is needed, the overview should point to existing docs.

---

## Key questions the overview should answer

The final document should answer these questions clearly.

### Repository-wide architecture

- What is `ctxledger` at a system level?
- What are the major runtime components?
- What is the MCP-facing runtime shape?
- How do transport, application, domain, and infrastructure concerns relate?

### Canonical boundaries

- What is canonical truth?
- What is derived?
- What is auxiliary?
- Why are workflow state and memory retrieval intentionally separated?

### Workflow

- What are the workflow identity layers?
- What are the core workflow entities?
- How is resumability represented?
- Why is `workflow_resume` different from memory retrieval?

### Multi-layer memory

- What memory layers exist?
- What is the purpose of each layer?
- How do layers relate to each other?
- What current implementation shape exists for each layer?

### PostgreSQL technology map

- Which PostgreSQL mechanisms are used by which layer?
- Where are plain relational tables used?
- Where is `JSONB` used to preserve structured state and metadata?
- Where is `pgvector` used?
- Where does Apache AGE fit?
- What remains canonical versus derived inside the PostgreSQL environment?

### Retrieval

- How do `workflow_resume`, `memory_get_context`, and `memory_search` differ?
- What retrieval routes currently exist?
- What grouped scopes exist in `memory_get_context`?
- What does `primary_only` mean?

### Data model

- What are the key relational entities?
- How do workflow entities link to memory entities?
- What are the core summary and membership structures?
- What semantic relations exist?
- What graph shape is currently meaningful?

### Operational characteristics

- What technical choices matter operationally?
- How does shared pool ownership affect the runtime model?
- What observability surfaces matter for understanding the system?
- How should canonical summary metrics and derived graph posture metrics be interpreted?

---

## Source materials

The drafting work should start from the following current docs and schema.

### Primary product docs

- `docs/project/product/architecture.md`
- `docs/project/product/design-principles.md`
- `docs/project/product/workflow-model.md`
- `docs/project/product/memory-model.md`
- `docs/project/product/mcp-api.md`
- `docs/project/product/specification.md`
- `docs/project/product/roadmap.md`

### Memory design and contract docs

- `docs/memory/design/memory_get_context_service_contract.md`
- `docs/memory/design/minimal_hierarchy_schema_repository_design.md`
- `docs/memory/design/minimal_prompt_resume_contract.md`
- `docs/memory/design/interaction_memory_contract.md`
- `docs/memory/design/file_work_metadata_contract.md`
- `docs/memory/design/failure_reuse_contract.md`
- `docs/memory/design/optional_age_summary_mirroring_design.md`

### Memory decision and closeout docs

- `docs/memory/decisions/minimal_hierarchy_model_decision.md`
- `docs/memory/decisions/first_age_slice_boundary_decision.md`
- `docs/memory/decisions/summary_hierarchy_0_6_0_milestone_slice_closeout.md`

### Schema and implementation validation sources

- `schemas/postgres.sql`

The final overview should cite code-validated facts even when some source docs use older phrasing such as "future" or "planned" for capabilities that are now implemented.

---

## Code verification targets

Before drafting the final technical overview, implementation-facing claims should be validated against the current codebase and schema.

Verification targets should include at least the following.

### Workflow runtime and resume behavior

Confirm the current implementation shape of:

- `WorkflowService.resume_workflow(...)`
- workflow service construction and runtime bootstrap
- current serialized workflow resume shape
- current distinction between workflow operational state and memory retrieval state

### Memory service behavior

Confirm the current implementation shape of:

- `MemoryService`
- episode persistence
- memory item persistence
- summary persistence
- summary membership persistence
- relation persistence
- embedding support
- interaction-memory handling
- file-work metadata normalization or filtering
- current search and context retrieval entry points

### Retrieval contracts

Confirm the current implementation shape of:

- `memory_get_context`
- `memory_search`
- grouped scopes
- retrieval routes
- `primary_only`
- summary-first and auxiliary context shaping
- relation-support and graph-support boundaries where implemented

### Runtime and MCP surface

Confirm the currently implemented and repository-evidenced surface of:

- HTTP MCP at `/mcp`
- tool-oriented workflow operations
- tool-oriented memory operations
- workflow resources
- request/response shaping that materially affects architectural explanation

### Persistence and PostgreSQL support

Confirm the current schema for:

- workflow entities
- episodic entities
- memory items
- embeddings
- relations
- summaries
- summary memberships
- artifact metadata
- structured failures

Confirm the currently visible PostgreSQL technologies and patterns such as:

- `pgcrypto`
- `vector`
- `JSONB`
- relational foreign keys
- unique and partial indexes
- HNSW index usage for embeddings
- shared pool posture and transaction-scoped unit of work

### Divergence handling

If any source doc conflicts with the current code or schema:

- record the mismatch in draft notes
- prefer the code/schema in the overview
- avoid reproducing stale design-intent wording as if it were current fact

---

## Current implementation-aligned observations to preserve

These observations should inform the draft unless later code review disproves them.

### Canonical workflow and memory posture

- canonical workflow and memory records live in PostgreSQL
- workflow control and memory retrieval are intentionally separate
- repository artifacts and projections are derived rather than canonical

### Memory layers

- workflow state is the operational truth layer
- episodes are append-only episodic memory records linked to workflows and optionally attempts
- semantic/procedural memory is represented through `memory_items`, `memory_embeddings`, and `memory_relations`
- hierarchical memory is represented canonically through `memory_summaries` and `memory_summary_memberships`
- graph-backed support is bounded, derived, and not the canonical hierarchy owner

### PostgreSQL technology posture

- relational tables and foreign keys define the canonical persistence model
- `JSONB` is used for flexible structured metadata and checkpoint or detail payloads
- `pgvector` is used for embedding storage and vector similarity indexing
- an HNSW index is present for embedding similarity lookup
- Apache AGE should be described as derived graph support, not canonical truth
- the runtime uses a shared pooled PostgreSQL posture with transaction-scoped unit-of-work behavior

### Retrieval posture

- `workflow_resume` returns canonical operational state
- `memory_get_context` returns support context
- `memory_search` provides bounded search over memory
- `primary_only` is a response-shaping mode, not a different retrieval algorithm
- grouped context and retrieval-route metadata are part of the current technical shape

---

## Proposed outline for the final technical overview

## 1. Introduction

Purpose of the system and why it exists.

Content goals:

- define `ctxledger` as a durable workflow runtime with multi-layer memory
- explain that workflow and memory are related but not conflated
- set expectations for canonical versus derived data

## 2. Design principles and architectural boundaries

Summarize the governing principles.

Content goals:

- canonical state in PostgreSQL
- repository files are projections only
- workflow control and memory retrieval are separate
- durable execution over convenience
- MCP as the public interface

This section should also introduce:

- canonical
- derived
- auxiliary

as repository-wide terms.

## 3. System context and runtime architecture

Explain the whole system from outside in.

Content goals:

- MCP-compatible clients
- authenticated HTTP MCP path at `/mcp`
- runtime core
- PostgreSQL
- optional embedding providers
- operator-facing surfaces such as CLI and Grafana

This section should include the system context diagram.

## 4. Layered internal architecture

Explain internal architectural layers.

Content goals:

- transport layer
- application layer
- domain layer
- infrastructure layer
- cross-cutting concerns
- dependency direction

This section should include the internal layer diagram.

## 5. Canonical, derived, and auxiliary data model

Explain the critical boundaries.

Content goals:

- what is canonical
- what is derived
- what is auxiliary
- why resume and recall must not collapse into one concept

This section should explicitly compare:

- `workflow_resume`
- `memory_get_context`
- `memory_search`

## 6. Workflow architecture

Explain the workflow subsystem.

Content goals:

- identity layers
- core workflow entities
- lifecycle
- resumability
- checkpoints and verify reports
- current active-work policy where relevant

This section should include a workflow ER diagram.

## 7. Multi-layer memory architecture

Explain the memory model as layers.

Content goals:

- Layer 1: workflow state
- Layer 2: episodic memory
- Layer 3: semantic / procedural memory
- Layer 4: hierarchical memory

This section should also explain the flow across layers, such as:

- workflow and checkpoint activity
- episode formation
- memory-item persistence
- embeddings and relations
- summary creation
- grouped retrieval

This section should include the memory layer stack diagram.

## 8. Retrieval architecture

Explain how memory and workflow state are read.

Content goals:

- `workflow_resume` as operational truth
- `memory_get_context` as grouped support context
- `memory_search` as bounded search and retrieval support
- grouped scopes
- retrieval routes
- summary-first shaping
- `primary_only`
- auxiliary context behavior

This section should include a retrieval flow diagram.

## 9. PostgreSQL technology map

Explain layer-by-layer PostgreSQL usage.

Content goals:

- relational tables
- foreign keys
- unique constraints and partial indexes
- `JSONB`
- `pgvector`
- Apache AGE
- connection pooling and unit-of-work posture

Recommended presentation:

- one summary table that maps each conceptual layer to the PostgreSQL technologies used and whether they are canonical or derived

## 10. Relational data model

Explain the current relational entities.

Content goals:

- workflow tables
- episode tables
- memory item tables
- summary tables
- relation tables
- artifact and failure tables
- cross-links between workflow and memory

Recommended presentation:

- separate ER diagrams for workflow and memory
- optionally a compact cross-link diagram

## 11. Graph posture and AGE-backed support

Explain graph support carefully.

Content goals:

- AGE is optional, derived, and rebuildable
- canonical ownership stays relational
- graph mirroring should be described as support for bounded traversal or retrieval assistance
- graph state absence should not be described as canonical data loss

This section should include a minimal graph-structure diagram, such as:

- `memory_summary`
- `memory_item`
- summary membership edges
- semantic relation edges where current implementation justifies mention

## 12. Interaction, file-work, and failure-reuse memory

Explain the `0.9.0` strengthening work that materially affects technical understanding.

Content goals:

- interaction-memory capture role
- file-work metadata role
- failure reuse and recovery memory role
- why these are retrieval-ready but not competing workflow truth systems

## 13. Operational characteristics and observability

Explain the runtime traits that matter to engineers and operators.

Content goals:

- process-scoped shared PostgreSQL pool
- transaction-scoped unit of work
- HTTP runtime posture
- current operator-facing stats
- canonical summary metrics versus derived graph posture metrics
- what degraded graph posture does and does not imply

## 14. Boundaries and non-goals

Close with constraints that prevent architectural misreading.

Content goals:

- graph is not canonical truth
- memory retrieval is not workflow execution
- repository projections are not source of truth
- `primary_only` is not a separate retrieval algorithm
- bounded historical recall is not unconstrained universal QA

---

## Diagram plan

The final overview should include diagrams where they materially improve clarity.

### Diagram 1: system context

Purpose:

- show clients, runtime, PostgreSQL, vector support, graph support, and operator surfaces

Recommended elements:

- MCP client / AI agent
- HTTP `/mcp`
- `ctxledger` runtime
- PostgreSQL
- `pgvector`
- Apache AGE
- optional embedding providers
- CLI / Grafana / operator surfaces

### Diagram 2: internal layered architecture

Purpose:

- show transport, application, domain, and infrastructure layering

### Diagram 3: multi-layer memory stack

Purpose:

- show the four-layer memory model and the flow from workflow events to retrieval-ready structures

### Diagram 4: retrieval flow

Purpose:

- show the difference between:
  - workflow resume
  - grouped context retrieval
  - bounded memory search

### Diagram 5: workflow ER

Purpose:

- show workspace, workflow instance, attempt, checkpoint, and verify-report relations

### Diagram 6: memory ER

Purpose:

- show episodes, memory items, embeddings, relations, summaries, and memberships

### Diagram 7: graph structure

Purpose:

- show the bounded graph support posture and how summary or relation structures map into derived graph form

Recommended initial format:

- Mermaid if repository conventions permit
- otherwise plain Markdown tables plus ASCII or path-based diagram snippets in a follow-up

---

## Recommended data-model breakdown for diagrams

To keep the document readable, avoid putting every entity into one giant ER figure.

Recommended split:

### Workflow ER

- `workspaces`
- `workflow_instances`
- `workflow_attempts`
- `workflow_checkpoints`
- `verify_reports`

### Memory ER

- `episodes`
- `episode_events`
- `memory_items`
- `memory_embeddings`
- `memory_relations`
- `memory_summaries`
- `memory_summary_memberships`

### Support / linkage view

- `artifacts`
- `failures`
- workflow-to-episode links
- episode-to-memory links
- workspace-scoped memory links
- optional note on interaction and file-work metadata living in `metadata_json` or related memory-item structures where implemented

---

## Drafting order

Recommended authoring sequence:

1. confirm current implementation facts from code and schema
2. write the boundary sections first:
   - canonical vs derived vs auxiliary
   - workflow vs memory retrieval
3. write the system context and internal layering sections
4. write the workflow architecture section
5. write the multi-layer memory section
6. write the retrieval architecture section
7. write the PostgreSQL technology map
8. write the data model sections
9. add diagrams
10. perform a final code-alignment pass to remove stale wording

This order reduces the chance of importing outdated terminology from historical design notes.

---

## Open questions to resolve before drafting the final overview

These questions should be answered explicitly during the implementation-alignment pass.

1. How should embeddings be described in the overview?
   - as canonical persisted records in PostgreSQL
   - as retrieval-support data
   - or both, with clear distinction between persistence and truth posture

2. How broadly should Apache AGE be described?
   - only as bounded derived support
   - or with a slightly broader explanation of current graph-backed auxiliary retrieval where code confirms it

3. How much detail should the overview include for interaction memory, file-work metadata, and failure reuse?
   - short positioning only
   - or a dedicated subsection with examples

4. Which current MCP resources should be called out as implemented versus future-facing?

5. What diagram format is best for this repository?
   - Mermaid
   - Markdown tables plus prose
   - separate diagram docs under a subdirectory

6. Should the final overview include brief example payload fragments?
   - only if they materially clarify grouped retrieval or resume structure
   - otherwise link to API docs instead

---

## Acceptance criteria for the plan

This plan is successful if the resulting technical overview can:

- explain `ctxledger` at a system level without depending on release-history reading
- describe the current layered memory model accurately
- distinguish workflow truth from memory support context
- distinguish canonical relational ownership from derived vector or graph support
- show how PostgreSQL, `pgvector`, and AGE are each used
- include enough data-model detail that engineers can orient themselves quickly
- remain consistent with current code and schema even when older docs differ

---

## Expected deliverables after this plan

Primary deliverable:

- `docs/project/product/technical-overview.md`

Optional supporting deliverables if needed:

- diagram files under a future `docs/project/product/diagrams/` directory
- follow-up doc cleanup tasks where current docs are found to drift from implementation
- compact glossary additions if terms such as canonical, derived, auxiliary, summary-first, or primary-only need stricter normalization across docs

---

## Final writing rule

The final technical overview must describe the repository as it is implemented now.

If a design note, roadmap note, or historical doc conflicts with the code or schema, the overview must follow the code and schema and treat the stale doc as supporting context rather than source of truth.