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
- the CLI supports:
  - text output
  - `--format json`
- canonical aggregation support was added across the workflow service and PostgreSQL repositories
- focused CLI validation passed:
  - `python -m pytest tests/test_cli.py -q`
  - `31 passed`
- live manual verification against the running Docker PostgreSQL also succeeded using:
  - `CTXLEDGER_DATABASE_URL=postgresql://ctxledger:ctxledger@localhost:5432/ctxledger ctxledger stats`

Recommended next sequence:
1. implement:
   - `ctxledger workflows`
   - `ctxledger memory-stats`
   - `ctxledger failures`
2. continue expanding shared DB-backed summary/query helpers as needed
3. add/extend CLI tests for the new observability commands
4. add Grafana compose overlay
5. define initial dashboard provisioning/query set
6. write Grafana operator runbook