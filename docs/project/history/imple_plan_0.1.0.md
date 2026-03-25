# ctxledger Implementation Plan v0.1.0

## 1. Document Purpose

This document defines the implementation plan for `ctxledger` version `0.1.0`.

The goal of `v0.1.0` is to deliver the **minimum usable remote MCP server**
that provides:

- durable workflow control
- workspace registration
- PostgreSQL-backed canonical state
- basic MCP 2025-03-26 compatible tools
- Docker-based local deployment
- a foundation for later memory features

This plan is derived primarily from `docs/project/product/specification.md`, and aligned with the current repository state, including:

- Python packaging via `pyproject.toml`
- source layout under `src/ctxledger`
- PostgreSQL schema stub in `schemas/postgres.sql`
- Docker deployment stub in `docker/docker-compose.yml`
- roadmap targets in `docs/project/product/roadmap.md`

---

## 2. Scope of v0.1.0

### 2.1 In Scope

Version `0.1.0` should implement the following:

1. **Remote MCP server skeleton**
   - Streamable HTTP as the runtime mode

2. **Workflow control layer (Layer 1 only)**
   - workspace registration
   - workflow start
   - checkpoint creation
   - workflow resume
   - workflow complete

3. **Canonical persistence in PostgreSQL**
   - durable storage for workflow state
   - resumable execution state
   - verify report persistence
   - workspace metadata persistence

4. **Repository projection generation**
   - `.agent/resume.json`
   - optionally `.agent/resume.md`
   - clearly treated as non-canonical output

5. **Containerized development/deployment**
   - `docker compose up` should start PostgreSQL and the MCP server

6. **Operational baseline**
   - configuration loading
   - authentication hook points
   - health/readiness checks
   - structured logging

### 2.2 Explicitly Out of Scope

The following should **not** be fully implemented in `v0.1.0`:

- episodic memory persistence as a complete feature
- semantic search
- pgvector-based retrieval logic
- hierarchical memory retrieval
- advanced relation graph features
- background workers
- distributed orchestration
- multi-tenant access control beyond a simple auth boundary
- rich verification pipelines beyond minimal report recording

### 2.3 Partial/Preparatory Scope

These may be prepared structurally, but not fully delivered:

- `memory_remember_episode`
- `memory_search`
- `memory_get_context`

For `v0.1.0`, these should either:
- return a clear “not yet implemented” MCP error, or
- expose a stub implementation that does not claim production readiness.

---

## 3. Product Definition for v0.1.0

### 3.1 Primary Outcome

You should be able to run `ctxledger`, register a repository workspace, start a workflow, create checkpoints, retrieve resumable state, and complete the workflow with all canonical state stored in PostgreSQL.

### 3.2 Definition of “Done”

`v0.1.0` is done when all of the following are true:

- the server starts successfully in local development
- PostgreSQL-backed tables exist and are initialized
- MCP tools for workflow control are callable
- `workspace_register`, `workflow_start`, `workflow_checkpoint`, `workflow_resume`, and `workflow_complete` persist and return valid data
- resumable workflow state can be reconstructed from PostgreSQL after restart
- Docker-based local deployment works
- core API behavior is documented
- basic tests validate critical workflow paths

---

## 4. Architecture Alignment

### 4.1 Governing Principles

Implementation must preserve the project’s design principles:

1. **Canonical state lives in PostgreSQL**
2. **Repository files are projections only**
3. **Planning identity and execution identity are separate**
4. **Workflow control and memory retrieval are separate layers**
5. **MCP is the public interface**
6. **Durable execution is prioritized over convenience**

### 4.2 Layering for v0.1.0

Only the first layer is functionally complete:

- **Layer 1 — Workflow Control:** implemented
- **Layer 2 — Episodic Memory:** schema-prep only or deferred
- **Layer 3 — Semantic Memory:** deferred
- **Layer 4 — Hierarchical Retrieval:** deferred

### 4.3 Execution Identity Model

The implementation should preserve the identity hierarchy described in the specification:

- Plan layer:
  - `plan_id` (future)
  - `ticket_id`
- Execution layer:
  - `workflow_instance_id`
- Operational layer:
  - `attempt_id`
  - `event_seq` (recommended for future-proofing even if not fully used now)

For `v0.1.0`, `ticket_id`, `workflow_instance_id`, and `attempt_id` are essential.

---

## 5. Deliverables

### 5.1 Code Deliverables

Expected implementation areas:

- `src/ctxledger/config.py`
- `src/ctxledger/server.py`
- `src/ctxledger/workflow/service.py`
- `src/ctxledger/memory/service.py` as stub
- database bootstrap/migration support
- MCP transport wiring
- repository projection writer

