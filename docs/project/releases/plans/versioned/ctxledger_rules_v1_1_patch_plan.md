# `.rules` `v1.1` Patch Plan for `ctxledger` `1.1.0`

## Purpose

This document defines a concrete patch plan for the policy updates that brought
the current repository `.rules` file to `v1.1`.

### Status

Applied and committed.

The canonical `.rules` file is already at `v1.1`, and the corresponding policy
updates were committed as:

- `19403cd` — `Tighten v1.1 repository rules policy`

It is not the final replacement rules text.
It is a **change plan against the current file**.

The goal is to make the update easy to review by answering:

- which current rules should remain unchanged
- which current rules should be tightened in place
- which current rules should be split
- which new rules should be added
- which wording changes are needed to align policy with runtime and observed
  PostgreSQL-backed usage

This patch plan is based on the completed `1.1.0` Phase 0 findings.

---

## Patch strategy

Apply the `v1.1` update using four change types only:

1. **preserve**
   - keep the current rule text materially unchanged
2. **tighten**
   - keep the rule identity, but strengthen wording or scope
3. **split**
   - replace one broad rule with two or more narrower rules
4. **add**
   - introduce a new rule without removing an existing one

This keeps the patch reviewable and minimizes accidental policy drift.

---

## Phase 0 findings that drive this patch

The patch should directly address these confirmed gaps:

1. structured checkpoint intent is strong, but high-value structured checkpoint
   fields are near-zero in observed checkpoint payloads
2. summary build exists, but summary production is negligible because explicit
   build requests are not being induced in practice
3. interaction capture is strong, but interaction linkage to episodes and stable
   workflow context is weak
4. resumability behavior is strong, but aggregate resume and fallback quality
   metrics are still missing
5. observability is strong for volume and state, but weak for quality, hygiene,
   and linkage gaps

The patch should not try to solve unrelated architecture questions.

---

## Patch scope summary

### Preserve unchanged in substance
- canonical posture rules
- workflow identity discipline
- resume safety rules
- completion guard and completion discipline
- summary truth-boundary rules
- route interpretation rules
- file-work restoration posture
- response-style rules unless a wording cleanup is needed

### Tighten
- checkpoint content expectations
- completion structured fields
- summary build requesting guidance
- observability guidance

### Split
- checkpoint content policy
- observability policy
- memory promotion policy

### Add
- explicit next narrow action rule
- explicit verify target rule
- interaction promotion rule
- agent-quality observability rule
- hygiene observability rule

---

## Section-by-section patch plan

## 1. `SECTION canonical_posture`

### Current status
This section is already one of the strongest parts of the ruleset.

### Patch action
**Preserve**

### Rules to preserve materially unchanged
- `canonical_system_of_record`
- `local_notes_are_auxiliary`
- `prefer_recoverability`

### Reason
These rules already align strongly with runtime behavior and the observed corpus.

### Patch note
Only allow wording cleanup if needed for consistency.
Do not change meaning.

---

## 2. `SECTION workflow`

## 2.1 Preserve workflow identity and completion rules

### Patch action
**Preserve**

### Rules to preserve materially unchanged
- `track_workspace`
- `resume_safely`
- `workflow_ids`
- `completion_guard`
- `completion_discipline`
- `workflow_failure_visibility`
- `end_of_loop`

### Reason
These rules are already strongly aligned with runtime behavior and observed use.

---

## 2.2 Tighten checkpoint discipline

### Current rule
- `checkpoint_discipline`

### Patch action
**Tighten**

### Current issue
The rule correctly requires checkpointing at meaningful moments, but it does not
by itself ensure that the checkpoint carries the most reusable structured state.

### Proposed patch
Keep the current trigger list, but add a stronger expectation that meaningful
checkpointing should preserve structured continuation state when known.

### Suggested patch direction
Add wording such as:
- checkpoints should preserve continuation-critical structure, not only prose
- planning and validation checkpoints should preserve the next concrete action
  and verification context when known

### Reason
Observed checkpoint volume is high, but structured checkpoint quality is low.

---

## 2.3 Split checkpoint content policy

### Current rule
- `checkpoint_content`

### Patch action
**Split**

