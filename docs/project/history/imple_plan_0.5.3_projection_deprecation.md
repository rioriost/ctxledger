# ctxledger v0.5.3 Implementation Plan: Deprecate User-Facing Local `.agent/` Projection Access

## Status

Draft implementation plan for `v0.5.3`.

## Objective

For `v0.5.3`, remove the user-facing feature that writes workflow resume projections into the local repository `.agent/` directory.

This work should make PostgreSQL-backed canonical workflow state, MCP tools, and existing HTTP/debug/operator surfaces the supported way to inspect and resume work, while treating repository-local `.agent/` artifacts as no longer user-facing behavior.

---

## 1. Background

Today, `ctxledger` still exposes a repository-local projection flow that writes:

- `.agent/resume.json`
- `.agent/resume.md`

These files are explicitly described as derived artifacts, not canonical state. However, the product still contains user-visible and test-visible behavior that makes these projections look like a supported workflow surface.

Examples of current exposure include:

- CLI subcommand: `write-resume-projection`
- default configuration for projection output under `.agent`
- Docker examples that enable projection writing by default
- documentation that names `.agent/resume.json` and `.agent/resume.md` as normal derived outputs
- tests that assert on `.agent/...` paths and projection-writing behavior

The `v0.5.3` goal is to deprecate that repository-local, user-facing access path.

---

## 2. Desired product direction

After this change:

- users should not rely on local `.agent/` files as an official interface
- workflow resumability should be consumed through canonical system surfaces
- `workflow_resume` and related canonical APIs remain the supported inspection path
- projection failure lifecycle remains canonical where it already models operational history
- repository-local `.agent/` projection writing should be removed or clearly retired from supported user workflows

In short:

- **supported**: PostgreSQL-backed workflow state, MCP tools, HTTP/operator inspection
- **deprecated/removed**: local repository `.agent/` projection artifacts as a user feature

---

## 3. Impact analysis

## 3.1 Runtime and config impact

### `src/ctxledger/config.py`

Current configuration contains a dedicated projection settings block:

- `enabled`
- `directory_name`
- `write_markdown`
- `write_json`

Current environment variables include:

- `CTXLEDGER_PROJECTION_ENABLED`
- `CTXLEDGER_PROJECTION_DIRECTORY`
- `CTXLEDGER_PROJECTION_WRITE_MARKDOWN`
- `CTXLEDGER_PROJECTION_WRITE_JSON`

### Impact

If local `.agent/` projection writing is being deprecated as a user feature, these settings are now overexposed for a feature that should no longer be part of the product surface.

### Change direction

Preferred direction for `v0.5.3`:

1. remove projection-writing configuration from public app settings
2. stop advertising projection env vars in docs and examples
3. if a transition period is needed, keep parsing legacy env vars only for compatibility, but do not use them to drive user-visible behavior

---

## 3.2 Projection writer implementation impact

### `src/ctxledger/projection/writer.py`

Current implementation:

- resolves workspace root
- creates projection directory
- writes `resume.json`
- writes `resume.md`
- records projection state updates
- records projection failure updates
- reconciles projection results back into workflow service state

### Impact

This module is the center of the deprecated functionality. It is specifically built around repository-local file output and `.agent`-style projection targets.

### Change direction

Possible options:

#### Option A: Full removal in `v0.5.3`
- remove projection writer module
- remove projection-writing invocation paths
- remove associated tests

#### Option B: Internal-only retention behind non-user-facing usage
- keep internal abstractions temporarily if needed for compatibility
- remove all CLI/docs/user-facing entry points
- stop defaulting output to `.agent`
- avoid presenting output paths as normal behavior

### Recommendation

Use **Option A** unless there is a known downstream dependency inside this repository that still requires the writer. Based on current repo-visible usage, the main user-facing dependency is the CLI command. If no hidden internal dependency exists, complete removal is cleaner and aligns with the stated goal.

---

## 3.3 CLI impact

### `src/ctxledger/__init__.py`

Current CLI surface includes:

- parser registration for `write-resume-projection`
- `_write_resume_projection(...)`
- success/error text that prints `.agent/resume.json` and `.agent/resume.md`

### Impact

This is the most obvious user-facing entry point for the deprecated feature.

### Change direction

For `v0.5.3`:

- remove the `write-resume-projection` subcommand from the parser
- remove `_write_resume_projection(...)`
- remove imports and wiring related to projection writer usage
- ensure help output and parser tests no longer mention the command

### Compatibility note

If a softer deprecation is desired, an intermediate behavior could keep the command name but return a controlled message such as:

- this command has been removed
- use `resume-workflow` or canonical APIs instead

