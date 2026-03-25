# ctxledger last session

## Summary

This continuation completed the requested documentation reorganization for
repository-level product/reference docs and version-oriented planning/release
artifacts.

The main result is that the repository now has a clearer top-level documentation
structure for project-wide material:

- current repository/product references are grouped under:
  - `docs/project/product/`
- version-specific plans and release-facing artifacts are grouped under:
  - `docs/project/releases/`
- historical implementation-plan artifacts are grouped under:
  - `docs/project/history/`

This continuation focused on file organization, path repair, and documentation
navigation clarity.

It did **not** change the underlying `0.6.0` hierarchical memory behavior,
retrieval contracts, AGE runtime behavior, or workflow-summary automation
behavior.

---

## What was completed

### 1. Added project-level documentation subdirectories

A new project-level docs grouping was introduced:

- `docs/project/product/`
- `docs/project/releases/`
- `docs/project/history/`

The intended reading is now:

### `docs/project/product/`
Use this for current repository-wide direction and reference material, including:

- architecture
- design principles
- specification
- workflow model
- memory model
- MCP API
- roadmap

### `docs/project/releases/`
Use this for version-by-version and milestone-oriented material, including:

- changelog
- release evidence
- versioned plans
- milestone plans
- release/remediation/checklist artifacts

### `docs/project/history/`
Use this for older implementation-plan material that still matters for traceability
but should not be read as the current canonical repository description.

---

### 2. Moved current product/reference docs into `docs/project/product/`

The following current repository-wide reference docs were moved under the new
product directory:

- `docs/project/product/specification.md`
- `docs/project/product/architecture.md`
- `docs/project/product/design-principles.md`
- `docs/project/product/workflow-model.md`
- `docs/project/product/memory-model.md`
- `docs/project/product/mcp-api.md`
- `docs/project/product/roadmap.md`

This means the current repository-wide policy/requirements/modeling material is
no longer mixed into the same flat directory as historical and version-specific
plan artifacts.

---

### 3. Moved versioned plans and release artifacts into `docs/project/releases/`

The following release/version-oriented artifacts were moved:

- `docs/project/releases/CHANGELOG.md`
- `docs/project/releases/v0.1.0_acceptance_evidence.md`
- `docs/project/releases/plans/...`

This makes the version-by-version planning and milestone material easier to
recognize as release-oriented or planning-oriented rather than current canonical
product reference documentation.

---

### 4. Moved older implementation-plan artifacts into `docs/project/history/`

The following older implementation-plan files were moved into the history area:

- `docs/project/history/imple_plan_0.1.0.md`
- `docs/project/history/imple_plan_review_0.1.0.md`
- `docs/project/history/imple_plan_0.5.3_projection_deprecation.md`
- `docs/project/history/imple_plan_0.5.4_projection_removal_cleanup.md`

This creates a clearer boundary between:

- current-state reference docs
- active/release-oriented planning docs
- historical implementation material

---

### 5. Repaired important documentation links

After the moves, key documentation references were updated so the new structure
is navigable.

Updated areas included:

- `README.md`
- `docs/CONTRIBUTING.md`
- `docs/SECURITY.md`
- `docs/grafana_operator_runbook.md`
- selected moved historical plan files

The main categories of repair were:

- current reference doc links now point to `docs/project/product/...`
- versioned planning links now point to `docs/project/releases/plans/...`
- moved historical-doc self-references now point to `docs/project/history/...`

---

### 6. Added a new project docs index

A new index file was added:

- `docs/project/README.md`

This file now explains:

- what belongs in `product/`
- what belongs in `releases/`
- what belongs in `history/`
- how to choose the right starting point depending on whether the reader wants:
  - current repository shape
  - version/release planning
  - historical implementation context

This should reduce future drift back toward a flat mixed-purpose docs layout.

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

At handoff, the documentation structure should now be read as:

### Current project/product references
- `docs/project/product/...`

### Versioned plans and release artifacts
- `docs/project/releases/...`

### Historical implementation-plan context
- `docs/project/history/...`

### Narrower topic-specific docs that remain outside `docs/project/`
Still top-level under `docs/` for now:

- deployment/operator guidance
- security guidance
- memory-specific design notes and runbooks

This means the reorganization currently applies specifically to:

- ctxledger全体の方針や機能要件、ロードマップ
- バージョン毎のプランや成果物

rather than to every topical sub-area inside `docs/`.

---

## What remains to watch

The structural reorganization is complete for the requested scope, but a few
follow-up concerns remain worth watching in future sessions:

1. Some deeper planning docs inside `docs/project/releases/plans/` may still
   contain old path references and could be cleaned incrementally if they become
   active again.
2. Topic-specific docs under `docs/memory/` remain intentionally separate for
   now; if broader docs taxonomy work happens later, that should be treated as a
   separate bounded slice.
3. Operator/security/deployment docs remain top-level and may or may not be
   reorganized later depending on whether a broader docs information architecture
   effort is chosen.

---

## Recommended next step

If another session continues from here, the most natural next step is **not**
more immediate restructuring unless a broken link or discoverability issue is
found.

Instead, the likely sensible next options are:

1. do a light sweep for stale path references inside:
   - `docs/project/releases/plans/`
2. decide whether topic-specific docs such as:
   - `docs/memory/`
   - operator runbooks
   should remain where they are or join a broader information architecture
   cleanup later
3. return to planning work for the next post-`0.6.0` milestone now that the
   project-wide docs structure is cleaner

The important handoff point is:

- the requested docs categorization is in place
- key top-level links were repaired
- the repository remains green after the reorganization
- future documentation cleanup can now proceed from a clearer base structure