### 5.2 Documentation Deliverables

Update or create:

- `README.md`
- `docs/project/product/mcp-api.md`
- `docs/operations/deployment/deployment.md`
- `docs/project/product/architecture.md`
- this file: `docs/project/history/imple_plan_0.1.0.md`

### 5.3 Infrastructure Deliverables

- `docker/docker-compose.yml` finalized for local use
- PostgreSQL schema initialization
- environment-variable configuration contract
- local startup instructions

---

## 6. Functional Plan

## 6.1 Workspace Registration

### Objective

Implement `workspace_register` so a repository workspace can be registered as a known execution target.

### Inputs

Recommended request fields:

- `repo_url`
- `canonical_path`
- `default_branch`

Optional future fields:

- `workspace_name`
- `metadata`

### Persistence

Insert a row into `workspaces` with:

- `workspace_id`
- `repo_url`
- `canonical_path`
- `default_branch`
- `created_at`

### Behavior

- if the workspace already exists by canonical path, return the existing record or perform idempotent upsert behavior
- validate required fields
- normalize path values where practical
- return `workspace_id` and persisted metadata

### Notes

This tool establishes the anchor for all workflow operations.

---

## 6.2 Workflow Start

### Objective

Implement `workflow_start` to create a durable workflow instance and its initial attempt.

### Inputs

Recommended fields:

- `workspace_id`
- `ticket_id`
- optional initial metadata
- optional operator/context notes

### Persistence

Create:

1. row in `workflow_instances`
2. initial row in `workflow_attempts`

Recommended initial states:

- workflow instance status: `running`
- workflow attempt status: `running`

### Response

Return at least:

- `workflow_instance_id`
- `attempt_id`
- `workspace_id`
- `ticket_id`
- `status`

### Notes

This operation defines execution identity. It must be durable and restart-safe.

---

## 6.3 Workflow Checkpoint

### Objective

Implement `workflow_checkpoint` to persist resumable workflow progress.

### Inputs

Recommended fields:

- `workflow_instance_id`
- `attempt_id`
- `step_name`
- optional structured checkpoint payload
- optional human-readable summary

### Persistence

Insert into `workflow_checkpoints`:

- `checkpoint_id`
- `workflow_instance_id`
- `attempt_id`
- `step_name`
- `created_at`

Recommended schema extension for practical use:

- `checkpoint_json JSONB`
- `summary TEXT`

### Behavior

- verify that the workflow/attempt pair is valid
- reject checkpoints for completed or terminal attempts unless explicitly allowed
- persist enough state to support `workflow_resume`

### Projection

After checkpoint creation, optionally regenerate:

- `.agent/resume.json`
- `.agent/resume.md`

These files must be projections from PostgreSQL, not a source of truth.

---

## 6.4 Workflow Resume

### Objective

Implement `workflow_resume` to return the latest resumable execution state.

### Inputs

Recommended fields:

- `workflow_instance_id`

Optional:

- `workspace_id`
- `include_projection`
- `include_verify_report`

### Resolution Logic

The tool should return:

- workflow instance metadata
- latest attempt
- latest checkpoint
- latest verify report if available
- current status
- enough data for an agent to continue safely

### Resource Mapping

This operation should also inform the resource:

- `workspace://{workspace_id}/resume`

and, where applicable:

- `workspace://{workspace_id}/workflow/{workflow_instance_id}`

### Notes

This is one of the most important operations in `v0.1.0`. It proves durable recovery.

---

## 6.5 Workflow Complete

### Objective

Implement `workflow_complete` to mark a workflow as terminal.

### Inputs

Recommended fields:

- `workflow_instance_id`
- `attempt_id`
- completion status
- optional final report
- optional verify result

### Persistence

Update:

- `workflow_attempts.status`
- `workflow_attempts.finished_at`
- `workflow_instances.status`

Optionally insert into:

- `verify_reports`

### Recommended Status Set

At minimum:

- `running`
- `completed`
- `failed`
- `cancelled`

### Notes

Even if verification is minimal in `v0.1.0`, the schema and service path should preserve room for commit/verify/retry behavior in later versions.

---

## 7. MCP API Plan

### 7.1 Protocol Goal

Target compatibility: **MCP 2025-03-26**

`v0.1.0` should focus on stable server behavior and correctly exposed tools/resources rather than broad feature completeness.

### 7.2 Tools to Implement

#### Required in v0.1.0

- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_resume`
- `workflow_complete`

#### Stub or Deferred

- `memory_remember_episode`
- `memory_search`
- `memory_get_context`

### 7.3 Resources to Implement

#### Required

- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`

#### Optional Stub

- `memory://episode/{episode_id}`
- `memory://summary/{scope}`

### 7.4 Error Model

Standardize MCP-visible errors for:

- invalid arguments
- unknown workspace
- unknown workflow instance
- invalid attempt reference
- invalid state transition
- unimplemented operation
- database unavailability

### 7.5 API Response Shape

Even if the internal server library influences exact shape, response bodies should be internally consistent and include:

- identifiers
- status
- timestamps
- machine-readable payload sections
- human-readable summary where helpful

---

## 8. Data Model Plan

## 8.1 Required Tables for v0.1.0

These must be concretely defined in `schemas/postgres.sql` or equivalent migration files:

### `workspaces`

Required columns:

- `workspace_id` UUID primary key
- `repo_url` TEXT
- `canonical_path` TEXT unique
- `default_branch` TEXT
- `created_at` TIMESTAMPTZ not null default now()

### `workflow_instances`

Required columns:

- `workflow_instance_id` UUID primary key
- `workspace_id` UUID references `workspaces`
- `ticket_id` TEXT not null
- `status` TEXT not null
- `created_at` TIMESTAMPTZ not null default now()

Recommended additions:

- `updated_at`
- `metadata_json JSONB`

### `workflow_attempts`

Required columns:

- `attempt_id` UUID primary key
- `workflow_instance_id` UUID references `workflow_instances`
- `status` TEXT not null
- `started_at` TIMESTAMPTZ not null default now()
- `finished_at` TIMESTAMPTZ null

Recommended additions:

- `attempt_number` INTEGER
- `failure_reason TEXT`
- `verify_status TEXT`

### `workflow_checkpoints`

Required columns:

- `checkpoint_id` UUID primary key
- `workflow_instance_id` UUID references `workflow_instances`
- `attempt_id` UUID references `workflow_attempts`
- `step_name` TEXT not null
- `created_at` TIMESTAMPTZ not null default now()

Recommended additions:

- `checkpoint_json JSONB`
- `summary TEXT`

### `verify_reports`

Required columns:

- `verify_id` UUID primary key
- `attempt_id` UUID references `workflow_attempts`
- `status` TEXT not null
- `report_json JSONB`
- `created_at` TIMESTAMPTZ not null default now()

## 8.2 Deferred Tables

These may exist in schema draft form but are not feature-complete in `v0.1.0`:

- `episodes`
- `episode_events`
- `episode_summaries`
- `episode_failures`
- `episode_artifacts`
- `memory_items`
- `memory_embeddings`
- `memory_relations`

## 8.3 Constraints and Indexes

At minimum, add indexes for:

- `workflow_instances(workspace_id, created_at desc)`
- `workflow_attempts(workflow_instance_id, started_at desc)`
- `workflow_checkpoints(workflow_instance_id, created_at desc)`
- `verify_reports(attempt_id, created_at desc)`

Also define:

- unique or idempotency-friendly constraint for workspace registration
- foreign keys with sensible delete behavior
- status checks where appropriate

---

## 9. Service Design Plan

## 9.1 `config.py`

### Responsibilities

- environment variable loading
- application settings object
- database connection settings
- server host/port settings
- proxy/auth-gateway integration expectations
- projection toggle/config
- log level

### Recommended Environment Variables

- `CTXLEDGER_DATABASE_URL`
- `CTXLEDGER_HOST`
- `CTXLEDGER_PORT`
- `CTXLEDGER_TRANSPORT`
- proxy-layer auth secret or gateway credential configuration
- `CTXLEDGER_ENABLE_HTTP`
- `CTXLEDGER_PROJECTION_ENABLED`

### Recommendation

Use a typed settings pattern so config validation happens at startup.

---

## 9.2 `server.py`

### Responsibilities

- initialize application
- connect MCP transport to tool handlers
- expose resources
- wire configuration and services
- expose health endpoints if framework permits
- manage startup/shutdown lifecycle

### Required Behavior

- fail fast on missing critical configuration
- establish database connectivity during startup
- register all `v0.1.0` tools/resources
- surface structured errors back to clients

---

## 9.3 `workflow/service.py`

### Responsibilities

- business logic for workspace/workflow operations
- transaction boundaries
- state transition validation
- resume-state assembly
- projection generation trigger

### Recommended Public Methods

- `register_workspace(...)`
- `start_workflow(...)`
- `create_checkpoint(...)`
- `resume_workflow(...)`
- `complete_workflow(...)`

### Design Guidance