### Current issue
The current rule mixes:
- structured expectations
- prose expectations
- optionality

This makes the rule directionally correct but too advisory in practice.

### Replace with
1. `checkpoint_required_structured_fields`
2. `checkpoint_preferred_structured_fields`
3. `checkpoint_prose_context`

### Proposed replacement intent

#### `checkpoint_required_structured_fields`
Require these when known:
- `current_objective`
- `next_intended_action`
- `verify_status`
- `what_remains`

#### `checkpoint_preferred_structured_fields`
Strongly prefer these when known:
- `root_cause`
- `recovery_pattern`
- `verify_target`
- `resume_hint`
- `blocker_or_risk`
- `failure_guard`
- `what_changed`
- `what_was_learned`

#### `checkpoint_prose_context`
Keep prose for:
- rationale
- tradeoffs
- nuance
- human-readable context

But explicitly say prose should not be the only carrier when required structured
fields are known.

### Reason
This is the clearest policy-to-runtime gap in the current ruleset.

---

## 2.4 Add explicit next narrow action rule

### Patch action
**Add**

### New rule
- `checkpoint_next_narrow_action`

### Proposed intent
- require or strongly prefer one executable next action for active work
- prefer one narrow slice over broad future intent
- preserve the next concrete continuation step in the checkpoint

### Why add instead of only tightening existing rules
Phase 0 showed this is one of the strongest successful patterns in the corpus.
It deserves first-class policy visibility.

### Suggested placement
Immediately after the structured checkpoint rules in `SECTION workflow`.

---

## 2.5 Add explicit verify target rule

### Patch action
**Add**

### New rule
- `checkpoint_verify_target`

### Proposed intent
- when a verification target is known, record it explicitly
- prefer named test, suite, command, or validation surface over generic claims

### Why add
The current rules mention verification status, but not strongly enough the
verification target itself.

### Suggested placement
Near `checkpoint_next_narrow_action`.

---

## 3. `SECTION memory`

## 3.1 Preserve summary truth and route interpretation rules

### Patch action
**Preserve**

### Rules to preserve materially unchanged
- `memory_get_context_reading`
- `route_meanings`
- `summary_truth_boundary`
- `summary_modes`
- `episode_less_path`
- `summary_selection_kind`
- `route_metadata_when_origin_matters`
- `completion_auto_memory_default`
- `explicit_episode_vs_auto_memory`
- `avoid_duplicate_closeout_episodes`
- `prefer_high_signal_episodes`
- `closeout_memory_fallback`
- `keep_facts_separate`

### Reason
These rules already align well with the current runtime and truth boundary.

---

## 3.2 Tighten completion structured fields

### Current rule
- `completion_structured_fields`

### Patch action
**Tighten**

### Current issue
The rule is good, but too narrow for the strongest observed patterns.

### Current fields
- `current_objective`
- `next_intended_action`
- `root_cause`
- `recovery_pattern`
- `what_remains`
- `verify_status`

### Proposed additions
- `verify_target`
- `resume_hint`
- `blocker_or_risk`
- `failure_guard`

### Reason
These fields are central to the `1.1.0` quality goals and should be induced more
strongly.

---

## 3.3 Tighten summary build requesting

### Current rule
- `summary_build_requesting`

### Patch action
**Tighten**

### Current issue
The current rule is conceptually correct, but too weakly induced in practice.

### Keep unchanged in substance
- explicit request field
- checkpoint-gated posture
- non-fatal reading

### Add stronger guidance
Request summary build more often for:
- high-signal workflow completion with passed verification
- repeated checkpoint theme with clear reuse value
- high-signal failure and recovery lesson
- closeout with reusable process lesson

### Reason
Observed summary build request usage is effectively zero.

---

## 3.4 Add summary build high-signal trigger rule

### Patch action
**Add**

### New rule
- `summary_build_high_signal_triggering`

### Proposed intent
- preserve explicit summary build policy
- add stronger induction for high-signal closeout and repeated-theme cases
- avoid requesting summary build only because a workflow is terminal

### Why add
This separates:
- summary build mechanism
from
- summary build induction policy

That makes the rules easier to reason about.

---

## 3.5 Split memory promotion policy

