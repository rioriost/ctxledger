# Workflow Model

## 1. Purpose

The workflow model defines how `ctxledger` represents, executes, persists, resumes, and terminates durable agent work.

This model separates:

- planning identity
- execution identity
- operational execution history
- resumable state snapshots

The workflow subsystem is designed so that:

- canonical workflow state lives in PostgreSQL
- execution can survive process restarts
- resume state can be reconstructed from canonical records
- future retry support can be added without redesigning core entities

---

## 2. Identity Layers

The workflow model distinguishes multiple identity layers.

### 2.1 Plan Layer

The plan layer represents user-facing or external planning identity.

Primary identifiers:

- `ticket_id`
- future `plan_id`

A `ticket_id` identifies the task or work request being executed.

### 2.2 Execution Layer

The execution layer represents one durable workflow record.

Primary identifier:

- `workflow_instance_id`

A `workflow_instance` is the canonical execution container for a single run of work associated with a workspace and ticket.

### 2.3 Operational Layer

The operational layer represents concrete execution attempts and resumable progress.

Primary identifiers:

- `attempt_id`
- `checkpoint_id`
- future `event_seq`

This layer records what actually happened during execution.

---

## 3. Core Entities

## 3.1 Workspace

A workflow always belongs to a registered workspace.

A workspace provides:

- canonical repository location
- source repository metadata
- default branch context
- scope for active workflow control

In `v0.1.0`, at most one active workflow may exist per workspace.

## 3.2 Workflow Instance

A `workflow_instance` is the durable execution record for one task run.

It represents:

- one execution scope for a given workspace
- one external task identity via `ticket_id`
- one lifecycle from start to terminal state
- zero or more attempts over time

A workflow instance is the top-level execution object used for resume and status inspection.

## 3.3 Workflow Attempt

A `workflow_attempt` represents one concrete execution try inside a workflow instance.

An attempt exists because:

- execution may fail
- execution may be cancelled
- future retry support requires multiple tries under one workflow

In `v0.1.0`, retry is structurally supported but remains minimal.  
The model still treats attempt as a first-class entity.

## 3.4 Workflow Checkpoint

A `workflow_checkpoint` is a resumable execution snapshot.

It is not only an event marker.  
It is intended to capture enough structured state to let a later agent safely continue work.

A checkpoint may include:

- current step name
- summary of completed work
- next intended action
- relevant files or artifacts
- verification context
- unresolved issues
- agent-facing resume instructions
- structured payload in `checkpoint_json`

## 3.5 Verify Report

A `verify_report` is a canonical operational evidence record attached to an attempt.

It records current verification status, such as:

- pending
- passed
- failed
- skipped

Verification is included in resume views, but in `v0.1.0` it is not yet a hard gate for workflow completion.

---

## 4. Hierarchy

The workflow hierarchy is:

Plan
 └ Ticket

Workspace
 └ Workflow Instance
    └ Attempt
       └ Checkpoint
       └ Verify Report

This hierarchy separates the user-facing task reference from actual runtime execution state.

---

## 5. Lifecycle Overview

The normal lifecycle is:

1. workspace registration
2. workflow start
3. initial attempt creation
4. agent execution
5. checkpoint creation
6. optional intermediate verification
7. further execution and additional checkpoints
8. termination as completed, failed, or cancelled
9. optional episode formation in the memory subsystem

This model prioritizes safe recovery over minimal record keeping.

---

## 6. State Machines

`workflow_instance` and `workflow_attempt` use separate state machines.

This separation is essential because workflow-wide outcome and per-attempt outcome are related but not identical.

## 6.1 Workflow Instance States

Allowed workflow instance states:

- `running`
- `completed`
- `failed`
- `cancelled`

### `running`
The workflow is active or operationally in progress.

This may mean:

- an active attempt is running
- the workflow has resumable progress and is not terminal

### `completed`
The workflow reached successful terminal completion.

### `failed`
The workflow reached terminal failure and is not being retried further.

### `cancelled`
The workflow was intentionally terminated by external/operator decision.

`cancelled` is terminal.

## 6.2 Workflow Attempt States

Allowed workflow attempt states:

- `running`
- `succeeded`
- `failed`
- `cancelled`

### `running`
The attempt is the current active execution try.

### `succeeded`
The attempt ended successfully.

### `failed`
The attempt ended unsuccessfully.

### `cancelled`
The attempt was intentionally terminated before normal completion.

`cancelled` is terminal.

---

## 7. State Mapping Rules

Typical end-state mapping is:

- workflow `completed` ↔ attempt `succeeded`
- workflow `failed` ↔ attempt `failed`
- workflow `cancelled` ↔ attempt `cancelled`

The system should not produce terminal workflow state and terminal attempt state combinations that contradict each other.

---

## 8. Active Workflow Policy

In `v0.1.0`, a workspace may have at most one active `running` workflow instance.

This rule exists to keep these behaviors unambiguous:

