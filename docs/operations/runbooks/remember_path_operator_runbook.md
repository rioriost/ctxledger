# Remember Path Operator Runbook

## 1. Purpose

Use this runbook when you need to answer any of these questions:

- is the system actually accumulating canonical layered memory
- are checkpoint-origin and completion-origin memory paths both firing
- are remember-path writes being skipped too often
- are summaries or graph reads thin because canonical remember writes are weak
- is duplicate suppression blocking expected memory creation

This runbook is operator-facing.
It is about **diagnosing remember-path behavior**, not changing canonical workflow truth.

---

## 2. Canonical reading first

Read the system in this order:

1. workflow / checkpoint truth
2. canonical memory artifacts
3. remember-path observability counters
4. relation counts and relation reasons
5. summary / graph layers

Keep these boundaries explicit:

- workflow state is canonical operational truth
- episodes, memory items, and memory relations are canonical remember artifacts
- summaries are canonical relational artifacts when explicitly built
- AGE graph state is derived and degradable
- graph thinness is often downstream of weak canonical remember input

Do **not** start by blaming the graph layer.

---

## 3. Current remember-path model

The current `0.8.0` remember-path should be read as two bounded automatic paths.

### 3.1 Checkpoint-origin path

A meaningful checkpoint may now produce:

- one canonical checkpoint-origin episode
- one canonical checkpoint note memory item
- promoted memory items for structured fields such as:
  - `current_objective`
  - `next_intended_action`
  - `root_cause`
  - `recovery_pattern`
  - `what_remains`
  - `verify_status`
- constrained `supports` relations when justified

### 3.2 Completion-origin path

A meaningful workflow completion may now produce:

- one canonical completion-origin episode
- one canonical completion note memory item
- promoted memory items for structured fields such as:
  - `current_objective`
  - `next_intended_action`
  - `root_cause`
  - `recovery_pattern`
  - `failure_reason`
  - `verify_status`
- constrained `supports` relations when justified

### 3.3 Why both paths matter

The repository should no longer be read as “memory starts only at `workflow_complete`”.

Checkpoint-origin memory is now an earlier canonical accumulation path.
Completion-origin memory is still the default closeout path.

---

## 4. Main counters to watch

Use both `stats` and `memory-stats`.

### 4.1 `stats`

`stats` gives the high-level operational picture.

Focus on:

- `checkpoint_count`
- `episode_count`
- `memory_item_count`
- `memory_embedding_count`
- `checkpoint_auto_memory_recorded`
- `checkpoint_auto_memory_skipped`
- `workflow_completion_auto_memory_recorded`
- `workflow_completion_auto_memory_skipped`

Concrete example:

```/dev/null/ctxledger_stats_example.txt#L1-18
ctxledger stats

Workspaces:
- total: 1

Workflows:
- running: 2
- completed: 14
- failed: 1
- cancelled: 0

Memory:
- episodes: 22
- memory_items: 58
- memory_embeddings: 58

Remember-path observability:
- checkpoint_auto_memory_recorded: 19
- checkpoint_auto_memory_skipped: 6
- workflow_completion_auto_memory_recorded: 14
- workflow_completion_auto_memory_skipped: 1
```

Quick reading:

- high `checkpoint_auto_memory_recorded` means checkpoint-origin memory is actively accumulating
- high `checkpoint_auto_memory_skipped` means many checkpoints are being gated out or suppressed
- high `workflow_completion_auto_memory_recorded` means closeout capture is healthy
- unexpected `workflow_completion_auto_memory_skipped` means completion summaries or reused checkpoint signal should be inspected

### 4.2 `memory-stats`

`memory-stats` gives the canonical memory picture.

Focus on:

- `episodes`
- `memory_items`
- `memory_embeddings`
- `memory_relations`
- `memory_item_provenance`
- `checkpoint_auto_memory_recorded`
- `checkpoint_auto_memory_skipped`
- `workflow_completion_auto_memory_recorded`
- `workflow_completion_auto_memory_skipped`

Concrete example:

```/dev/null/ctxledger_memory_stats_example.txt#L1-18
ctxledger memory-stats

Counts:
- episodes: 22
- memory_items: 58
- memory_embeddings: 58
- memory_relations: 17

Remember-path observability:
- checkpoint_auto_memory_recorded: 19
- checkpoint_auto_memory_skipped: 6
- workflow_completion_auto_memory_recorded: 14
- workflow_completion_auto_memory_skipped: 1

Memory item provenance:
- workflow_checkpoint_auto: 31
- workflow_complete_auto: 23
- episode: 4
```

Quick reading:

- `workflow_checkpoint_auto` in provenance confirms checkpoint-origin canonical memory is being written
- `workflow_complete_auto` confirms closeout-origin canonical memory is being written
- non-zero `memory_relations` means the graph layer has canonical relation input to mirror
- if provenance grows but relations stay flat, inspect promoted fields and relation candidate quality

### 4.3 Counter meaning

Read the counters like this:

- `checkpoint_auto_memory_recorded`
  - count of checkpoint-origin canonical memory items written
- `checkpoint_auto_memory_skipped`
  - rough count of checkpoints that did not yield checkpoint-origin memory items
- `workflow_completion_auto_memory_recorded`
  - count of completion-origin canonical memory items written
- `workflow_completion_auto_memory_skipped`
  - rough count of workflow completions that did not yield completion-origin memory items

These are coarse operator counters.
They help you spot underperforming paths quickly.
They are **not** a replacement for detailed per-event investigation.

---

## 5. Healthy readings

The exact numbers vary, but these patterns are healthy.

### 5.1 Healthy checkpoint path

- checkpoints exist
- `checkpoint_auto_memory_recorded > 0`
- `memory_item_provenance` includes `workflow_checkpoint_auto`
- `memory_relations > 0` in representative remember-path-heavy usage
- `memory_get_context` can surface checkpoint-origin promoted items and relation explanations

### 5.2 Healthy completion path

- completed / failed / cancelled workflows exist
- `workflow_completion_auto_memory_recorded > 0`
- `memory_item_provenance` includes `workflow_complete_auto`
- completion-origin notes and promoted fields appear in canonical memory
- relation counts rise when structured closeout fields justify links

### 5.3 Healthy layered-memory reading

A healthy representative deployment tends to show:

- workflow and checkpoint truth present
- episodes present
- memory items present
- memory relations present
- relation-aware retrieval returning meaningful auxiliary context
- summary / graph layers reading from non-trivial canonical substrate

---

## 6. Unhealthy readings and what they usually mean

### 6.1 `checkpoint_count` high, `checkpoint_auto_memory_recorded` near zero

Usually means one or more of:

- checkpoints are too low-signal
- structured fields are often absent
- duplicate suppression is skipping near-identical checkpoint memory
- remember-path auto-memory is active but mostly gated out

Check:

- whether checkpoints contain `current_objective`, `next_intended_action`, `root_cause`, `recovery_pattern`, or `what_remains`
- whether checkpoints are repeating nearly the same summary and fields
- whether verify data is present when it should be

### 6.2 workflow completions exist, but `workflow_completion_auto_memory_recorded` stays low

Usually means:

- closeout summaries are weak
- completion depends on low-signal checkpoint state
- duplicate suppression is skipping repeated closeout memory
- the workflow closed without enough structured signal

Check:

- completion summary quality
- latest checkpoint structure
- verify outcome presence
- whether the completion is just repeating a recent equivalent closeout

### 6.3 episodes and memory items exist, but `memory_relations = 0`

Read this first as a canonical remember-path weakness.

Usually means:

- promoted memory items are too sparse
- relation candidate pairs are not being formed
- structured fields are present too inconsistently
- the workload does not actually create justified `supports` edges

Do **not** jump straight to graph debugging.

### 6.4 `memory_relations > 0`, but graph reads still look thin

Then inspect:

- AGE availability
- AGE bootstrap / refresh recency
- whether the read path is querying the expected graph scope
- whether canonical relation volume is still too low for the desired graph behavior

### 6.5 recorded counts rise, skipped counts also rise

This often means:

- the path is active
- some events are healthy
- but signal quality is inconsistent

That usually points to workload quality, structured field completeness, or duplicate suppression behavior rather than a total runtime break.

---

## 7. Investigation flow

Use this sequence.

### Step 1 — Confirm workflow truth exists

Check that the repository is actually receiving:

- workflows
- attempts
- checkpoints
- verify reports where expected

If this truth is weak, remember-path output will also be weak.

### Step 2 — Check high-level remember counters

Inspect:

- `checkpoint_auto_memory_recorded`
- `checkpoint_auto_memory_skipped`
- `workflow_completion_auto_memory_recorded`
- `workflow_completion_auto_memory_skipped`

Ask:

- is checkpoint-origin memory firing at all
- is completion-origin memory firing at all
- which side is underperforming

### Step 3 — Check provenance mix

Look at `memory_item_provenance`.

You want to know whether canonical memory is being created from:

- explicit episodes
- checkpoint automation
- completion automation

If `workflow_checkpoint_auto` is absent in a checkpoint-heavy workflow, investigate checkpoint signal quality.
If `workflow_complete_auto` is absent in a completion-heavy workflow, investigate closeout signal quality.

### Step 4 — Check relation volume

Inspect `memory_relations`.

If zero or unexpectedly low:

- inspect promoted field usage
- inspect constrained relation candidates
- inspect whether the workload meaningfully creates:
  - next action -> objective
  - recovery pattern -> root cause
  - verification -> note

### Step 5 — Inspect remember-path explainability

Use retrieval/debug surfaces to confirm:

- memory origin
- promotion field
- promotion source
- relation reason

The important questions are:

- did this memory come from checkpoint automation or completion automation
- which structured field created it
- why was this `supports` edge written

Concrete command sequence:

```/dev/null/remember_path_commands.txt#L1-14
ctxledger stats
ctxledger memory-stats

# then inspect a specific workflow
memory_get_context
  workflow_instance_id = <workflow_instance_id>
  query = "root cause recovery pattern"
  limit = 10
  include_episodes = true
  include_memory_items = true
  include_summaries = true

# then inspect retrieval ranking
memory_search
  query = "root cause recovery pattern"
  workspace_id = <workspace_id>
  limit = 10
```

What to read in the outputs:

- in `memory_get_context.details`
  - `remember_path_origin_counts`
  - `remember_path_promotion_field_counts`
  - `remember_path_relation_reason_counts`
  - `remember_path_explainability_by_episode`
- in `memory_search.results[].ranking_details`
  - `remember_path_detail.memory_origin`
  - `remember_path_detail.promotion_field`
  - `remember_path_detail.promotion_source`
  - `remember_path_detail.supports_relation_present`
  - `remember_path_detail.supports_relation_reasons`

### Step 6 — Inspect summary / graph only after canonical checks

Only after the relational path looks healthy, inspect:

- summary build state
- summary membership
- AGE refresh / bootstrap state
- graph-backed read thinness

---

## 8. How to read explainability surfaces

The retrieval surfaces should now be read as explainability helpers, not as second canonical truth systems.

### 8.1 In memory context

Look for details such as:

- remember-path origin counts
- promotion field counts
- relation reason counts
- per-episode remember-path memory explanations
- per-episode relation explanations

Interpretation:

- `workflow_checkpoint_auto`
  - came from checkpoint-origin automation
- `workflow_complete_auto`
  - came from completion-origin automation
- `promotion_field`
  - identifies which structured signal produced a memory item
- `relation_reason`
  - identifies why a constrained `supports` edge exists

### 8.2 In search ranking details

Look for remember-path ranking details such as:

- `memory_origin`
- `promotion_field`
- `promotion_source`
- `checkpoint_id`
- `step_name`
- `supports_relation_present`
- `supports_relation_reasons`

Interpretation:

- if a result has `supports_relation_present = true`, it is participating in canonical relation structure
- if a result has `promotion_field = root_cause`, it was promoted from that structured signal
- if a result has `memory_origin = workflow_complete_auto`, it is closeout-derived rather than checkpoint-derived

---

## 9. Duplicate suppression guidance

