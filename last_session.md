# ctxledger last session

## Summary
`0.3.0` is now effectively closed out.

The repository was revalidated after stale test expectations were corrected, the docs were aligned with the actual implemented scope, and the release tag was created.

The next planned work is `0.4.0`, which is now defined as the **observability milestone**:
- operator-facing CLI inspection/reporting
- optional deployable **Grafana-based** dashboard support

Hierarchical memory retrieval is no longer the `0.4.0` focus.
That work has been shifted to `0.5.0`.

## Final 0.3.0 status
### Validation
- focused duplicate-closeout rerun passed:
  - `python -m pytest tests/test_coverage_targets.py -q -k old_episode_and_non_auto_memory_paths`
  - `1 passed`
- full suite rerun passed:
  - `python -m pytest -q`
  - `780 passed, 1 skipped`

### Skipped test
The single skipped test is expected:
- real OpenAI integration requires `OPENAI_API_KEY`

### Release judgment
- internal `0.3.0` release judgment: **GO**
- provider wording should remain honest:
  - strongest validated paths:
    - `openai`
    - `local_stub`
    - `custom_http`
  - `voyageai` and `cohere` config surfaces exist, but full provider-specific runtime support remains incomplete
- `memory_get_context` should still be described as:
  - episode-oriented
  - not yet a finished hierarchical retrieval surface

## Important implementation/result notes
### Duplicate closeout behavior
A stale expectation in `tests/test_coverage_targets.py` was corrected.

Current behavior:
- exact-summary duplicate suppression still applies to prior auto-memory episodes even when the prior episode is old
- `_recent_workflow_completion_memory()` filters to:
  - `memory_origin == "workflow_complete_auto"`
- exact normalized-summary equality is checked before the near-duplicate time-window gate
- non-auto episodes are ignored for that duplicate path

Correct expected result:
- `AutoMemoryDuplicateCheckResult(should_record=False, skipped_reason="duplicate_closeout_auto_memory")`

### Runtime auto-memory + embeddings
The runtime `workflow_complete` auto-memory path was debugged end-to-end.

Confirmed:
- `OPENAI_API_KEY` forwarding was working
- direct `memory_remember_episode` with OpenAI embeddings was healthy
- the runtime blocker was a stale live PostgreSQL constraint:
  - `memory_items_provenance_valid`
- after updating the live constraint to allow:
  - `workflow_complete_auto`
- MCP/runtime closeout auto-memory stored:
  - the episode
  - the memory item
  - the OpenAI embedding

### Deployment / schema drift note
A durable deployment note was added for the live-schema drift failure mode:
- stale `memory_items_provenance_valid`
- retained PostgreSQL volume means restart/rebuild alone may not fix it

## Live PostgreSQL observability insight
A live inspection of the running PostgreSQL container showed that canonical state has already accumulated enough meaningful activity that direct observability now feels more valuable than repository projection files.

Representative observed counts:
- `40` workspaces
- `58` workflow instances
- `58` workflow attempts
- `369` workflow checkpoints
- `369` verify reports
- `34` episodes
- `24` memory items
- `3` memory embeddings

Takeaway:
- projection still exists as implemented derived behavior
- but product direction now feels better served by:
  - canonical workflow observability
  - canonical memory observability
  - operator-facing inspection surfaces

## Roadmap shift now in effect
### 0.4.0
`0.4.0` is now the observability milestone.

Focus:
- workflow and memory observability
- operator-facing CLI inspection tools
- optional deployable **Grafana** dashboard support
- better visibility into canonical runtime state

### 0.5.0
Hierarchical retrieval work moved here.

Focus:
- hierarchical memory retrieval
- summary layers
- relation-aware context assembly
- more multi-layer `memory_get_context` behavior

## Docs updated
The roadmap/scope shift was aligned across:
- `README.md`
- `docs/roadmap.md`
- `docs/mcp-api.md`
- `docs/deployment.md`
- `docs/CHANGELOG.md`

A dedicated implementation plan was also added:
- `docs/plans/observability_0_4_0_plan.md`

## Git state recorded
Relevant recent commit/tag state:
- `92035f5`
  - `Align coverage tests and document schema drift recovery`
- `8e4f3fb`
  - `Finalize 0.3.0 docs and observability roadmap`
- `d627f25`
  - `Add 0.4.0 observability implementation plan`
- git tag:
  - `v0.3.0`