- workspace-scoped resume
- `.agent/resume.json`
- `.agent/resume.md`
- operator understanding of current active work

This invariant should be enforced primarily by the database, with application-level checks used for clearer user-facing errors.

---

## 9. Attempt Model and Retry Readiness

The workflow model is retry-capable even though `v0.1.0` keeps retry behavior minimal.

Rules:

- a workflow may own multiple attempts over time
- at most one attempt may be active at a time
- a new attempt may only be created after the previous active attempt becomes terminal
- attempts should be ordered using `attempt_number`

This allows future introduction of explicit retry operations without changing the core data model.

---

## 10. Checkpoint Semantics

A checkpoint is a durable resume snapshot.

It should support safe continuation by capturing the current execution situation, not just a label.

Recommended checkpoint fields include:

- `workflow_instance_id`
- `attempt_id`
- `step_name`
- `summary`
- `checkpoint_json`
- `created_at`

Recommended `checkpoint_json` contents include:

- current objective
- completed work summary
- next intended action
- relevant file references
- artifact references
- branch or commit context
- verify context
- unresolved risks
- agent-facing resume instructions

The latest checkpoint is the primary canonical input for workflow resume reconstruction.

---

## 11. Resume Model

`workflow_resume` should return a composite view assembled from canonical records.

It is not just the latest checkpoint row.

The resume view should combine:

- workspace metadata
- workflow instance metadata
- active or latest attempt
- latest checkpoint
- latest verify report
- projection status
- warnings or issues
- resumable classification

This makes resume a recovery interface, not just a status lookup.

---

## 12. Resumable Status

A workflow resume response may classify the state as:

- `resumable`
- `terminal`
- `blocked`
- `inconsistent`

### `resumable`
There is sufficient canonical state to continue safely.

### `terminal`
The workflow is already in a terminal state and is not to be resumed as active work.

### `blocked`
The workflow is not terminal, but continuation is not currently safe or possible without intervention.

### `inconsistent`
Canonical records exist but contain unexpected or conflicting state that requires inspection.

---

## 13. Partial Resume and Diagnostic Issues

Resume should return as much useful data as possible, even if the workflow state is imperfect.

Examples of diagnostic issues include:

- running workflow without active attempt
- running attempt without checkpoint
- missing verify context
- open projection failure
- stale projection
- workspace path unavailable

Hard failures such as unknown workflow, unknown workspace, or authentication failure remain request errors.  
Operational inconsistencies should instead be surfaced in the assembled resume view whenever possible.

## 13.1 Projection Failure Lifecycle in Resume

Projection failure tracking participates directly in the workflow resume model.

Projection failures should be treated as canonical operational metadata associated with a workflow, even though the projection files themselves are derived artifacts.

Representative projection failure lifecycle states are:

- `open`
- `resolved`
- `ignored`

### `open`

An `open` projection failure means:

- a projection write failed
- the failure is still considered operationally active
- resume should surface the failure as an unresolved issue

Repeated failures for the same projection type should remain visible as repeated failure records rather than collapsing immediately into a single boolean state.

### `resolved`

A projection failure becomes `resolved` when the system has sufficient evidence that the failure is no longer open.

In `v0.1.0`, the representative resolution path is:

- successful projection reconciliation for the same projection type
- closure of matching open projection failure records in canonical storage

Representative operational meaning:

- `resolved` should be used when the system has evidence of successful reconciliation, not merely because an operator wants the warning to disappear
- closing a failure as `resolved` records that the issue is no longer open due to recovery or equivalent successful closure semantics
- `resolved_at` should record when the failure stopped being open

### `ignored`

A projection failure becomes `ignored` when the system or operator decides that the failure should no longer be treated as an active unresolved issue.

Ignoring means:

- the failure history remains canonical
- the failure is no longer open
- resume should stop surfacing it as an `open projection failure`

Ignoring is not equivalent to successful projection recovery.  
It is a lifecycle transition for issue visibility and operational handling.

Representative operator-handling semantics:

- `ignored` should be used when an operator or higher-level workflow policy intentionally suppresses the failure as an active unresolved issue without claiming that the projection was successfully repaired
- this is appropriate for cases such as known-noncritical projection outputs, temporary operator acceptance, or policy-driven suppression of a projection write problem
- `ignored` should preserve historical failure details so later readers can distinguish operator closure from successful reconciliation
- `resolved_at` should still be recorded for ignored failures because the failure is no longer open, but lifecycle `status` must remain the source of truth for whether closure happened by recovery or by operator decision

## 13.2 Projection Failure Visibility Rules

Resume should distinguish projection status from projection failure lifecycle state.

Important consequences:

- a projection may still be `failed` even when no open projection failures remain
- `failed` projection status alone does not imply that an unresolved open failure still exists
- `open projection failure` warnings should be emitted only when open projection failures exist

Representative behavior:

- `projection.status = failed` and `open_failure_count > 0`
  - emit `open projection failure`