### Current situation
Memory usage guidance is spread across:
- `memory_search_usage`
- `remember_episode_usage`
- `memory_episode_content`
- summary-related rules
- file-work rules

### Patch action
**Split conceptually by adding narrower rules**

### Add
- `interaction_promotion_usage`

### Keep existing rules
- `memory_search_usage`
- `remember_episode_usage`
- `memory_episode_content`

### Proposed new rule intent
Use interaction memory for:
- bounded recall
- resumability support
- historical progress lookup
- file-work intent recall

Promote only high-signal interaction material for:
- root cause clarification
- retry decision
- resume decision
- fallback-prevention decision
- user correction that changes execution direction
- orchestration-boundary finding
- file-work intent that materially affects recovery

### Reason
Phase 0 showed the gap is not capture volume.
It is promotion and linkage quality.

---

## 3.6 Preserve file-work rules

### Patch action
**Preserve**

### Rules to preserve materially unchanged
- `file_work_recording_required`
- `file_work_recording_scope`
- `file_work_recovery_usage`
- `file_work_required_for_context_restoration`

### Reason
This is one of the strongest current policy-to-runtime alignments.

### Optional wording cleanup
Only if needed for consistency with the rest of the file.

---

## 4. Observability patch plan

## 4.1 Split observability policy

### Current rules
- `observability_validation`
- `observability_signal_reading`

### Patch action
**Split and tighten**

### Current issue
The current observability rules are useful, but mostly baseline-oriented.
They do not distinguish:
- baseline operator checks
- agent-quality checks
- hygiene checks

### Replace or augment with
1. `observability_baseline_checks`
2. `observability_agent_quality_checks`
3. `observability_hygiene_checks`

### Proposed intent

#### `observability_baseline_checks`
Keep current checks:
- `stats`
- `memory-stats`
- `age-graph-readiness`

#### `observability_agent_quality_checks`
Add checks for:
- structured checkpoint coverage
- summary build request rate
- summary build success visibility
- summary build skip visibility
- aggregate resume success visibility
- aggregate resume failure visibility
- fallback-prevention visibility

#### `observability_hygiene_checks`
Add checks for:
- summary backlog
- unlinked interaction volume
- weak linkage visibility
- null workspace memory volume
- missing expected file-work coverage when detectable

### Reason
Phase 0 showed observability is strong for counts and state, but weak for
quality and hygiene.

---

## 4.2 Tighten observability signal reading

### Current rule
- `observability_signal_reading`

### Patch action
**Tighten**

### Current issue
The rule currently names only:
- `interaction_memory_item_count`
- `file_work_memory_item_count`

### Proposed additions
Add these as operator signals, not canonical truth:
- `structured_checkpoint_coverage`
- `summary_backlog`
- `unlinked_interaction_volume`
- `null_workspace_memory_volume`

### Reason
These are the most important new `1.1.0` observability targets.

---

## 5. `SECTION agent_behavior`

## 5.1 Preserve explicit state and session tracking rules

### Patch action
**Preserve**

### Rules to preserve materially unchanged
- `prefer_explicit_state_transitions`
- `session_tracking_visibility`
- `parallelize_independent_operations`
- `dependency_ordering`
- `workflow_completion_payloads`
- `summary_build_payload`
- `do_not_flatten_summary_build`
- `summary_automation_policy`

### Reason
These rules already align well with the runtime and current operating posture.

---

## 5.2 Tighten prefer-structure-over-prose

### Current rule
- `prefer_structure_over_prose`

### Patch action
**Tighten**

### Current issue
The rule is directionally correct, but should now explicitly cover checkpoint
structure.

### Proposed patch
Add wording such as:
- never omit required structured checkpoint fields only because prose summary
  exists

### Reason
This directly addresses one of the strongest Phase 0 gaps.

---

## 6. `SECTION response_style`

### Patch action
**Preserve**

### Rules to preserve materially unchanged
- `terse_default`
- `japanese_conciseness`
- `no_redundancy`
- `structure_for_brevity`
- `output_budget`
- `uncertainty_policy`
- `actionability`

### Reason
These rules matter indirectly, but they are not the main source of the current
durable-memory quality gaps.

---

## Concrete patch list