## Important files for next session
- `docs/plans/observability_0_4_0_plan.md`
- `docs/roadmap.md`
- `README.md`
- `docs/deployment.md`
- `docs/mcp-api.md`
- `docs/CHANGELOG.md`
- `src/ctxledger/__init__.py`
- `src/ctxledger/db/postgres.py`
- `src/ctxledger/workflow/service.py`
- `src/ctxledger/workflow/memory_bridge.py`
- `src/ctxledger/memory/service.py`
- `tests/test_cli.py`
- `tests/test_coverage_targets.py`

## Next recommended action
Continue concrete `0.4.0` implementation work from the observability plan.

Current progress:
- `ctxledger stats` has now been implemented as the first observability CLI surface
- `ctxledger workflows` is now implemented as the second observability CLI surface
- `ctxledger memory-stats` is now implemented as the third observability CLI surface
- `ctxledger failures` is now implemented as the fourth observability CLI surface
- the CLI supports:
  - text output
  - `--format json`
- `ctxledger workflows` currently supports:
  - `--limit`
  - `--status`
  - `--workspace-id`
  - `--ticket-id`
  - `--format json`
- `ctxledger memory-stats` currently reports:
  - episode count
  - memory item count
  - memory embedding count
  - memory relation count
  - memory item provenance breakdown
  - latest memory activity timestamps
- `ctxledger failures` currently supports:
  - `--limit`
  - `--status`
  - `--open-only`
  - `--format json`
- `ctxledger failures` currently reports:
  - failure scope/type
  - lifecycle state (`open`, `resolved`, `ignored`)
  - target path
  - error code
  - error message
  - occurred/resolved timestamps
  - retry count
  - open failure count
  - attempt id when present
- canonical aggregation/query support was added across the workflow service and both PostgreSQL and in-memory repositories
- focused CLI validation passed:
  - `python -m pytest tests/test_cli.py -q`
  - `46 passed`
- manual operator verification confirmed the CLI observability commands work:
  - `ctxledger workflows`
  - `ctxledger memory-stats`
  - `ctxledger failures`
- Grafana groundwork has now been validated live:
  - observability SQL bootstrap file added and applied:
    - `docs/sql/observability_views.sql`
  - Grafana compose overlay added and verified with the current local stack shape:
    - `docker/docker-compose.observability.yml`
    - startup used together with:
      - `docker/docker-compose.yml`
      - `docker/docker-compose.small-auth.yml`
  - datasource provisioning added and confirmed working:
    - `docker/grafana/provisioning/datasources/postgres.yml`
  - dashboard provider provisioning added and confirmed working:
    - `docker/grafana/provisioning/dashboards/dashboards.yml`
  - initial dashboards added and confirmed rendering real data:
    - `docker/grafana/dashboards/runtime_overview.json`
    - `docker/grafana/dashboards/memory_overview.json`
    - `docker/grafana/dashboards/failure_overview.json`
  - operator runbook added:
    - `docs/grafana_operator_runbook.md`
- important live Grafana bring-up note:
  - dashboard datasource UID references originally needed correction
  - dashboards should use the provisioned fixed UID:
    - `ctxledger-postgres`
  - this was necessary for live dashboard data rendering
- deployment guidance was expanded to describe:
  - read-only Grafana PostgreSQL access
  - `observability` schema / view approach
  - SQL-injection risk posture and mitigations
- `ctxledger workflows` text output includes:
  - workflow instance id
  - workspace path fallbacking to workspace id when needed
  - ticket id
  - latest checkpoint step
  - latest verify status
  - updated timestamp
- `ctxledger memory-stats` text output includes:
  - counts section
  - provenance breakdown section
  - latest activity section
- `ctxledger failures` text output includes:
  - lifecycle-first summary line
  - scope
  - path
  - error code
  - error message
  - occurred/resolved timestamps
  - retry count
  - open failure count
- current dashboard/operator UX gaps:
  - stat panels still show series label `value` in places
  - pie chart/table presentation can be made more operator-friendly with better aliases and panel options
  - README does not yet document the Grafana compose overlay flow

Recommended next sequence:
1. check that all live Grafana bring-up fixes are reflected in the repository
   - especially datasource UID usage in dashboard JSON
   - and any other changes required for the current local stack shape
2. add README guidance for bringing up Grafana with Docker Compose
   - including the current auth-overlay-compatible startup shape
   - and the required PostgreSQL observability/bootstrap steps
3. make Grafana dashboards more operator-friendly
   - improve panel aliases/labels
   - remove generic `value` presentation where possible
   - improve pie/table readability
   - consider a workflow-activity dashboard if still useful