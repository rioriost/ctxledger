# Memory Documentation Index

This directory contains **memory-specific documentation** for `ctxledger`.

The memory docs are organized by document role so that design direction,
decision records, operator guidance, and validation material are easier to
distinguish.

## Directory layout

### `decisions/`

Use this directory for **decision records, contract-boundary decisions, and
closeout-oriented milestone reading**.

Typical contents include:

- decision records
- retrieval-contract decisions
- boundary decisions
- milestone closeout notes
- refinement checklists that are being used as decision/closeout records
- targeting or policy decisions

Current files include:

- `decisions/first_age_slice_boundary_decision.md`
- `decisions/first_memory_get_context_hierarchical_improvement_decision.md`
- `decisions/minimal_hierarchy_model_decision.md`
- `decisions/grouped_selection_primary_surface_decision.md`
- `decisions/auxiliary_groups_top_level_sibling_decision.md`
- `decisions/episode_less_summary_first_decision.md`
- `decisions/age_image_selection_decision.md`
- `decisions/age_image_candidate_decision_record_template.md`
- `decisions/summary_hierarchy_0_6_0_milestone_slice_closeout.md`
- `decisions/phase_e_summary_hierarchy_refinement_checklist.md`
- `decisions/workflow_summary_targeting_policy.md`

### `design/`

Use this directory for **design notes, design direction, implementation-shape
documents, and prototype/design-prep material**.

Typical contents include:

- service-contract notes
- implementation-shape docs
- schema/repository design docs
- prototype design notes
- image-selection notes and design records
- future-shape design exploration
- workflow automation design direction

Current files include:

- `design/memory_get_context_service_contract.md`
- `design/minimal_hierarchy_schema_repository_design.md`
- `design/minimal_summary_write_build_path.md`
- `design/next_minimal_hierarchy_primitive_design.md`
- `design/optional_age_summary_mirroring_design.md`
- `design/constrained_age_supports_prototype.md`
- `design/constrained_age_supports_prototype_implementation_plan.md`
- `design/age_setup_first_slice.md`
- `design/age_graph_population_bootstrap.md`
- `design/age_docker_provisioning_plan.md`
- `design/age_image_selection_note.md`
- `design/age_image_candidate_prebuilt_record.md`
- `design/age_image_candidate_prebuilt_concrete_record.md`
- `design/age_image_candidate_repo_build_record.md`
- `design/workflow_summary_automation_direction.md`

### `runbooks/`

Use this directory for **operator/developer-facing procedural guidance**.

Typical contents include:

- explicit operational runbooks
- command-oriented usage notes
- verification workflows
- operational troubleshooting or inspection steps

Current files include:

- `runbooks/summary_build_runbook.md`
- `runbooks/age_prototype_validation_runbook.md`

### `validation/`

Use this directory for **validation-specific templates, observations, and other
validation-oriented material**.

Typical contents include:

- validation templates
- validation observations
- repeatable validation scaffolds
- evidence-oriented supporting material

Current files include:

- `validation/age_prototype_validation_observation_template.md`

---

## How to choose the right memory docs

### If you want the current memory architecture or implementation direction
Start with:

- `design/memory_get_context_service_contract.md`
- `decisions/minimal_hierarchy_model_decision.md`
- for clients that want the grouped primary surface without flatter compatibility fields, read the `primary_only` guidance in `design/memory_get_context_service_contract.md`
- `decisions/first_age_slice_boundary_decision.md`
- `decisions/first_memory_get_context_hierarchical_improvement_decision.md`
- `design/minimal_hierarchy_schema_repository_design.md`

### If you want the current bounded `0.6.0` milestone reading
Start with:

- `decisions/summary_hierarchy_0_6_0_milestone_slice_closeout.md`
- `decisions/phase_e_summary_hierarchy_refinement_checklist.md`
- `decisions/workflow_summary_targeting_policy.md`

### If you want operator guidance
Start with:

- `runbooks/summary_build_runbook.md`
- `runbooks/age_prototype_validation_runbook.md`

### If you want validation-specific scaffolding
Start with:

- `validation/age_prototype_validation_observation_template.md`

---

## Current reading of the structure

A practical shorthand for the memory docs is:

- **What was decided?**
  - `decisions/`
- **How is it shaped or designed?**
  - `design/`
- **How do I operate or verify it?**
  - `runbooks/`
- **How do I record or template validation?**
  - `validation/`

---

## Scope note

This `docs/memory/` directory is for **memory-topic documentation**.

It is narrower than:

- `docs/project/product/`
- `docs/project/releases/`
- `docs/project/history/`

Use those `docs/project/` directories for broader repository-wide product,
release, and historical planning material.

Use `docs/memory/` when the document is specifically about:

- memory hierarchy
- memory retrieval
- summary behavior
- AGE-backed memory support
- memory validation/operator workflows

---

## Editing guidance

When adding new memory docs:

- put decision records and closeout/boundary calls in `decisions/`
- put design and implementation-shape material in `design/`
- put operator/developer procedures in `runbooks/`
- put templates and validation evidence helpers in `validation/`

Avoid putting all new memory docs back into the top-level `docs/memory/`
directory when one of the role-based subdirectories is a better fit.