- `projection.status = failed` and `open_failure_count = 0`
  - do not emit `open projection failure`
  - emit either `ignored projection failure` or `resolved projection failure` when closed failure history exists
  - retain failed projection state for diagnosis
- `projection.status = fresh`
  - open projection failure warnings should not remain after successful reconciliation

Closed failure visibility should remain available in the assembled resume model even after failures are no longer open.

Representative read-side surfaces include:

- closed failure history attached to the resume result
- warning details containing closed failure entries
- dedicated closed failure history HTTP read surfaces where implemented
- failure metadata including:
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

Representative operator-facing interpretation:

- closed failure history should remain inspectable after an operator ignores open failures
- readers should be able to distinguish `ignored` from `resolved` without inferring from timestamps alone
- operator action that closes an open failure should change unresolved warning behavior, but it should not erase diagnostic history

## 13.3 Repeated Failure and Retry Metadata

Repeated projection failures should remain visible in canonical resume metadata.

Representative fields include:

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

`retry_count` should represent how many prior open failures already existed for the same projection stream before the current failure was recorded.

Representative examples:

- first failure for a projection stream: `retry_count = 0`
- second consecutive open failure for the same projection stream: `retry_count = 1`

This allows resume consumers to distinguish:

- one-off transient failure
- repeated unresolved failure
- failure that was later resolved
- failure that was later ignored

---

## 14. Workspace-Scoped Resume

The workflow model supports a workspace-level current view.

Resource:

- `workspace://{workspace_id}/resume`

Selection rule:

1. if a running workflow exists, return that workflow
2. otherwise return the latest workflow for the workspace
3. if no workflow exists, return empty/not-found behavior

This resource provides the current operational view for a workspace.  
For exact workflow identity lookup, a workflow-specific resource should be used.

---

## 15. Start, Checkpoint, and Termination Semantics

## 15.1 Workflow Start

`workflow_start` creates:

- a new workflow instance
- an initial attempt

Typical initial states:

- workflow instance: `running`
- attempt: `running`

## 15.2 Workflow Checkpoint

`workflow_checkpoint` persists resumable progress for a specific workflow and attempt.

It may also attach a verification record when appropriate.

Checkpoint creation does not terminate the workflow.

## 15.3 Workflow Complete

`workflow_complete` is treated architecturally as a workflow termination operation.

Although the name says "complete", it may terminate the workflow as:

- `completed`
- `failed`
- `cancelled`

This operation should keep workflow and attempt terminal states consistent.

---

## 16. Cancellation Semantics

Cancellation is modeled as terminal, not as pause.

If an operator cancels execution:

- the current attempt becomes `cancelled`
- the workflow may become `cancelled`
- resume should report the workflow as terminal

If work is later restarted, the system should use:

- a new attempt, or
- a new workflow instance

The original cancelled execution is not revived in place.

---

## 17. Verification in the Workflow Model

Verification is a supporting operational record, not yet a controlling gate.

In `v0.1.0`:

- verification records are canonical
- latest verification should appear in resume
- verification can be recorded at checkpoint time
- verification can be recorded at termination time
- completion does not require verification to pass

This design leaves room for future policy-driven verification gates.

---

## 18. Ordering and Time

Workflow records are ordered primarily by timestamps.

Important time fields include:

- `created_at`
- `updated_at`
- `started_at`
- `finished_at`

Ordering rules:

- latest workflow: timestamp-based
- latest checkpoint: `created_at`
- latest verify report: `created_at`
- attempt order: `attempt_number`, with timestamps as support

Global event sequencing is intentionally deferred beyond `v0.1.0`.

---

## 19. Failure and Artifact References

The workflow model should remain compatible with future structured failure and artifact tracking.

Future workflow-adjacent records may include:

- structured failure records
- projection failure records
- artifact metadata
- links from checkpoints to artifacts
- links from attempts to verification evidence

Projection failure records are especially important because they connect derived repository state back to canonical operational state.

At minimum, the workflow model should remain compatible with projection failure fields such as:

- projection type
- target path
- failure status
- retry count
- occurrence timestamp
- resolution timestamp
- workflow ownership
- attempt ownership where available

These are not required to define the core workflow hierarchy, but they are important extensions of the operational model.

---

## 20. Relationship to Memory

Workflow control and memory are related but distinct.

Workflow control answers:

- what is currently running
- what happened operationally
- where can execution resume

Memory answers:

- what knowledge should be retained
- what prior work is relevant
- what lessons or procedures should be recalled

A completed workflow may later produce:

- an episode
- memory items
- artifact references
- structured failure knowledge

However, memory does not define workflow canonical state.

---

## 21. Design Intent

This workflow model is designed to support:

- durable execution
- safe restart and recovery
- explicit state transitions
- future retry support
- canonical resume reconstruction
- clear separation between operational truth and derived projections

The most important property of the model is not simply that it records progress, but that it supports trustworthy continuation of long-running agent work.