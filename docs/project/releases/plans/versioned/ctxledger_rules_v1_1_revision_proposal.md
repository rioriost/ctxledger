# `.rules` `v1.1` Revision Proposal for `ctxledger` `1.1.0`

## 1. Purpose

This document proposes a bounded `v1.1` revision of the repository `.rules`
used with `ctxledger`.

The proposal is aligned with the completed `1.1.0` Phase 0 findings and should
be read as a **policy refinement proposal**, not yet as the final canonical
rules text.

The main purpose of `v1.1` is to improve the parts of the current ruleset that
are directionally correct but still too advisory in practice.

In particular, `v1.1` should improve:

- structured checkpoint quality
- summary-build induction
- interaction-memory promotion posture
- observability for agent-quality and hygiene
- alignment between what the rules ask for and what the runtime can actually
  store, surface, and measure

---

## 2. Why a `v1.1` revision is needed

Phase 0 showed a clear split between areas where `.rules` and runtime already
reinforce each other well, and areas where the rules are still mostly advisory.

### Strong current alignment

The current ruleset already aligns well with runtime behavior for:

- canonical-first posture
- workflow tracking and identifier discipline
- resumability-first session handling
- completion discipline
- summary truth boundaries
- file-work recording posture

### Weak current alignment

The current ruleset is weaker in practice for:

- structured checkpoint population
- explicit `next_intended_action` / next narrow action capture
- explicit `verify_target` capture
- explicit summary-build requesting
- interaction-memory promotion into stronger reusable knowledge
- observability of quality, hygiene, and linkage gaps

### Evidence-backed reason for revision

The Phase 0 findings showed:

- structured checkpoint fields are supported or partially supported, but are
  near-zero in observed checkpoint payloads
- summary build exists, but no observed checkpoint requested
  `build_episode_summary`
- interaction capture is strong, but interaction linkage is weak
- observability is strong for volume and state, but weak for quality and hygiene
- file-work recording is one of the strongest examples of policy and runtime
  reinforcing each other successfully

This means `v1.1` should not rewrite the whole ruleset.
It should tighten the parts that need stronger induction and clearer structure.

---

## 3. Revision goals

The `v1.1` revision should pursue five goals.

### 3.1 Make high-value checkpoint structure more habitual

The rules should make it easier and more normal for agents to record:

- current objective
- next narrow action
- what changed
- what was learned
- what remains
- verify target
- blocker or risk
- resume hint
- failure guard

### 3.2 Make summary build requests happen when they should

The rules should preserve the current explicit and non-fatal summary-build
policy, but induce it more often for high-signal work.

### 3.3 Improve interaction-memory promotion posture

The rules should distinguish between:

- bounded interaction capture
- high-signal interaction promotion
- broad semantic interpretation of all interaction traffic

Only the second should be strengthened in `1.1.0`.

### 3.4 Expand observability from volume to quality

The rules should continue to require operator checks, but should now include
agent-quality and hygiene signals such as:

- structured checkpoint coverage
- summary backlog
- unlinked interaction volume
- null-`workspace_id` memory volume
- aggregate resume and fallback quality

### 3.5 Preserve the strongest current rules unchanged

The revision should not destabilize the parts of the ruleset that are already
working well.

---

## 4. What should remain unchanged

The following rule areas should remain materially unchanged in `v1.1`.

### 4.1 Canonical posture

Keep unchanged in substance:

- canonical system-of-record posture
- local notes are auxiliary
- reliable resumability over brevity
- explicit operational trail over ambiguous minimalism

### 4.2 Workflow identity and completion discipline

Keep unchanged in substance:

- literal workflow identifier handling
- safe resume posture
- completion guard
- completion discipline
- no checkpoint after terminal workflow
- no use of `workflow_complete` as save-progress

### 4.3 Summary truth boundary

Keep unchanged in substance:

- canonical relational summary state is primary
- graph-backed summary state is derived and degradable
- summary-first route meanings remain explicit
- graph summary must not become canonical truth

### 4.4 File-work restoration posture

Keep unchanged in substance:

- file-touching work requires durable file-work recording
- file-work is required restoration material
- file-work should remain workflow-scoped and purpose-preserving

These are among the strongest current alignments and should not be weakened.

---

## 5. Main revision themes

## Theme 1. Stronger structured checkpoint policy

### Problem

The current rules correctly ask for rich checkpoint content, but the wording is
still permissive enough that most of the signal remains prose-only.

### `v1.1` direction

Split checkpoint expectations into:

1. required structured fields when known
2. recommended prose context when useful

### Proposed policy shift

Current posture:
- include in checkpoint when possible

Proposed `v1.1` posture:
- require a smaller set of structured fields when known
- keep prose for nuance, not as the primary carrier of core continuation state

### Proposed required structured fields when known

- `current_objective`
- `next_intended_action`
- `verify_status`
- `what_remains`

