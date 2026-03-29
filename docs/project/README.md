# Project Documentation Index

This directory groups repository-level documentation into clearer categories so
that current product references, versioned release/planning artifacts, and
historical implementation notes are easier to navigate.

## Directory layout

### `product/`

Use this directory for **current repository-wide direction and reference
material**.

Typical contents include:

- overall architecture
- design principles
- product/specification-level behavior
- workflow and memory models
- MCP interface reference
- roadmap and milestone direction

Current files:

- `product/specification.md`
- `product/architecture.md`
- `product/design-principles.md`
- `product/workflow-model.md`
- `product/memory-model.md`
- `product/mcp-api.md`
- `product/roadmap.md`
- `product/technical-overview.md`

### `releases/`

Use this directory for **version-oriented planning and release artifacts**.

Typical contents include:

- changelog entries
- version-specific plans
- milestone plans
- release acceptance evidence
- release checklists and remediation plans

Current files include:

- `releases/CHANGELOG.md`
- `releases/v0.1.0_acceptance_evidence.md`
- `releases/0.7.0_status_review.md`
- `releases/0.7.0_behavior_summary.md`
- `releases/0.7.0_acceptance_review.md`
- `releases/plans/...`
- `releases/plans/versioned/remember_path_0_8_0_plan.md`

The `releases/plans/` subtree is itself organized so that **version semantics**
and **topic/domain semantics** are easier to distinguish:

- `releases/plans/versioned/`
  - for plans whose main identity is a release or milestone line such as
    `0.4.0`, `0.5.1`, `0.6.0`, or `0.7.0`
- `releases/plans/domains/`
  - for topic clusters with multiple related planning artifacts, such as auth or
    MCP
- `releases/plans/README.md`
  - for the entry-point explanation of that taxonomy

### `history/`

Use this directory for **older implementation plans and historical artifacts**
that are still useful for traceability, but should not be mistaken for the
current canonical repository description.

Typical contents include:

- older implementation plans
- plan reviews
- historical cleanup plans
- superseded planning artifacts that still matter for context

Current files include:

- `history/imple_plan_0.1.0.md`
- `history/imple_plan_review_0.1.0.md`
- `history/imple_plan_0.5.3_projection_deprecation.md`
- `history/imple_plan_0.5.4_projection_removal_cleanup.md`

---

## How to choose the right docs

### If you want the current repository shape
Start with:

- `product/specification.md`
- `product/architecture.md`
- `product/workflow-model.md`
- `product/memory-model.md`
- `product/mcp-api.md`
- `product/roadmap.md`
- `product/technical-overview.md`

### If you want version-by-version plans or release evidence
Start with:

- `releases/CHANGELOG.md`
- `releases/0.7.0_status_review.md`
- `releases/0.7.0_behavior_summary.md`
- `releases/0.7.0_acceptance_review.md`
- `releases/plans/README.md`
- `releases/plans/versioned/`
- `releases/plans/domains/`
- `releases/v0.1.0_acceptance_evidence.md`

### If you want historical planning context
Start with:

- `history/`

Treat files there as historical/supporting context unless they explicitly remain
current for a narrow purpose.

---

## Scope note

This `project/` directory is intended for **ctxledger-wide project
documentation**.

Other top-level `docs/` areas may still exist for narrower topics, such as:

- deployment/operator guidance
- security guidance
- memory-specific design notes and runbooks

Those are not replaced by this directory.
This directory is specifically for organizing:

- ctxledger全体の方針や機能要件、ロードマップ
- バージョン毎のプランや成果物

into clearer subdirectories.

---

## Editing guidance

When adding or moving files:

- put current canonical repository/product references in `product/`
- put versioned planning and release artifacts in `releases/`
- put older/superseded implementation material in `history/`

Within `releases/plans/`:

- put milestone/release-line plans in `releases/plans/versioned/`
- put topic-cluster planning sets in `releases/plans/domains/`
- keep `releases/plans/README.md` as the navigation entry point for that subtree

Avoid mixing current-state reference docs with historical planning notes in the
same location when a clearer category exists.