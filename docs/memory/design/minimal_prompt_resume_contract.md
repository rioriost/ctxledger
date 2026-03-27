# Minimal-Prompt Resume Contract

## Purpose

This note defines the bounded current contract direction for **minimal-prompt
resume** in `ctxledger`.

Minimal-prompt resume means a user can give a short continuation request such as:

- `resume`
- `continue`
- `作業を再開`

and the system can recover the most appropriate continuation target from durable
state with a bounded, explainable selection model.

This contract is intentionally narrow.

It does **not** define arbitrary conversational intent inference.
It defines the minimum bounded resume behavior needed for the `0.9.0` product
goals around:

- resumability from minimal prompts
- explicit workspace-context continuation selection
- bounded mainline-versus-detour recovery
- explainable selected-versus-latest behavior
- canonical-first continuation recovery

---

## Why this contract exists

`ctxledger` already has durable state for:

- workspaces
- workflow instances
- attempts
- checkpoints
- verify reports
- task-recall details
- memory and summary support layers

That means the system can often resume a **specific workflow** when the caller
already knows the workflow identity.

However, a practical user often does not say:

- resume workflow `123e4567-e89b-12d3-a456-426614174000`

A practical user says:

- `resume`
- `continue`
- `続き`
- `作業を再開`

That leaves a narrower but important problem:

- from the current workspace context, **which** workflow should be foregrounded?

Without an explicit contract, the system can drift into bad behavior:

1. too weak
   - the user must still supply workflow identity or ad hoc local notes

2. too opaque
   - a workflow is selected but the user cannot understand why

3. too magical
   - the system implies broad intent inference beyond durable evidence

This contract exists to keep minimal-prompt resume in the useful middle:
**bounded, canonical-first, explainable workspace-context continuation
selection**.

---

## Core contract posture

Minimal-prompt resume should be read using these rules:

- canonical workflow and checkpoint state remain PostgreSQL-first
- minimal-prompt resume is a **selection layer** over canonical workflow truth
- `workflow_resume` remains the workflow-id-specific resume path
- workspace-context resume determines **which** workflow should be resumed
- selected-versus-latest behavior must remain explicit
- mainline-versus-detour interpretation must remain bounded and explainable
- local auxiliary notes must not be required as the primary system of record

This means minimal-prompt resume is:

- workspace-context-aware
- canonical-first
- heuristic but bounded
- explanation-backed
- operationally useful

It is **not**:

- a second workflow-truth system
- an unconstrained intent-inference engine
- a replacement for explicit workflow-id resume when the caller already knows the
  target workflow

---

## Two resume entry points

The bounded `0.9.0` reading should preserve a clear separation between two resume
entry points.

### 1. Workflow-specific resume

This path is used when the caller already knows the workflow identity.

Examples:

- `workflow_resume`
- HTTP workflow resume by workflow instance id
- equivalent operator-facing CLI inspection paths

This path answers:

- can this workflow be resumed?
- what is the latest checkpoint?
- what is the next hint?
- what warnings or verify details exist?

This path does **not** decide which workflow should be resumed for a workspace.
It inspects one already-selected workflow.

### 2. Workspace-context minimal-prompt resume

This path is used when the caller does **not** provide workflow identity and is
effectively asking:

- what should I resume here?
- which workflow is the best continuation target for this workspace right now?

This path should:

- inspect the bounded candidate set for the workspace
- select one workflow as the current continuation target
- explain why that workflow was selected
- preserve explicit comparison against the latest workflow where relevant

This is the intended contract surface for short prompts like:

- `resume`
- `continue`
- `作業を再開`

---

## Supported user prompt class

At the current intended boundary, this contract supports short continuation
prompts whose meaning is close to:

- resume the current work
- continue the work in this workspace
- recover the next intended development action
- return to the most appropriate mainline task when the latest work was a detour

The supported prompt class is therefore:

- **minimal continuation prompts interpreted against current workspace context**

This contract does **not** currently promise correct recovery for:

- broad cross-workspace continuation requests
- prompts that intentionally omit the workspace while multiple unrelated
  workspaces are equally plausible
- complex natural-language project-planning questions
- arbitrary narrative requests about all prior work

---

## Canonical first, derived second

Minimal-prompt resume should be assembled in this order.

## Step 1 — Workspace-scoped canonical workflow state

Use canonical workflow data first to determine the bounded candidate set and
selection posture.

Canonical sources include:

- workspace registration
- workflow instances
- attempts
- checkpoints
- verify reports

The first question is:

- what workflows in this workspace are valid continuation candidates?

## Step 2 — Bounded continuation heuristics