### Proposed strongly preferred structured fields when known

- `root_cause`
- `recovery_pattern`
- `verify_target`
- `resume_hint`
- `blocker_or_risk`
- `failure_guard`

### Proposed prose role

Prose should remain useful for:

- nuance
- rationale
- explanation
- tradeoffs
- human-readable context

But prose should no longer be the only expected carrier for the most important
continuation fields.

---

## Theme 2. Explicit next narrow action policy

### Problem

Phase 0 showed that the strongest successful work patterns repeatedly use a
narrow next action, but the current rules do not isolate that behavior strongly
enough.

### `v1.1` direction

Add an explicit rule for next narrow action capture.

### Proposed new rule

`RULE checkpoint_next_narrow_action`

Intent:
- require or strongly prefer one executable next action for active work
- avoid broad future intent when a narrower next step is known

### Proposed behavior

- prefer one next action over a list of vague future possibilities
- prefer an executable slice over a thematic aspiration
- use the checkpoint to preserve the next concrete continuation step

### Why this matters

This is one of the strongest evidence-backed agent-improvement patterns in the
current corpus.

---

## Theme 3. Explicit verify target policy

### Problem

The current rules mention verification status, but do not strongly require the
agent to preserve the verification target itself.

### `v1.1` direction

Add a rule that distinguishes:

- verification outcome
- verification target

### Proposed new rule

`RULE checkpoint_verify_target`

Intent:
- when a verification target is known, record it explicitly
- prefer named test, suite, command, or validation surface over generic claims

### Preferred examples

Good:
- `tests/integration/test_run_workflow_phase_handoff.py`
- `Phase 3 E2E suite`
- `targeted validation tests`
- `ctxledger memory-stats`

Weak:
- `validated`
- `tests pass`
- `looks good`

### Why this matters

The strongest reusable patterns in the corpus combine:

- implementation slice
- named verification target
- passed outcome

---

## Theme 4. Stronger summary-build induction

### Problem

The current summary-build policy is conceptually correct, but too weakly induced
in practice.

Phase 0 showed:

- summary build exists
- summary build is explicit and checkpoint-gated
- no observed checkpoint requested summary build
- summary volume is negligible

### `v1.1` direction

Keep the current explicit and non-fatal posture, but add stronger guidance for
when summary build should be requested.

### Proposed policy refinement

Do not change these core readings:

- explicit
- checkpoint-gated
- non-fatal

But add stronger induction for cases such as:

- high-signal workflow completion with passed verification
- repeated checkpoint theme with clear reuse value
- high-signal failure and recovery lesson
- closeout where the work is clearly reusable beyond the current session

### Proposed new rule

`RULE summary_build_high_signal_triggering`

Intent:
- request summary build when the work is clearly reusable enough to justify it
- avoid leaving all summary creation to rare manual operator action

### Why this matters

This is the clearest current gap between implemented capability and actual use.

---

## Theme 5. Interaction-memory promotion policy

### Problem

The current rules correctly treat interaction memory as bounded and useful, but
they do not yet distinguish strongly enough between:

- capture everything boundedly
- promote only the high-signal parts

### `v1.1` direction

Add a narrower promotion policy for interaction memory.

### Proposed new rule

`RULE interaction_promotion_usage`

Intent:
- use interaction memory for bounded recall and context
- promote only high-signal interaction material into stronger durable knowledge

### High-signal promotion candidates

- root cause clarification
- retry decision
- resume decision
- fallback-prevention decision
- user correction that changes execution direction
- orchestration-boundary finding
- file-work intent that materially affects recovery

### Explicit non-goal

Do not require broad semantic interpretation of all interaction traffic in
`1.1.0`.

### Why this matters

Phase 0 showed that interaction capture is already strong.
The gap is promotion and linkage, not raw capture volume.

---

## Theme 6. Agent-quality observability policy

### Problem

The current observability rules are useful, but they are still mostly
volume-oriented.

### `v1.1` direction

Split observability checks into:

1. baseline operator checks
2. agent-quality checks
3. hygiene checks

### Baseline operator checks

Keep current checks such as:

- `stats`
- `memory-stats`
- `age-graph-readiness`

### Proposed new agent-quality checks

- structured checkpoint coverage
- summary build request rate
- summary build success / skip visibility
- aggregate resume success / failure visibility
- fallback-prevention visibility

### Proposed new hygiene checks

- unlinked interaction volume
- null-`workspace_id` memory volume
- weak-linkage visibility
- missing expected file-work coverage where detectable

### Proposed new rule split

Current broad observability rule should be split into narrower rules such as:

- `RULE observability_baseline_checks`
- `RULE observability_agent_quality_checks`
- `RULE observability_hygiene_checks`

### Why this matters

Phase 0 showed that observability is already strong for counts and state.
The missing layer is quality and hygiene.

---

## 6. Proposed rule changes by area

## 6.1 Workflow section changes