## Preserve as-is or near-as-is
- `default_language`
- `user_note_language`
- `canonical_system_of_record`
- `local_notes_are_auxiliary`
- `prefer_recoverability`
- `track_workspace`
- `resume_safely`
- `workflow_ids`
- `completion_guard`
- `completion_discipline`
- `workflow_failure_visibility`
- `end_of_loop`
- `memory_get_context_reading`
- `route_meanings`
- `summary_truth_boundary`
- `summary_modes`
- `episode_less_path`
- `summary_selection_kind`
- `route_metadata_when_origin_matters`
- `memory_search_usage`
- `remember_episode_usage`
- `completion_auto_memory_default`
- `explicit_episode_vs_auto_memory`
- `avoid_duplicate_closeout_episodes`
- `prefer_high_signal_episodes`
- `closeout_memory_fallback`
- `file_work_recording_required`
- `file_work_recording_scope`
- `file_work_recovery_usage`
- `file_work_required_for_context_restoration`
- `memory_episode_content`
- `keep_changes_small`
- `test_and_doc_focus`
- `prefer_explicit_state_transitions`
- `session_tracking_visibility`
- `parallelize_independent_operations`
- `dependency_ordering`
- `workflow_completion_payloads`
- `summary_build_payload`
- `do_not_flatten_summary_build`
- `summary_automation_policy`
- `keep_facts_separate`
- response-style rules

---

## Tighten in place
- `checkpoint_discipline`
- `completion_structured_fields`
- `summary_build_requesting`
- `observability_signal_reading`
- `prefer_structure_over_prose`

---

## Split or replace broad rules
- replace broad `checkpoint_content` with:
  - `checkpoint_required_structured_fields`
  - `checkpoint_preferred_structured_fields`
  - `checkpoint_prose_context`
- replace broad `observability_validation` with:
  - `observability_baseline_checks`
  - `observability_agent_quality_checks`
  - `observability_hygiene_checks`

---

## Add new rules
- `checkpoint_next_narrow_action`
- `checkpoint_verify_target`
- `summary_build_high_signal_triggering`
- `interaction_promotion_usage`

---

## Suggested patch order

### Patch 1
Introduce the new checkpoint structure rules and tighten
`prefer_structure_over_prose`.

### Patch 2
Add `checkpoint_next_narrow_action` and `checkpoint_verify_target`.

### Patch 3
Tighten `completion_structured_fields`.

### Patch 4
Tighten `summary_build_requesting` and add
`summary_build_high_signal_triggering`.

### Patch 5
Add `interaction_promotion_usage`.

### Patch 6
Split observability into baseline, agent-quality, and hygiene checks.

### Patch 7
Tighten `observability_signal_reading`.

### Patch 8
Do a final consistency pass for naming and section ordering.

---

## Naming decisions to resolve before patching `.rules`

### 1. `next_narrow_action` vs `next_intended_action`
Current runtime and rules mostly use `next_intended_action`.
The new policy language often wants `next_narrow_action`.

Recommended patch decision:
- keep `next_intended_action` as the structured field name
- use `next narrow action` only as explanatory prose in rule descriptions

### 2. `blocker_or_risk`
Current rules already use this concept in prose.
Recommended patch decision:
- keep this exact name for structured policy wording

### 3. `failure_guard`
This is new and may need runtime support later.
Recommended patch decision:
- add as preferred structured field, not required field, in `v1.1`

---

## Validation checklist for the patch itself

After patching `.rules`, validate whether the new wording is likely to improve
actual behavior.

### Expected near-term improvements
- more checkpoints with structured continuation fields
- more explicit next intended actions
- more explicit verify targets
- non-zero summary build request usage
- clearer operator expectation for quality and hygiene checks

### Things that should not regress
- canonical-first posture
- workflow identity discipline
- completion discipline
- summary truth boundary
- file-work restoration posture

---

## One-line patch summary

Patch `.rules` `v1` into `v1.1` by preserving the strongest canonical and
workflow rules, while tightening structured checkpoint expectations, adding
explicit next-action and verify-target rules, strengthening summary-build
induction, clarifying interaction promotion, and splitting observability into
baseline, agent-quality, and hygiene checks.