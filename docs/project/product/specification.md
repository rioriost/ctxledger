
# ctxledger: Durable Workflow Runtime with Multi-Layer Memory (MCP 2025-03-26)

## AI Execution Boundary

`ctxledger` distinguishes between two different AI-execution patterns and does not treat them as interchangeable.

### 1. Persistence-oriented AI work

This pattern is appropriate when AI model output is used to create or update durable stored state.

Representative examples include:

- generating embeddings for records that are already stored
- deriving summaries or classifications from stored records
- storing AI-produced output into:
  - another table
  - another column
  - another derived retrieval structure

This is the natural fit for PostgreSQL-side AI integration such as the `azure_ai` extension.

### 2. Interactive client-facing AI work

This pattern is appropriate when AI model output is returned directly to an MCP client as part of an immediate request/response interaction.

Representative examples include:

- generating a response that is returned directly to the caller
- serving low-latency AI-backed tool output without first materializing it into durable relational state
- producing transient inference output for immediate client consumption

This is **not** a natural fit for PostgreSQL-side `azure_ai` execution.

## Governing rule

`azure_ai` should be treated as a persistence-oriented / materialization-oriented execution path.

It is well suited for:

- embeddings for stored memory items
- AI-enriched derived records
- database-resident AI processing whose outputs are stored durably

It is not the preferred path for:

- direct interactive AI responses returned immediately to MCP clients
- request/response inference where the database is only an unnecessary hop

In large Azure deployments, both PostgreSQL-side AI and application-side AI may use the same Azure OpenAI deployment, but they serve different purposes:

- PostgreSQL-side AI:
  - persistence-oriented
  - derived-state generation
  - retrieval-support materialization
- application-side AI:
  - interactive
  - client-facing
  - immediate-response oriented

A further distinction matters inside retrieval behavior itself:

- **query-time semantic search used to retrieve stored memory**
  - can still be treated as persistence-oriented / retrieval-support work
  - even when a query embedding is generated at request time
  - because the purpose is to score against already materialized stored embeddings and return durable memory records more effectively
- **interactive AI generation returned directly to the client**
  - is not retrieval-support materialization
  - and should remain on the application-side interactive path

For large Azure deployments, this means PostgreSQL-side `azure_ai` may still be a reasonable fit for query-time semantic search when:

- the query embedding is generated only to compare against already stored embedding rows
- the operation is part of durable memory retrieval rather than free-form client-facing inference
- the response returned to the client is still fundamentally a retrieval result over stored canonical or derived records

By contrast, if the model output itself is the client-facing answer, the application-side path remains the preferred boundary.

Current bounded release-facing `0.8.0` review artifacts:

- `docs/project/releases/0.8.0_acceptance_review.md`
- `docs/project/releases/0.8.0_closeout.md`

## Current Operator Metrics

The current operator-facing stats surfaces also expose canonical-summary and derived-graph posture metrics.

Canonical summary volume metrics:

- `memory_summary_count`
- `memory_summary_membership_count`

Derived AGE graph posture metrics:

- `age_summary_graph_ready_count`
- `age_summary_graph_stale_count`
- `age_summary_graph_degraded_count`
- `age_summary_graph_unknown_count`

These should be interpreted in this order:

1. canonical relational summary volume first
2. derived graph posture second

A degraded, stale, or unknown graph posture should not be interpreted as canonical summary loss when the relational summary metrics still show canonical summary state.

## Overview
This project provides a **remote MCP server** implementing:

1. **Durable Workflow Control**
2. **Multi-layer Agent Memory**
3. **PostgreSQL-backed canonical state**
4. **[MCP 2025-03-26](https://modelcontextprotocol.io/specification/2025-03-26) compatible interface**
5. **FastAPI + uvicorn based HTTP runtime**
6. **Docker deployment**

The system is designed for AI agent editors (Zed and other MCP-compatible tools)
to reliably execute long-running development workflows with persistent memory.

---

# Architecture

## Core Components

### MCP Server
Responsibilities:

- Implements MCP 2025-03-26 protocol
- Exposes workflow and memory operations as MCP tools
- Exposes read-only data as MCP resources
- Manages workspace registry
- Orchestrates workflow execution state

Transport:

- Streamable HTTP
- FastAPI application wrapper served by `uvicorn` for the current remote HTTP runtime path

---

### PostgreSQL
Canonical data store for:

- workflow control state
- episodic memory
- semantic memory
- embeddings (pgvector)

---

### Docker Deployment

Recommended stack:

docker-compose

services:
  mcp-server
  postgres

Current local deployment/runtime shape:

- FastAPI application wrapper
- `uvicorn` process
- PostgreSQL container with persistent volume
- MCP HTTP endpoint exposed at `/mcp`

PostgreSQL volume persistence is required.

---

# Design Principles

1. **Canonical state lives in PostgreSQL**
2. **Repository files are projections only**
3. **Planning identity and execution identity are separate**
4. **Workflow control and memory retrieval are separate layers**
5. **Zed is treated as a client, not a platform dependency**

---

# Workflow Model

## Entities

Plan Layer:
- plan_id
- ticket_id

Execution Layer:
- workflow_instance_id

Operational Layer:
- attempt_id
- event_seq

---

## Execution Lifecycle

1. Workflow start
2. Attempt creation
3. Agent execution
4. Checkpoint
5. Verify
6. Commit or retry
7. Episode recording

---

# Memory Model

The system uses a **multi-layer memory architecture**.

The current `memory_get_context` contract also supports a response-shaping flag:

- `primary_only`

This flag should be read as a narrowing preference over the same retrieval behavior, not as a separate retrieval algorithm.
When `primary_only = true`, clients should expect the primary grouped hierarchy-aware surface and route metadata to remain available, while flatter compatibility-oriented explainability fields may be omitted.

## Layer 1 — Workflow Control

Tables:

- workspaces
- workflow_instances
- workflow_attempts
- workflow_checkpoints
- verify_reports
- projection_states
- projection_failures

Purpose:

- durable execution
- safe resume
- commit verification
- projection freshness visibility
- projection failure lifecycle tracking

---

## Layer 2 — Episodic Memory

Tables:

- episodes
- episode_events
- episode_summaries
- episode_failures
- episode_artifacts

Purpose:

- record past tasks
- store lessons learned
- enable future recall

---

## Layer 3 — Semantic / Procedural Memory

Tables:

- memory_items
- memory_embeddings
- memory_relations

Purpose:

- reusable knowledge
- repository-specific insights
- procedural guidance

Execution boundary for this layer:

- when embeddings or related derived retrieval data are being created from stored records, PostgreSQL-side AI execution is reasonable
- when AI output is meant to be returned directly to the MCP client without durable storage, application-side execution is the preferred boundary

This layer also includes a bounded query-time semantic-search concern.

That query-time concern should be read carefully:

- if the system generates a query embedding only so it can compare that query against already stored embeddings and rank stored memory records, the operation still belongs to retrieval-support behavior
- for large Azure deployments, PostgreSQL-side `azure_ai` can therefore still be a reasonable fit for this query-time semantic search path
- the reason is that the model call is still in service of retrieving durable stored memory, not producing an unconstrained client-facing AI answer

In other words:

- **stored derived memory structures**
  - good fit for PostgreSQL-side `azure_ai`
- **query-time semantic ranking over stored embeddings**
  - can also be a good fit for PostgreSQL-side `azure_ai` in large Azure deployments
- **direct client-visible AI responses**
  - better fit for application-side execution

---

## Layer 4 — Hierarchical Retrieval (Mnemis-inspired)

Features:

- hierarchical summaries
- relation graph
- semantic embedding search

Capabilities:

- retrieve relevant past work
- retrieve high-level project knowledge
- support long-context reasoning
- expose a grouped primary retrieval surface that can be consumed directly by clients using `primary_only = true`

Current interpretation rules:

## AI boundary note for future large Azure deployments

Future Azure-hosted large deployments may use Azure OpenAI from two different execution locations:

1. PostgreSQL-side, through `azure_ai`
2. application-side, through the runtime

Those two locations should be selected by purpose, not treated as interchangeable implementation details.

Use PostgreSQL-side AI when:

- the input is already stored in PostgreSQL
- the output should be stored durably
- the work is part of a derived retrieval or enrichment pipeline
- a query-time semantic-search step exists only to retrieve or rank stored durable memory more effectively

Use application-side AI when:

- the result is intended to be returned directly to the MCP client
- the interaction is request/response oriented
- adding a database execution hop would not improve correctness or durability
- the model output itself is the primary client-visible answer rather than a retrieval-support computation

This preserves the repository’s broader design rule:

- canonical truth remains PostgreSQL-backed
- derived AI-enriched stored structures can be materialized from PostgreSQL
- query-time semantic search over stored embeddings can still remain on the PostgreSQL-side retrieval-support path in large Azure deployments
- interactive client-facing AI behavior should not be forced through the database unless there is a clear architectural reason

- `memory_context_groups` is the primary grouped hierarchy-aware surface
- route and selection metadata in `details` should be treated as the primary additive explainability surface
- flatter compatibility-oriented fields remain supported, but they should be read as derived or compatibility views rather than as the strongest contract shape

---

# PostgreSQL Schema (Initial)

## workspaces

workspace_id
repo_url
canonical_path
default_branch
created_at

---

## workflow_instances

workflow_instance_id
workspace_id
ticket_id
status
created_at

---

## workflow_attempts

attempt_id
workflow_instance_id
status
started_at
finished_at

---

## workflow_checkpoints

checkpoint_id
workflow_instance_id
attempt_id
step_name
created_at

---

## verify_reports

verify_id
attempt_id
status
report_json
created_at

---

## projection_states

projection_state_id
workspace_id
workflow_instance_id
projection_type
target_path
status
last_successful_write_at
last_canonical_update_at

Representative projection statuses:

- fresh
- stale
- missing
- failed

---

## projection_failures

projection_failure_id
workspace_id
workflow_instance_id
attempt_id
projection_type
target_path
error_code
error_message
status
retry_count
occurred_at
resolved_at

Representative failure lifecycle states:

- open
- resolved
- ignored

Notes:

- projection file contents are derived artifacts and are not canonical
- projection failure metadata is canonical operational state
- repeated failures for the same projection type should remain visible as repeated records
- `retry_count` represents how many prior open failures already existed for the same projection stream before the current failure was recorded
- `occurred_at` is the timestamp when the individual projection failure record was created
- `resolved_at` is `NULL` while the failure record remains `open`
- `resolved_at` is set when an `open` failure transitions to either `resolved` or `ignored`
- `resolved_at` records closure time, not successful write time
- `ignored` uses the same `resolved_at` field as `resolved`; the distinction between the two closure modes is carried by `status`

---

# Memory Tables

## episodes

episode_id
workflow_instance_id
summary
created_at

---

## episode_failures

failure_id
episode_id
description
resolution

---

## memory_items

memory_id
type
content
created_at

---

## memory_embeddings

memory_id
embedding vector

(pgvector)

---

# MCP API

Target protocol version:

MCP 2025-03-26

---

## Tools

workspace_register

Registers repository workspace

---

workflow_start

Start workflow instance and create the initial running attempt

---

workflow_checkpoint

Persist workflow checkpoint and optional verification context

---

workflow_resume

Return latest resumable state assembled from canonical records

Representative response contents:

- workspace metadata
- workflow metadata
- active or latest attempt
- latest checkpoint
- latest verify report
- projection status
- warnings/issues
- resumable classification
- closed projection failure history

Representative projection-related warnings:

- stale projection
- open projection failure
- ignored projection failure
- resolved projection failure
- missing projection

Projection failure visibility rules:

- `open projection failure` should be emitted only when open projection failures exist
- `ignored projection failure` and `resolved projection failure` should be emitted only when closed projection failures exist
- `projection.status = failed` by itself does not necessarily imply an open unresolved failure
- a projection may remain `failed` even when `open_failure_count = 0`

Representative projection failure metadata exposed through resume:

- projection_type
- target_path
- attempt_id
- open_failure_count
- retry_count
- status
- occurred_at
- resolved_at
- error_code
- error_message

Representative closed projection failure history exposed through resume:

- `WorkflowResume.closed_projection_failures`
- closed failure records with:
  - `projection_type`
  - `target_path`
  - `attempt_id`
  - `error_code`
  - `error_message`
  - `occurred_at`
  - `resolved_at`
  - `open_failure_count`
  - `retry_count`
  - `status`

Dedicated HTTP read surface for closed projection failure history:

- `GET /workflow-resume/{workflow_instance_id}/closed-projection-failures`

Representative response contents:

- `workflow_instance_id`
- `closed_projection_failures`

Representative closed failure record fields:

- `projection_type`
- `target_path`
- `attempt_id`
- `error_code`
- `error_message`
- `occurred_at`
- `resolved_at`
- `open_failure_count`
- `retry_count`
- `status`

Behavior notes:

- this endpoint is a read-only assembled HTTP surface over canonical state
- it exposes closed failure lifecycle history only
- open projection failures remain visible through resume warnings and related resume projection diagnostics
- closed lifecycle records may be `resolved` or `ignored`

---

workflow_complete

Mark workflow finished with a terminal workflow status

Representative terminal outcomes:

- completed
- failed
- cancelled

---

memory_remember_episode

Store episode summary

---

memory_search

Semantic search over memory

---

memory_get_context

Retrieve relevant memory for agent

---

## Projection Failure Lifecycle Summary

Projection failure lifecycle is distinct from projection freshness status.

Representative lifecycle states:

- `open`
- `resolved`
- `ignored`

Meaning:

- `open`
  - projection write failed and the failure is still operationally active
- `resolved`
  - the failure is no longer open because successful reconciliation or explicit resolution occurred
- `ignored`
  - the failure is no longer open because the system or operator decided to stop treating it as an active unresolved issue

Important distinctions:

- projection status such as `failed` describes the projection artifact state
- failure lifecycle state describes whether failure records are still open
- `ignored` is not the same as successful projection recovery
- repeated failures should remain visible as repeated operational events rather than a single boolean flag

Representative retry behavior:

- first open failure for a projection stream: `retry_count = 0`
- second consecutive open failure for the same projection stream: `retry_count = 1`

---

# Resources

workspace://{workspace_id}/resume

Latest workflow resume information

---

workspace://{workspace_id}/workflow/{workflow_instance_id}

Workflow details

---

memory://episode/{episode_id}

Episode record

---

memory://summary/{scope}

Hierarchical summary

---

# Repository Projection

Repositories may contain:

.agent/resume.json

.agent/resume.md

These are **non-canonical projections** and can be regenerated from PostgreSQL.

---

# Security

Recommended:

- Reverse proxy
- Proxy-layer authentication
- TLS

---

# Implementation Phases

## Phase 1

PostgreSQL-backed workflow control

---

## Phase 2

Episodic memory

---

## Phase 3

Semantic memory + pgvector

---

## Phase 4

Hierarchical retrieval

---

# Goals

The system provides:

- durable agent workflow execution
- cross-session persistence
- multi-layer agent memory
- MCP-compatible remote service
