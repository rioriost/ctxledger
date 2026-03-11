
# ctxledger: Durable Workflow Runtime with Multi-Layer Memory (MCP 2025-03-26)

## Overview
This project provides a **remote MCP server** implementing:

1. **Durable Workflow Control**
2. **Multi-layer Agent Memory**
3. **PostgreSQL-backed canonical state**
4. **MCP 2025-03-26 compatible interface**
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

Purpose:

- durable execution
- safe resume
- commit verification

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

Start workflow instance

---

workflow_checkpoint

Persist workflow checkpoint

---

workflow_resume

Return latest resumable state

---

workflow_complete

Mark workflow finished

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