However, this adds transitional code. Since the user request says the feature is being abolished, full removal is preferable unless release management explicitly wants a one-version deprecation window.

---

## 3.4 Workflow and projection-state model impact

### `src/ctxledger/workflow/service.py`
### `src/ctxledger/db/__init__.py`
### PostgreSQL observability / failure model

Current system still tracks:

- projection state
- projection failures
- projection artifact types:
  - `resume_json`
  - `resume_md`

### Impact

This area needs careful separation:

- removing local `.agent/` file writing does **not automatically require** removing canonical projection-state history
- but if the only remaining projection artifacts are the deprecated local files, then keeping these artifact types may create dead model surface

### Risk

A partial removal could leave the system in an awkward state:

- no user-visible projection writer
- but canonical APIs still report `resume_json` / `resume_md` projection entries forever
- warnings and closed projection failure reporting still refer to `.agent/resume.json`

That would be confusing and look unfinished.

### Change direction

Two possible levels:

#### Minimal model change
- stop creating/updating projection states for local file outputs
- keep historical rows and failure lifecycle support intact
- allow old records to remain queryable as historical artifacts
- ensure new workflows no longer produce fresh `.agent` projection state

#### Strong cleanup
- also reduce or retire `resume_json` / `resume_md` as active projection artifact types in business logic
- adjust resume warnings so they do not assume local projection freshness as part of current workflow quality

### Recommendation

For `v0.5.3`, use **minimal model change** unless the team wants a broader schema/contract cleanup in the same release.

That means:

- do not generate new local projection records
- preserve existing historical projection data
- ensure resume surfaces treat old projection entries as historical/derived, not as an expected ongoing deliverable

This keeps migration risk lower and avoids unnecessary schema churn in a deprecation release.

---

## 3.5 HTTP and MCP surface impact

### Current repo-visible surfaces

- `workflow_resume`
- debug/inspection handlers
- projection failure action routes:
  - `projection_failures_ignore`
  - `projection_failures_resolve`

### Impact

These are not the same as the local `.agent/` feature. They are canonical service surfaces and should remain.

However, some responses currently include projection details such as:

- `target_path`
- projection warnings
- closed projection failures for `resume_json` / `resume_md`

### Change direction

Keep canonical APIs, but revise semantics where needed:

- they may still report historical projection data
- they should not imply that local `.agent` files are expected as a current supported workflow surface
- documentation should describe such fields as legacy/historical if they remain visible

---

## 3.6 Docker and environment examples impact

### Files observed

- `docker/docker-compose.yml`
- `docker/docker-compose.small-auth.yml`

Current examples set:

- `CTXLEDGER_PROJECTION_ENABLED: "true"`
- `CTXLEDGER_PROJECTION_DIRECTORY: .agent`
- `CTXLEDGER_PROJECTION_WRITE_JSON: "true"`
- `CTXLEDGER_PROJECTION_WRITE_MARKDOWN: "true"`

### Impact

These examples actively advertise the deprecated behavior.

### Change direction

For `v0.5.3`:

- remove projection env vars from Docker examples
- avoid implying that `.agent` output is a recommended deployment behavior
- keep examples focused on canonical database-backed operation

---

## 3.7 Documentation impact

### Files observed

- `README.md`
- `docs/project/product/architecture.md`
- `docs/deployment.md`
- `docs/CONTRIBUTING.md`
- `docs/SECURITY.md`
- existing implementation plan docs

### Impact

Documentation currently reinforces the idea that projection files exist and are normal derived outputs.

### Change direction

Docs need coordinated updates:

#### `README.md`
- stop listing `.agent/resume.json` and `.agent/resume.md` as expected derived files for users
- clarify that canonical state is inspected through service interfaces
- if historical note is useful, mention that repository-local projection artifacts were deprecated/removed in `v0.5.3`

#### `docs/project/product/architecture.md`
- replace examples that specifically point to `.agent/resume.json`
- keep the higher-level “derived artifacts vs canonical state” principle, but avoid anchoring the architecture to a removed local file feature

#### `docs/deployment.md`
- remove projection env vars from supported configuration guidance
- update environment variable table accordingly

#### `docs/CONTRIBUTING.md`
- keep architectural direction around canonical-vs-derived separation, but remove any implication that `.agent` artifacts are an active contributor-facing surface

#### `docs/SECURITY.md`
- likely lower impact
- keep projection failure route security notes if those routes remain
- avoid wording that suggests local projection files are a normal operational interface

---

## 3.8 Test impact

### Files observed

- `tests/test_cli.py`
- `tests/test_config.py`
- `tests/test_coverage_targets.py`
- `tests/test_mcp_modules.py`
- `tests/test_postgres_integration.py`

### Impact categories

