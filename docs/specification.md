
# ctxledger: Durable Workflow Runtime with Multi-Layer Memory (MCP 2025-03-26)

## Overview
This project provides a **remote MCP server** implementing:

1. **Durable Workflow Control**
2. **Multi-layer Agent Memory**
3. **PostgreSQL-backed canonical state**
4. **[MCP 2025-03-26](https://modelcontextprotocol.io/specification/2025-03-26) compatible interface**
5. **Docker deployment**

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

- Streamable HTTP (primary)
- stdio (development)

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
- Bearer token authentication
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