Once the candidate set exists, apply bounded selection heuristics such as:

- running workflow presence
- latest workflow presence
- workflow terminal versus non-terminal status
- latest attempt presence
- latest checkpoint presence
- detour-like versus mainline-like signals

These heuristics are derived interpretation layers over canonical state.
They help choose the continuation target.
They do not redefine canonical workflow truth.

## Step 3 — Explanation surfaces

Return explicit explanation details for:

- selected workflow
- latest workflow
- running workflow
- selected-versus-latest relationship
- detour override behavior where relevant
- ranking details where available

The user or operator should be able to answer:

- why was this selected?
- was the latest workflow deprioritized?
- did the system prefer a prior mainline over a latest detour?
- were there resumability signals such as checkpoint or attempt history?

---

## Candidate selection model

At the bounded current reading, workspace-context minimal-prompt resume should
select from a representative candidate set in the workspace and prefer candidates
using a practical continuation ordering.

### Preferred ordering themes

The current intended ordering themes are:

1. running workflow is strongly preferred
2. non-terminal workflows are preferred over terminal workflows
3. workflows with latest-attempt signal are stronger than workflows without it
4. workflows with latest-checkpoint signal are stronger than workflows without it
5. mainline-like candidates are preferred over detour-like candidates
6. latest workflow remains visible even when it is not selected

This should be read as a **bounded ranking posture**, not a promise of perfect
inference.

### Why this ordering exists

The point is to better support the user question:

- what should I continue right now?

rather than the weaker question:

- what workflow row was created most recently?

The latest workflow is often useful.
But the latest workflow is not always the right continuation target when:

- it is already terminal
- it was a detour
- an earlier still-active mainline remains the more useful target

---

## Selected versus latest

A core part of this contract is the distinction between:

- `latest`
- `selected`

### Latest

`latest` means the newest workflow considered for workspace resume.

It is a temporal fact.

### Selected

`selected` means the workflow chosen as the continuation target after applying
bounded workspace-resume heuristics.

It is a derived operational choice.

### Required contract reading

The system should explicitly preserve:

- whether selected equals latest
- whether selected differs from latest
- whether latest was deprioritized
- why the selected candidate won

This distinction matters because a valid resume system must be able to say:

- the latest workflow exists
- but it was not selected for continuation
- because the latest workflow looked terminal or detour-like
- and a non-terminal mainline candidate was stronger

Without this distinction, minimal-prompt resume becomes opaque.

---

## Mainline versus detour

Minimal-prompt resume should preserve a bounded reading of:

- mainline continuation
- detour work

### Mainline-like reading

A workflow or checkpoint is mainline-like when it appears aligned with the
primary task line for the workspace.

Representative signals may include:

- primary task ticket naming
- current objective continuity
- next intended action continuity
- absence of documentation/cleanup/diagnostic detour signals

### Detour-like reading

A workflow or checkpoint is detour-like when it appears to be:

- docs follow-up
- cleanup-only work
- narrow diagnostics
- operator notes or runbook work
- another bounded side path that is not the best mainline continuation target

### Required contract reading

Mainline-versus-detour behavior must remain:

- bounded
- heuristic
- explicit
- explainable

The contract should never imply that the system can perfectly infer project
intent from arbitrary text.
It should only claim that bounded signals can help avoid obviously poor
continuation choices.

---

## Detour override behavior

At the current intended boundary, the workspace-context resume path may prefer a
non-detour-like non-terminal workflow over the latest workflow when the latest
workflow looks detour-like.

When that happens, the response should preserve enough information to explain:

- the latest workflow existed
- the latest workflow looked detour-like
- a non-detour-like candidate was available
- the override was applied
- the selected candidate became the preferred continuation target

This is one of the most important bounded `0.9.0` behaviors because it helps the
system recover the likely mainline after an incidental side trip.

---

## Terminal override behavior

The workspace-context resume path may also prefer a non-terminal workflow over
the latest workflow when the latest workflow is terminal.

When that happens, the response should preserve enough information to explain:

- the latest workflow existed
- the latest workflow was terminal
- a non-terminal candidate was available
- the selected candidate became the preferred continuation target

This prevents a weak resume reading where the system only points at the newest
workflow even when that workflow is already finished.

---

## Minimum explanation surface

A bounded minimal-prompt resume response should preserve enough structured
information to answer:

- what workspace was considered?
- which workflow was selected?
- which workflow was latest?
- which workflow was running?
- how many candidates were considered?
- was latest deprioritized?
- did selected equal latest?
- did selected equal running?
- was a detour override applied?
- were explanations present?
- were ranking details present?