Keep this module free from transport-specific concerns. It should be reusable from HTTP entry paths and any future transport boundary without embedding transport assumptions.

---

## 9.4 `memory/service.py`

### Responsibilities in v0.1.0

- provide placeholder structure for future memory features
- return explicit unsupported/unimplemented responses
- avoid pretending semantic retrieval already exists

### Reason

This keeps architecture aligned with the specification while preventing accidental scope creep.

---

## 10. PostgreSQL Implementation Plan

### 10.1 Migration Strategy

For `v0.1.0`, one of the following is acceptable:

1. a single bootstrap SQL file, or
2. a small migration framework if you want to invest early

Given the current repository state, a bootstrap SQL file is sufficient for `0.1.0`.

### 10.2 Recommended SQL Features

- `uuid` support via `pgcrypto` or application-generated UUIDs
- `jsonb` for checkpoint/report payloads
- timestamps with timezone
- explicit indexes
- optional `vector` extension preparation, but not required for active `0.1.0` features

### 10.3 Initialization Order

1. create extensions if needed
2. create workflow tables
3. create deferred memory tables
4. create indexes
5. optionally seed status enums/check tables if implemented

---

## 11. Repository Projection Plan

### 11.1 Principle

Projection files must be **derived artifacts** and never the source of truth.

### 11.2 Projection Targets

Recommended generated files inside a registered repository:

- `.agent/resume.json`
- `.agent/resume.md`

### 11.3 JSON Projection Content

Recommended fields:

- `workspace_id`
- `workflow_instance_id`
- `attempt_id`
- `ticket_id`
- `status`
- `latest_step`
- `checkpoint_created_at`
- `resume_summary`
- `verify_status`
- `updated_at`

### 11.4 Markdown Projection Content

Recommended content:

- workflow summary
- latest checkpoint
- current status
- verification summary
- instructions for the next agent step

### 11.5 Write Policy

Projection generation should be:

- optional/configurable
- best-effort
- non-fatal if the repository path is unavailable

Failure to write a projection must not invalidate canonical workflow persistence.

---

## 12. Deployment Plan

## 12.1 Docker Compose Outcome

`docker/docker-compose.yml` should support local boot with:

- `postgres` using a persistent volume
- `ctxledger` server container
- environment injection for DB connection and server settings

Historical note:
This section is part of the original `v0.1.0` implementation planning material.
It should not be read as the canonical description of the repository's current
operator-facing deployment posture.
For current deployment guidance, use:
- `README.md`
- `docs/operations/deployment/deployment.md`
- `docs/operations/security/SECURITY.md`

### 12.2 Recommended Compose Additions

- PostgreSQL port exposure for local debugging
- MCP server port exposure, likely `8080`
- volume for PostgreSQL data
- optional bind mount for local development
- startup ordering / healthcheck dependency if supported

Historical note:
The `8080` host-exposed MCP path described here reflects the planning posture at
the time this document was written.
It is not the current recommended public/operator-facing access path.

### 12.3 Container Runtime Goal

After startup, the documented MCP endpoint should be available at:

- `http://localhost:8080/mcp`

Historical note:
The endpoint above is preserved here as part of the original implementation
plan.
For the current repository state, treat this as historical planning context
rather than current operator guidance.
Refer to `README.md` and `docs/operations/deployment/deployment.md` for the current HTTPS-oriented
operator-facing path.

---

## 13. Security Plan

## 13.1 Minimum Security for v0.1.0

Implement at least:

- reverse-proxy or auth-gateway enforcement in front of non-private HTTP deployments
- configuration that supports proxy-layer secret or gateway credential management
- disabled-by-default or explicit-dev-mode behavior only for local development

## 13.2 Deferred Security

Postpone to later versions:

- full identity provider integration
- granular authorization
- audit-grade access logging
- advanced secret rotation

## 13.3 Reverse Proxy/TLS

Document as recommended production topology, even if not bundled in `0.1.0`.

---

## 14. Testing Plan

## 14.1 Test Priorities

There are currently no test files, so `v0.1.0` should introduce a basic test layer.

### Highest Priority Tests

1. workspace registration persists correctly
2. workflow start creates workflow instance and attempt
3. checkpoint creation persists resumable state
4. resume returns latest checkpoint after restart/reload
5. complete transitions workflow to terminal state
6. invalid transitions are rejected

## 14.2 Test Types

### Unit Tests

Target:

- service-layer state transitions
- config validation
- projection payload shaping

### Integration Tests

Target:

- PostgreSQL-backed persistence
- MCP tool invocation path
- end-to-end workflow lifecycle

