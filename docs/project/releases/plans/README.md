# Release Plans Documentation Index

This directory contains **version-oriented and release-oriented planning
artifacts** for `ctxledger`.

The release plans are organized to reduce two common sources of confusion:

1. **version semantics**
   - plans tied to a specific milestone or release line such as `0.4.0`,
     `0.5.1`, `0.6.0`, or `0.7.0`
2. **topic/domain semantics**
   - plans clustered around a continuing area such as auth or MCP, where multiple
     related planning and review artifacts belong together

The goal of this directory is to keep those two dimensions readable without
forcing every document into one flat mixed list.

## Directory layout

### `versioned/`

Use this directory for **plans that are primarily organized by version or
milestone**.

Typical contents include:

- milestone plans like `*_0_4_0_plan.md`
- targeted release-line plans like `*_0_5_1_plan.md`
- version-specific implementation focus docs
- milestone planning artifacts whose main identity is the release they belong to

Current examples include:

- `versioned/observability_0_4_0_plan.md`
- `versioned/refactoring_0_5_0_plan.md`
- `versioned/connection_pooling_0_5_1_plan.md`
- `versioned/workflow_resume_timeout_0_5_2_plan.md`
- `versioned/test_suite_split_and_coverage_0_5_5_plan.md`
- `versioned/hierarchical_memory_0_6_0_plan.md`
- `versioned/task_recall_0_7_0_plan.md`
- `versioned/remember_path_0_8_0_plan.md`

### `domains/`

Use this directory for **topic/domain planning clusters** where multiple
documents belong to the same continuing subject area.

Typical contents include:

- topic-specific planning indexes
- decision-prep docs
- remediation plans
- audits
- patch sequences
- review/release gates
- worked examples or templates

Current domain groupings include:

#### `domains/auth/`
For auth and deployment-boundary planning artifacts, such as:

- auth planning index
- auth proxy scaling plan
- large-pattern gateway evaluation memo
- shortlist examples
- decision-record templates

#### `domains/mcp/`
For MCP transport/protocol planning artifacts, such as:

- compliance remediation
- conformance audit
- rewrite decision and execution planning
- patch plans
- review gates
- release acceptance criteria

---

## How to choose the right release plan docs

### If you know the version or milestone first
Start in:

- `versioned/`

Use this when your question is primarily:

- “What was planned for `0.5.1`?”
- “What is the `0.6.0` milestone plan?”
- “What was the targeted plan for `0.7.0`?”

### If you know the subject area first
Start in:

- `domains/`

Use this when your question is primarily:

- “What is the auth planning set?”
- “What MCP planning docs should I read together?”
- “Where is the planning index for this topic?”
- “Where are the related remediation/audit/checklist docs for this domain?”

### If you want the release-level record rather than a plan
Go up one level and use:

- `../CHANGELOG.md`
- `../v0.1.0_acceptance_evidence.md`

Those are release artifacts, not planning taxonomy entries.

---

## Current reading of the structure

A practical shorthand for this directory is:

- **What was planned for a specific version?**
  - `versioned/`
- **What planning documents belong to a specific topic cluster?**
  - `domains/`

This avoids mixing:

- milestone-numbered plans
- subject-area planning sets
- review/audit/checklist families

into one flat list.

---

## Relationship to other documentation areas

This directory is narrower than:

- `docs/project/product/`
- `docs/project/history/`

Use those directories for:

### `docs/project/product/`
- current repository-wide reference docs
- specification
- architecture
- roadmap
- models and product-level behavior

### `docs/project/history/`
- older implementation-plan artifacts
- historical planning context
- superseded or traceability-oriented documents

Use `docs/project/releases/plans/` when the document is specifically about:

- planning a release or milestone
- planning a domain-specific rollout or remediation
- release-gate or review-gate expectations
- audits/checklists/templates that belong to a release-planning cluster

---

## Editing guidance

When adding new release-planning docs:

- put the file in `versioned/` if its main identity is a release or milestone
  line
- put the file in `domains/<topic>/` if its main identity is a continuing topic
  cluster with related companion docs
- keep release evidence and changelog entries one level up in
  `docs/project/releases/`, not inside `plans/`

Avoid putting every new plan directly in this directory root unless there is a
clear reason that it does not fit either:

- `versioned/`
- `domains/`

---

## Naming guidance

Prefer names that make the primary organizing principle obvious:

- version-first names for `versioned/`
  - example:
    - `hierarchical_memory_0_6_0_plan.md`
- topic-first names for `domains/<topic>/`
  - example:
    - `auth_proxy_scaling_plan.md`
    - `mcp_planning_index.md`

This keeps browsing understandable even without reading every file first.