A practical minimum explanation surface should include fields equivalent to:

- `strategy`
- `candidate_count`
- `selected_workflow_instance_id`
- `running_workflow_instance_id`
- `latest_workflow_instance_id`
- `selected_reason`
- `latest_deprioritized`
- `signals`
- `explanations`
- `ranking_details`

The exact response shape may evolve, but that reading should remain stable.

---

## Required signals posture

The current bounded contract should preserve explicit signals for representative
selection facts such as:

- `running_workflow_available`
- `latest_workflow_terminal`
- `non_terminal_candidate_available`
- `selected_equals_latest`
- `selected_equals_running`
- `latest_ticket_detour_like`
- `latest_checkpoint_detour_like`
- `selected_ticket_detour_like`
- `selected_checkpoint_detour_like`
- `detour_override_applied`
- `ranking_details_present`
- `explanations_present`

These signals matter because they keep the resume choice auditable.

---

## Relationship to historical recall

Minimal-prompt resume and historical recall are related but not identical.

Minimal-prompt resume answers:

- what should I continue?

Historical recall answers questions like:

- what happened yesterday?
- where did we stop?
- what remains?
- what happened for this keyword?

Minimal-prompt resume may reuse some of the same durable state and explanation
surfaces, but it should remain a narrower continuation-selection contract rather
than a broad historical-question system.

---

## Relationship to interaction memory

Interaction memory can strengthen minimal-prompt resume by helping recover:

- what the user most recently wanted
- what the agent believed it was doing
- whether a recent message looked like a detour
- what bounded next step was discussed

However, interaction memory remains a supportive layer.

The canonical workflow and checkpoint system-of-record still determines:

- which workflows exist
- which workflow states are terminal or non-terminal
- what checkpoint data was actually recorded

Interaction memory can help explain continuation.
It does not replace canonical workflow truth.

---

## Relationship to `.rules`

Repository `.rules` should align with this contract where they materially shape
resume behavior.

That means `.rules` should reinforce at least these readings:

- prefer resuming existing workflow context before starting a new one
- treat canonical workflow and checkpoint state as the system of record
- avoid relying on local auxiliary notes as primary resume truth
- preserve checkpoint discipline so later resume is better supported
- preserve enough explicit operational trail for later continuation recovery

If `.rules` and implementation drift apart, the milestone should treat that as a
real contract problem rather than a documentation nit.

---

## Non-acceptance examples

The following should be treated as failures of the intended contract.

- plain `resume` still depends mainly on ad hoc local notes
- the system selects a workflow but cannot explain why
- selected-versus-latest distinction is hidden
- detour override behavior exists but is not surfaced explicitly
- latest workflow is always chosen even when terminal or clearly detour-like
- interaction memory silently becomes a competing workflow-truth layer
- the repository implies magical continuation inference beyond the bounded
  current model

---

## Validation expectations for `0.9.0`

Focused validation for this contract should cover representative cases such as:

- latest non-terminal mainline workflow is selected when no running workflow is
  present
- running workflow is preferred over a latest non-running workflow
- non-terminal workflow is preferred over latest terminal workflow
- non-detour-like workflow is preferred over latest detour-like workflow
- selected-versus-latest explanation surfaces are present and stable
- ranking details remain explicit where the bounded contract promises them
- workspace-context resume does not require local auxiliary notes as primary
  truth

Validation should exist at the narrowest useful layers, including where relevant:

- runtime helper tests
- resource/serializer response-shaping tests
- HTTP or MCP boundary tests for workspace-context resume behavior

---

## Expected implementation boundary for `0.9.0`

The bounded `0.9.0` implementation should support:

- a clear workspace-context entry point for minimal-prompt resume
- explicit separation from workflow-id-specific resume
- bounded selected-versus-latest explanation
- bounded mainline-versus-detour explanation
- stable structured selection signals
- focused tests and docs for the contract

The milestone does **not** need to provide:

- unconstrained natural-language intent inference
- cross-workspace magical selection with no anchoring context
- a general-purpose conversational reasoning engine about all prior work

---

## Summary

Minimal-prompt resume in `ctxledger` should be read as:

- a workspace-context continuation-selection contract
- grounded in canonical workflow and checkpoint truth
- strengthened by bounded selection heuristics
- explicit about selected-versus-latest behavior
- explicit about mainline-versus-detour behavior
- explainable enough for operator and agent trust

It should help the repository honestly claim, for the bounded `0.9.0` slice:

- a user can say `resume`
- and the system can more reliably recover the intended continuation target
  without inventing a second workflow-truth system