### Keep
- workflow tracking rules
- resume-safely rules
- workflow identifier literal reading
- completion guard
- completion discipline

### Add or refine
- explicit next narrow action rule
- explicit verify target rule
- stronger structured checkpoint requirement split

---

## 6.2 Memory section changes

### Keep
- summary truth boundary
- route interpretation rules
- explicit episode vs auto-memory distinction
- file-work restoration posture

### Add or refine
- stronger summary-build induction
- interaction promotion policy
- stronger structured checkpoint field expectations for memory usefulness
- observability split for quality and hygiene

---

## 6.3 Agent behavior section changes

### Keep
- explicit state transition preference
- session tracking visibility
- prefer structure over prose
- dependency ordering and parallelization rules

### Add or refine
- stronger preference for structured checkpoint fields over prose when both are
  available
- stronger requirement to preserve next narrow action in active work
- stronger requirement to preserve verify target when known

---

## 7. Proposed concrete revision set

This section lists the most likely concrete `v1.1` changes.

## 7.1 Tighten existing rules

### Tighten `checkpoint_content`
Current issue:
- too advisory

Proposed direction:
- split into:
  - required structured fields when known
  - recommended prose context

### Tighten `completion_structured_fields`
Current issue:
- good direction, but too narrow for the strongest observed patterns

Proposed direction:
- add:
  - `verify_target`
  - `resume_hint`
  - `blocker_or_risk`
  - `failure_guard`

### Tighten `summary_build_requesting`
Current issue:
- correct but too weakly induced

Proposed direction:
- preserve explicit request field
- add stronger guidance for high-signal closeout and repeated-theme cases

---

## 7.2 Add new rules

### `RULE checkpoint_next_narrow_action`
Purpose:
- preserve one executable next step

### `RULE checkpoint_verify_target`
Purpose:
- preserve named verification target when known

### `RULE interaction_promotion_usage`
Purpose:
- distinguish bounded interaction capture from high-signal promotion

### `RULE observability_agent_quality_checks`
Purpose:
- require quality-oriented checks beyond raw counts

### `RULE observability_hygiene_checks`
Purpose:
- require hygiene-oriented checks for weak linkage and missing scope

---

## 7.3 Split broad rules

### Split checkpoint content rules
Into:
- structured checkpoint requirements
- prose checkpoint guidance

### Split observability rules
Into:
- baseline checks
- agent-quality checks
- hygiene checks

### Split memory usage guidance
Into:
- summary promotion
- interaction promotion
- file-work restoration

---

## 8. Proposed `v1.1` operator reading

The intended operator reading after `v1.1` should be:

- workflow tracking remains strict and canonical-first
- checkpoints should carry more reusable structure
- summary build remains explicit and non-fatal, but should be requested more
  often for high-signal work
- interaction capture remains bounded, but high-signal interaction material
  should be promoted more deliberately
- observability should answer not only “how much exists?” but also:
  - “how good is the structure?”
  - “how much is still unlinked?”
  - “how much reusable knowledge is still under-produced?”
  - “how resumable is the operating model in practice?”

---

## 9. Non-goals for `.rules` `v1.1`

The `v1.1` revision should not try to:

- replace runtime enforcement with policy prose
- redefine canonical truth boundaries
- require broad semantic interpretation of all interaction traffic
- force graph-first knowledge behavior
- rewrite the entire ruleset from scratch
- weaken the current strong workflow and file-work posture

This should remain a bounded refinement release for the ruleset.

---

## 10. Recommended implementation order

This implementation order has now been completed at the policy-file level.

The `.rules` revision should be implemented in this order.

### Step 1
Tighten structured checkpoint expectations.

### Step 2
Add explicit next narrow action and verify target rules.

### Step 3
Strengthen summary-build induction rules.

### Step 4
Add interaction-promotion guidance.

### Step 5
Split observability into baseline, agent-quality, and hygiene checks.

### Step 6
Update examples and operator-facing documentation so the revised rules are easy
to apply consistently.

---

## 11. Validation expectations for the revision

The `v1.1` revision should be considered successful only if it improves actual
runtime usage patterns, not only rule wording.

Validation should therefore look for:

- increased structured checkpoint field population
- non-zero summary build request usage
- improved summary production relative to episode volume
- improved interaction linkage quality
- visibility of weak-linkage and hygiene gaps
- better operator ability to interpret agent-quality signals

The revision should be read as successful when the rules induce measurably
better durable records.

---

## 12. One-line proposal summary

`.rules` `v1.1` should preserve the strongest current canonical and workflow
discipline rules, while tightening structured checkpoint expectations,
strengthening summary-build induction, clarifying interaction promotion, and
expanding observability from raw volume into agent-quality and hygiene signals.

### Outcome note

This proposal is now historical planning context.
The canonical `.rules` file is already version `v1.1`, and the corresponding
policy updates were committed in `19403cd`.