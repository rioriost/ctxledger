# ctxledger last session

## Summary

This continuation completed the requested taxonomy reorganization for
`docs/project/releases/plans/`.

The main result is that the release-planning area is now easier to navigate
because it no longer mixes version-oriented plans and topic/domain planning sets
in one flat directory.

The new reading is:

- version-tied milestone/release plans live under:
  - `docs/project/releases/plans/versioned/`
- continuing topic/domain planning clusters live under:
  - `docs/project/releases/plans/domains/`
- the subtree now has an explicit navigation index at:
  - `docs/project/releases/plans/README.md`

This continuation focused on documentation information architecture, path
repair, and navigation clarity.

It did **not** change release behavior, runtime behavior, memory behavior,
workflow behavior, deployment behavior, or security behavior.

---

## What was completed

### 1. Added a release-plans taxonomy

The following new structure was introduced under
`docs/project/releases/plans/`:

- `docs/project/releases/plans/versioned/`
- `docs/project/releases/plans/domains/`
- `docs/project/releases/plans/domains/auth/`
- `docs/project/releases/plans/domains/mcp/`

The intent of this taxonomy is to separate:

- **version semantics**
  - plans whose main identity is a release or milestone line such as
    `0.4.0`, `0.5.1`, `0.6.0`, or `0.7.0`
- **domain semantics**
  - planning clusters whose main identity is a continuing topic area such as
    auth or MCP

This removes one of the remaining high-friction parts of the docs structure.

---

### 2. Moved version-oriented plans into `versioned/`

The following clearly version-tied plans were moved into:

- `docs/project/releases/plans/versioned/`

Representative moves include:

- `observability_0_4_0_plan.md`
- `refactoring_0_5_0_plan.md`
- `connection_pooling_0_5_1_plan.md`
- `workflow_resume_timeout_0_5_2_plan.md`
- `test_suite_split_and_coverage_0_5_5_plan.md`
- `hierarchical_memory_0_6_0_plan.md`
- `task_recall_0_7_0_plan.md`

This means a reader asking:

- “What was planned for `0.5.1`?”
- “Where is the `0.6.0` milestone plan?”

can now browse directly by release line.

---

### 3. Moved auth planning docs into `domains/auth/`

The following auth/deployment-boundary planning cluster was moved into:

- `docs/project/releases/plans/domains/auth/`

Moved files:

- `auth_planning_index.md`
- `auth_proxy_scaling_plan.md`
- `auth_large_gateway_evaluation_memo.md`
- `auth_large_gateway_decision_record_template.md`
- `auth_large_gateway_shortlist_example.md`

This groups together:

- auth planning index material
- current small-vs-large auth planning direction
- large-pattern evaluation prep
- gateway selection prep artifacts

instead of leaving them intermingled with unrelated versioned and MCP planning
documents.

---

### 4. Moved MCP planning docs into `domains/mcp/`

The main MCP planning/remediation/review cluster was moved into:

- `docs/project/releases/plans/domains/mcp/`

Moved files include:

- `mcp_planning_index.md`
- `mcp_2025_03_26_compliance_remediation_plan.md`
- `mcp_2025_03_26_conformance_audit.md`
- `mcp_transport_rewrite_decision_memo.md`
- `mcp_transport_rewrite_execution_plan.md`
- `mcp_transport_cutover_checklist.md`
- `mcp_module_split_proposal.md`
- `mcp_pr_sequence_overview.md`
- `mcp_first_patch_plan.md`
- `mcp_second_patch_plan.md`
- `mcp_third_patch_plan.md`
- `mcp_review_gate_checklist.md`
- `mcp_release_acceptance_checklist.md`
- `http_mcp_acceptance_remediation_plan.md`

This makes the MCP planning set readable as one continuing domain cluster rather
than as a scattered set of files mixed into a flat release-plans directory.

---

### 5. Left uncategorized general plans at the root for now

A small number of plans remain directly under:

- `docs/project/releases/plans/`