Duplicate suppression is now part of remember-path quality control for both:

- checkpoint-origin memory
- completion-origin memory

### 9.1 What suppression is for

It exists to prevent the canonical layer from filling with near-identical notes.

### 9.2 What suppression is **not**

It is not a bug by default.
It is not evidence that the remember path is broken.

### 9.3 When suppression is probably healthy

- repeated checkpoint summaries with the same step and same promoted fields
- repeated closeout summaries with the same effective structured content
- repeated next-action / objective combinations with minimal change

### 9.4 When suppression may be hiding useful memory

- checkpoint summaries look similar, but `root_cause` changed materially
- `recovery_pattern` changed materially
- `what_remains` changed materially
- verify outcome changed materially
- failure reason changed materially

If recorded counts stay low and skipped counts stay high in active work, inspect whether the workload is evolving semantically but still being read as near-duplicate.

---

## 10. Summary and graph investigation boundary

Summary and graph layers remain downstream.

### 10.1 Check summary only after canonical remember writes

Inspect summary behavior after confirming:

- episodes exist
- promoted memory items exist
- relations exist where expected

### 10.2 Check graph only after summary / relation substrate is plausible

AGE graph usefulness depends on:

- canonical memory items
- canonical relations
- bootstrap / refresh health

If checkpoint automation is writing promoted items and `supports` relations, but graph behavior still looks thin, then a graph-layer investigation is justified.

### 10.3 Practical graph reading

Checkpoint-origin relations are now expected to be legitimate graph input.
If those relations exist canonically but are not reflected after refresh, check the derived graph pipeline.

---

## 11. Common operator scenarios

### Scenario A — “We added many checkpoints but recall still looks weak”

Check:

- are checkpoints high-signal
- are checkpoint-origin memory counters rising
- is `workflow_checkpoint_auto` present in provenance counts
- are promoted fields actually populated
- are relation counts rising

Most often the issue is weak checkpoint signal, not retrieval code.

### Scenario B — “Completion memory exists, but graph is still thin”

Check:

- relation counts
- relation reasons
- whether completions produce enough promoted items
- AGE refresh / bootstrap status

Most often the graph is underfed rather than broken.

### Scenario C — “Skipped counts are unexpectedly high”

Check:

- structured field completeness
- summary quality
- duplicate suppression
- whether the workload repeats the same step / same semantic content

### Scenario D — “Search results look correct but not explainable”

Check whether ranking details include:

- origin
- promotion field
- relation participation

If not, treat that as an explainability gap rather than canonical data loss.

---

## 11.1 Minimal command playbook

Use this when you want the shortest practical investigation path.

### Case A — checkpoint path looks weak

```/dev/null/checkpoint_path_playbook.txt#L1-8
ctxledger stats
ctxledger memory-stats

memory_get_context
  workflow_instance_id = <workflow_instance_id>
  query = "current objective next action root cause recovery pattern"
  limit = 10
```

Read:

- whether `checkpoint_auto_memory_recorded` is rising
- whether `workflow_checkpoint_auto` appears in provenance
- whether `remember_path_promotion_field_counts` includes the expected structured fields

### Case B — completion path looks weak

```/dev/null/completion_path_playbook.txt#L1-8
ctxledger stats
ctxledger memory-stats

memory_get_context
  workflow_instance_id = <workflow_instance_id>
  query = "completion summary failure reason verify status"
  limit = 10
```

Read:

- whether `workflow_completion_auto_memory_recorded` is rising
- whether `workflow_complete_auto` appears in provenance
- whether completion-origin promoted fields and relation reasons are visible

### Case C — relations exist but retrieval still looks thin

```/dev/null/relation_path_playbook.txt#L1-10
ctxledger memory-stats

memory_get_context
  workflow_instance_id = <workflow_instance_id>
  query = "supports relation"
  limit = 10
  include_memory_items = true
  include_summaries = true

memory_search
  query = "supports relation"
  workspace_id = <workspace_id>
```

Read:

- `memory_relations`
- `related_context_relation_types`
- `remember_path_relation_reason_counts`
- `supports_relation_present`
- `supports_relation_reasons`