### Smoke Tests

Target:

- server startup
- docker compose boot
- basic endpoint availability

## 14.3 Suggested Initial Matrix

- happy path workflow lifecycle
- unknown workspace/workflow IDs
- duplicate workspace registration
- checkpoint after completion
- resume with no checkpoint yet
- verify report attached on completion

---

## 15. Implementation Sequence

## Phase A — Foundation

1. finalize configuration model
2. choose MCP server/runtime library approach
3. define startup lifecycle
4. finalize directory/module responsibilities

## Phase B — Database Baseline

1. flesh out `schemas/postgres.sql`
2. add required columns, constraints, indexes
3. validate local Postgres bootstrap through Docker

## Phase C — Workflow Service

1. implement workspace registration
2. implement workflow start
3. implement checkpoint creation
4. implement resume assembly
5. implement completion flow

## Phase D — MCP Exposure

1. bind service methods to MCP tools
2. bind read-only resources
3. standardize error responses
4. validate HTTP operation

## Phase E — Projection and Ops

1. implement projection writer
2. add logging
3. add health/readiness behavior
4. add auth boundary

## Phase F — Test and Documentation Pass

1. add unit/integration tests
2. update README
3. update deployment/API docs
4. verify `docker compose up` flow

---

## 16. Risks and Mitigations

## 16.1 Risk: Over-scoping memory features

### Problem

The specification includes broad memory architecture, but the roadmap indicates `0.1` is focused on the workflow kernel.

### Mitigation

Keep memory services stubbed and focus delivery on Layer 1.

## 16.2 Risk: MCP transport complexity

### Problem

Keeping transport concerns broader than the HTTP runtime contract can expand implementation effort.

### Mitigation

Implement one shared application/service core and keep transport adapters thin.

## 16.3 Risk: Resume state under-specified

### Problem

A weak checkpoint model will make durable recovery unreliable.

### Mitigation

Add `JSONB` checkpoint payload support early, even in `0.1.0`.

## 16.4 Risk: Repository projection confusion

### Problem

Projection files may be mistaken for canonical state.

### Mitigation

Document clearly and enforce write-only projection behavior from persisted database state.

## 16.5 Risk: Empty current code skeleton

### Problem

Current Python modules appear to be placeholders.

### Mitigation

Treat `v0.1.0` as a foundational implementation milestone, not just a polishing release.

---

## 17. Acceptance Criteria

`v0.1.0` is acceptable when all items below are satisfied:

- `ctxledger` starts from local development configuration
- PostgreSQL schema initializes successfully
- Docker Compose starts `postgres` and `ctxledger`
- `workspace_register` works idempotently or predictably
- `workflow_start` creates durable records
- `workflow_checkpoint` persists latest resumable state
- `workflow_resume` reconstructs latest workflow state from PostgreSQL
- `workflow_complete` closes the workflow and stores final status
- repository projection can be generated from persisted state
- deferred memory tools do not misrepresent their readiness
- core tests exist and pass for the workflow lifecycle
- documentation explains how to run and use the system

---

## 18. Recommended Non-Goals for the First Merge

To keep delivery realistic, avoid delaying `0.1.0` for:

- perfect schema generality
- sophisticated retry orchestration
- complex event sourcing
- advanced verification agents
- full memory ingestion pipeline
- vector search integration
- production-grade multi-user auth

The first merge should prioritize a **correct, durable workflow kernel**.

---

## 19. Suggested Task Breakdown

### Task Group 1 — Bootstrap
- implement settings/config
- define server entrypoint
- wire package CLI entry

### Task Group 2 — Persistence
- finalize SQL schema
- add DB initialization path
- validate connectivity

### Task Group 3 — Workflow Domain
- workspace service
- workflow lifecycle service
- state validation rules

### Task Group 4 — MCP Interface
- tool registration
- resource registration
- error mapping

### Task Group 5 — Projection
- resume JSON writer
- resume Markdown writer

### Task Group 6 — Operations
- Docker Compose completion
- health checks
- logging
- proxy/auth boundary integration

### Task Group 7 — Quality
- unit tests
- integration tests
- docs updates

---

## 20. Final Recommendation

You should treat `ctxledger v0.1.0` as the **workflow kernel release**.

The most important success criterion is not breadth of features, but confidence in these guarantees:

- workflow state is durable
- restart/resume works
- PostgreSQL is the source of truth
- MCP is the stable interface
- the codebase is structured for memory features in later releases

If this version delivers a clean, durable Layer 1 with a credible extension path into episodic and semantic memory, it will satisfy both the specification and the roadmap.