These are currently the files that do not yet fit as cleanly into the first-pass
taxonomy or that should be reconsidered separately if deeper planning taxonomy
work is done later.

Representative remaining files include:

- `automatic_multilayer_memory_plan.md`
- `openai_default_embedding_integration_plan.md`
- `http_fastapi_cleanup_plan.md`

This was intentional.
The goal of this continuation was to create a clearer taxonomy without forcing
every file into a possibly misleading bucket.

---

### 6. Added a release-plans index

A new index file was added:

- `docs/project/releases/plans/README.md`

This file now explains:

- what belongs in `versioned/`
- what belongs in `domains/`
- how to choose whether to browse by version or by subject area
- why the subtree is no longer flat
- how new planning docs should be categorized going forward

This should reduce future drift back toward a mixed list of files with no obvious
organizing principle.

---

### 7. Repaired key references to the new taxonomy

After the moves, key references were updated so the new release-plans taxonomy is
navigable and self-consistent.

Updated areas included:

- `README.md`
- `docs/CONTRIBUTING.md`
- `docs/project/README.md`
- `docs/operations/README.md`
- `docs/operations/security/SECURITY.md`
- the moved auth planning docs
- the moved MCP planning docs

The main categories of repair were:

- old auth plan links now point to:
  - `docs/project/releases/plans/domains/auth/...`
- old MCP plan links now point to:
  - `docs/project/releases/plans/domains/mcp/...`
- old versioned milestone plan links now point to:
  - `docs/project/releases/plans/versioned/...`
- generic release-plans entry references now point to:
  - `docs/project/releases/plans/README.md`

---

## Validation performed

### Focused validation

Command:

- `python -m pytest tests/http/test_server_http.py tests/http/test_coverage_targets_http.py tests/runtime/test_coverage_targets_runtime.py tests/server/test_server.py tests/mcp/test_tool_handlers_workflow.py -q`

Result:

- **214 passed**

### Full-suite validation

Command:

- `python -m pytest -q`

Result:

- **932 passed, 1 skipped**

---

## Current repository reading after this continuation

At handoff, the main documentation structure should now be read as:

### Project-wide repository references
- `docs/project/product/...`

### Release/version artifacts
- `docs/project/releases/...`

### Release-planning taxonomy
- `docs/project/releases/plans/README.md`
- `docs/project/releases/plans/versioned/...`
- `docs/project/releases/plans/domains/auth/...`
- `docs/project/releases/plans/domains/mcp/...`

### Memory-topic docs
- `docs/memory/decisions/...`
- `docs/memory/design/...`
- `docs/memory/runbooks/...`
- `docs/memory/validation/...`

### Operations-facing docs
- `docs/operations/deployment/...`
- `docs/operations/security/...`
- `docs/operations/runbooks/...`

The important improvement from this continuation is that
`docs/project/releases/plans/` now has an explicit organizing principle instead
of being a flat directory that mixed version semantics and domain semantics.

---

## What remains to watch

This taxonomy reorganization is complete for the current bounded scope, but a few
follow-up concerns remain worth watching in future sessions:

1. A few remaining root-level release plans may still deserve domain or
   versioned categorization later if a clear home becomes obvious.
2. Some less-active release documents may still contain stale references that can
   be cleaned incrementally if those files become active again.
3. Future plan additions should follow the new taxonomy so the subtree does not
   drift back toward a flat mixed list.

---

## Recommended next step

If another session continues from here, the most natural next step is **not**
another broad release-plans restructuring unless a specific ambiguity remains.

Instead, the likely sensible next options are:

1. do small targeted stale-link repairs only when a specific remaining file
   cluster becomes active
2. decide whether the remaining uncategorized root-level plans should gain an
   additional taxonomy bucket later
3. return to feature or milestone planning work now that the documentation
   structure is much clearer

The important handoff point is:

- `docs/project/releases/plans/` is no longer a flat mixed directory
- version-tied plans and domain clusters are now separated
- key entry-point links were repaired
- the repository remains green after the reorganization
- future release-plan additions can now follow a clearer taxonomy