#### CLI tests
These will need direct updates because they currently verify:

- parser includes `write-resume-projection`
- command success/error behavior
- `.agent/resume.json` and `.agent/resume.md` output
- projection targets in returned data

#### Config tests
These currently assume projection env vars are part of minimum valid configuration.

#### Projection writer tests
These are likely removable if writer is removed.

#### Integration tests
These may need fixture/env simplification if projection env vars are no longer part of normal settings.

### Change direction

- remove tests for deleted command/module
- update config fixtures to no longer require projection env vars
- preserve tests around `resume-workflow` and canonical resume behavior
- adjust any assertions that hardcode `.agent/...` paths

---

## 4. Recommended scope for `v0.5.3`

## In scope

1. Remove user-facing CLI support for writing local resume projections
2. Remove or retire the projection writer implementation
3. Remove projection-writing configuration from normal supported settings surface
4. Remove `.agent` projection guidance from docs and Docker examples
5. Update tests to align with canonical-only resume workflow access
6. Keep canonical workflow/memory/projection-history interfaces functioning

## Out of scope unless discovered necessary

1. Database schema migrations removing historical projection tables or columns
2. Removal of all projection-failure lifecycle functionality
3. Large redesign of workflow resume payloads
4. Retroactive cleanup of historical projection records already stored in PostgreSQL

---

## 5. Implementation strategy

## Phase 1: Docs-first plan capture

Create this document and use it as the working contract for `v0.5.3`.

Deliverables:

- `docs/imple_plan_0.5.3_projection_deprecation.md`

Exit criteria:

- impact areas identified
- preferred implementation direction stated
- code changes can proceed in a bounded way

---

## Phase 2: Remove user-facing CLI projection workflow

### Tasks

1. remove `write-resume-projection` parser registration
2. remove `_write_resume_projection(...)`
3. remove imports tied only to that command
4. update parser/help tests
5. remove command behavior tests

### Expected result

Users can no longer invoke local projection writing through the CLI.

### Verification

- CLI tests pass
- help output no longer contains `write-resume-projection`

---

## Phase 3: Remove local projection writer implementation

### Tasks

1. remove `src/ctxledger/projection/writer.py` usage
2. remove `src/ctxledger/projection/__init__.py` exports if no longer needed
3. remove projection-writer-specific tests
4. clean dead imports

### Expected result

No repository-local `.agent/resume.*` file writing path remains in the application runtime.

### Verification

- search for active code references to `ResumeProjectionWriter`
- tests pass without projection writer module usage
- no runtime path creates `.agent/resume.json` or `.agent/resume.md`

---

## Phase 4: Simplify configuration surface

### Tasks

1. remove projection settings from `AppSettings` if nothing still consumes them
2. delete validation rules that only exist for projection writing
3. stop loading projection env vars into runtime settings
4. update config tests and fixtures
5. update integration fixtures that currently include projection env vars

### Expected result

Projection-writing environment variables are no longer part of normal product configuration.

### Verification

- config tests pass
- minimum valid environment no longer includes projection vars
- docs no longer advertise projection vars as supported knobs

---

## Phase 5: Documentation and examples cleanup

### Tasks

1. update `README.md`
2. update `docs/architecture.md`
3. update `docs/deployment.md`
4. update any implementation-plan or contributor docs that imply `.agent` is supported
5. remove `.agent` path examples where they describe active behavior

### Expected result

Public docs consistently describe canonical service-backed workflow access instead of local `.agent` files.

### Verification

- repo doc search no longer presents `.agent/resume.json` or `.agent/resume.md` as a supported current feature
- any remaining mentions are clearly historical or internal

---

## Phase 6: Canonical resume behavior review

### Tasks

1. inspect `resume-workflow` output wording
2. confirm projection-related warnings do not imply required local files
3. decide whether legacy projection details remain visible as historical metadata
4. if needed, adjust wording from “projection expected” toward “historical projection state”

### Expected result

Resume inspection remains useful without teaching users to expect local repository artifacts.

### Verification

- `resume-workflow` output remains coherent for new workflows with no fresh projection writes
- warning text is not misleading

---

## 6. Detailed implementation plan

## 6.1 Code changes

### A. CLI removal
Modify:

- `src/ctxledger/__init__.py`

Changes:

- remove `write-resume-projection` parser block
- remove `_write_resume_projection`
- remove dead imports from that path
- preserve `resume-workflow`

### B. Projection package cleanup
Modify/remove:

- `src/ctxledger/projection/writer.py`
- `src/ctxledger/projection/__init__.py`

Changes:

- remove writer and related exports if unused
- or leave internal stubs only if required temporarily, but do not expose user-facing behavior

### C. Config cleanup
Modify:

- `src/ctxledger/config.py`

Changes:

- remove `ProjectionSettings`
- remove `projection` from `AppSettings`
- remove projection env parsing
- remove projection validation branches

### D. Test cleanup
Modify:

- `tests/test_cli.py`
- `tests/test_config.py`
- `tests/test_coverage_targets.py`
- `tests/test_mcp_modules.py`
- `tests/test_postgres_integration.py`

Changes:

- delete tests for removed CLI command
- update fixture builders that construct `ProjectionSettings`
- remove `.agent/...` assertions
- preserve tests for canonical workflow resume behavior

### E. Docs and examples
Modify:

- `README.md`
- `docs/architecture.md`
- `docs/deployment.md`
- `docker/docker-compose.yml`
- `docker/docker-compose.small-auth.yml`

Changes:

- remove `.agent`-projection guidance
- remove projection env var examples
- reinforce canonical interfaces

---

## 6.2 Migration and compatibility notes

This change is functionally breaking for users who relied on local `.agent/` files.

Recommended release notes should say:

- local `.agent/resume.json` and `.agent/resume.md` projection writing has been removed as a supported feature
- use canonical resume inspection through `workflow_resume`, `resume-workflow`, and other supported service interfaces
- any historical projection state in PostgreSQL may still appear as legacy metadata

If a hard break is considered too abrupt, one fallback is:

- keep parser entry temporarily
- return a deprecation/removal message
- remove actual write behavior

But this should only be done if release UX requires it.

---

## 7. Risks and mitigations

## Risk 1: Hidden coupling to projection settings

### Description
Projection settings may be referenced more broadly than initial search results suggest.

### Mitigation
- perform repo-wide reference cleanup before deleting the settings type
- remove in small commits if needed
- run full diagnostics/tests after config changes

---

## Risk 2: Historical projection metadata still appears in resume output

### Description
Users may still see `resume_json`, `resume_md`, or old `.agent/...` paths in canonical workflow responses.

### Mitigation
- treat old records as historical
- adjust wording where necessary
- do not create new projection updates after removal

---

## Risk 3: Docs drift

### Description
Removing code but leaving docs/examples would create conflicting product messaging.

### Mitigation
- bundle docs updates in same release work
- explicitly search for:
  - `.agent`
  - `resume.json`
  - `resume.md`
  - `CTXLEDGER_PROJECTION_`

---

## Risk 4: Over-removal of projection failure semantics

### Description
Projection failure lifecycle handling may still be operationally useful for existing historical data.

### Mitigation
- do not remove canonical projection failure tools in `v0.5.3`
- limit scope to local user-facing `.agent` projection abolishment
- defer broader projection-domain simplification to a later release if desired

---

## 8. Acceptance criteria

`v0.5.3` is complete when all of the following are true:

1. `write-resume-projection` is no longer a supported CLI command
2. `ctxledger` no longer writes `.agent/resume.json` or `.agent/resume.md` as a user-facing feature
3. public docs and Docker examples no longer advertise local `.agent` projection usage
4. normal runtime configuration no longer depends on projection-writing env vars
5. tests are updated and pass under the new behavior
6. canonical resume inspection surfaces remain functional

---

## 9. Recommended execution order

1. add this planning document
2. remove CLI command and related tests
3. remove writer module and direct dependencies
4. simplify config model and env handling
5. update docs and Docker examples
6. run diagnostics/tests
7. update `last_session.md`
8. commit with a descriptive message

---

## 10. Suggested commit breakdown

### Commit 1
`docs: add v0.5.3 projection deprecation implementation plan`

### Commit 2
`cli: remove write-resume-projection command`

### Commit 3
`core: remove local resume projection writer and config surface`

### Commit 4
`docs: remove .agent projection guidance from user-facing docs`

### Commit 5
`tests: update fixtures and assertions for projection deprecation`

---

## 11. Recommended next implementation step

Start with the CLI removal path first.

Reason:

- it is the clearest user-facing feature boundary
- it minimizes the chance that docs or tests keep treating `.agent` as supported
- once removed, remaining internal cleanup becomes easier to reason about

Concretely:

1. delete `write-resume-projection` command wiring
2. remove its tests
3. then remove projection-writer and config surface in the next pass

---

## 12. Summary

The `v0.5.3` work should be treated as a product-surface cleanup, not merely a file path rename.

The central decision is:

- local repository `.agent/` resume projections are no longer a supported user feature

That implies coordinated change across:

- CLI
- config
- implementation
- tests
- docs
- Docker examples

The safest release shape is:

- remove the user-facing local projection writer
- keep canonical workflow and projection-history APIs
- document the canonical interfaces as the supported path forward