Use this when you want the shortest practical investigation path.

### Case A — checkpoint path looks weak

```/dev/null/checkpoint_path_playbook.txt#L1-8
ctxledger stats
ctxledger memory-stats

memory_get_context
  workflow_instance_id = <workflow_instance_id>
  query = "current objective next action root cause recovery pattern"
  limit = 10
```

Read:

- whether `checkpoint_auto_memory_recorded` is rising
- whether `workflow_checkpoint_auto` appears in provenance
- whether `remember_path_promotion_field_counts` includes the expected structured fields

### Case B — completion path looks weak

```/dev/null/completion_path_playbook.txt#L1-8
ctxledger stats
ctxledger memory-stats

memory_get_context
  workflow_instance_id = <workflow_instance_id>
  query = "completion summary failure reason verify status"
  limit = 10
```

Read:

- whether `workflow_completion_auto_memory_recorded` is rising
- whether `workflow_complete_auto` appears in provenance
- whether completion-origin promoted fields and relation reasons are visible

### Case C — relations exist but retrieval still looks thin

```/dev/null/relation_path_playbook.txt#L1-10
ctxledger memory-stats

memory_get_context
  workflow_instance_id = <workflow_instance_id>
  query = "supports relation"
  limit = 10
  include_memory_items = true
  include_summaries = true

memory_search
  query = "supports relation"
  workspace_id = <workspace_id>
```

Read:

- `memory_relations`
- `related_context_relation_types`
- `remember_path_relation_reason_counts`
- `supports_relation_present`
- `supports_relation_reasons`

## 12. Recommended operator actions by symptom

### Low checkpoint recording

Do:

- improve checkpoint structure
- require `current_objective`
- require `next_intended_action`
- add `root_cause`, `recovery_pattern`, and `what_remains` when known
- inspect duplicate suppression if repetition is high

### Low completion recording

Do:

- improve completion summaries
- make verify outcome explicit
- make failure reason explicit on failure paths
- ensure the latest checkpoint contains reusable structured fields

### Low relation counts

Do:

- inspect promoted memory item types
- inspect relation reasons
- verify that the workload creates justified candidate pairs
- validate relation-aware retrieval before touching graph code

### Thin graph behavior

Do:

- confirm canonical relation input first
- confirm graph refresh / bootstrap later

---

## 13. Escalation criteria

Escalate from normal operator investigation to engineering investigation when:

- counters suggest the path should be firing but canonical artifacts do not appear
- structured fields are clearly present but promoted items are absent
- promoted items exist but justified `supports` relations do not appear
- canonical relations exist but retrieval explainability omits them
- canonical relations exist and graph refresh succeeds, but graph still does not reflect them

At that point, preserve:

- the relevant workflow id
- the relevant checkpoint id
- provenance observations
- recorded / skipped counter readings
- relation counts
- whether the issue is checkpoint-origin, completion-origin, or both

---

## 14. Minimal operator checklist

Use this short checklist first.

1. Run `ctxledger stats`.
2. Run `ctxledger memory-stats`.
3. Are workflows / checkpoints / verify reports present?
4. Are `checkpoint_auto_memory_recorded` and `workflow_completion_auto_memory_recorded` non-zero where expected?
5. Does `memory_item_provenance` include `workflow_checkpoint_auto` and/or `workflow_complete_auto`?
6. Are `memory_relations` non-zero in representative remember-path-heavy usage?
7. Use `memory_get_context` to inspect origin / promoted field / relation reason details for one affected workflow.
8. Use `memory_search` to inspect ranking explainability for one affected workspace.
9. Only then inspect summary and graph layers.

---

## 15. Current expected outcome

A healthy current `0.8.0` deployment should be able to show:

- checkpoint-origin canonical memory before completion
- completion-origin canonical memory at closeout
- constrained canonical `supports` relations
- explainable retrieval details for origin / promotion / relation reason
- operator-visible recorded versus skipped counters
- downstream summary / graph enrichment that is visibly fed by canonical relational memory

That is the intended operational reading of the current remember path.